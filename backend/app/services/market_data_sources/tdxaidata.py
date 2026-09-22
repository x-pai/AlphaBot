"""通达信官方 TdxAiData 数据源适配。"""

from __future__ import annotations

import asyncio
import math
import re
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Any

from app.core.config import settings
from app.services.market_data_sources.base import MarketDataSourceBase
from app.services.market_data_sources.tdxaidata_client import TdxAiDataClient, TdxAiDataUnavailable


_CODE = re.compile(r"^\d{1,6}$")
_SUFFIXES = {"SH": "SH", "SS": "SH", "SZ": "SZ", "BJ": "BJ"}


def _tdx_symbol(raw: str) -> tuple[str, str] | None:
    """规范化 A 股代码及交易所；不把港股/美股代码猜成 A 股。"""
    value = (raw or "").strip().upper()
    suffix = None
    if "." in value:
        value, suffix = value.rsplit(".", 1)
        suffix = _SUFFIXES.get(suffix)
        if suffix is None:
            return None
    elif value.startswith(("SH", "SZ", "BJ")) and len(value) > 2:
        suffix, value = value[:2], value[2:]

    if not _CODE.fullmatch(value):
        return None
    code = value.zfill(6)
    if code == "000000":
        return None
    if code.startswith("920"):
        inferred = "BJ"
    elif code.startswith(("4", "8")):
        inferred = "BJ"
    elif code.startswith(("5", "6", "9")):
        inferred = "SH"
    else:
        inferred = "SZ"
    if suffix and suffix != inferred:
        return None
    return code, suffix or inferred


def _finite_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _as_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        converted = to_dict()
        if isinstance(converted, dict):
            return converted
    return {}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    to_list = getattr(value, "tolist", None)
    if callable(to_list):
        converted = to_list()
        if isinstance(converted, list):
            return converted
    return []


def _code_key(raw: Any) -> str | None:
    value = str(raw or "").upper().strip()
    if re.fullmatch(r"\d{6}\.(SH|SZ|BJ)", value):
        return value[:6]
    normalized = _tdx_symbol(value)
    return normalized[0] if normalized else None


def _field_rows(data: Any, code: str, field: str) -> list[dict[str, Any]]:
    """取 get_gpjy_value 返回的指定证券/字段历史行。"""
    mapping = _as_mapping(data)
    security = next((_as_mapping(mapping[key]) for key in (code, f'{code}.SH', f'{code}.SZ', f'{code}.BJ') if key in mapping), None)
    if security is None:
        return []

    raw_rows = None
    for key, value in security.items():
        if str(key).upper() == field.upper():
            raw_rows = value
            break
    rows = _as_list(raw_rows)
    if rows and isinstance(rows[0], dict):
        return [row for row in rows if isinstance(row, dict)]
    # Some SDK builds flatten a single professional field as Date/Value arrays.
    if isinstance(raw_rows, dict):
        dates = _as_list(raw_rows.get("Date"))
        values = _as_list(raw_rows.get("Value"))
        return [{"Date": date, "Value": value} for date, value in zip(dates, values)]
    return []


def _row_for_date(rows: list[dict[str, Any]], day: str | None) -> dict[str, Any] | None:
    matches = [row for row in rows if _date_key(row.get("Date"))]
    if day:
        return next((row for row in matches if _date_key(row.get("Date")) == day), None)
    return max(matches, key=lambda row: _date_key(row.get("Date")) or "", default=None)


