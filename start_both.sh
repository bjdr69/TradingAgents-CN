#!/bin/bash
# TradingAgents-CN 双版本启动脚本

echo "🚀 启动TradingAgents-CN 双版本应用..."
echo

# 激活虚拟环境
source env/bin/activate

# 检查项目是否已安装
if ! python -c "import tradingagents" 2>/dev/null; then
    echo "📦 安装项目到虚拟环境..."
    pip install -e .
fi

echo "🖥️  启动Web版 (端口 8501)..."
gnome-terminal --title="TradingAgents-CN Web版" -- bash -c "python start_web.py; exec bash" 2>/dev/null || \
xterm -title "TradingAgents-CN Web版" -e "python start_web.py" 2>/dev/null || \
osascript -e 'tell app "Terminal" to do script "cd '$(pwd)' && python start_web.py"' 2>/dev/null || \
echo "⚠️  请手动在新终端运行: python start_web.py"

sleep 2

echo "📱 启动手机版 (端口 8502)..."
gnome-terminal --title="TradingAgents-CN 手机版" -- bash -c "python start_mobile.py; exec bash" 2>/dev/null || \
xterm -title "TradingAgents-CN 手机版" -e "python start_mobile.py" 2>/dev/null || \
osascript -e 'tell app "Terminal" to do script "cd '$(pwd)' && python start_mobile.py"' 2>/dev/null || \
echo "⚠️  请手动在新终端运行: python start_mobile.py"

echo
echo "✅ 两个版本已启动！"
echo "🖥️  Web版: http://localhost:8501"
echo "📱 手机版: http://localhost:8502"
echo
echo "💡 提示: 两个版本会在新终端窗口中运行"
echo "⏹️  关闭对应终端即可停止应用"
echo

echo "按任意键退出..."
read -n 1