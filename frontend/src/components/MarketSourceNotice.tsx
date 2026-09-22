'use client';
import { useEffect, useState } from 'react';
import { getMarketSourceInfo } from '@/lib/market/client';

export default function MarketSourceNotice() {
  const [notice, setNotice] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    const refresh = () => getMarketSourceInfo().then(info => {
      if (active) setNotice(info.notice || null);
    }).catch(() => { if (active) setNotice('数据源状态暂不可用，请稍后重试。'); });
    void refresh();
    const timer = setInterval(refresh, 15000);
    return () => { active = false; clearInterval(timer); };
  }, []);
  return notice ? <p role="status" className="order-1 rounded-lg border border-border bg-muted/30 px-4 py-3 text-xs text-muted-foreground">{notice} 缺失数值显示为“--”，完整样本才参与板块及成分评分。</p> : null;
}
