import asyncio
import os
from pathlib import Path
import time

import pandas as pd
import pytest

from app.core.config import settings
from app.services.market_cache import source_key
from app.services.market_data_sources.factory import MarketDataSourceFactory, MarketDataSourceConfigurationError
from app.services.market_data_sources.tdxaidata import TdxAiDataMarketDataSource, _tdx_symbol, _minute_of_day
from app.services.market_data_sources.tdxaidata_client import TdxAiDataClient, TdxAiDataUnavailable
from app.services.market_emotion_service import MarketEmotionService
from app.services.trading_calendar_service import TradingCalendarService


@pytest.fixture
def tdx(monkeypatch):
    monkeypatch.setattr(settings, 'DEFAULT_MARKET_DATA_SOURCE', 'tdxaidata')
    monkeypatch.setattr(MarketDataSourceFactory, '_explicit_bindings', {})


def test_full_switch_and_no_mixed_bindings(tdx):
    assert set(MarketDataSourceFactory.current_bindings().values()) == {'tdxaidata'}
    assert len(MarketDataSourceFactory.current_bindings()) == 12
    with pytest.raises(MarketDataSourceConfigurationError, match='mixed'):
        MarketDataSourceFactory.reconfigure({'quotes':'xgb'})
    assert MarketDataSourceFactory._explicit_bindings == {}


def test_unknown_source_and_cache_isolation(monkeypatch):
    monkeypatch.setattr(settings,'DEFAULT_MARKET_DATA_SOURCE','missing')
    with pytest.raises(MarketDataSourceConfigurationError):
        MarketDataSourceFactory.resolve('quotes')
    assert source_key('quotes','tdxaidata','market:quotes') != source_key('quotes','xgb','market:quotes')


def test_symbol_and_times_do_not_guess_unknown_values():
    assert _tdx_symbol('920001') == ('920001','BJ')
    assert _tdx_symbol('000001.SH') is None
    assert _tdx_symbol('00700.HK') is None
    assert _minute_of_day('093201') == 572
    assert _minute_of_day(0.4) is None
    assert _minute_of_day('0') is None


@pytest.mark.asyncio
async def test_fundflow_units_and_incomplete_permissions():
    source=TdxAiDataMarketDataSource()
    async def call(method,*args,**kwargs):
        return [{'Date':'20260922','Amo':[['20000','10000','3','4'],['30000','10000','3','4'],['50000','70000'],['0','10000']]}]
    source._client.call=call
    rows=await source.fetch_fundflow(['600000'],1)
    row=rows['600000'][0]
    assert row['superIn']==2
    assert row['mainIn']==5 and row['mainOut']==2 and row['netInflow']==3
    assert row['netMedium']==-2
    async def incomplete(*args,**kwargs):
        return [{'Date':'20260922','Amo':[['20000','10000']]}]
    source._client.call=incomplete
    with pytest.raises(TdxAiDataUnavailable,match='incomplete L2'):
        await source.fetch_fundflow(['000001'],1)
    await source.aclose()


@pytest.mark.asyncio
async def test_sparse_limit_history_breaks_on_trading_day_gap():
    source=TdxAiDataMarketDataSource()
    async def calendar(*args,**kwargs): return ['20260917','20260918','20260921','20260922']
    source.fetch_trading_dates=calendar
    rows=[{'Date':'20260917','Value':['2']},{'Date':'20260921','Value':['2']},{'Date':'20260922','Value':['2']}]
    assert await source._streak(rows,'20260922')==2
    rows[1]['Value']=['1']
    assert await source._streak(rows,'20260922')==1
    await source.aclose()


@pytest.mark.asyncio
async def test_board_ids_and_batch_quotes():
    source=TdxAiDataMarketDataSource()
    calls=[]
    async def call(method,*args,**kwargs):
        calls.append((method,args))
        if method=='get_stock_list':return [{'Code':'600000.SH','Name':'浦发银行'}]
        if method=='get_market_snapshot_batch':return {'600000.SH':{'Now':'10.5','LastClose':'10'}}
        raise AssertionError(method)
    source._client.call=call
    result=await source.fetch_quotes(['600000','600000.SH','00700.HK'])
    assert result['600000']['change']==pytest.approx(5)
    assert calls[-1][0]=='get_market_snapshot_batch'
    async def boards():return {'881002.SH':'煤炭开采'}
    source._boards=boards
    assert await source._board_symbol('881002')=='881002.SH'
    with pytest.raises(ValueError): await source.fetch_members('xgb-123')
    await source.aclose()


