"""真实数据验收：.venv/bin/python scripts/verify_tdxaidata_market.py [--full]。不需要 Redis。"""
import asyncio
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.market_data_sources.tdxaidata import TdxAiDataMarketDataSource
from app.schemas.market import PlateFlowItem, PlateMemberItem, QuoteItem, FundflowRow, TopicStockItem, PayoffItem, TurnoverData, PlateIndexItem

async def main():
    if '--history' in sys.argv:
        print('历史全市场自动回补已暂停；该脚本不会绕过成本限制。')
        return 1
    if '--full' in sys.argv:
        print('人气榜与历史回补已暂停；本次只验证当前允许的接口。')
    source=TdxAiDataMarketDataSource()
    failures=[]
    cases=[('calendar',lambda:source.fetch_trading_dates()),
           ('quotes',lambda:source.fetch_quotes(['600000','000001'])),
           ('universe',source.fetch_universe),
           ('members',lambda:source.fetch_members('881002.SH')),
           ('plate_index',lambda:source.fetch_plate_index('881002.SH',12)),
           ('fundflow',lambda:source.fetch_fundflow(['600000','000001'],3)),
           ('turnover',source.fetch_turnover),('trending',source.fetch_trending)]
    if '--full' in sys.argv:
        cases += [('pools',lambda:source.fetch_pool('zt')),('broken',lambda:source.fetch_pool('zb')),('down',lambda:source.fetch_pool('dt')),
                  ('surge',source.fetch_surge),('strong',lambda:source.fetch_payoff('strong')),
                  ('drawdown',lambda:source.fetch_payoff('drawdown'))]
    if '--turnover-check' in sys.argv:
        async def compare():
            names, quotes, _ = await source._all_quotes()
            indices = await source._snapshots(['000001.SH','399001.SZ'])
            stock_amount = sum(float(q.get('Amount') or 0) for s,q in quotes.items() if s.endswith(('.SH','.SZ'))) * 10000
            index_amount = sum(float(q.get('Amount') or 0) for q in indices.values()) * 10000
            turnover = await source.fetch_turnover()
            return {'stockAmount':stock_amount, 'indexAmount':index_amount, 'minuteAmount':turnover['current'],
                    'stockToIndexRatio': stock_amount/index_amount if index_amount else None}
        cases = [('turnover_scope',compare)]
    if '--payoff' in sys.argv:
        cases = [('strong',lambda:source.fetch_payoff('strong')),('drawdown',lambda:source.fetch_payoff('drawdown'))]
    try:
        for name,fn in cases:
            started=time.monotonic()
            try:
                result=await fn()
                model={'quotes':QuoteItem,'universe':PlateFlowItem,'members':PlateMemberItem,'plate_index':PlateIndexItem,
                       'pools':TopicStockItem,'broken':TopicStockItem,'down':TopicStockItem,'strong':PayoffItem,'hot':PayoffItem,'drawdown':PayoffItem}.get(name)
                if model:
                    for row in result.values() if isinstance(result,dict) else result: model.model_validate(row)
                if name=='fundflow':
                    for rows in result.values():
                        for row in rows: FundflowRow.model_validate(row)
                if name=='turnover': TurnoverData.model_validate(result)
                example=(next(iter(result.values()),None) if isinstance(result,dict) else result[0] if result else None)
                if name in ('turnover','turnover_scope'): example={k:v for k,v in result.items() if k!='points'}
                print(json.dumps({'dataset':name,'seconds':round(time.monotonic()-started,2),'count':len(result),'sample':example},ensure_ascii=False,default=str),flush=True)
            except Exception as exc:
                failures.append(name)
                print(json.dumps({'dataset':name,'seconds':round(time.monotonic()-started,2),'error':str(exc)},ensure_ascii=False),flush=True)
                if '--history' in sys.argv: break
    finally:
        await source.aclose()
    return bool(failures)
if __name__=='__main__': sys.exit(asyncio.run(main()))
