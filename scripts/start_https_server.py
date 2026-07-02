#!/usr/bin/env python
"""启动HTTPS后端服务器"""

import sys
import os
import subprocess
import time

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Starting HTTPS backend server on port 9876...")

# 检查SSL证书文件是否存在
ssl_cert = "ssl/cert.pem"
ssl_key = "ssl/key.pem"

if not os.path.exists(ssl_cert) or not os.path.exists(ssl_key):
    print("[ERROR] SSL证书文件不存在！")
    print("请先生成SSL证书：")
    print("  mkdir -p ssl")
    print("  openssl req -x509 -newkey rsa:4096 -keyout ssl/key.pem -out ssl/cert.pem -days 365 -nodes -subj \"/CN=localhost\"")
    sys.exit(1)

# 使用subprocess启动HTTPS服务器
cmd = [
    sys.executable, "-m", "uvicorn", "backend.main:app",
    "--host", "0.0.0.0",
    "--port", "9876",
    "--ssl-keyfile", ssl_key,
    "--ssl-certfile", ssl_cert
]

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
    print(f"SSL certificate: {os.path.abspath(ssl_cert)}")
    print(f"SSL key: {os.path.abspath(ssl_key)}")
    
    # 等待几秒让服务器启动
    time.sleep(3)
    
    # 检查进程状态
    if process.poll() is None:
        print("[OK] HTTPS backend server is running")
        print("[OK] Server URL: https://localhost:9876")
        print("[OK] API docs: https://localhost:9876/api/docs")
        
        # 测试健康检查（使用HTTPS）
        import requests
        try:
            # 禁用SSL证书验证（自签名证书）
            response = requests.get('https://localhost:9876/api/health', timeout=5, verify=False)
            print(f"[OK] Health check: Status {response.status_code}")
        except Exception as e:
            print(f"[ERROR] Health check failed: {e}")
        
        # 保持进程运行
        print("\nHTTPS server is running in background. Press Ctrl+C to stop.")
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
    print(f"Failed to start HTTPS server: {e}")
    import traceback
    traceback.print_exc()