@pytest.mark.asyncio
async def test_turnover_preserves_minutes_units_and_yesterday_alignment():
    source=TdxAiDataMarketDataSource()
    async def calendar(*args,**kwargs):return ['20260921','20260922']
    async def bars(*args,**kwargs):
        return {'Amount':pd.DataFrame({'000001.SH':[1,2,2,4],'399001.SZ':[3,4,6,8]},
              index=pd.to_datetime(['2026-09-21 09:31','2026-09-21 09:32','2026-09-22 09:31','2026-09-22 09:32']))}
    source.fetch_trading_dates=calendar; source._bars=bars
    data=await source.fetch_turnover()
    assert data['points']==[{'time':'09:31','today':80000,'yesterday':40000},{'time':'09:32','today':200000,'yesterday':100000}]
    assert data['change']==100000
    await source.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize('operation', ['hot', 'pool', 'strong', 'drawdown', 'history'])
async def test_expensive_scans_rejected_before_sdk_calls(operation):
    source = TdxAiDataMarketDataSource()
    async def day(value=None): return value or '20260922'
    async def forbidden(*args, **kwargs):
        raise AssertionError('cost guard must run before any SDK query')
    source._day = day
    source._client.call = forbidden
    with pytest.raises(TdxAiDataUnavailable, match='暂停'):
        if operation == 'pool':
            await source.fetch_pool('zt', '20260921')
        elif operation == 'history':
            await source._history('20260921')
        else:
            await source.fetch_payoff(operation, '20260921')
    await source.aclose()


@pytest.mark.asyncio
async def test_calendar_and_emotion_never_use_old_network(tdx,monkeypatch):
    source=TdxAiDataMarketDataSource()
    async def calendar(*args):return ['20260921','20260922']
    source.fetch_trading_dates=calendar
    monkeypatch.setattr(MarketDataSourceFactory,'_instances',{'tdxaidata':source})
    monkeypatch.setattr(TradingCalendarService,'_trade_calendar_source',None)
    async def forbidden(*args,**kwargs):raise AssertionError('old provider called')
    monkeypatch.setattr(TradingCalendarService,'_run_sync',forbidden)
    monkeypatch.setattr(MarketEmotionService,'_call_tqlex',forbidden)
    assert len(await TradingCalendarService.get_trade_calendar())==2
    assert (await MarketEmotionService.get_intraday_emotion())['unavailableReason']
    assert (await MarketEmotionService.get_short_emotion())['unavailableReason']
    await source.aclose()


@pytest.mark.asyncio
async def test_failures_are_not_cached_as_empty():
    source=TdxAiDataMarketDataSource(); calls=0
    async def loader():
        nonlocal calls
        calls+=1
        if calls==1:raise TdxAiDataUnavailable('offline')
        return [1]
    with pytest.raises(TdxAiDataUnavailable):await source._remember('test',60,loader)
    assert await source._remember('test',60,loader)==[1]
    assert calls==2
    await source.aclose()


def fake_worker(pipe, _lib, _token, runtime):
    os.chdir(runtime)
    try:
        while True:
            method,args,kwargs=pipe.recv()
            if method=='slow':time.sleep(5)
            pipe.send((True, os.getcwd()))
    except EOFError:pass


@pytest.mark.asyncio
async def test_native_worker_isolates_cwd_and_recovers_from_timeout(monkeypatch):
    monkeypatch.setattr('app.services.market_data_sources.tdxaidata_client._worker',fake_worker)
    client=TdxAiDataClient(); cwd=Path.cwd()
    child_cwd=await client.call('cwd',timeout_seconds=5)
    assert child_cwd!=str(cwd) and Path.cwd()==cwd
    with pytest.raises(TdxAiDataUnavailable,match='timed out'):
        await client.call('slow',timeout_seconds=.1)
    assert client._process is None and not Path(child_cwd).exists()
    assert await client.call('cwd',timeout_seconds=5)!=child_cwd
    await client.aclose()
    assert Path.cwd()==cwd


