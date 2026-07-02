#!/usr/bin/env python
"""启动后端服务器"""

import sys
import os
import subprocess
import time

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Starting backend server on port 9876...")

# 使用subprocess启动服务器
cmd = [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "9876"]

try:
    # 启动服务器进程
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True
    )
    
    print(f"Server started with PID: {process.pid}")
    
    # 等待几秒让服务器启动
    time.sleep(3)
    
    # 检查进程状态
    if process.poll() is None:
        print("[OK] Backend server is running")
        print("[OK] Server URL: http://localhost:9876")
        print("[OK] API docs: http://localhost:9876/api/docs")
        
        # 测试健康检查
        import requests
        try:
            response = requests.get('http://localhost:9876/api/health', timeout=5)
            print(f"[OK] Health check: Status {response.status_code}")
        except Exception as e:
            print(f"[ERROR] Health check failed: {e}")
        
        # 保持进程运行
        print("\nServer is running in background. Press Ctrl+C to stop.")
        try:
            process.wait()
        except KeyboardInterrupt:
            print("\nStopping server...")
            process.terminate()
            process.wait()
    else:
        # 读取输出以查看错误
        stdout, _ = process.communicate()
        print(f"Server process terminated with code: {process.returncode}")
        print("Output:", stdout)
        
except Exception as e:
    print(f"Failed to start server: {e}")
    import traceback
    traceback.print_exc()