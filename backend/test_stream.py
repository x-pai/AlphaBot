#!/usr/bin/env python3
"""
测试流式传输功能的脚本
"""
import asyncio
import aiohttp
import json
import sys

async def test_stream_chat():
    """测试流式聊天功能"""
    url = "http://localhost:8000/api/v1/agent/chat"
    
    # 测试数据
    data = {
        "content": "分析一下贵州茅台的股票表现",
        "session_id": None,
        "enable_web_search": False,
        "stream": True
    }
    
    headers = {
        "Content-Type": "application/json",
        # 注意：实际使用时需要添加认证token
        # "Authorization": "Bearer your_token_here"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=headers) as response:
                if response.status != 200:
                    print(f"HTTP错误: {response.status}")
                    print(await response.text())
                    return
                
                print("开始接收流式响应...")
                print("=" * 50)
                
                async for line in response.content:
                    if line:
                        try:
                            # 解码并解析JSON
                            line_str = line.decode('utf-8').strip()
                            if line_str:
                                message = json.loads(line_str)
                                
                                # 根据消息类型显示不同内容
                                if message.get('type') == 'start':
                                    print(f"🚀 开始处理: {message.get('session_id')}")
                                    
                                elif message.get('type') == 'thinking':
                                    print(f"🤔 思考中: {message.get('content')}")
                                    
                                elif message.get('type') == 'tool_calls':
                                    print(f"🔧 工具调用: {len(message.get('tool_calls', []))} 个工具")
                                    
                                elif message.get('type') == 'tool_start':
                                    print(f"⚙️  执行工具: {message.get('tool_name')}")
                                    
                                elif message.get('type') == 'tool_result':
                                    print(f"✅ 工具结果: {message.get('tool_name')} 完成")
                                    
                                elif message.get('type') == 'content':
                                    print(f"💬 最终回复:")
                                    print(f"   {message.get('content')}")
                                    
                                elif message.get('type') == 'end':
                                    print(f"🏁 处理完成")
                                    
                                elif message.get('type') == 'error':
                                    print(f"❌ 错误: {message.get('error')}")
                                
                        except json.JSONDecodeError as e:
                            print(f"JSON解析错误: {e}")
                            print(f"原始数据: {line_str}")
                        except Exception as e:
                            print(f"处理错误: {e}")
                
                print("=" * 50)
                print("流式响应接收完成")
                
    except aiohttp.ClientError as e:
        print(f"网络错误: {e}")
    except Exception as e:
        print(f"未知错误: {e}")

async def test_traditional_chat():
    """测试传统聊天功能（非流式）"""
    url = "http://localhost:8000/api/v1/agent/chat"
    
    data = {
        "content": "分析一下贵州茅台的股票表现",
        "session_id": None,
        "enable_web_search": False,
        "stream": False
    }
    
    headers = {
        "Content-Type": "application/json",
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=headers) as response:
                if response.status != 200:
                    print(f"HTTP错误: {response.status}")
                    print(await response.text())
                    return
                
                result = await response.json()
                print("传统响应:")
                print("=" * 50)
                print(json.dumps(result, indent=2, ensure_ascii=False))
                print("=" * 50)
                
    except Exception as e:
        print(f"传统聊天测试错误: {e}")

async def main():
    """主函数"""
    print("AlphaBot 流式传输测试")
    print("=" * 50)
    
    if len(sys.argv) > 1 and sys.argv[1] == "traditional":
        print("测试传统聊天模式...")
        await test_traditional_chat()
    else:
        print("测试流式聊天模式...")
        await test_stream_chat()

if __name__ == "__main__":
    asyncio.run(main())
