# TestForge HTTPS 安全配置指南

## 问题描述

当前TestForge运行在HTTP协议上，存在以下安全风险：
1. **数据传输未加密**：用户名、密码、API密钥等敏感信息以明文传输
2. **中间人攻击风险**：攻击者可能窃听或篡改通信内容
3. **浏览器安全限制**：某些现代浏览器功能（如Service Workers）需要HTTPS

## 解决方案概述

提供了三种HTTPS配置方案：
1. **开发环境**：自签名证书（快速启动）
2. **生产环境**：正式SSL证书（推荐）
3. **生产环境**：反向代理 + SSL证书（最佳实践）

## 方案一：自签名证书（开发环境）

### 步骤1：生成SSL证书

#### Windows 系统：
```cmd
# 方法1：使用批处理脚本
generate_ssl_cert.bat

# 方法2：手动生成
mkdir ssl
cd ssl
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=localhost"
```

#### Linux/macOS 系统：
```bash
# 方法1：使用Shell脚本
chmod +x generate_ssl_cert.sh
./generate_ssl_cert.sh

# 方法2：手动生成
mkdir -p ssl
openssl req -x509 -newkey rsa:4096 -keyout ssl/key.pem -out ssl/cert.pem -days 365 -nodes -subj "/CN=localhost"
```

### 步骤2：启动HTTPS服务

#### Windows 系统：
```cmd
# 方法1：一键启动（推荐）
start_https_all.bat

# 方法2：手动启动
# 终端1：启动后端
python start_https_server.py

# 终端2：启动前端
cd frontend
npm run dev
```

#### Linux/macOS 系统：
```bash
# 方法1：Python脚本启动
python start_https_all.py

# 方法2：手动启动
# 终端1：启动后端
python start_https_server.py

# 终端2：启动前端
cd frontend && npm run dev
```

### 步骤3：访问服务

1. **前端应用**：https://localhost:3000
2. **后端API**：https://localhost:9876  
3. **API文档**：https://localhost:9876/api/docs

### 处理浏览器安全警告

由于使用的是自签名证书，浏览器会显示安全警告：

#### Chrome/Edge：
1. 点击"高级"
2. 点击"继续前往localhost（不安全）"

#### Firefox：
1. 点击"高级"
2. 点击"接受风险并继续"

#### Safari：
1. 点击"显示详细信息"
2. 点击"访问此网站"

## 方案二：正式SSL证书（生产环境）

### 步骤1：获取正式证书

#### 免费证书（推荐）：
```bash
# 使用Let's Encrypt + certbot
sudo apt-get install certbot
sudo certbot certonly --standalone -d testforge.example.com
```

#### 商业证书：
从以下服务商购买：
- DigiCert
- GlobalSign
- Sectigo
- 阿里云SSL证书
- 腾讯云SSL证书

### 步骤2：配置证书

将获取的证书文件复制到项目目录：
```bash
mkdir -p ssl
cp /etc/letsencrypt/live/testforge.example.com/fullchain.pem ssl/cert.pem
cp /etc/letsencrypt/live/testforge.example.com/privkey.pem ssl/key.pem
```

### 步骤3：启动服务

```bash
# 启动HTTPS后端
python start_https_server.py

# 启动HTTPS前端
cd frontend && npm run dev
```

## 方案三：反向代理（生产环境最佳实践）

### Nginx配置示例

```nginx
# /etc/nginx/sites-available/testforge
server {
    listen 80;
    server_name testforge.example.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name testforge.example.com;
    
    # SSL证书配置
    ssl_certificate /etc/letsencrypt/live/testforge.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/testforge.example.com/privkey.pem;
    
    # SSL安全配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # 安全头部
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";
    
    # 静态文件服务（前端）
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
    
    # API代理（后端）
    location /api {
        proxy_pass http://localhost:9876;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        
        # API超时设置
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }
    
    # WebSocket支持
    location /ws {
        proxy_pass http://localhost:9876;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 启用Nginx配置

```bash
# 创建软链接
sudo ln -s /etc/nginx/sites-available/testforge /etc/nginx/sites-enabled/

