#!/usr/bin/env python
"""启动后端服务器并捕获错误"""

import sys
import os
import subprocess
import time

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Starting backend server...")

# 尝试直接导入
try:
    from backend.main import app
    print("[OK] Backend app imported successfully")
except Exception as e:
    print(f"[ERROR] Failed to import backend app: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 使用uvicorn启动服务器
cmd = [
    sys.executable, "-m", "uvicorn", 
    "backend.main:app",
    "--host", "0.0.0.0",
    "--port", "9876",
    "--reload"
]

print(f"Starting command: {' '.join(cmd)}")

# 启动服务器
try:
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True
    )
    
    # 等待并输出日志
    print("Server starting...")
    for i in range(10):  # 等待最多10秒
        line = process.stdout.readline()
        if line:
            print(f"Server: {line.strip()}")
        
        # 检查进程是否还在运行
        if process.poll() is not None:
            print(f"Server process terminated with code: {process.returncode}")
            break
        
        time.sleep(1)
    
    # 如果进程还在运行，说明启动成功
    if process.poll() is None:
        print("\n[SUCCESS] Backend server is running on http://localhost:9876")
        print("Press Ctrl+C to stop the server")
        
        # 保持进程运行
        try:
            process.wait()
        except KeyboardInterrupt:
            print("\nStopping server...")
            process.terminate()
            process.wait()
            
except Exception as e:
    print(f"[ERROR] Failed to start server: {e}")
    import traceback
    traceback.print_exc()