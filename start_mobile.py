#!/usr/bin/env python3
"""
TradingAgents-CN 手机版启动脚本
专为移动设备优化的股票分析界面启动器
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    """主函数"""
    print("📱 TradingAgents-CN 手机版启动器")
    print("=" * 50)
    
    # 获取项目根目录
    project_root = Path(__file__).parent
    mobile_app_file = project_root / "mobile_app.py"
    
    # 检查文件是否存在
    if not mobile_app_file.exists():
        print(f"❌ 找不到手机版应用文件: {mobile_app_file}")
        return
    
    # 检查虚拟环境
    in_venv = (
        hasattr(sys, 'real_prefix') or 
        (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
    )
    
    if not in_venv:
        print("⚠️ 建议在虚拟环境中运行:")
        print("   Windows: .\\env\\Scripts\\activate")
        print("   Linux/macOS: source env/bin/activate")
        print()
    
    # 检查streamlit是否安装
    try:
        import streamlit
        print("✅ Streamlit已安装")
    except ImportError:
        print("❌ Streamlit未安装，正在安装...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "streamlit", "plotly"], check=True)
            print("✅ Streamlit安装成功")
        except subprocess.CalledProcessError:
            print("❌ Streamlit安装失败，请手动安装: pip install streamlit plotly")
            return
    
    # 设置环境变量，添加项目根目录到Python路径
    env = os.environ.copy()
    current_path = env.get('PYTHONPATH', '')
    if current_path:
        env['PYTHONPATH'] = f"{project_root}{os.pathsep}{current_path}"
    else:
        env['PYTHONPATH'] = str(project_root)
    
    # 构建启动命令 - 使用8502端口避免与Web版冲突
    # 检查是否需要仅监听localhost
    localhost_only = "--localhost" in sys.argv or "--local" in sys.argv
    server_address = "localhost" if localhost_only else "0.0.0.0"
    
    cmd = [
        sys.executable, "-m", "streamlit", "run",
        str(mobile_app_file),
        "--server.port", "8502",
        "--server.address", server_address,
        "--browser.gatherUsageStats", "false",
        "--server.fileWatcherType", "none",
        "--server.runOnSave", "false"
    ]
    
    print("📱 启动手机版应用...")
    if localhost_only:
        print("🌐 仅监听本机: http://localhost:8502")
        print("💡 使用默认启动可允许手机访问")
    else:
        print("🌐 监听所有地址: http://0.0.0.0:8502")
        print("📱 手机访问: http://[您的IP地址]:8502")
        print("💻 本机访问: http://localhost:8502")
        print("💡 使用 --localhost 参数可仅监听本机")
    print("💡 Web版本运行在 http://localhost:8501")
    print("⏹️  按 Ctrl+C 停止应用")
    print("=" * 50)
    
    try:
        # 启动应用，传递修改后的环境变量
        subprocess.run(cmd, cwd=project_root, env=env)
    except KeyboardInterrupt:
        print("\n⏹️ 手机版应用已停止")
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        print("\n💡 如果遇到模块导入问题，请尝试:")
        print("   1. 激活虚拟环境")
        print("   2. 运行: pip install -e .")
        print("   3. 再次启动手机版应用")

if __name__ == "__main__":
    main()