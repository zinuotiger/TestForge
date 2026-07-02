@echo off
REM 一键启动HTTPS环境的Windows批处理脚本
echo ========================================
echo   启动TestForge HTTPS环境
echo ========================================

REM 检查SSL证书
if not exist "ssl\cert.pem" (
    echo [ERROR] SSL证书不存在！
    echo 请先运行 generate_ssl_cert.bat 生成证书
    pause
    exit /b 1
)

if not exist "ssl\key.pem" (
    echo [ERROR] SSL私钥不存在！
    echo 请先运行 generate_ssl_cert.bat 生成证书
    pause
    exit /b 1
)

echo [OK] SSL证书检查通过
echo.

REM 启动HTTPS后端服务器
echo 启动HTTPS后端服务器...
start "TestForge HTTPS Backend" cmd /k "python start_https_server.py"
timeout /t 5 /nobreak >nul

echo [OK] 后端服务器已启动
echo.

REM 启动HTTPS前端服务器
echo 启动HTTPS前端服务器...
cd frontend
start "TestForge HTTPS Frontend" cmd /k "npm run dev"
cd ..

echo.
echo ========================================
echo   HTTPS环境启动完成！
echo ========================================
echo.
echo 访问地址:
echo   前端应用: https://localhost:3000
echo   后端API:  https://localhost:9876
echo   API文档:  https://localhost:9876/api/docs
echo.
echo 重要提示:
echo   1. 这是自签名证书，浏览器会显示安全警告
echo   2. 点击"高级" -> "继续前往localhost(不安全)"即可访问
echo   3. 开发环境可安全使用，生产环境请使用正式证书
echo.
echo 按任意键退出此窗口...
pause >nul