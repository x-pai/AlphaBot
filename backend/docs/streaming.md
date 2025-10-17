# AlphaBot 流式传输功能

## 概述

AlphaBot现在支持流式传输功能，可以实时显示AI处理过程，避免长时间等待导致的超时问题。该功能借鉴了xAI的Chunked NDJSON格式，提供更好的用户体验。

## 功能特性

### 后端特性
- **流式响应**: 使用FastAPI的StreamingResponse实现
- **Chunked NDJSON**: 采用类似xAI的流式数据格式
- **实时状态**: 显示思考、工具调用、执行结果等各个阶段
- **错误处理**: 完善的错误处理和状态管理

### 前端特性
- **实时显示**: 实时显示AI处理过程
- **状态指示**: 显示当前处理状态（思考中、执行工具等）
- **开关控制**: 可以开启/关闭流式传输
- **兼容性**: 同时支持流式和非流式模式

## 技术实现

### 后端实现

#### 1. 接口修改
```python
@router.post("/chat")
async def agent_chat(
    request: AgentMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _: None = Depends(check_usage_limit)
):
    # 如果启用流式传输
    if request.stream:
        return StreamingResponse(
            stream_agent_response(...),
            media_type="application/x-ndjson"
        )
    # 非流式传输的原有逻辑
    ...
```

#### 2. 流式响应格式
```json
{"type": "start", "session_id": "uuid", "timestamp": "uuid"}
{"type": "thinking", "content": "正在分析数据...", "timestamp": "uuid"}
{"type": "tool_calls", "tool_calls": [...], "timestamp": "uuid"}
{"type": "tool_start", "tool_name": "search_stocks", "timestamp": "uuid"}
{"type": "tool_result", "tool_name": "search_stocks", "result": {...}, "timestamp": "uuid"}
{"type": "content", "content": "最终回复内容", "session_id": "uuid", "timestamp": "uuid"}
{"type": "end", "session_id": "uuid", "timestamp": "uuid"}
{"type": "error", "error": "错误信息", "timestamp": "uuid"}
```

### 前端实现

#### 1. API调用
```typescript
export async function chatWithAgentStream(
  data: {
    content: string;
    session_id?: string;
    enable_web_search?: boolean;
  },
  onMessage: (message: any) => void
): Promise<void>
```

#### 2. 流式处理
```typescript
const handleStreamingChat = async (input: string) => {
  await chatWithAgentStream(
    { content: input, session_id: currentSession, enable_web_search: webSearchEnabled },
    (message) => {
      switch (message.type) {
        case 'start':
          // 处理开始信号
          break;
        case 'thinking':
          // 显示思考状态
          break;
        case 'content':
          // 显示最终内容
          break;
        // ... 其他状态处理
      }
    }
  );
};
```

## 使用方法

### 1. 后端配置
无需额外配置，流式传输功能已集成到现有的agent/chat接口中。

### 2. 前端使用
在AgentChat组件中，用户可以通过界面上的"流式传输"开关来控制是否使用流式模式。

### 3. API调用示例

#### 流式调用
```javascript
// 前端调用
await chatWithAgentStream(
  {
    content: "分析贵州茅台股票",
    session_id: "session-123",
    enable_web_search: false
  },
  (message) => {
    console.log('收到消息:', message);
  }
);
```

#### 传统调用
```javascript
// 前端调用
const response = await chatWithAgent({
  content: "分析贵州茅台股票",
  session_id: "session-123",
  enable_web_search: false,
  stream: false
});
```

## 测试

### 1. 运行测试脚本
```bash
# 测试流式传输
python test_stream.py

# 测试传统模式
python test_stream.py traditional
```

### 2. 前端测试
1. 启动前端应用
2. 进入AgentChat页面
3. 开启"流式传输"开关
4. 发送消息观察实时响应

## 优势

### 1. 用户体验
- **实时反馈**: 用户可以看到AI的思考过程
- **避免超时**: 长时间处理不会导致请求超时
- **状态透明**: 清楚了解当前处理状态

### 2. 技术优势
- **可扩展**: 易于添加新的状态类型
- **兼容性**: 同时支持流式和非流式模式
- **标准化**: 采用NDJSON格式，便于解析

### 3. 性能优势
- **内存效率**: 流式处理减少内存占用
- **网络优化**: 分块传输减少网络延迟
- **并发支持**: 支持多个并发流式请求

## 注意事项

1. **认证**: 流式请求需要有效的认证token
2. **错误处理**: 需要处理网络中断等异常情况
3. **状态管理**: 前端需要正确管理流式状态
4. **兼容性**: 确保非流式模式仍然正常工作

## 未来改进

1. **断线重连**: 支持网络中断后自动重连
2. **进度条**: 显示处理进度
3. **取消功能**: 允许用户取消正在进行的请求
4. **批量处理**: 支持批量流式请求
5. **性能监控**: 添加流式传输的性能监控

## 总结

流式传输功能大大提升了AlphaBot的用户体验，通过实时显示AI处理过程，用户可以更好地理解系统的工作方式，同时避免了长时间等待的问题。该功能采用标准化的NDJSON格式，具有良好的可扩展性和兼容性。