@pytest.mark.asyncio
async def test_security_universe_excludes_pending_and_future_listings():
    source = TdxAiDataMarketDataSource()
    async def catalog(*args): return {'600000.SH':'A', '001246.SZ':'Pending', '000001.SZ':'Future'}
    async def batch(*args): return {'600000.SH':{'J_start':'19991110'}, '001246.SZ':{'J_start':'0'}, '000001.SZ':{'J_start':'20261001'}}
    source._catalog = catalog
    source._batch = batch
    assert await source._listed_catalog('20260922') == {'600000.SH':'A'}
    await source.aclose()


def test_authentication_error_does_not_retry_and_cools_down(monkeypatch):
    from app.services.market_data_sources.tdxaidata_client import TdxAiDataAuthenticationError
    client=TdxAiDataClient()
    calls=[]
    def fail(*args):
        calls.append(args)
        raise TdxAiDataAuthenticationError('TokenKey Insufficient Or Key Error')
    monkeypatch.setattr(client, '_exchange_once', fail)
    for _ in range(2):
        with pytest.raises(TdxAiDataAuthenticationError):client._exchange(('method',[],{}),30)
    assert len(calls)==1


@pytest.mark.asyncio
async def test_authentication_error_never_expands_professional_queries():
    from app.services.market_data_sources.tdxaidata_client import TdxAiDataAuthenticationError
    source=TdxAiDataMarketDataSource(); calls=[]
    async def fail(*args,**kwargs):
        calls.append(args)
        raise TdxAiDataAuthenticationError('TokenKey Insufficient Or Key Error')
    source._client.call=fail
    with pytest.raises(TdxAiDataAuthenticationError):
        await source._professional(['600000.SH','000001.SZ'],['GP15'],'20260901','20260922')
    assert len(calls)==1
    await source.aclose()


@pytest.mark.asyncio
async def test_detail_budget_rejects_before_request_and_does_not_truncate():
    source = TdxAiDataMarketDataSource()
    async def forbidden(*args, **kwargs):
        raise AssertionError('budget exceeded but SDK was called')
    source._client.call = forbidden
    symbols = [f'{600000+i}.SH' for i in range(101)]
    with pytest.raises(TdxAiDataUnavailable, match='100'):
        await source._professional(symbols, ['GP15'], '20260901', '20260922')
    await source.aclose()


@pytest.mark.asyncio
async def test_transient_failure_never_expands_into_symbol_or_daily_requests():
    source = TdxAiDataMarketDataSource()
    calls = []
    async def fail(*args, **kwargs):
        calls.append(args)
        raise TdxAiDataUnavailable('temporary SDK error')
    source._client.call = fail
    with pytest.raises(TdxAiDataUnavailable):
        await source._professional(['600000.SH', '000001.SZ'], ['GP15'], '20260901', '20260922')
    assert len(calls) == 1
    assert calls[0][0] == 'get_gpjy_value'
    await source.aclose()


@pytest.mark.asyncio
async def test_realtime_quotes_still_use_native_batch():
    source = TdxAiDataMarketDataSource()
    calls = []
    async def call(method, symbols, fields):
        calls.append((method, len(symbols)))
        return {symbol: {'Now': 10, 'LastClose': 9} for symbol in symbols}
    source._client.call = call
    symbols = [f'{600000+i}.SH' for i in range(205)]
    result = await source._snapshots(symbols)
    assert len(result) == 205
    assert calls == [('get_market_snapshot_batch', 100), ('get_market_snapshot_batch', 100), ('get_market_snapshot_batch', 5)]
    await source.aclose()


@pytest.mark.asyncio
async def test_disabled_hot_route_service_never_reads_calendar_or_sdk(tdx, monkeypatch):
    from app.services.market_domain_service import MarketDomainService
    source = TdxAiDataMarketDataSource()
    async def forbidden(*args, **kwargs):
        raise AssertionError('disabled ranking should not query calendar or SDK')
    source._client.call = forbidden
    monkeypatch.setattr(MarketDataSourceFactory, '_instances', {'tdxaidata': source})
    monkeypatch.setattr(MarketDomainService, '_cache_trade_day', forbidden)
    with pytest.raises(TdxAiDataUnavailable, match='人气榜已暂停'):
        await MarketDomainService.get_payoff('hot')
    await source.aclose()
