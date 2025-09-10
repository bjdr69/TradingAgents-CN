
import sys
from pathlib import Path
import os

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tradingagents.dataflows.optimized_china_data import get_optimized_china_data_provider

if __name__ == "__main__":
    # 设置环境变量，指定使用akshare
    os.environ['DEFAULT_CHINA_DATA_SOURCE'] = 'akshare'
    
    # 获取数据提供者
    provider = get_optimized_china_data_provider()
    provider.cache.clear_old_cache(max_age_days=0)
    
    # 获取基本面数据
    fundamentals = provider.get_fundamentals_data("600036")
    
    # 打印结果
    print(fundamentals)
