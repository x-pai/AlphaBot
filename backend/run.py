import uvicorn
import os

if __name__ == "__main__":
    # 获取端口，默认为 8000
    port = int(os.environ.get("PORT", 8000))
    
    # 启动服务器
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True) 