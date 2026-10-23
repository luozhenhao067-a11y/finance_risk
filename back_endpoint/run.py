"""开发入口：python run.py

生产部署请保持单进程（--workers 1），登录限流与后台任务链依赖进程内状态。
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