def _date_key(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y%m%d")
    text = str(value).strip()
    digits = re.sub(r"\D", "", text.split(".")[0])
    return digits[:8] if len(digits) >= 8 else None


def _values(row: dict[str, Any] | None) -> list[Any]:
    if not row:
        return []
    raw = row.get("Value", row.get("value"))
    if isinstance(raw, (list, tuple)):
        return list(raw)
    return [raw] if raw is not None else []


def _status(row: dict[str, Any] | None) -> int | None:
    values = _values(row)
    number = _finite_number(values[0]) if values else None
    return int(number) if number is not None else None


def _minute_of_day(value: Any) -> int | None:
    text = str(value or "").strip().split(".")[0].replace(":", "")
    if not text.isdigit() or len(text) not in (5, 6):
        return None
    text = text.zfill(6)
    hour, minute, second = int(text[:2]), int(text[2:4]), int(text[4:])
    return hour * 60 + minute if 9 <= hour <= 15 and minute < 60 and second < 60 else None


def _market_series(data: Any, field: str, code: str) -> list[tuple[str, Any]]:
    """解析 pandas DataFrame 或 SDK 不带 pandas 时的 field -> code -> list 结构。"""
    fields = _as_mapping(data)
    frame = next((value for key, value in fields.items() if str(key).lower() == field.lower()), None)
    if frame is None:
        return []

    # pandas DataFrame: rows are dates and columns are security codes.
    columns = [str(item) for item in _as_list(getattr(frame, "columns", None))]
    index = _as_list(getattr(frame, "index", None))
    values = _as_list(getattr(frame, "values", None))
    if columns and values:
        code_column = next((i for i, item in enumerate(columns) if _code_key(item) == code), None)
        if code_column is not None:
            return [(str(date), row[code_column]) for date, row in zip(index, values) if code_column < len(row)]
        code_row = next((i for i, item in enumerate(index) if _code_key(item) == code), None)
        if code_row is not None and code_row < len(values):
            return [(str(date), value) for date, value in zip(columns, values[code_row])]

    mapping = _as_mapping(frame)
    nested = next((value for key, value in mapping.items() if _code_key(key) == code), None)
    if isinstance(nested, dict):
        return [(str(date), value) for date, value in nested.items()]
    values_list = _as_list(nested)
    if values_list:
        date_list: list[Any] = []
        date_frame = next((value for key, value in fields.items() if str(key).lower() == "date"), None)
        date_mapping = _as_mapping(date_frame)
        dates = next((value for key, value in date_mapping.items() if _code_key(key) == code), None)
        date_list = _as_list(dates)
        if not date_list:
            return [(str(index), value) for index, value in enumerate(values_list)]
        return [(str(date), value) for date, value in zip(date_list, values_list)]
    return []


def _market_value(data: Any, field: str, code: str) -> float | None:
    series = _market_series(data, field, code)
    if not series:
        return None
    return _finite_number(series[-1][1])


def _number(row, field, scale=1.0):
    value = _finite_number(row.get(field))
    return value / scale if value is not None else None


def _change(row):
    price, previous = _number(row, 'Now'), _number(row, 'LastClose')
    return (price / previous - 1) * 100 if price is not None and price > 0 and previous and previous > 0 else None


def _records(raw):
    if isinstance(raw, dict):
        return {str(k): v for k, v in raw.items() if isinstance(v, dict)}
    return {str(row['Code']): row for row in _as_list(raw) if isinstance(row, dict) and row.get('Code')}


class TdxAiDataMarketDataSource(MarketDataSourceBase):
    SUPPORTED_DATASETS = frozenset({
        'quotes', 'pools', 'universe', 'members', 'plate_index', 'fundflow',
        'turnover', 'payoff_strong', 'payoff_hot', 'payoff_drawdown', 'surge', 'trending',
    })
    BATCH_SIZE = 100

    def __init__(self):
        self._client = TdxAiDataClient()
        self._cache = {}
        self._locks = {}

    async def _remember(self, key, ttl, loader):
        async with self._locks.setdefault(key, asyncio.Lock()):
            cached = self._cache.get(key)
            if cached and cached[0] > time.monotonic():
                return cached[1]
            value = await loader()
            # cache only successful calls; exceptions propagate to the API.
            if len(self._cache) > 2048:
                self._cache = {k: v for k, v in self._cache.items() if v[0] > time.monotonic()}
            self._cache[key] = (time.monotonic() + ttl, value)
            return value

    async def _catalog(self, market='5'):
        async def load():
            raw = await self._client.call('get_stock_list', market, 1)
            rows = {str(row['Code']): str(row['Name']) for row in _as_list(raw)
                    if isinstance(row, dict) and row.get('Code') and row.get('Name')}
            if not rows:
                raise TdxAiDataUnavailable(f'empty security catalog: {market}')
            return rows
        return await self._remember(('catalog', market), 21600, load)

    async def _listed_catalog(self, day):
        async def load():
            names = await self._catalog()
            info = await self._batch('get_stock_info_batch', names, ['J_start'])
            if any('J_start' not in row for row in info.values()):
                raise TdxAiDataUnavailable('listing dates unavailable')
            # SDK 列表含待上市证券，J_start=0；它们不属于历史/实时可交易截面。
            return {symbol: name for symbol, name in names.items()
                    if (listed := _date_key(info[symbol].get('J_start'))) and listed <= day}
        return await self._remember(('listed', day), 21600, load)

    async def _boards(self):
        return {**await self._catalog('11'), **await self._catalog('12')}

    async def _batch(self, method, symbols, fields=None):
        symbols = list(dict.fromkeys(symbols))
        result = {}
        for offset in range(0, len(symbols), self.BATCH_SIZE):
            part = symbols[offset:offset + self.BATCH_SIZE]
            raw = _records(await self._client.call(method, part, fields or []))
            missing = [s for s in part if not raw.get(s)]
            if missing:
                raise TdxAiDataUnavailable(f'{method}: incomplete response ({len(missing)} securities missing)')
            result.update(raw)
        return result

    async def _snapshots(self, symbols):
        return await self._batch('get_market_snapshot_batch', symbols)

    async def _more(self, symbols):
        return await self._batch('get_more_info_batch', symbols, [
            'HqDate', 'ZAF', 'Zjl_HB', 'fHSL', 'ZTPrice', 'DTPrice', 'FCAmo',
            'ZTGPNum', 'LastStartZT', 'LastZTHzNum', 'CJJEPre1',
        ])

    async def _all_quotes(self):
        async def load():
            names = await self._listed_catalog(await self._day())
            return names, await self._snapshots(names), await self._more(names)
        return await self._remember('all-quotes', 30, load)

    async def fetch_trading_dates(self, start='19900101', end=None):
        end = end or datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d')
        async def load():
            raw = await self._client.call('get_trading_dates', 'SH', start, end)
            days = sorted({d for v in _as_list(raw) if (d := _date_key(v)) and start <= d <= end})
            if not days:
                raise TdxAiDataUnavailable('empty trading calendar')
            return days
        return await self._remember(('calendar', start, end), 21600, load)

    async def _day(self, value=None):
        if value:
            return datetime.strptime(value.replace('-', ''), '%Y%m%d').strftime('%Y%m%d')
        return (await self.fetch_trading_dates())[-1]

    async def fetch_quotes(self, codes):
        symbols = list(dict.fromkeys(f'{v[0]}.{v[1]}' for code in codes if (v := _tdx_symbol(code))))
        if len(symbols) > max(1, settings.TDXAIDATA_MAX_SYMBOLS):
            raise ValueError(f'TDXAIDATA_MAX_SYMBOLS={settings.TDXAIDATA_MAX_SYMBOLS} exceeded')
        if not symbols:
            return {}
        names, snapshots = await self._catalog(), await self._snapshots(symbols)
        return {s[:6]: {'name': names.get(s, s[:6]), 'price': _number(row, 'Now'), 'change': _change(row)}
                for s, row in snapshots.items()}

    async def _relations(self, symbol):
        async def load():
            rows = await self._client.call('get_relation', symbol)
            return list(dict.fromkeys(str(r['BlockName']) for r in _as_list(rows)
                        if isinstance(r, dict) and r.get('BlockName') and r.get('BlockType') in ('概念','行业','研究行业')))
        return await self._remember(('relations', symbol), 21600, load)

    async def _board_symbol(self, plate_id):
        boards = await self._boards()
        symbol = plate_id if plate_id in boards else f'{plate_id}.SH'
        if symbol not in boards:
            raise ValueError('unknown tdxaidata plate ID')
        return symbol

    async def _member_names(self, symbol):
        async def load():
            raw = await self._client.call('get_stock_list_in_sector', symbol, 0, 1)
            return {r['Code']: r['Name'] for r in _as_list(raw) if isinstance(r, dict) and r.get('Code') and r.get('Name')}
        return await self._remember(('members', symbol), 21600, load)

    async def fetch_universe(self):
        async def load():
            boards = await self._boards()
            quotes, more = await self._snapshots(boards), await self._more(boards)
            result = []
            for symbol, name in boards.items():
                q, m = quotes[symbol], more[symbol]
                members = await self._member_names(symbol)
                up, down = _number(q, 'UpHome'), _number(q, 'DownHome')
                flat = len(members)-up-down if members and up is not None and down is not None else None
                result.append({'code': symbol, 'name': name, 'change': _change(q),
                    'netFlow': _number(m, 'Zjl_HB', 10000), 'ztCount': _number(q, 'Outside'),
                    'upCount': _number(q, 'UpHome'), 'downCount': _number(q, 'DownHome'),
                    'flatCount': flat if flat is not None and flat >= 0 else None})
            return sorted(result, key=lambda x: x['change'] if x['change'] is not None else -math.inf, reverse=True)
        return await self._remember('universe', 60, load)

    async def fetch_members(self, plate_id):
        symbol = await self._board_symbol(plate_id)
        names = await self._member_names(symbol)
        quotes, more = await self._snapshots(names), await self._more(names)
        return [{'code': s[:6], 'name': name, 'price': _number(quotes[s], 'Now'),
                 'change': _change(quotes[s]), 'amount': _number(quotes[s], 'Amount', 10000),
                 'netFlow': _number(more[s], 'Zjl_HB', 10000), 'turnoverRate': _number(more[s], 'fHSL')}
                for s, name in names.items()]

    async def _bars(self, symbols, fields, count=60, day=None, period='1d'):
        # SDK count 模式忽略 start；end 使用收盘时间，防止只截取到当天 00:00。
        return await self._client.call('get_market_data', fields, list(symbols), period, '',
            (day + '150000') if day else '', count, 'none', False)

    async def fetch_plate_index(self, plate_id, count):
        symbol = await self._board_symbol(plate_id)
        data = await self._bars([symbol], ['Open','High','Low','Close'], max(1, min(count, 60)))
        return self._ohlc(data, symbol)

    @staticmethod
    def _ohlc(data, symbol):
        series = {f.lower(): {_date_key(d): _finite_number(v) for d, v in _market_series(data, f, symbol[:6])}
                  for f in ('Open','High','Low','Close')}
        result = []
        for day in sorted(d for d in series['close'] if d):
            row = {field: values.get(day) for field, values in series.items()}
            if all(v is not None and v > 0 for v in row.values()):
                result.append({'date': day, **row})
        if not result:
            raise TdxAiDataUnavailable(f'empty OHLC: {symbol}')
        return result

    async def fetch_fundflow(self, codes, days):
        result = {}
        for code in dict.fromkeys(codes):
            normalized = _tdx_symbol(code)
            if not normalized:
                continue
            symbol = '.'.join(normalized)
            async def load():
                raw = await self._client.call('get_exday_data', symbol, max(1, min(days, 10)))
                rows = []
                for record in _as_list(raw):
                    day, amo = _date_key(record.get('Date')), record.get('Amo')
                    if not day or not isinstance(amo, list) or len(amo) != 4:
                        raise TdxAiDataUnavailable('incomplete L2 amount matrix; verify professional permissions')
                    item = {'prodCode': symbol, 'date': day}
                    for label, values in zip(('super','big','medium','small'), amo):
                        pair = [_finite_number(v) for v in values[:2]]
                        if len(pair) != 2 or any(v is None or v < 0 for v in pair):
                            raise TdxAiDataUnavailable('invalid L2 amount matrix')
                        buy, sell = [v / 10000 for v in pair]  # 实测 Amo 为元，领域为万元。
                        item.update({label+'In': buy, label+'Out': sell, 'net'+label.title(): buy-sell})
                    item['mainIn'] = item['superIn'] + item['bigIn']
                    item['mainOut'] = item['superOut'] + item['bigOut']
                    item['netInflow'] = item['mainIn'] - item['mainOut']
                    rows.append(item)
                if not rows:
                    raise TdxAiDataUnavailable(f'no L2 history: {symbol}')
                return sorted(rows, key=lambda r:r['date'])
            result[normalized[0]] = await self._remember(('fundflow', symbol, days), 120, load)
        return result

    async def _professional(self, symbols, fields, start, end):
        symbols = list(dict.fromkeys(symbols))
        self._check_detail_budget(symbols)
        result = {}
        # 专业数据接口在 SDK 内部逐股请求；每组 20 只限制单次阻塞。
        for i in range(0, len(symbols), 20):
            part = list(symbols)[i:i+20]
            # 1.1.1 仅查询无事件的 GP 字段会打印 Invalid server response；
            # 同查有每日记录的 GP27 可得到合法的 GP15=null，区分空事件与失败。
            query_fields = list(dict.fromkeys([*fields, 'GP27']))
            raw = await self._client.call('get_gpjy_value', part, query_fields, start, end)
            for symbol, record in _as_mapping(raw).items():
                if isinstance(record, dict):
                    result[symbol] = {field: record.get(field) for field in fields}
            if any(symbol not in result for symbol in part):
                raise TdxAiDataUnavailable('incomplete professional response')
        return result

    async def _history(self, day):
        raise TdxAiDataUnavailable('历史股票池自动回补已暂停：尚未确认低成本名单接口，不执行全市场逐股扫描。')

    @staticmethod
    def _check_detail_budget(symbols):
        # A hard per-operation ceiling, not a truncation: never present partial pools as complete.
        if len(set(symbols)) > 100:
            raise TdxAiDataUnavailable('候选股详情超过单次 100 只成本上限，已停止查询；未返回截断名单。')

    async def _streak(self, rows, day):
        days = await self.fetch_trading_dates((datetime.strptime(day, '%Y%m%d')-timedelta(days=60)).strftime('%Y%m%d'), day)
        statuses = {_date_key(r.get('Date')): _status(r) for r in rows}
        count = 0
        for d in reversed(days):
            if statuses.get(d) != 2:
                break
            count += 1
        return count

    async def fetch_pool(self, kind, date=None):
        if kind not in {'zt','zb','dt'}:
            raise ValueError(f'unknown pool kind: {kind}')
        day = await self._day(date)
        if day != await self._day():
            return await self._history(day)
        pools = await self._remember(('pools', day), 30 if day == await self._day() else 21600,
                                     lambda: self._build_pools(day))
        return pools[kind]

    async def _build_pools(self, day):
        if day != await self._day():
            return await self._history(day)
        names = await self._catalog()
        current = day == await self._day()
        history = {} if current else await self._history(day)
        quotes, more = ({}, {})
        if current:
            _, quotes, more = await self._all_quotes()
        selected = []
        for symbol, name in names.items():
            row = _row_for_date(_field_rows(history, symbol[:6], 'GP15'), day)
            state = _status(row)
            q, m = quotes.get(symbol, {}), more.get(symbol, {})
            if current and _date_key(m.get('HqDate')) == day:
                now, high, low = _number(q,'Now'), _number(q,'Max'), _number(q,'Min')
                up, down, previous = _number(m,'ZTPrice'), _number(m,'DTPrice'), _number(q,'LastClose')
                if now and previous and up and down and up > previous > down > 0:
                    state = 2 if abs(now-up) < 0.005 else -2 if abs(now-down) < 0.005 else 1 if high and high >= up-0.005 else -1 if low and 0 < low <= down+0.005 else 0
            if state not in {2,1,-2}:
                continue
            kind = {2:'zt',1:'zb',-2:'dt'}[state]
            selected.append((symbol, name, kind, row, q, m))
        pools = {'zt':[], 'zb':[], 'dt':[]}
        symbols = [r[0] for r in selected]
        if current and symbols:
            start = (datetime.strptime(day, '%Y%m%d')-timedelta(days=60)).strftime('%Y%m%d')
            history = await self._professional(symbols, ['GP15'], start, day)
            for symbol, _name, kind, *_ in selected:
                rows = _as_mapping(history.setdefault(symbol, {})).get('GP15') or []
                rows = [r for r in rows if _date_key(r.get('Date')) != day]
                rows.append({'Date':day, 'Value':[{'zt':2,'zb':1,'dt':-2}[kind]]})
                history[symbol]['GP15'] = rows
        details = await self._professional(symbols, ['GP14','GP24','GP33','GP34','GP40'], day, day) if symbols else {}
        bars = await self._bars(symbols, ['Close'], 1, day) if symbols and not current else {}
        for symbol, name, kind, row, q, m in selected:
            up = kind != 'dt'
            values = _values(_row_for_date(_field_rows(details, symbol[:6], 'GP24' if up else 'GP34'), day))
            opened = _values(_row_for_date(_field_rows(details, symbol[:6], 'GP14' if up else 'GP33'), day))
            status_values = _values(row)
            fund = _number(m,'FCAmo') if current else _finite_number(status_values[1]) if len(status_values)>1 else None
            if kind == 'zb':
                fund = 0.0  # 当前处于炸板，封单为零。
            tags = await self._relations(symbol)
            item = {'code':symbol[:6], 'name':name, 'type':kind, 'reason':tags[0] if tags else '未分类', 'concepts':tags,
                    'lbc': await self._streak(_field_rows(history,symbol[:6],'GP15'),day) if kind=='zt' else 0,
                    'time':_minute_of_day(values[0]) if values else None,
                    'fund':round(abs(fund)*10000) if fund is not None else None,
                    'price':_number(q,'Now') if current else _market_value(bars,'Close',symbol[:6]),
                    'turnoverRate':_number(m,'fHSL') if current else None,
                    'zbc': int(v) if len(opened)>1 and (v:=_finite_number(opened[1])) is not None else None,
                    'firstBreak':None, 'lastSealTs':None}
            if current:
                # SDK 1.1.1 多代码拼接返回错误 Code，逐只请求并验证代码。
                raw = _records(await self._client.call('get_zdt_data', [symbol]))
                detail = raw.get(symbol, {})
                if detail.get('Code') == symbol and _number(detail,'ZDTStatusNow') in {1,2,3,4,5,6}:
                    suffix = 'ZT' if up else 'DT'
                    item['time'] = _minute_of_day(detail.get('FirstTime'+suffix)) or item['time']
                    item['zbc'] = _number(detail,'OpenTimes'+suffix)
                    minute = _minute_of_day(detail.get('LastTime'+suffix))
                    if minute is not None:
                        instant = datetime.strptime(day,'%Y%m%d').replace(hour=minute//60, minute=minute%60,tzinfo=ZoneInfo('Asia/Shanghai'))
                        item['lastSealTs'] = int(instant.timestamp())
            pools[kind].append(item)
        return pools

    async def fetch_payoff(self, kind, date=None):
        if kind == 'hot':
            raise TdxAiDataUnavailable('人气榜已暂停：尚未确认直接排名接口，不执行全市场 GP27 逐股扫描。')
        if kind not in {'strong', 'drawdown'}:
            raise ValueError(f'unknown payoff kind: {kind}')
        day = await self._day(date)
        if day != await self._day():
            return await self._history(day)
        names = await self._listed_catalog(day)
        if kind == 'strong':
            if day == await self._day():
                _, _, more = await self._all_quotes()
                symbols = [s for s,m in more.items() if s in names and (_number(m,'LastZTHzNum') or 0) >= 2]
                start = (datetime.strptime(day,'%Y%m%d')-timedelta(days=40)).strftime('%Y%m%d')
                history = await self._professional(symbols,['GP15'],start,day)
            else:
                history = await self._history(day)
            calendar = (await self.fetch_trading_dates(end=day))[-20:]
            candidates = []
            for symbol in names:
                hits = [d for d in calendar if _status(_row_for_date(_field_rows(history,symbol[:6],'GP15'),d))==2]
                if len(hits)>=2 and 'ST' not in names[symbol].upper():
                    candidates.append((len(hits),len(calendar)-calendar.index(hits[0]),symbol))
            candidates.sort(reverse=True)
            top = candidates[:50]
            current_quotes = await self._snapshots([s for _,_,s in top]) if top and day == await self._day() else {}
            bars = await self._bars([s for _,_,s in top],['Close'],2,day) if top and not current_quotes else {}
            result=[]
            for boards,days,s in top:
                prices=[_finite_number(v) for _,v in _market_series(bars,'Close',s[:6])]
                tags=await self._relations(s)
                result.append({'name':names[s], 'change':_change(current_quotes[s]) if s in current_quotes else (prices[-1]/prices[-2]-1)*100 if len(prices)>=2 and prices[-2] and prices[-1] else None,
                               'plate':tags[0] if tags else '', 'days':days,'boards':boards,'method':'近20交易日涨停统计'})
            return result
        if kind == 'drawdown':
            pools = await self.fetch_pool('zb',day)
            result=[]
            for item in pools:
                if 'ST' in item['name'].upper():
                    continue
                s='.'.join(_tdx_symbol(item['code']))
                data=await self._bars([s],['High','Low','Close'],240,day,'1m')
                highs=dict(_market_series(data,'High',s[:6]))
                closes=dict(_market_series(data,'Close',s[:6]))
                peak=0.0; drawdown=0.0; valid=False
                for stamp in sorted(highs):
                    if _date_key(stamp)!=day:
                        continue
                    high,close=_finite_number(highs[stamp]),_finite_number(closes.get(stamp))
                    if not high or not close:
                        continue
                    peak=max(peak,high); drawdown=min(drawdown,(close/peak-1)*100); valid=True
                if valid:
                    bars=self._ohlc(await self._bars([s],['Open','High','Low','Close'],2,day),s)
                    change=_change((await self._snapshots([s]))[s]) if day == await self._day() else (bars[-1]['close']/bars[-2]['close']-1)*100 if len(bars)>1 else None
                    result.append({'name':item['name'],'change':change,'maxDrawdown':drawdown,
                                   'industryBlock':item['reason'],'method':'分钟收盘价相对此前最高价的最大回撤'})
            return sorted(result,key=lambda r:r['maxDrawdown'])[:50]
        raise ValueError(f'unknown payoff kind: {kind}')

    async def fetch_surge(self):
        names, quotes, _ = await self._all_quotes()
        candidates=sorted(((v,s) for s,q in quotes.items() if (v:=_number(q,'Zangsu')) is not None and v>=3),reverse=True)[:50]
        return [{'code':s[:6],'name':names[s],'plates':await self._relations(s),
                 'analysis':f'通达信行情筛选：涨速 {speed:.2f}%（规则计算）'} for speed,s in candidates]

    async def fetch_trending(self):
        universe=await self.fetch_universe()
        candidates=sorted((r for r in universe if r['change'] is not None and r['change']>0),
                          key=lambda r:(r['ztCount'] or 0,r['change']),reverse=True)[:10]
        return [{'plateId':r['code'],'name':r['name'],
                 'description':f"按涨停家数、涨幅排序的通达信板块（规则计算），涨幅 {r['change']:.2f}%", 'stocks':[]}
                for r in candidates]

    async def fetch_turnover(self):
        days=(await self.fetch_trading_dates())[-2:]
        if len(days)<2:
            raise TdxAiDataUnavailable('two trading days required')
        # 沪深市场成交额；不叠加重叠的成分指数或北交所。
        symbols=['000001.SH','399001.SZ']
        data=await self._bars(symbols,['Amount'],500,days[-1],'1m')
        series={s:dict(_market_series(data,'Amount',s[:6])) for s in symbols}
        curves={day:{} for day in days}
        for day in days:
            totals={s:0.0 for s in symbols}
            stamps=sorted(set.intersection(*(set(v) for v in series.values())))
            for stamp in stamps:
                if _date_key(stamp)!=day:
                    continue
                values={s:_finite_number(series[s][stamp]) for s in symbols}
                if any(v is None or v<0 for v in values.values()):
                    continue
                for s,v in values.items(): totals[s]+=v*10000
                curves[day][str(stamp)[11:16]]=sum(totals.values())
        today,yesterday=curves[days[-1]],curves[days[-2]]
        if not today or not yesterday:
            raise TdxAiDataUnavailable('minute turnover unavailable')
        points=[{'time':t,'today':v,'yesterday':yesterday.get(t)} for t,v in today.items()]
        current,previous=points[-1]['today'],points[-1]['yesterday']
        predict=current*list(yesterday.values())[-1]/previous if previous and previous>0 else None
        return {'current':current,'previous':previous,'change':current-previous if previous is not None else None,
                'predict':predict,'points':points,'method':'沪深成交额；按昨日同分钟累计占比估算全天'}

    async def aclose(self):
        await self._client.aclose()
