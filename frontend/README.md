# AlphaBot前端

AlphaBot的前端界面，使用 React、TypeScript 和 Ant Design 构建。

## 功能特点

- 股票搜索和详情展示
- 交互式股票图表
- 技术指标可视化
- AI 分析结果展示
- 用户投资组合管理

## 技术栈

- **React**: UI 库
- **TypeScript**: 类型安全的 JavaScript
- **Ant Design**: UI 组件库
- **ECharts**: 图表库
- **Redux Toolkit**: 状态管理
- **React Router**: 路由管理
- **Axios**: HTTP 客户端

## 开发环境设置

### 前提条件

- Node.js 14.x 或更高版本
- npm 6.x 或更高版本

### 安装步骤

1. 克隆仓库
```bash
git clone https://github.com/x-pai/ai-stock-assistant.git
cd ai-stock-assistant/frontend
```

2. 安装依赖
```bash
npm install
```

3. 启动开发服务器
```bash
npm start
```

应用将在 http://localhost:3000 上运行。

## 项目结构

```
frontend/
├── public/              # 静态资源
├── src/                 # 源代码
│   ├── api/             # API 请求
│   ├── components/      # 可复用组件
│   ├── pages/           # 页面组件
│   ├── store/           # Redux 状态管理
│   ├── types/           # TypeScript 类型定义
│   ├── utils/           # 工具函数
│   ├── App.tsx          # 应用入口组件
│   └── index.tsx        # 应用入口点
├── .env                 # 环境变量
├── package.json         # 项目依赖
├── tsconfig.json        # TypeScript 配置
└── README.md            # 项目说明
```

## 构建生产版本

```bash
npm run build
```

构建产物将生成在 `build` 目录中。

## Docker 部署

使用 Docker 构建和运行前端：

```bash
# 构建镜像
docker build -t ai-stock-assistant-frontend .

# 运行容器
docker run -p 3000:80 ai-stock-assistant-frontend
```

## 开发指南

### 添加新页面

1. 在 `src/pages` 目录下创建新页面组件
2. 在 `src/App.tsx` 中添加路由

### 添加新组件

1. 在 `src/components` 目录下创建新组件
2. 导出组件并在需要的地方导入使用

### 添加新 API 请求

1. 在 `src/api` 目录下添加新的 API 请求函数
2. 使用 Axios 发送请求并处理响应

## 测试

```bash
# 运行单元测试
npm test

# 运行端到端测试
npm run test:e2e
```

## 贡献指南

请参阅项目根目录的 [贡献指南](../README.md#贡献指南)。
