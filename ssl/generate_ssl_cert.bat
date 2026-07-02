@echo off
REM 生成SSL证书的Windows批处理脚本
echo 生成TestForge HTTPS SSL证书...

REM 创建SSL目录
if not exist "ssl" mkdir ssl

REM 检查是否已有证书
if exist "ssl\cert.pem" (
    if exist "ssl\key.pem" (
        echo SSL证书已存在。
        echo 证书信息:
        openssl x509 -in ssl\cert.pem -text -noout | findstr "Subject:"
        echo 证书有效期:
        openssl x509 -in ssl\cert.pem -dates -noout
        set /p choice="是否重新生成? (y/N): "
        if /i not "%choice%"=="y" (
            echo 使用现有证书。
            pause
            exit /b 0
        )
    )
)

REM 检查OpenSSL是否可用
where openssl >nul 2>nul
if %errorlevel% neq 0 (
    echo 错误: OpenSSL未安装！
    echo 请先安装OpenSSL:
    echo 1. 下载并安装OpenSSL: https://slproweb.com/products/Win32OpenSSL.html
    echo 2. 确保openssl.exe在系统PATH中
    pause
    exit /b 1
)

REM 生成新的自签名证书
echo 生成新的自签名证书...
openssl req -x509 -newkey rsa:4096 ^
    -keyout ssl\key.pem ^
    -out ssl\cert.pem ^
    -days 365 ^
    -nodes ^
    -subj "/C=CN/ST=Beijing/L=Beijing/O=TestForge/OU=Development/CN=localhost"

REM 检查生成结果
if exist "ssl\cert.pem" (
    if exist "ssl\key.pem" (
        echo [OK] SSL证书生成成功！
        echo.
        echo 证书文件:
        echo   - ssl\cert.pem (证书)
        echo   - ssl\key.pem (私钥)
        echo.
        echo 证书信息:
        openssl x509 -in ssl\cert.pem -text -noout | findstr "Subject:"
        echo.
        echo 使用方法:
        echo   1. 启动HTTPS后端: python start_https_server.py
        echo   2. 启动HTTPS前端: cd frontend && npm run dev
        echo.
        echo 访问地址:
        echo   - 后端API: https://localhost:9876
        echo   - 前端应用: https://localhost:3000
        echo   - API文档: https://localhost:9876/api/docs
        echo.
        echo [注意] 这是自签名证书，浏览器会显示安全警告。
        echo        在开发环境中可以安全忽略。
    ) else (
        echo [ERROR] 私钥生成失败！
    )
) else (
    echo [ERROR] 证书生成失败！
)

pause