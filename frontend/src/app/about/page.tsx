// frontend/src/app/about/page.tsx
'use client';

import React from 'react';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import { Button } from '../../components/ui/button';
import Image from 'next/image';

export default function AboutPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">关于我们</h1>
        <Link href="/">
          <Button variant="outline" size="sm" className="flex items-center">
            <ArrowLeft className="h-4 w-4 mr-2" />
            返回主页
          </Button>
        </Link>
      </div>
      
      <div className="grid md:grid-cols-2 gap-8">
        <div>
          <h2 className="text-xl font-semibold mb-4">AlphaBot智能投资助理</h2>
          <p className="text-muted-foreground mb-4">
            AlphaBot是一个基于多数据源和多种分析模式的智能股票分析助手，旨在帮助投资者做出更明智的投资决策。
            我们结合了传统技术分析、机器学习和大语言模型，为用户提供全面、专业的投资分析服务。
          </p>
          
          <h3 className="text-lg font-medium mt-6 mb-3">我们的团队</h3>
          <p className="text-muted-foreground">
            我们是一群热爱金融科技的开发者和投资爱好者，致力于将先进的AI技术应用于投资领域，
            让更多普通投资者能够享受到科技带来的投资便利。
          </p>
          
          <h3 className="text-lg font-medium mt-6 mb-3">支持我们</h3>
          <p className="text-muted-foreground mb-4">
            如果您觉得 AlphaBot 对您有帮助，欢迎打赏支持我们继续改进：
          </p>
          <div className="flex gap-6 mb-6">
            <div className="flex flex-col items-center">
              <div className="bg-white p-3 rounded-md shadow-md mb-2">
                <Image 
                  src="/wechat_sponsor.jpg" 
                  alt="微信打赏" 
                  width={140} 
                  height={140}
                  className="w-32 h-32"
                />
              </div>
              <p className="text-sm text-muted-foreground">微信赞赏</p>
            </div>
            <div className="flex flex-col items-center">
              <div className="bg-white p-3 rounded-md shadow-md mb-2">
                <Image 
                  src="/alipay_sponsor.jpg" 
                  alt="支付宝打赏" 
                  width={140} 
                  height={140}
                  className="w-32 h-32"
                />
              </div>
              <p className="text-sm text-muted-foreground">支付宝</p>
            </div>
          </div>

          <h3 className="text-lg font-medium mt-6 mb-3">联系我们</h3>
          <p className="text-muted-foreground">
            如有任何问题、建议或合作意向，欢迎通过以下方式联系我们：
          </p>
          <p className="text-muted-foreground">
            邮箱：<a href="mailto:alpha.bot.ai@gmail.com" className="text-primary hover:underline">ben_zzz@163.com</a>
          </p> 
        </div>
        
        <div className="flex flex-col items-center justify-center bg-card p-8 rounded-lg border border-border">
          <h2 className="text-xl font-semibold mb-6">关注我们的公众号</h2>
          <div className="bg-white p-3 rounded-md shadow-md mb-4">
            <Image 
              src="/qrcode.jpg" 
              alt="AlphaBot公众号" 
              width={192} 
              height={192}
              className="w-48 h-48"
            />
          </div>
          <h3 className="font-medium text-lg mt-2">「AlphaBot」</h3>
          <p className="text-center text-muted-foreground mt-4 max-w-md">
            扫描上方二维码关注公众号，获取：
          </p>
          <ul className="mt-3 space-y-2 text-muted-foreground">
            <li className="flex items-center">
              <span className="w-2 h-2 bg-primary rounded-full mr-2"></span>
              每日市场热点分析与AI选股推荐
            </li>
            <li className="flex items-center">
              <span className="w-2 h-2 bg-primary rounded-full mr-2"></span>
              专业投资策略与技术指标解读
            </li>
            <li className="flex items-center">
              <span className="w-2 h-2 bg-primary rounded-full mr-2"></span>
              AlphaBot新功能抢先体验资格
            </li>
            <li className="flex items-center">
              <span className="w-2 h-2 bg-primary rounded-full mr-2"></span>
              投资者社区活动与线下交流机会
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}