# TradingAgents-CN 双版本启动脚本

Write-Host "🚀 启动TradingAgents-CN 双版本应用..." -ForegroundColor Green
Write-Host ""

# 激活虚拟环境
& ".\env\Scripts\Activate.ps1"

# 检查项目是否已安装
try {
    python -c "import tradingagents" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "📦 安装项目到虚拟环境..." -ForegroundColor Yellow
        pip install -e .
    }
} catch {
    Write-Host "📦 安装项目到虚拟环境..." -ForegroundColor Yellow
    pip install -e .
}

Write-Host "🖥️  启动Web版 (端口 8501)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "python start_web.py" -WindowStyle Normal

Start-Sleep -Seconds 2

Write-Host "📱 启动手机版 (端口 8502)..." -ForegroundColor Magenta  
Start-Process powershell -ArgumentList "-NoExit", "-Command", "python start_mobile.py" -WindowStyle Normal

Write-Host ""
Write-Host "✅ 两个版本已启动！" -ForegroundColor Green
Write-Host "🖥️  Web版: http://localhost:8501" -ForegroundColor Cyan
Write-Host "📱 手机版: http://localhost:8502" -ForegroundColor Magenta
Write-Host ""
Write-Host "💡 提示: 两个版本会在新窗口中运行" -ForegroundColor Yellow
Write-Host "⏹️  关闭对应窗口即可停止应用" -ForegroundColor Yellow
Write-Host ""

Write-Host "按任意键退出..." -ForegroundColor Yellow
Read-Host