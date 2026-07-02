#!/usr/bin/env python
"""一键启动TestForge HTTPS环境"""

import os
import subprocess
import sys
import time

def check_ssl_certificates():
    """检查SSL证书是否存在"""
    cert_path = "ssl/cert.pem"
    key_path = "ssl/key.pem"
    
    if not os.path.exists(cert_path):
        print("[ERROR] SSL证书不存在！")
        print("请先运行 generate_ssl_cert.bat 或 generate_ssl_cert.sh 生成证书")
        return False
    
    if not os.path.exists(key_path):
        print("[ERROR] SSL私钥不存在！")
        print("请先运行 generate_ssl_cert.bat 或 generate_ssl_cert.sh 生成证书")
        return False
    
    print("[OK] SSL证书检查通过")
    return True

def start_backend_server():
    """启动HTTPS后端服务器"""
    print("\n启动HTTPS后端服务器...")
    
    # 使用之前创建的启动脚本
    backend_script = "start_https_server.py"
    
    try:
        # 在新的命令窗口启动后端
        if sys.platform == "win32":
            subprocess.Popen(
                ["start", "cmd", "/k", f"python {backend_script}"],
                shell=True
            )
        else:
            # Linux/macOS
            subprocess.Popen(
                ["gnome-terminal", "--", "python3", backend_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        
        print("[OK] 后端服务器已启动")
        return True
        
    except Exception as e:
        print(f"[ERROR] 启动后端服务器失败: {e}")
        return False

def start_frontend_server():
    """启动HTTPS前端服务器"""
    print("\n启动HTTPS前端服务器...")
    
    try:
        # 进入frontend目录并启动
        frontend_dir = "frontend"
        
        if sys.platform == "win32":
            subprocess.Popen(
                ["start", "cmd", "/k", f"cd {frontend_dir} && npm run dev"],
                shell=True
            )
        else:
            # Linux/macOS
            subprocess.Popen(
                ["gnome-terminal", "--", "bash", "-c", f"cd {frontend_dir} && npm run dev"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        
        print("[OK] 前端服务器已启动")
        return True
        
    except Exception as e:
        print(f"[ERROR] 启动前端服务器失败: {e}")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("        启动TestForge HTTPS环境")
    print("=" * 60)
    
    # 检查SSL证书
    if not check_ssl_certificates():
        sys.exit(1)
    
    # 启动后端服务器
    if not start_backend_server():
        sys.exit(1)
    
    # 等待后端启动
    time.sleep(5)
    
    # 启动前端服务器
    if not start_frontend_server():
        sys.exit(1)
    
    # 显示访问信息
    print("\n" + "=" * 60)
    print("        HTTPS环境启动完成！")
    print("=" * 60)
    print("\n访问地址:")
    print("   前端应用: https://localhost:3000")
    print("   后端API:  https://localhost:9876")
    print("   API文档:  https://localhost:9876/api/docs")
    print("\n重要提示:")
    print("   1. 这是自签名证书，浏览器会显示安全警告")
    print("   2. 点击'高级' -> '继续前往localhost(不安全)'即可访问")
    print("   3. 开发环境可安全使用，生产环境请使用正式证书")
    print("\n按 Ctrl+C 退出此脚本...")
    
    try:
        # 保持脚本运行
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n正在关闭...")

if __name__ == "__main__":
    main()