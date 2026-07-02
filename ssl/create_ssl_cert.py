#!/usr/bin/env python
"""创建SSL证书的Python脚本（不依赖OpenSSL命令行）"""

import os
import sys
import ssl
import datetime
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption

def generate_self_signed_cert(cert_path="ssl/cert.pem", key_path="ssl/key.pem", days_valid=365):
    """生成自签名SSL证书"""
    
    # 创建SSL目录
    os.makedirs(os.path.dirname(cert_path), exist_ok=True)
    
    print("正在生成自签名SSL证书...")
    
    try:
        # 生成RSA私钥
        print("1. 生成RSA私钥...")
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=4096,
        )
        
        # 创建证书主题
        print("2. 创建证书主题...")
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "CN"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Beijing"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Beijing"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "TestForge"),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Development"),
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
        ])
        
        # 创建证书
        print("3. 创建证书...")
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.datetime.utcnow()
        ).not_valid_after(
            datetime.datetime.utcnow() + datetime.timedelta(days=days_valid)
        ).add_extension(
            x509.SubjectAlternativeName([x509.DNSName("localhost")]),
            critical=False,
        ).sign(private_key, hashes.SHA256())
        
        # 保存私钥
        print("4. 保存私钥...")
        with open(key_path, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ))
        
        # 保存证书
        print("5. 保存证书...")
        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        
        print(f"\n[OK] SSL证书生成成功！")
        print(f"   证书文件: {os.path.abspath(cert_path)}")
        print(f"   私钥文件: {os.path.abspath(key_path)}")
        print(f"   有效期: {days_valid}天")
        print(f"   主题: CN=localhost, O=TestForge, OU=Development, L=Beijing, ST=Beijing, C=CN")
        
        return True
        
    except Exception as e:
        print(f"\n[ERROR] SSL证书生成失败: {e}")
        return False

def check_dependencies():
    """检查依赖"""
    try:
        import cryptography
        print(f"[OK] cryptography版本: {cryptography.__version__}")
        return True
    except ImportError:
        print("[ERROR] 缺少cryptography库")
        print("   请安装: pip install cryptography")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("        TestForge SSL证书生成工具")
    print("=" * 60)
    
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    # 检查是否已存在证书
    cert_path = "ssl/cert.pem"
    key_path = "ssl/key.pem"
    
    if os.path.exists(cert_path) and os.path.exists(key_path):
        print(f"\n[WARNING] SSL证书已存在:")
        print(f"   {cert_path}")
        print(f"   {key_path}")
        
        response = input("\n是否重新生成? (y/N): ").strip().lower()
        if response != 'y':
            print("使用现有证书。")
            sys.exit(0)
    
    # 生成证书
    success = generate_self_signed_cert(cert_path, key_path)
    
    if success:
        print("\n" + "=" * 60)
        print("使用说明:")
        print("=" * 60)
        print("1. 启动HTTPS后端服务器:")
        print("   python start_https_server.py")
        print("\n2. 启动HTTPS前端服务器:")
        print("   cd frontend && npm run dev")
        print("\n3. 访问地址:")
        print("   前端: https://localhost:3000")
        print("   后端: https://localhost:9876")
        print("   API文档: https://localhost:9876/api/docs")
        print("\n[WARNING] 注意: 这是自签名证书，浏览器会显示安全警告。")
        print("          在开发环境中可以安全忽略此警告。")
        print("=" * 60)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()