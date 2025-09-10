@echo off
echo 🚀 启动TradingAgents-CN 双版本应用...
echo.

REM 激活虚拟环境
call env\Scripts\activate.bat

REM 检查项目是否已安装
python -c "import tradingagents" 2>nul
if errorlevel 1 (
    echo 📦 安装项目到虚拟环境...
    pip install -e .
)

echo 🖥️  启动Web版 (端口 8501)...
start "TradingAgents-CN Web版" cmd /k "python start_web.py"

echo 📱 启动手机版 (端口 8502)...
start "TradingAgents-CN 手机版" cmd /k "python start_mobile.py"

echo.
echo ✅ 两个版本已启动！
echo 🖥️  Web版: http://localhost:8501
echo 📱 手机版: http://localhost:8502
echo.
echo 💡 提示: 两个版本会在新窗口中运行
echo ⏹️  关闭对应窗口即可停止应用
echo.

pause