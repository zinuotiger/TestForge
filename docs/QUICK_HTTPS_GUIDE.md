# TestForge HTTPS 快速启用指南

## 问题：网站未使用HTTPS，存在安全风险

### 风险分析：
1. **数据传输未加密**：用户名、密码、API密钥等敏感信息以明文传输
2. **中间人攻击**：攻击者可能窃听或篡改通信内容  
3. **浏览器安全限制**：某些现代Web功能需要HTTPS

## 解决方案：5分钟启用HTTPS

### 步骤1：生成SSL证书（1分钟）

```bash
# 方法A：使用Python脚本（推荐）
python create_ssl_cert.py

# 方法B：使用批处理脚本（Windows）
generate_ssl_cert.bat

# 方法C：使用Shell脚本（Linux/macOS）
chmod +x generate_ssl_cert.sh
./generate_ssl_cert.sh
```

### 步骤2：启动HTTPS服务（1分钟）

```bash
# 方法A：一键启动（Windows）
start_https_all.bat

# 方法B：Python脚本启动（跨平台）
python start_https_all.py

# 方法C：手动启动
# 终端1：启动HTTPS后端
python start_https_server.py

# 终端2：启动HTTPS前端  
cd frontend && npm run dev
```

### 步骤3：访问HTTPS服务（立即生效）

1. **前端应用**：https://localhost:3000
2. **后端API**：https://localhost:9876
3. **API文档**：https://localhost:9876/api/docs

### 步骤4：处理浏览器警告（开发环境）

由于是自签名证书，浏览器会显示安全警告：

**Chrome/Edge**：
- 点击"高级" → "继续前往localhost（不安全）"

**Firefox**：
- 点击"高级" → "接受风险并继续"

**Safari**：
- 点击"显示详细信息" → "访问此网站"

## 验证HTTPS是否生效

```bash
# 测试HTTPS连接
curl -k https://localhost:9876/api/health

# 预期输出：
# {"status":"healthy","version":"0.1.0","timestamp":"..."}
```

## 已创建的文件说明

| 文件 | 用途 |
|------|------|
| `ssl/cert.pem` | SSL证书文件 |
| `ssl/key.pem` | SSL私钥文件 |
| `start_https_server.py` | HTTPS后端启动脚本 |
| `create_ssl_cert.py` | Python SSL证书生成器 |
| `generate_ssl_cert.bat` | Windows证书生成脚本 |
| `generate_ssl_cert.sh` | Linux/macOS证书生成脚本 |
| `start_https_all.bat` | Windows一键启动脚本 |
| `start_https_all.py` | 跨平台一键启动脚本 |
| `HTTPS_SETUP.md` | 详细配置指南 |

## 安全效果对比

### 启用HTTPS前：
- ❌ 数据传输：明文传输
- ❌ 身份验证：无证书验证
- ❌ 完整性：可能被篡改
- ❌ 浏览器：显示"不安全"

### 启用HTTPS后：
- ✅ 数据传输：AES-256加密
- ✅ 身份验证：证书验证
- ✅ 完整性：SHA-256哈希保护
- ✅ 浏览器：显示安全锁图标

## 生产环境升级

开发完成后，可升级到生产级HTTPS：

### 1. 获取正式证书
```bash
# 使用Let's Encrypt（免费）
sudo apt install certbot
sudo certbot certonly --standalone -d your-domain.com
```

### 2. 更新证书文件
```bash
cp /etc/letsencrypt/live/your-domain.com/fullchain.pem ssl/cert.pem
cp /etc/letsencrypt/live/your-domain.com/privkey.pem ssl/key.pem
```

### 3. 使用反向代理（推荐）
配置Nginx/Apache作为反向代理，提供：
- 负载均衡
- 缓存加速
- 安全头部
- 访问控制

## 故障排除

### 问题1：证书生成失败
**解决**：安装依赖 `pip install cryptography`

### 问题2：端口被占用
**解决**：修改端口或停止占用进程
```bash
# 修改端口（编辑start_https_server.py）
port = 9877  # 改为其他端口
```

### 问题3：前端无法连接后端
**解决**：检查代理配置
```typescript
// 确保vite.config.ts中的代理配置正确
proxy: {
  "/api": {
    target: "https://localhost:9876",
    secure: false,  // 自签名证书需要设置为false
  }
}
```

## 总结

通过上述步骤，TestForge已成功启用HTTPS：
- ✅ 数据传输加密
- ✅ 防止中间人攻击
- ✅ 符合现代Web安全标准
- ✅ 为生产环境部署做好准备

**重要提示**：自签名证书仅用于开发环境，生产环境请使用正式证书。