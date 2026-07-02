#!/usr/bin/env bash
# 生成SSL证书脚本

echo "生成TestForge HTTPS SSL证书..."

# 创建SSL目录
mkdir -p ssl

# 检查是否已有证书
if [ -f "ssl/cert.pem" ] && [ -f "ssl/key.pem" ]; then
    echo "SSL证书已存在。"
    echo "证书信息:"
    openssl x509 -in ssl/cert.pem -text -noout | grep -A1 "Subject:"
    echo "证书有效期:"
    openssl x509 -in ssl/cert.pem -dates -noout
    read -p "是否重新生成? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "使用现有证书。"
        exit 0
    fi
fi

# 生成新的自签名证书
echo "生成新的自签名证书..."
openssl req -x509 -newkey rsa:4096 \
    -keyout ssl/key.pem \
    -out ssl/cert.pem \
    -days 365 \
    -nodes \
    -subj "/C=CN/ST=Beijing/L=Beijing/O=TestForge/OU=Development/CN=localhost"

# 检查生成结果
if [ -f "ssl/cert.pem" ] && [ -f "ssl/key.pem" ]; then
    echo "✅ SSL证书生成成功！"
    echo ""
    echo "证书文件:"
    echo "  - ssl/cert.pem (证书)"
    echo "  - ssl/key.pem (私钥)"
    echo ""
    echo "证书信息:"
    openssl x509 -in ssl/cert.pem -text -noout | grep -A1 "Subject:"
    echo ""
    echo "使用方法:"
    echo "  1. 启动HTTPS后端: python start_https_server.py"
    echo "  2. 启动HTTPS前端: cd frontend && npm run dev"
    echo ""
    echo "访问地址:"
    echo "  - 后端API: https://localhost:9876"
    echo "  - 前端应用: https://localhost:3000"
    echo "  - API文档: https://localhost:9876/api/docs"
    echo ""
    echo "⚠️ 注意: 这是自签名证书，浏览器会显示安全警告。"
    echo "      在开发环境中可以安全忽略。"
else
    echo "❌ SSL证书生成失败！"
    exit 1
fi