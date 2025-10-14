中文|[English](README_en.md)

# 🤖 AlphaBot - 你的智能股票分析助手

> "在股市中，赚钱的不是最聪明的人，而是最有纪律的人。" —— 沃伦·巴菲特（可能没说过，但听起来很有道理）

## 🎭 当AI遇上股市：一场理性与数据的较量

欢迎来到AlphaBot的世界，这里不仅有冷冰冰的数据分析，还有暖心的交易建议。我们知道，你使用这个应用的原因可能是：

- 📉 上个月的交易让你怀疑人生
- 🧠 你的交易决策常常被"我感觉它会涨"所主导
- 💸 你有"追高杀跌"的优秀传统
- 🎰 你把股市当成了一个大型赌场（并且总是庄家赢）

别担心，我们都经历过。AlphaBot就是为了帮助你从"感觉派交易员"晋升为"数据派投资者"而生的。

## 🛡️ 免责声明（认真脸）

**重要提示：使用本项目前，请确认您已经明白以下事实**

1. **这不是一个印钞机**：本项目不能保证让你成为下一个巴菲特或西蒙斯。如果有这种功能，我们早就退休去马尔代夫了。

2. **市场风险**：股市有风险，入市需谨慎。记住，市场永远是对的，即使它看起来不讲道理。

3. **AI也会犯错**：我们的AI模型虽然聪明，但它不会预测地震、政变或者你邻居突然决定抛售所有股票。

4. **用户责任**：如果你在使用本软件后亏钱了，请记住是你自己点的"买入"按钮，不是我们。

5. **数据来源**：我们使用的数据来自第三方，如果数据出错，那真的不是我们的锅。

**使用本项目即表示您同意：无论盈亏，都保持微笑，因为至少你学到了宝贵的经验。**

## 🧙‍♂️ 核心功能：从数据到决策

### 🤖 AlphaBot Agent 智能助手（全新上线！）

- **智能问答**：基于大语言模型的智能金融顾问，随时解答您的投资疑问
- **联网搜索**：实时获取最新市场资讯和公司新闻
- **数据可视化**：通过自然语言生成专业的股票走势图和分析报告
- **量化策略**：根据您的需求推荐和解释适合的量化交易策略

### 📊 多数据源支持

- **全球市场数据**：通过Alpha Vantage获取全球股票市场数据
- **中国市场数据**：通过Tushare和AKShare获取A股市场数据
- **实时行情更新**：自动同步最新市场数据

### 🤖 AI智能分析

- **技术分析**：基于历史数据的趋势和形态分析
- **基本面分析**：公司财务指标和行业对比分析
- **机器学习预测**：使用训练好的模型进行市场预测
- **大语言模型分析**：利用OpenAI API进行深度市场解读

### 📈 交易辅助功能

- **股票搜索**：快速查找和筛选股票
- **历史数据**：查看历史价格和交易数据
- **技术指标**：计算和展示常用技术指标
- **风险评估**：AI驱动的风险评估和建议

## 🚀 快速开始

### 方法一：使用 Docker（推荐）

项目提供了 Docker Compose 配置和一键部署脚本，可以快速部署整个应用。

#### 前提条件

- Docker 和 Docker Compose 已安装
- 一颗平常心（这个很重要）

#### 部署步骤

1. 克隆仓库
```bash
git clone https://github.com/x-pai/alphabot.git
cd alphabot
```

2. 运行部署脚本
```bash
./deploy.sh
```

Windows
```bash
./deploy.ps1 # 使用新版本的PowerShell
```

相关issues:
- [未找到/backend/entrepoint.sh文件或文件夹](https://github.com/x-pai/AlphaBot/issues/17)
- [alphabot-backend | exec /backend/entrypoint.sh: no such file or directory](https://github.com/x-pai/AlphaBot/issues/16)

3. 访问应用
- 后端 API 文档：http://localhost:8000/api/v1/docs
- 前端界面：http://localhost:3000

![安装教程](materials/howtoinstall.gif)

使用教程：[【AlphaBot使用教程】专业帮您把复杂的投资决策变成简单的错误决定](https://www.bilibili.com/video/BV14ZxEz2EYS/?share_source=copy_web&vd_source=ad23b126ca275748fca93b1519b60b36)

### 方法二：手动安装（适合喜欢折腾的朋友）

#### 后端

```bash
cd backend
pip install -r requirements.txt
# 配置 .env 文件
python train_model.py  # 可选，训练机器学习模型
uvicorn app.main:app --reload
```

#### 前端

```bash
cd frontend
npm install
npm start
```

#### 数据库工具
```bash
backend/app/cli/README.md
```

默认账户密码：admin/admin123

## 🧩 使用AlphaBot Agent

访问应用后，您可以直接使用全新上线的AlphaBot Agent智能助手：

1. 点击界面中的"智能助手"按钮进入对话界面
2. 输入您的金融问题或分析需求
3. 启用"联网搜索"功能获取最新资讯
4. 查看AI生成的专业分析和建议

![AlphaBot Agent演示](materials/agent_demo.png)

## 📝 交易者誓言

使用AlphaBot，请默念以下誓言：

1. 我承诺遵循数据分析，而不是我的直觉
2. 我承诺设置止损并严格执行
3. 我承诺不在情绪激动时交易
4. 我承诺把风险控制放在首位
5. 我承诺记住：保存资金是交易的第一要务

## 🤝 加入我们的"理性交易者"社区

公众号：
<div align="center">
  <img src="./materials/mp_weixin_qr.png" alt="AlphaBot公众号" width="300"/>
</div>

微信群：
<div align="center">
  <img src="./materials/wechat_group_qr.jpg" alt="AlphaBot微信群" width="300"/>
</div>

~~QQ群：[点击链接加入群聊【AlphaBot交易者联盟】](https://qm.qq.com/q/ES8Fp8AdpY)~~

## 💰 赞助本项目

如果AlphaBot帮你避免了一次冲动交易，或者帮你建立了更好的交易系统，请考虑赞助我们。你的支持将用于：

1. 服务器维护（因为AI模型很能吃内存）
2. 数据源订阅（优质数据不是免费的）
3. 开发者的咖啡（这是最重要的）

<div align="center">
  <img src="./materials/sponsor_qr.jpg" alt="赞助二维码" width="250"/>
  <p>微信扫码赞助（金额随意，心意最重要）</p>
</div>

### 赞助商展示

<table>
  <tr>
    <td align="center" width="180">
      <a href="https://example.com">
        <img src="./materials/sponsors/example_corp.png" width="160" alt="示例公司" />
        <br />
        <b>示例公司</b>
      </a>
    </td>
    <td align="center" width="180">
      <a href="https://your-company.com">
        <img src="./materials/sponsors/your_logo.png" width="160" alt="贵公司Logo" />
        <br />
        <b>贵公司名称</b>
      </a>
    </td>
  </tr>
</table>

> 查看我们的[赞助计划](sponsors.md)了解更多企业赞助选项。

## 🧠 记住

> "市场可以保持非理性的时间，比你能保持资金充裕的时间更长。" —— 凯恩斯

但有了AlphaBot，至少你能保持理性的时间会更长一些。

祝交易愉快！记住，最好的交易有时候是不交易。

## 🧑‍💻 贡献指南

请参考 [CONTRIBUTING.md](CONTRIBUTING.md) 获取详细的分支规范、提交要求、PR 模板与问题报告流程。
