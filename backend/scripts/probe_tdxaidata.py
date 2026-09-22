"""运行: .venv/bin/python scripts/probe_tdxaidata.py [--full]。只输出结构与少量行情样本。"""
import asyncio
import json
from pathlib import Path
import sys
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.market_data_sources.tdxaidata_client import TdxAiDataClient


def sample(value):
    if hasattr(value, "to_dict"):
        return {"shape": list(value.shape), "tail": str(value.tail(2))}
    if isinstance(value, dict):
        return {"keys": list(value)[:110], "sample": {k: sample(v) for k, v in list(value.items())[:2]}}
    if isinstance(value, list):
        return {"count": len(value), "sample": value[:2]}
    return value


async def main():
    client = TdxAiDataClient()
    today = datetime.now().strftime('%Y%m%d')
    start = (datetime.now()-timedelta(days=10)).strftime('%Y%m%d')
    cases = [
        ('get_stock_list', ['5', 1]),
        ('get_stock_list', ['15', 1]),
        ('get_market_snapshot_batch', [['600000.SH', '000001.SZ'], []]),
        ('get_more_info_batch', [['600000.SH', '000001.SZ'], []]),
        ('get_exday_data', ['600000.SH', 3]),
        ('get_trading_dates', ['SH', start, today]),
    ]
    if '--full' in sys.argv:
        cases += [
            ('get_stock_list_in_sector', ['880301.SH', 0, 1]),
            ('get_market_snapshot_batch', [['880301.SH','000001.SH','399001.SZ'], []]),
            ('get_more_info_batch', [['880301.SH'], []]),
            ('get_relation', ['600000.SH']),
            ('get_market_data', [['Close','Amount'], ['600000.SH'], '1d', start, today, 10, 'none', False]),
            ('get_more_info_batch', [['600000.SH','880301.SH'], ['HqDate','Zjl','Zjl_HB','fHSL','ZTGPNum']]),
            ('get_minute_data', ['000001.SH', today]),
            ('get_zdt_data', [['000001.SZ', '600000.SH']]),
            ('get_gpjy_value', [['600000.SH'], ['GP15', 'GP24', 'GP27'], start, today]),
            ('get_market_data', [[], ['000001.SH', '399001.SZ'], '1m', start, today, 500, 'none', False]),
        ]
    if '--diagnose' in sys.argv:
        cases = [
            ('get_stock_list', ['11', 1]), ('get_stock_list', ['12', 1]),
            ('get_zdt_data', [['600000.SH']]),
            ('get_gpjy_value', [['600000.SH'], ['GP15','GP27'], '', '']),
            ('get_gpjy_value_by_date', [['600000.SH'], ['GP15','GP27'], 2026, 921]),
            ('get_market_data', [['Amount'], ['000001.SH','399001.SZ'], '1m', '', today+'150000', 500, 'none', False]),
            ('get_market_data', [['Amount'], ['600000.SH'], '1d', '', today+'150000', 3, 'none', False]),
            ('get_more_info_batch', [['600000.SH','880301.SH'], ['HqDate','Zjl','Zjl_HB','fHSL','ZTGPNum']]),
        ]
    if '--range' in sys.argv:
        cases = [('get_gpjy_value', [['600000.SH','000504.SZ','001278.SZ'], ['GP15','GP27'], '20260915','20260922'])]
    if '--listing' in sys.argv:
        symbols = ['301717.SZ','302132.SZ','001246.SZ','301569.SZ','301660.SZ','301716.SZ']
        cases = [('get_stock_info_batch', [symbols, ['Name','J_start']])]
        cases += [('get_gpjy_value', [[symbol], ['GP15','GP27'], '20260525','20260922']) for symbol in symbols]
    failures = 0
    try:
        for method, args in cases:
            try:
                result = await client.call(method, *args)
                print(json.dumps({'method': method, 'args': args, 'result': (result if '--listing' in sys.argv or '--range' in sys.argv or '--diagnose' in sys.argv and method in ('get_zdt_data','get_gpjy_value','get_gpjy_value_by_date','get_more_info_batch') else sample(result))}, ensure_ascii=False, default=str), flush=True)
                if not result and not hasattr(result, 'shape'):
                    failures += 1
            except Exception as exc:
                failures += 1
                print(json.dumps({'method': method, 'error': str(exc)}, ensure_ascii=False), flush=True)
    finally:
        await client.aclose()
    return failures

if __name__ == '__main__':
    sys.exit(bool(asyncio.run(main())))