# 测试配置
sudo nginx -t

# 重启Nginx
sudo systemctl restart nginx
```

## 环境变量配置

可以通过环境变量控制HTTPS行为：

```bash
# 设置证书路径
export TESTFORGE_SSL_CERT_FILE=ssl/cert.pem
export TESTFORGE_SSL_KEY_FILE=ssl/key.pem

# 设置HTTPS端口（默认9876）
export TESTFORGE_HTTPS_PORT=443

# 设置HTTP重定向（强制HTTPS）
export TESTFORGE_FORCE_HTTPS=true

# 启动服务
python start_https_server.py
```

## 验证HTTPS配置

### 1. 证书验证
```bash
# 检查证书信息
openssl x509 -in ssl/cert.pem -text -noout

# 检查证书有效期
openssl x509 -in ssl/cert.pem -dates -noout
```

### 2. 服务验证
```bash
# 使用curl测试
curl -k https://localhost:9876/api/health

# 使用openssl测试
openssl s_client -connect localhost:9876 -servername localhost
```

### 3. 安全扫描
```bash
# 使用sslscan（需要安装）
sslscan localhost:9876

# 使用testssl.sh
testssl.sh https://localhost:9876
```

## 故障排除

### 常见问题1：证书不受信任
**症状**：浏览器显示"您的连接不是私密连接"
**解决**：导入自签名证书到系统信任存储，或使用正式证书

### 常见问题2：连接被拒绝
**症状**：无法连接到https://localhost:9876
**解决**：
1. 检查服务器是否启动：`netstat -an | grep 9876`
2. 检查防火墙设置
3. 确认证书文件权限正确

### 常见问题3：混合内容警告
**症状**：页面加载但显示"不安全"
**解决**：确保所有资源（CSS、JS、图片）都通过HTTPS加载

### 常见问题4：证书过期
**症状**：浏览器显示"证书已过期"
**解决**：更新证书（自签名证书有效期1年）

## 安全最佳实践

### 1. 证书管理
- 使用Let's Encrypt自动续期
- 设置证书过期提醒
- 定期轮换私钥

### 2. SSL/TLS配置
- 禁用旧协议（SSLv2、SSLv3、TLS 1.0、TLS 1.1）
- 启用完美前向保密（PFS）
- 使用强密码套件

### 3. 安全头部
确保配置以下HTTP安全头部：
- Strict-Transport-Security
- Content-Security-Policy
- X-Content-Type-Options
- X-Frame-Options
- X-XSS-Protection

### 4. 监控与日志
- 监控证书过期时间
- 记录SSL/TLS握手错误
- 定期安全扫描

## 自动续期脚本（Let's Encrypt）

```bash
#!/bin/bash
# renew_cert.sh

DOMAIN="testforge.example.com"
EMAIL="admin@example.com"

# 续期证书
certbot renew --quiet

# 重启服务
systemctl restart nginx
systemctl restart testforge-backend

# 发送通知
echo "证书续期完成：$(date)" | mail -s "TestForge证书续期通知" $EMAIL
```

## 相关文件说明

| 文件 | 说明 |
|------|------|
| `ssl/cert.pem` | SSL证书文件 |
| `ssl/key.pem` | SSL私钥文件 |
| `start_https_server.py` | HTTPS后端启动脚本 |
| `generate_ssl_cert.sh` | 生成SSL证书脚本（Linux/macOS） |
| `generate_ssl_cert.bat` | 生成SSL证书脚本（Windows） |
| `start_https_all.bat` | 一键启动HTTPS环境（Windows） |
| `start_https_all.py` | 一键启动HTTPS环境（跨平台） |
| `frontend/vite.config.ts` | 前端HTTPS配置 |

## 总结

通过启用HTTPS，TestForge可以提供：
1. ✅ **数据传输加密**：保护敏感信息
2. ✅ **身份验证**：防止中间人攻击
3. ✅ **完整性保护**：防止数据篡改
4. ✅ **浏览器兼容**：支持现代Web功能

建议开发环境使用方案一，生产环境使用方案二或方案三。