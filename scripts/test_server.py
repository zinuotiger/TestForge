import subprocess
import sys
import time
import threading
import requests

def read_output(pipe, prefix):
    """读取子进程输出"""
    for line in iter(pipe.readline, ''):
        print(f"{prefix}: {line}", end='')

# 启动后端服务器
print("Starting backend server...")
process = subprocess.Popen(
    [sys.executable, '-m', 'uvicorn', 'backend.main:app', '--host', '0.0.0.0', '--port', '9876'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1,
    universal_newlines=True
)

# 启动线程读取输出
stdout_thread = threading.Thread(target=read_output, args=(process.stdout, "STDOUT"))
stderr_thread = threading.Thread(target=read_output, args=(process.stderr, "STDERR"))
stdout_thread.daemon = True
stderr_thread.daemon = True
stdout_thread.start()
stderr_thread.start()

# 等待服务器启动
print("Waiting for server to start...")
time.sleep(10)

# 检查进程状态
if process.poll() is not None:
    print("Server process terminated!")
    sys.exit(1)

# 测试API
print("Testing API endpoints...")
try:
    # 尝试连接
    response = requests.get('http://localhost:9876/api/health', timeout=5)
    print(f"Health API: Status {response.status_code}, Response: {response.text}")
    
    # 测试token用量API
    response = requests.get('http://localhost:9876/api/token-usage/summary', timeout=5)
    print(f"Token Usage API: Status {response.status_code}, Response: {response.text[:200]}")
    
except Exception as e:
    print(f"API test failed: {e}")

# 保持运行一段时间
print("Server is running. Press Ctrl+C to stop.")
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Stopping server...")
    process.terminate()
    process.wait()