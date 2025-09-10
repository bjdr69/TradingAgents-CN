#!/usr/bin/env python3
"""
TradingAgents-CN 手机版UI
专为移动设备优化的股票分析界面，支持后台任务处理
"""

import streamlit as st
import os
import sys
import json
import uuid
import threading
import time
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 加载环境变量
load_dotenv(project_root / ".env", override=True)

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('mobile')

# 导入核心功能
from web.utils.analysis_runner import run_stock_analysis, validate_analysis_params
from web.utils.smart_session_manager import get_persistent_analysis_id, set_persistent_analysis_id
from web.utils.report_exporter import render_export_buttons

# 导入模型配置功能
from web.utils.persistence import load_model_selection, save_model_selection

# 任务状态管理
class MobileTaskManager:
    """移动端任务管理器 - 支持文件持久化"""

    def __init__(self):
        self.tasks_file = project_root / "temp" / "mobile_tasks.json"
        self.progress_file = project_root / "temp" / "mobile_progress.json"
        self.task_lock = threading.Lock()
        self.progress_lock = threading.Lock()
        
        # 确保临时目录存在
        self.tasks_file.parent.mkdir(exist_ok=True)
        
        # 加载已存在的任务
        self._load_tasks()
        self._load_progress()
        
    def _load_tasks(self):
        """从文件加载任务"""
        try:
            if self.tasks_file.exists():
                with open(self.tasks_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 转换时间字符串回datetime对象
                    for task_id, task in data.items():
                        if 'created_at' in task and isinstance(task['created_at'], str):
                            task['created_at'] = datetime.fromisoformat(task['created_at'])
                        if 'updated_at' in task and isinstance(task['updated_at'], str):
                            task['updated_at'] = datetime.fromisoformat(task['updated_at'])
                        if 'completed_at' in task and task['completed_at'] and isinstance(task['completed_at'], str):
                            task['completed_at'] = datetime.fromisoformat(task['completed_at'])
                    self.tasks = data
                    logger.info(f"📱 [持久化] 加载了 {len(self.tasks)} 个任务")
            else:
                self.tasks = {}
        except Exception as e:
            logger.error(f"❌ [持久化] 加载任务失败: {e}")
            self.tasks = {}
    
    def _save_tasks(self):
        """保存任务到文件"""
        try:
            # 转换datetime对象为字符串以便JSON序列化
            serializable_tasks = {}
            for task_id, task in self.tasks.items():
                serializable_task = self._clean_task_for_serialization(task.copy())
                serializable_tasks[task_id] = serializable_task
            
            with open(self.tasks_file, 'w', encoding='utf-8') as f:
                json.dump(serializable_tasks, f, ensure_ascii=False, indent=2)
            logger.debug(f"📱 [持久化] 保存了 {len(self.tasks)} 个任务")
        except Exception as e:
            logger.error(f"❌ [持久化] 保存任务失败: {e}")
    
    def _clean_task_for_serialization(self, task):
        """清理任务对象以便JSON序列化"""
        cleaned_task = {}
        for key, value in task.items():
            try:
                if key in ['created_at', 'updated_at', 'completed_at'] and isinstance(value, datetime):
                    cleaned_task[key] = value.isoformat()
                elif key == 'result' and isinstance(value, dict):
                    # 特别处理result字段，清理其中的复杂对象
                    cleaned_task[key] = self._clean_result_for_serialization(value)
                elif isinstance(value, (str, int, float, bool, list, dict, type(None))):
                    cleaned_task[key] = value
                else:
                    # 对于其他类型，转换为字符串
                    cleaned_task[key] = str(value)
            except Exception as e:
                logger.warning(f"⚠️ [清理] 无法序列化任务字段 {key}: {e}")
                cleaned_task[key] = f"<序列化失败: {type(value).__name__}>"
        
        return cleaned_task
    
    def _clean_result_for_serialization(self, result):
        """清理分析结果以便JSON序列化"""
        return self._deep_clean_for_json(result)
    
    def _deep_clean_for_json(self, obj):
        """深度清理对象以便JSON序列化"""
        if obj is None:
            return None
        elif isinstance(obj, (str, int, float, bool)):
            return obj
        elif isinstance(obj, list):
            return [self._deep_clean_for_json(item) for item in obj]
        elif isinstance(obj, dict):
            cleaned = {}
            for key, value in obj.items():
                try:
                    cleaned[str(key)] = self._deep_clean_for_json(value)
                except Exception as e:
                    logger.warning(f"⚠️ [深度清理] 字段 {key} 清理失败: {e}")
                    cleaned[str(key)] = f"<清理失败: {type(value).__name__}>"
            return cleaned
        else:
            # 对于其他类型，尝试转换为字符串
            try:
                # 测试是否可以JSON序列化
                json.dumps(obj)
                return obj
            except (TypeError, ValueError):
                return str(obj)
    
    def _load_progress(self):
        """从文件加载进度缓存"""
        try:
            if self.progress_file.exists():
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    self.progress_cache = json.load(f)
                    logger.debug(f"📊 [持久化] 加载了 {len(self.progress_cache)} 个进度记录")
            else:
                self.progress_cache = {}
        except Exception as e:
            logger.error(f"❌ [持久化] 加载进度失败: {e}")
            self.progress_cache = {}
    
    def _save_progress(self):
        """保存进度缓存到文件"""
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(self.progress_cache, f, ensure_ascii=False, indent=2)
            logger.debug(f"📊 [持久化] 保存了 {len(self.progress_cache)} 个进度记录")
        except Exception as e:
            logger.error(f"❌ [持久化] 保存进度失败: {e}")
    
    def create_task(self, analysis_params):
        """创建新任务"""
        task_id = str(uuid.uuid4())
        task = {
            'id': task_id,
            'params': analysis_params,
            'status': 'pending',  # pending, running, completed, failed
            'progress': 0,
            'result': None,
            'error': None,
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
            'completed_at': None
        }
        
        with self.task_lock:
            self.tasks[task_id] = task
            self._save_tasks()  # 立即保存到文件
        
        logger.info(f"📱 [移动端] 创建新任务: {task_id}")
        return task_id
    
    def update_task_status(self, task_id, status, progress=0, result=None, error=None):
        """更新任务状态"""
        with self.task_lock:
            if task_id in self.tasks:
                self.tasks[task_id]['status'] = status
                self.tasks[task_id]['progress'] = progress
                if result is not None:
                    self.tasks[task_id]['result'] = result
                if error is not None:
                    self.tasks[task_id]['error'] = error
                self.tasks[task_id]['updated_at'] = datetime.now()
                if status == 'completed':
                    self.tasks[task_id]['completed_at'] = datetime.now()
                
                self._save_tasks()  # 立即保存到文件
                logger.debug(f"📱 [移动端] 更新任务 {task_id} 状态: {status}, 进度: {progress}%")
                return True
        logger.warning(f"📱 [移动端] 未找到任务 {task_id} 来更新状态")
        return False
    
    def get_task(self, task_id):
        """获取任务信息"""
        with self.task_lock:
            return self.tasks.get(task_id)
    
    def get_all_tasks(self):
        """获取所有任务"""
        with self.task_lock:
            return list(self.tasks.values())

    def delete_task(self, task_id):
        """删除任务"""
        with self.task_lock:
            if task_id in self.tasks:
                del self.tasks[task_id]
                self._save_tasks()  # 立即保存到文件
                logger.info(f"📱 [移动端] 任务已删除: {task_id}")
                return True
        logger.warning(f"📱 [移动端] 未找到任务 {task_id} 来删除")
        return False

    def stop_task(self, task_id):
        """停止任务（标记为失败）"""
        with self.task_lock:
            if task_id in self.tasks:
                self.tasks[task_id]['status'] = 'failed'
                self.tasks[task_id]['error'] = '用户手动停止分析'
                self.tasks[task_id]['updated_at'] = datetime.now()
                self._save_tasks()  # 立即保存到文件
                logger.info(f"📱 [移动端] 任务已停止: {task_id}")
                return True
        logger.warning(f"📱 [移动端] 未找到任务 {task_id} 来停止")
        return False

    def thread_safe_progress_update(self, task_id, progress):
        """线程安全的进度更新"""
        with self.progress_lock:
            self.progress_cache[task_id] = {
                'progress': progress,
                'timestamp': datetime.now().isoformat()
            }
            self._save_progress()  # 立即保存进度到文件
            logger.debug(f"📊 [进度缓存] 任务 {task_id} 进度更新: {progress}%")
        
        # 同时更新主任务状态
        self.update_task_status(task_id, 'running', progress)

    def thread_safe_callback_function(self, message, step=None, total_steps=None):
        """创建线程安全的回调函数"""
        def callback(task_id):
            try:
                if step is None:
                    progress = 10  # 初始化进度
                elif total_steps:
                    progress = (step / total_steps * 100)
                else:
                    progress = min(100, step)

                # 确保进度在0-100范围内
                progress = max(0, min(100, progress))

                self.thread_safe_progress_update(task_id, progress)
                logger.debug(f"📊 [回调] 任务进度更新: {task_id} -> {progress}% (消息: {message})")

            except Exception as e:
                logger.error(f"❌ [回调] 进度更新失败: {e}")

        return callback

    def sync_progress_from_cache(self):
        """从缓存同步进度到主任务状态"""
        with self.progress_lock:
            for task_id, progress_data in self.progress_cache.items():
                if isinstance(progress_data, dict):
                    progress = progress_data.get('progress', 0)
                    timestamp = progress_data.get('timestamp')
                else:
                    progress = progress_data  # 兼容旧格式
                    timestamp = None
                
                with self.task_lock:
                    if task_id in self.tasks and self.tasks[task_id]['status'] == 'running':
                        # 更新进度
                        self.tasks[task_id]['progress'] = progress
                        
                        # 更新时间戳
                        if timestamp:
                            try:
                                self.tasks[task_id]['updated_at'] = datetime.fromisoformat(timestamp)
                            except:
                                self.tasks[task_id]['updated_at'] = datetime.now()
                        else:
                            self.tasks[task_id]['updated_at'] = datetime.now()
                        
                        logger.debug(f"📊 [进度同步] 任务 {task_id} 进度: {progress}%, 时间: {self.tasks[task_id]['updated_at']}")
        
        # 保存同步后的状态
        self._save_tasks()
    
    def cleanup_old_tasks(self, hours=24):
        """清理旧任务"""
        current_time = datetime.now()
        tasks_to_remove = []
        
        with self.task_lock:
            for task_id, task in self.tasks.items():
                if task['status'] in ['completed', 'failed']:
                    if task.get('completed_at'):
                        time_diff = current_time - task['completed_at']
                        if time_diff.total_seconds() > hours * 3600:
                            tasks_to_remove.append(task_id)
            
            for task_id in tasks_to_remove:
                del self.tasks[task_id]
                if task_id in self.progress_cache:
                    del self.progress_cache[task_id]
            
            if tasks_to_remove:
                self._save_tasks()
                self._save_progress()
                logger.info(f"📱 [清理] 清理了 {len(tasks_to_remove)} 个过期任务")

# 全局任务管理器实例
_global_task_manager = None



def get_task_manager():
    """获取全局任务管理器实例"""
    global _global_task_manager
    if _global_task_manager is None:
        _global_task_manager = MobileTaskManager()
        logger.info("📱 [移动端] 创建全局任务管理器实例")
    return _global_task_manager

def initialize_model_config():
    """初始化模型配置到session state"""
    if 'llm_provider' not in st.session_state:
        saved_config = load_model_selection()
        st.session_state.llm_provider = saved_config.get('provider', 'dashscope')
        st.session_state.model_category = saved_config.get('category', 'openai')
        st.session_state.llm_model = saved_config.get('model', '')
        st.session_state.memory_provider = saved_config.get('memory_provider')
        st.session_state.memory_model = saved_config.get('memory_model')
        st.session_state.enable_memory = saved_config.get('enable_memory', True) # 默认启用记忆功能
        logger.info("🔧 [Mobile] 模型配置已初始化")


def run_analysis_in_background(task_id, analysis_params, model_config):
    """在后台运行分析任务"""
    try:
        # 获取任务管理器实例
        task_mgr = get_task_manager()
        
        # 更新任务状态为运行中
        task_mgr.update_task_status(task_id, 'running', 10)

        logger.info(f"📱 [移动端] 开始后台分析任务: {task_id}")
        logger.debug(f"📱 [移动端] 分析参数: {analysis_params}")

        # 使用传入的模型配置（避免在后台线程中访问session_state）
        llm_provider = model_config.get('llm_provider', 'dashscope')
        llm_model = model_config.get('llm_model', 'qwen-plus')
        memory_provider = model_config.get('memory_provider', 'dashscope')
        memory_model = model_config.get('memory_model', '')

        logger.info(f"📱 [移动端] 模型配置: provider={llm_provider}, model={llm_model}, memory_provider={memory_provider}, memory_model={memory_model}")

        # 创建进度回调函数
        progress_counter = {'count': 0}  # 用于跟踪回调次数
        
        def progress_callback(message, step=None, total_steps=None):
            """进度回调函数"""
            try:
                progress_counter['count'] += 1
                
                # 根据步骤计算进度
                if step is None:
                    # 基于回调次数估算进度
                    progress = min(20 + progress_counter['count'] * 5, 90)
                elif total_steps and total_steps > 0:
                    # 根据step和total_steps计算进度 (20%-90%)
                    progress = 20 + (step / total_steps * 70)
                else:
                    # 如果没有total_steps，直接使用step作为进度
                    progress = max(20, min(90, step))

                # 确保进度在合理范围内
                progress = max(20, min(90, int(progress)))
                
                # 特殊处理：如果消息包含"完成"相关词汇，设置为90%
                if any(keyword in message for keyword in ["完成", "成功", "整理结果", "记录使用"]):
                    progress = 90

                # 更新任务进度 - 使用线程安全的方法
                task_mgr.thread_safe_progress_update(task_id, progress)
                logger.info(f"📊 [进度回调] {message} - 进度: {progress}% (第{progress_counter['count']}次回调)")

            except Exception as e:
                logger.error(f"❌ [进度回调] 更新失败: {e}")

        result = run_stock_analysis(
            stock_symbol=analysis_params['stock_symbol'],
            market_type=analysis_params['market_type'],
            analysis_date=analysis_params.get('analysis_date'),
            research_depth=analysis_params.get('research_depth', 3),
            analysts=analysis_params.get('selected_analysts', ['market', 'fundamentals']),
            llm_provider=llm_provider,
            llm_model=llm_model,
            memory_provider=memory_provider,
            memory_model=memory_model,
            progress_callback=progress_callback
        )

        # 更新进度到100%
        task_mgr.thread_safe_progress_update(task_id, 100)
        
        # 结果会在update_task_status中自动清理
        
        # 更新任务状态为完成
        task_mgr.update_task_status(task_id, 'completed', 100, result)
        logger.info(f"✅ [移动端] 分析任务完成: {task_id}")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ [移动端] 分析任务失败: {task_id}, 错误: {error_msg}", exc_info=True)
        
        # 确保错误信息被正确保存
        task_mgr.update_task_status(task_id, 'failed', 0, None, error_msg)
        
        # 额外日志确认状态更新
        logger.info(f"📱 [移动端] 任务状态已更新为失败: {task_id}")



def render_mobile_header():
    """渲染移动端头部"""
    st.markdown("""
    <div style="text-align: center; padding: 1rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                color: white; border-radius: 10px; margin-bottom: 1rem;">
        <h1 style="margin: 0; font-size: 1.5rem;">📱 TradingAgents-CN</h1>
        <p style="margin: 0.2rem 0 0 0; font-size: 0.9rem; opacity: 0.9;">移动股票分析平台</p>
    </div>
    """, unsafe_allow_html=True)

def render_mobile_analysis_form():
    """渲染移动端分析表单"""
    st.subheader("📋 新建分析")
    
    # 获取缓存的表单配置（确保不为None）
    cached_config = st.session_state.get('mobile_form_config') or {}

    with st.form("mobile_analysis_form"):
        # 市场选择（使用缓存的值）
        market_options = ["美股", "A股", "港股"]
        cached_market = cached_config.get('market_type', 'A股') if cached_config else 'A股'
        try:
            market_index = market_options.index(cached_market)
        except (ValueError, TypeError):
            market_index = 1  # 默认A股

        market_type = st.selectbox(
            "选择市场 🌍",
            options=market_options,
            index=market_index,
            help="选择要分析的股票市场"
        )

        # 根据市场类型显示不同的输入提示
        cached_stock = cached_config.get('stock_symbol', '') if cached_config else ''
        
        col1, col2 = st.columns(2)
        
        with col1:
            if market_type == "美股":
                stock_symbol = st.text_input(
                    "股票代码 📈",
                    value=cached_stock if (cached_config and cached_config.get('market_type') == '美股') else '',
                    placeholder="输入美股代码，如 AAPL, TSLA, MSFT",
                    help="输入要分析的美股代码，输入完成后请按回车键确认",
                    key="mobile_us_stock_input"
                ).upper().strip()

            elif market_type == "港股":
                stock_symbol = st.text_input(
                    "股票代码 📈",
                    value=cached_stock if (cached_config and cached_config.get('market_type') == '港股') else '',
                    placeholder="输入港股代码，如 0700.HK, 9988.HK, 3690.HK",
                    help="输入要分析的港股代码，如 0700.HK(腾讯控股), 9988.HK(阿里巴巴), 3690.HK(美团)，输入完成后请按回车键确认",
                    key="mobile_hk_stock_input"
                ).upper().strip()

            else:  # A股
                stock_symbol = st.text_input(
                    "股票代码 📈",
                    value=cached_stock if (cached_config and cached_config.get('market_type') == 'A股') else '',
                    placeholder="输入A股代码，如 000001, 600519",
                    help="输入要分析的A股代码，如 000001(平安银行), 600519(贵州茅台)，输入完成后请按回车键确认",
                    key="mobile_cn_stock_input"
                ).strip()
        
        # 显示股票代码输入状态提示
        if not stock_symbol:
            st.info("💡 请在上方输入股票代码，输入完成后按回车键确认")
        else:
            st.success(f"✅ 已输入股票代码: {stock_symbol}")
            
        with col2:
            # 分析日期 (可选，默认当日)
            cached_date_str = cached_config.get('analysis_date')
            if cached_date_str:
                try:
                    # 尝试解析缓存的日期字符串
                    cached_date = datetime.fromisoformat(cached_date_str).date()
                except ValueError:
                    # 如果解析失败，使用今天
                    cached_date = datetime.now().date()
            else:
                cached_date = datetime.now().date()
                
            analysis_date = st.date_input(
                "分析日期 📅 (可选)",
                value=cached_date,
                help="选择分析的基准日期，默认为当日"
            )
        
        # 研究深度（使用缓存的值）
        # 将文本选项映射到数字深度
        depth_mapping = {"快速": 1, "基础": 2, "标准": 3, "深度": 4, "全面": 5}
        reverse_depth_mapping = {v: k for k, v in depth_mapping.items()}
        
        cached_depth_text = cached_config.get('research_depth_text', "标准") if cached_config else "标准"
        # 确保缓存的值是有效的选项
        if cached_depth_text not in depth_mapping:
            cached_depth_text = "标准"
        cached_depth = depth_mapping[cached_depth_text]
        
        research_depth_text = st.select_slider(
            "研究深度 🔍",
            options=["快速", "基础", "标准", "深度", "全面"],
            value=cached_depth_text,
            help="选择分析的深度级别，级别越高分析越详细但耗时更长"
        )
        # 转换为数字深度
        research_depth = depth_mapping[research_depth_text]

        # 分析师团队选择
        st.markdown("### 👥 选择分析师团队")
        
        # 获取缓存的分析师选择
        cached_analysts = cached_config.get('selected_analysts', ['market', 'fundamentals']) if cached_config else ['market', 'fundamentals']

        col1, col2 = st.columns(2)
        
        with col1:
            market_analyst = st.checkbox(
                "📈 市场分析师",
                value='market' in cached_analysts,
                help="专注于技术面分析、价格趋势、技术指标"
            )

            social_analyst = st.checkbox(
                "💭 社交媒体分析师",
                value='social' in cached_analysts,
                help="分析社交媒体情绪、投资者情绪指标"
            )

        with col2:
            news_analyst = st.checkbox(
                "📰 新闻分析师",
                value='news' in cached_analysts,
                help="分析相关新闻事件、市场动态影响"
            )

            fundamentals_analyst = st.checkbox(
                "💰 基本面分析师",
                value='fundamentals' in cached_analysts,
                help="分析财务数据、公司基本面、估值水平"
            )
        
        # 收集选中的分析师
        selected_analysts = []
        if market_analyst:
            selected_analysts.append("market")
        if social_analyst:
            selected_analysts.append("social")
        if news_analyst:
            selected_analysts.append("news")
        if fundamentals_analyst:
            selected_analysts.append("fundamentals")
        
        # 显示选择摘要
        if selected_analysts:
            st.success(f"已选择 {len(selected_analysts)} 个分析师")
        else:
            st.warning("请至少选择一个分析师")
        
        # 高级选项
        with st.expander("🔧 高级选项"):
            include_sentiment = st.checkbox(
                "包含情绪分析",
                value=cached_config.get('include_sentiment', True), # 默认启用
                help="是否包含市场情绪和投资者情绪分析"
            )
            
            include_risk_assessment = st.checkbox(
                "包含风险评估",
                value=cached_config.get('include_risk_assessment', True), # 默认启用
                help="是否包含详细的风险因素评估"
            )
            
            custom_prompt = st.text_area(
                "自定义分析要求",
                value=cached_config.get('custom_prompt', ''),
                placeholder="输入特定的分析要求或关注点...",
                help="可以输入特定的分析要求，AI会在分析中重点关注"
            )

        # 提交按钮
        submitted = st.form_submit_button(
            "🚀 开始分析",
            use_container_width=True,
            type="primary"
        )
        
        if submitted:
            if not stock_symbol:
                st.error("请输入股票代码")
                return None
            
            # 验证参数 (将 date 对象转换为字符串)
            validation_result = validate_analysis_params(
                stock_symbol=stock_symbol,
                analysis_date=analysis_date.isoformat(),  # 转换为字符串
                analysts=selected_analysts,
                research_depth=research_depth,
                market_type=market_type
            )
            is_valid, validation_errors = validation_result
            if not is_valid:
                for error in validation_errors:
                    st.error(error)
                return None
            
            # 创建分析参数
            analysis_params = {
                'stock_symbol': stock_symbol,
                'market_type': market_type,
                'analysis_date': analysis_date.isoformat(), # 存储为ISO格式字符串
                'research_depth': research_depth,
                'research_depth_text': research_depth_text, # 也存储文本形式以便恢复
                'selected_analysts': selected_analysts,
                'include_sentiment': include_sentiment, # 新增高级选项
                'include_risk_assessment': include_risk_assessment, # 新增高级选项
                'custom_prompt': custom_prompt, # 新增高级选项
                'created_at': datetime.now().isoformat()
            }
            
            # 保存表单配置到缓存
            st.session_state.mobile_form_config = analysis_params
            
            # 获取任务管理器并创建后台任务
            task_mgr = get_task_manager()
            task_id = task_mgr.create_task(analysis_params)
            
            # 准备模型配置（在主线程中获取，传递给后台线程）
            model_config = {
                'llm_provider': st.session_state.get('llm_provider', 'dashscope'),
                'llm_model': st.session_state.get('llm_model', 'qwen-plus'),
                'memory_provider': st.session_state.get('memory_provider', 'dashscope'),
                'memory_model': st.session_state.get('memory_model', ''),
                'enable_memory': st.session_state.get('enable_memory', True)
            }
            
            # 启动后台线程
            thread = threading.Thread(
                target=run_analysis_in_background,
                args=(task_id, analysis_params, model_config),
                daemon=True
            )
            thread.start()
            
            st.success("✅ 分析任务已开始，可在后台运行！")
            st.info("💡 提示：您可以切换到任务列表查看进度")
            
            # 自动切换到任务列表标签页
            st.session_state['active_tab'] = 1
            
            return task_id
    
    return None

def get_web_style_progress_info(progress, stock_symbol):
    """获取网页版样式的进度信息"""
    # 根据进度确定当前步骤和状态（参照网页版的分析步骤）
    if progress < 10:
        current_step_name = "准备阶段"
        current_step_description = "初始化分析引擎和数据源"
        last_message = "正在准备分析环境..."
    elif progress < 20:
        current_step_name = "数据获取"
        current_step_description = f"获取 {stock_symbol} 的基础数据和市场信息"
        last_message = "正在获取股票基础数据..."
    elif progress < 35:
        current_step_name = "技术分析"
        current_step_description = f"分析 {stock_symbol} 的技术指标和价格走势"
        last_message = "正在进行技术面分析..."
    elif progress < 50:
        current_step_name = "基本面分析"
        current_step_description = f"分析 {stock_symbol} 的财务状况和基本面指标"
        last_message = "正在分析公司基本面..."
    elif progress < 65:
        current_step_name = "市场情绪分析"
        current_step_description = f"分析 {stock_symbol} 的市场情绪和投资者行为"
        last_message = "正在分析市场情绪和新闻..."
    elif progress < 80:
        current_step_name = "综合评估"
        current_step_description = f"综合评估 {stock_symbol} 的投资价值和风险"
        last_message = "正在进行综合投资评估..."
    elif progress < 95:
        current_step_name = "投资建议生成"
        current_step_description = f"生成 {stock_symbol} 的具体投资建议和目标价位"
        last_message = "正在生成投资建议..."
    else:
        current_step_name = "分析完成"
        current_step_description = f"完成 {stock_symbol} 的全面投资分析"
        last_message = "投资分析报告已生成完成"
    
    return current_step_name, current_step_description, last_message

def get_web_style_status_message(progress, stock_symbol):
    """获取网页版样式的状态信息（显示已完成的分析内容）"""
    completed_tasks = []
    
    # 根据进度显示已完成的分析任务
    if progress >= 10:
        completed_tasks.append("✅ 数据获取完成")
    if progress >= 35:
        completed_tasks.append("✅ 技术分析完成")
    if progress >= 50:
        completed_tasks.append("✅ 基本面分析完成")
    if progress >= 65:
        completed_tasks.append("✅ 市场情绪分析完成")
    if progress >= 80:
        completed_tasks.append("✅ 综合评估完成")
    if progress >= 95:
        completed_tasks.append("✅ 投资建议生成完成")
    if progress >= 100:
        return f"🎉 {stock_symbol} 投资分析报告已完成"
    
    # 显示当前正在进行的任务
    if progress < 10:
        current_task = "正在初始化分析引擎..."
    elif progress < 20:
        current_task = f"正在获取 {stock_symbol} 基础数据..."
    elif progress < 35:
        current_task = f"正在分析 {stock_symbol} 技术指标..."
    elif progress < 50:
        current_task = f"正在分析 {stock_symbol} 基本面..."
    elif progress < 65:
        current_task = f"正在分析 {stock_symbol} 市场情绪..."
    elif progress < 80:
        current_task = f"正在进行 {stock_symbol} 综合评估..."
    elif progress < 95:
        current_task = f"正在生成 {stock_symbol} 投资建议..."
    else:
        current_task = f"正在完成 {stock_symbol} 分析报告..."
    
    # 组合状态信息
    if completed_tasks:
        # 显示最近完成的任务 + 当前任务
        latest_completed = completed_tasks[-1]
        return f"{latest_completed}，{current_task}"
    else:
        # 只显示当前任务
        return current_task

def render_task_status(task):
    """渲染任务状态"""
    status_colors = {
        'pending': '🟡',
        'running': '🔵',
        'completed': '🟢',
        'failed': '🔴'
    }
    
    status_texts = {
        'pending': '等待中',
        'running': '运行中',
        'completed': '已完成',
        'failed': '失败'
    }
    
    status_icon = status_colors.get(task['status'], '⚪')
    status_text = status_texts.get(task['status'], '未知')
    
    # 时间格式化
    created_time = task['created_at'].strftime('%H:%M:%S') if isinstance(task['created_at'], datetime) else task['created_at']
    
    # 获取最新进度 - 确保数据同步
    task_mgr = get_task_manager()
    task_mgr.sync_progress_from_cache()  # 强制同步进度缓存
    current_task = task_mgr.get_task(task['id'])
    if current_task:
        task = current_task  # 使用最新的任务状态
    
    # 运行中任务使用网页版样式的进度显示
    if task['status'] == 'running':
        # 获取任务信息
        stock_symbol = task['params']['stock_symbol']
        progress = task.get('progress', 0)
        
        # 计算时间信息
        created_at = task['created_at']
        updated_at = task.get('updated_at', created_at)
        
        if isinstance(created_at, datetime) and isinstance(updated_at, datetime):
            elapsed_seconds = (updated_at - created_at).total_seconds()
            
            # 估算总时间（基于当前进度）
            if progress > 0:
                estimated_total_seconds = (elapsed_seconds / progress) * 100
                remaining_seconds = max(estimated_total_seconds - elapsed_seconds, 0)
            else:
                estimated_total_seconds = 300  # 默认5分钟
                remaining_seconds = estimated_total_seconds
        else:
            elapsed_seconds = 0
            remaining_seconds = 300
        
        # 格式化时间显示
        def format_time(seconds):
            if seconds < 60:
                return f"{seconds:.1f}秒"
            elif seconds < 3600:
                minutes = seconds / 60
                return f"{minutes:.1f}分钟"
            else:
                hours = seconds / 3600
                return f"{hours:.1f}小时"
        
        # 获取网页版样式的进度信息
        current_step_name, current_step_description, last_message = get_web_style_progress_info(progress, stock_symbol)
        
        # 显示标题（参照网页版）
        st.markdown("### 📊 分析进度")
        
        # 显示当前步骤（参照网页版）
        st.write(f"**当前步骤**: {current_step_name}")
        
        # 显示三列指标（手机版优化 - 使用更紧凑的布局）
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("进度", f"{progress:.1f}%")
        
        with col2:
            st.metric("已用时间", format_time(elapsed_seconds))
        
        with col3:
            if progress >= 95:
                st.metric("预计剩余", "即将完成")
            else:
                st.metric("预计剩余", format_time(remaining_seconds))
        
        # 显示进度条（参照网页版）
        st.progress(min(progress / 100.0, 1.0))
        
        # 显示当前任务（显示分析类型名称）
        st.write(f"**当前任务**: {current_step_name}")
        
        # 显示当前状态（按网页版逻辑显示完成的分析内容）
        status_icon = "🔄" if progress < 100 else "✅"
        web_style_status = get_web_style_status_message(progress, stock_symbol)
        st.info(f"{status_icon} **当前状态**: {web_style_status}")
        
        # 显示刷新控制（参照网页版）
        col1, col2 = st.columns(2)
        with col1:
            refresh_key = f"refresh_{task['id'][:8]}"
            if st.button("🔄 刷新进度", key=refresh_key, use_container_width=True):
                st.rerun()
        
        with col2:
            auto_refresh_key = f"auto_refresh_{task['id'][:8]}"
            auto_refresh = st.checkbox("🔄 自动刷新", value=True, key=auto_refresh_key)
            if auto_refresh:
                time.sleep(3)
                st.rerun()
        
        # 停止分析按钮
        st.markdown("---")
        stop_key = f"stop_{task['id'][:8]}"
        if st.button("🛑 停止分析", key=stop_key, use_container_width=True, type="secondary"):
            task_mgr = get_task_manager()
            success = task_mgr.stop_task(task['id'])
            if success:
                st.warning("⏹️ 任务已停止")
            st.rerun()
        
        return  # 运行中任务直接返回，不显示展开器
    else:
        # 非运行中任务使用普通展开器
        with st.expander(f"{status_icon} {task['params']['stock_symbol']} - {status_text} ({created_time})", expanded=False):
            
            if task['status'] == 'completed':
                # 显示成功信息和结果
                st.success("✅ 分析完成！")
                
                # 显示简要结果
                result = task['result']
                if result and 'decision' in result:
                    decision = result['decision']
                    st.markdown(f"**投资建议**: {decision.get('action', 'N/A').upper()}")
                    st.markdown(f"**置信度**: {decision.get('confidence', 0) * 100:.1f}%")
                    st.markdown(f"**风险评分**: {decision.get('risk_score', 0) * 100:.1f}%")
                    
                    # 显示目标价位
                    target_price = decision.get('target_price')
                    if target_price is not None and isinstance(target_price, (int, float)) and target_price > 0:
                        # 根据市场类型确定货币符号
                        market_type = task['params'].get('market_type', 'A股')
                        if market_type == '美股':
                            currency_symbol = '$'
                        elif market_type == '港股':
                            currency_symbol = 'HK$'
                        else:  # A股
                            currency_symbol = '¥'
                        
                        st.markdown(f"**目标价位**: {currency_symbol}{target_price:.2f}")
                    else:
                        st.markdown("**目标价位**: 待分析")
                    
                    # 查看详细结果按钮
                    view_key = f"view_{task['id'][:8]}"
                    if st.button("📊 查看详细报告", key=view_key, use_container_width=True):
                        st.session_state['view_task_id'] = task['id']
                        st.rerun()
                
                    # 删除任务按钮
                    delete_key = f"delete_completed_{task['id'][:8]}"
                    if st.button("🗑️ 删除任务", key=delete_key, use_container_width=True):
                        task_mgr = get_task_manager()
                        success = task_mgr.delete_task(task['id'])
                        if success:
                            st.success("✅ 任务已删除")
                            time.sleep(1)  # 短暂延迟让用户看到反馈
                        else:
                            st.error("❌ 删除失败")
                        st.rerun()

            elif task['status'] == 'failed':
                # 显示错误信息
                st.error(f"❌ 分析失败: {task['error']}")
                col_retry, col_delete = st.columns(2)
                with col_retry:
                    retry_key = f"retry_{task['id'][:8]}"
                    if st.button("🔄 重试", key=retry_key, use_container_width=True):
                        # 重新创建任务
                        task_mgr = get_task_manager()
                        new_task_id = task_mgr.create_task(task['params'])
                        
                        # 获取当前模型配置
                        model_config = {
                            'llm_provider': st.session_state.get('llm_provider', 'dashscope'),
                            'llm_model': st.session_state.get('llm_model', 'qwen-plus'),
                            'memory_provider': st.session_state.get('memory_provider', 'dashscope'),
                            'memory_model': st.session_state.get('memory_model', ''),
                            'enable_memory': st.session_state.get('enable_memory', True)
                        }
                        
                        thread = threading.Thread(
                            target=run_analysis_in_background,
                            args=(new_task_id, task['params'], model_config),
                            daemon=True
                        )
                        thread.start()
                        st.success("✅ 重试任务已创建")
                        st.rerun()
                with col_delete:
                    delete_key = f"delete_failed_{task['id'][:8]}"
                    if st.button("🗑️ 删除任务", key=delete_key, use_container_width=True):
                        task_mgr = get_task_manager()
                        success = task_mgr.delete_task(task['id'])
                        if success:
                            st.success("✅ 任务已删除")
                            time.sleep(1)  # 短暂延迟让用户看到反馈
                        else:
                            st.error("❌ 删除失败")
                        st.rerun()

def render_task_list():
    """渲染任务列表"""
    task_mgr = get_task_manager()
    
    # 在渲染前强制同步进度数据
    task_mgr.sync_progress_from_cache()
    
    tasks = task_mgr.get_all_tasks()
    
    if not tasks:
        st.info("📋 暂无分析任务")
        return
    
    # 按时间倒序排序
    tasks.sort(key=lambda x: x['created_at'], reverse=True)
    
    # 显示任务统计 - 手机版优化布局，使用更紧凑的显示
    status_counts = {}
    for task in tasks:
        status = task['status']
        status_counts[status] = status_counts.get(status, 0) + 1
    
    # 使用紧凑的一行显示，避免折叠
    st.markdown(f"""
    <div style="display: flex; justify-content: space-around; background-color: #f8f9fa; padding: 0.5rem; border-radius: 8px; margin: 0.5rem 0;">
        <div style="text-align: center;">
            <div style="font-size: 1.2rem; font-weight: bold; color: #333;">{len(tasks)}</div>
            <div style="font-size: 0.8rem; color: #666;">总任务</div>
        </div>
        <div style="text-align: center;">
            <div style="font-size: 1.2rem; font-weight: bold; color: #007bff;">{status_counts.get('running', 0)}</div>
            <div style="font-size: 0.8rem; color: #666;">运行中</div>
        </div>
        <div style="text-align: center;">
            <div style="font-size: 1.2rem; font-weight: bold; color: #28a745;">{status_counts.get('completed', 0)}</div>
            <div style="font-size: 0.8rem; color: #666;">已完成</div>
        </div>
        <div style="text-align: center;">
            <div style="font-size: 1.2rem; font-weight: bold; color: #dc3545;">{status_counts.get('failed', 0)}</div>
            <div style="font-size: 0.8rem; color: #666;">失败</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 任务列表标题放在统计下方
    st.subheader("📋 任务列表")
    
    for task in tasks:
        render_task_status(task)

def render_detailed_result(task_id):
    """渲染详细分析结果"""
    task_mgr = get_task_manager()
    task = task_mgr.get_task(task_id)
    
    if not task or task['status'] != 'completed' or not task['result']:
        st.error("无法显示分析结果")
        # 添加返回按钮即使在错误情况下
        if st.button("⬅️ 返回任务列表", key="return_error", use_container_width=True):
            st.session_state.pop('view_task_id', None)
            st.rerun()
        return
    
    # 顶部返回按钮
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("⬅️ 返回", key="return_top", use_container_width=True):
            st.session_state.pop('view_task_id', None)
            st.rerun()
    with col2:
        st.subheader(f"📊 详细分析报告 - {task['params']['stock_symbol']}")
    
    result = task['result']
    state = result.get('state', {})
    
    # 显示任务完成时间
    if task['completed_at']:
        st.info(f"✅ **任务完成时间**: {task['completed_at'].strftime('%Y-%m-%d %H:%M:%S')}")

    # 投资决策
    st.markdown("### 🎯 投资决策")
    decision = result.get('decision', {})
    
    # 显示投资决策指标（包含目标价位）
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("建议操作", decision.get('action', 'N/A').upper())
    with col2:
        st.metric("置信度", f"{decision.get('confidence', 0) * 100:.1f}%")
    with col3:
        st.metric("风险评分", f"{decision.get('risk_score', 0) * 100:.1f}%")
    with col4:
        # 显示目标价位
        target_price = decision.get('target_price')
        if target_price is not None and isinstance(target_price, (int, float)) and target_price > 0:
            # 根据市场类型确定货币符号
            market_type = task['params'].get('market_type', 'A股')
            if market_type == '美股':
                currency_symbol = '$'
            elif market_type == '港股':
                currency_symbol = 'HK$'
            else:  # A股
                currency_symbol = '¥'
            
            st.metric("目标价位", f"{currency_symbol}{target_price:.2f}")
        else:
            st.metric("目标价位", "待分析")
    
    # 推理过程
    if 'reasoning' in decision:
        st.markdown("### 💭 推理过程")
        st.write(decision['reasoning'])
    
    # 详细分析报告
    st.markdown("### 📋 详细分析")
    
    # 定义分析模块
    analysis_modules = [
        {
            'key': 'market_report',
            'title': '📈 市场技术分析',
            'icon': '📈',
            'description': '技术指标、价格趋势、支撑阻力位分析'
        },
        {
            'key': 'fundamentals_report', 
            'title': '💰 基本面分析',
            'icon': '💰',
            'description': '财务数据、估值水平、盈利能力分析'
        },
        {
            'key': 'sentiment_report',
            'title': '💭 市场情绪分析', 
            'icon': '💭',
            'description': '投资者情绪、社交媒体情绪指标'
        },
        {
            'key': 'news_report',
            'title': '📰 新闻事件分析',
            'icon': '📰', 
            'description': '相关新闻事件、市场动态影响分析'
        },
        {
            'key': 'risk_assessment',
            'title': '⚠️ 风险评估',
            'icon': '⚠️',
            'description': '风险因素识别、风险等级评估'
        },
        {
            'key': 'investment_plan',
            'title': '📋 投资建议',
            'icon': '📋',
            'description': '具体投资策略、仓位管理建议'
        }
    ]
    
    # 创建标签页
    tabs = st.tabs([f"{module['icon']} {module['title']}" for module in analysis_modules])
    
    for i, (tab, module) in enumerate(zip(tabs, analysis_modules)):
        with tab:
            st.markdown(f"*{module['description']}*")
            
            if module['key'] in state and state[module['key']]:
                # 格式化显示内容
                content = state[module['key']]
                if isinstance(content, str):
                    st.markdown(content)
                elif isinstance(content, dict):
                    # 如果是字典，格式化显示
                    for key, value in content.items():
                        st.subheader(key.replace('_', ' ').title())
                        st.write(value)
                else:
                    st.write(content)
            else:
                st.info(f"暂无{module['title']}数据")
    
    # 风险提示
    st.markdown("### ⚠️ 重要风险提示")
    st.error("""
    **投资风险提示**:
    - **仅供参考**: 本分析结果仅供参考，不构成投资建议
    - **投资风险**: 股票投资有风险，可能导致本金损失
    - **理性决策**: 请结合多方信息进行理性投资决策
    - **专业咨询**: 重大投资决策建议咨询专业财务顾问
    - **自担风险**: 投资决策及其后果由投资者自行承担
    """)
    
    # 导出功能
    st.markdown("### 📤 导出报告")
    render_export_buttons(result)
    
    # 返回按钮
    if st.button("⬅️ 返回任务列表", key="return_to_list", use_container_width=True):
        st.session_state.pop('view_task_id', None)
        st.rerun()


def load_models_from_config():
    """从 config/models.json 加载模型配置"""
    config_path = project_root / "config" / "models.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def render_mobile_config():
    """渲染移动端配置界面"""
    st.subheader("⚙️ AI模型配置")
    
    try:
        models_config = load_models_from_config()
        
        # 如果配置为空，显示默认配置
        if not models_config:
            st.warning("⚠️ 未找到模型配置文件，使用默认配置")
            models_config = {
                "dashscope": {
                    "qwen-plus": {"description": "通义千问Plus"},
                    "qwen-max": {"description": "通义千问Max"}
                },
                "deepseek": {
                    "deepseek-chat": {"description": "DeepSeek Chat"},
                    "deepseek-coder": {"description": "DeepSeek Coder"}
                }
            }
    except Exception as e:
        st.error(f"❌ 加载配置失败: {e}")
        st.info("💡 使用默认配置")
        models_config = {
            "dashscope": {
                "qwen-plus": {"description": "通义千问Plus"},
                "qwen-max": {"description": "通义千问Max"}
            }
        }
    
    # 从session state获取当前配置
    provider_options = list(models_config.keys())
    current_provider = st.session_state.get('llm_provider', provider_options[0] if provider_options else 'dashscope')
    
    try:
        provider_index = provider_options.index(current_provider) if current_provider in provider_options else 0
    except (ValueError, IndexError):
        provider_index = 0
    
    llm_provider = st.selectbox(
        "LLM提供商",
        options=provider_options,
        index=provider_index,
        format_func=lambda x: {
            "dashscope": "🇨🇳 阿里百炼",
            "deepseek": "🚀 DeepSeek V3",
            "google": "🌟 Google AI",
            "openrouter": "🌐 OpenRouter",
            "硅基流动": "🔥 硅基流动"
        }.get(x, x),
        help="选择AI模型提供商",
        key="mobile_llm_provider_select"
    )
    
    # 简化的模型选择
    st.markdown("---")
    
    # 根据提供商显示不同的模型选项
    if llm_provider == "openrouter":
        # OpenRouter模型分类选择
        model_category = st.selectbox(
            "模型类别",
            options=["openai", "anthropic", "meta", "google", "custom"],
            index=["openai", "anthropic", "meta", "google", "custom"].index(st.session_state.model_category) if st.session_state.model_category in ["openai", "anthropic", "meta", "google", "custom"] else 0,
            format_func=lambda x: {
                "openai": "🤖 OpenAI (GPT系列)",
                "anthropic": "🧠 Anthropic (Claude系列)",
                "meta": "🦙 Meta (Llama系列)",
                "google": "🌟 Google (Gemini系列)",
                "custom": "✏️ 自定义模型"
            }[x],
            help="选择模型厂商类别或自定义输入",
            key="mobile_model_category_select"
        )
        
        # 根据厂商显示不同的模型
        if model_category == "openai":
            openai_models = models_config.get("openrouter", {}).get("openai", {})
            openai_options = list(openai_models.keys())
            
            current_index = 0
            if st.session_state.llm_model in openai_options:
                current_index = openai_options.index(st.session_state.llm_model)
                
            llm_model = st.selectbox(
                "选择OpenAI模型",
                options=openai_options,
                index=current_index,
                format_func=lambda x: openai_models.get(x, {}).get('description', x) if isinstance(openai_models.get(x), dict) else x,
                help="OpenAI公司的GPT和o系列模型，包含最新o4",
                key="mobile_openai_model_select"
            )
        elif model_category == "anthropic":
            anthropic_models = models_config.get("openrouter", {}).get("anthropic", {})
            anthropic_options = list(anthropic_models.keys())
            
            current_index = 0
            if st.session_state.llm_model in anthropic_options:
                current_index = anthropic_options.index(st.session_state.llm_model)
                
            llm_model = st.selectbox(
                "选择Anthropic模型",
                options=anthropic_options,
                index=current_index,
                format_func=lambda x: anthropic_models.get(x, {}).get('description', x) if isinstance(anthropic_models.get(x), dict) else x,
                help="Anthropic公司的Claude系列模型，包含最新Claude 4",
                key="mobile_anthropic_model_select"
            )
        elif model_category == "meta":
            meta_models = models_config.get("openrouter", {}).get("meta", {})
            meta_options = list(meta_models.keys())
            
            current_index = 0
            if st.session_state.llm_model in meta_options:
                current_index = meta_options.index(st.session_state.llm_model)
                
            llm_model = st.selectbox(
                "选择Meta模型",
                options=meta_options,
                index=current_index,
                format_func=lambda x: meta_models.get(x, {}).get('description', x) if isinstance(meta_models.get(x), dict) else x,
                help="Meta公司的Llama系列模型，包含最新Llama 4",
                key="mobile_meta_model_select"
            )
        elif model_category == "google":
            google_models = models_config.get("openrouter", {}).get("google", {})
            google_openrouter_options = list(google_models.keys())
            
            current_index = 0
            if st.session_state.llm_model in google_openrouter_options:
                current_index = google_openrouter_options.index(st.session_state.llm_model)
                
            llm_model = st.selectbox(
                "选择Google模型",
                options=google_openrouter_options,
                index=current_index,
                format_func=lambda x: google_models.get(x, {}).get('description', x) if isinstance(google_models.get(x), dict) else x,
                help="Google公司的Gemini/Gemma系列模型，包含最新Gemini 2.5",
                key="mobile_google_openrouter_model_select"
            )
        else:  # custom
            st.markdown("### ✏️ 自定义模型")
            
            # 自定义模型输入
            llm_model = st.text_input(
                "输入模型ID",
                value=st.session_state.llm_model if st.session_state.llm_model else "",
                placeholder="例如: anthropic/claude-3.7-sonnet",
                help="输入OpenRouter支持的任何模型ID",
                key="mobile_custom_model_input"
            )
            
            # 常用模型快速选择
            st.markdown("**快速选择常用模型:**")
            
            # 长条形按钮，每个占一行
            if st.button("🧠 Claude 3.7 Sonnet - 最新对话模型", key="mobile_claude37", use_container_width=True):
                model_id = "anthropic/claude-3.7-sonnet"
                st.session_state.llm_model = model_id
                save_model_selection(
                    llm_provider,
                    model_category,
                    model_id,
                    st.session_state.get('memory_provider'),
                    st.session_state.get('memory_model')
                )
                st.rerun()

            if st.button("💎 Claude 4 Opus - 顶级性能模型", key="mobile_claude4opus", use_container_width=True):
                model_id = "anthropic/claude-opus-4"
                st.session_state.llm_model = model_id
                save_model_selection(
                    llm_provider,
                    model_category,
                    model_id,
                    st.session_state.get('memory_provider'),
                    st.session_state.get('memory_model')
                )
                st.rerun()

            if st.button("🤖 GPT-4o - OpenAI旗舰模型", key="mobile_gpt4o", use_container_width=True):
                model_id = "openai/gpt-4o"
                st.session_state.llm_model = model_id
                save_model_selection(
                    llm_provider,
                    model_category,
                    model_id,
                    st.session_state.get('memory_provider'),
                    st.session_state.get('memory_model')
                )
                st.rerun()

            if st.button("🦙 Llama 4 Scout - Meta最新模型", key="mobile_llama4", use_container_width=True):
                model_id = "meta-llama/llama-4-scout"
                st.session_state.llm_model = model_id
                save_model_selection(
                    llm_provider,
                    model_category,
                    model_id,
                    st.session_state.get('memory_provider'),
                    st.session_state.get('memory_model')
                )
                st.rerun()

            if st.button("🌟 Gemini 2.5 Pro - Google多模态", key="mobile_gemini25", use_container_width=True):
                model_id = "google/gemini-2.5-pro"
                st.session_state.llm_model = model_id
                save_model_selection(
                    llm_provider,
                    model_category,
                    model_id,
                    st.session_state.get('memory_provider'),
                    st.session_state.get('memory_model')
                )
                st.rerun()
    else:  # 处理其他提供商
        provider_models = models_config.get(llm_provider, {})
        model_options = list(provider_models.keys())
        
        if not model_options:
            st.warning(f"⚠️ 未找到{llm_provider}的模型配置")
            model_options = ["default-model"]
        
        current_model = st.session_state.get('llm_model', model_options[0] if model_options else 'default-model')
        
        try:
            current_index = model_options.index(current_model) if current_model in model_options else 0
        except (ValueError, IndexError):
            current_index = 0
            
        llm_model = st.selectbox(
            f"选择{llm_provider}模型",
            options=model_options,
            index=current_index,
            format_func=lambda x: provider_models.get(x, {}).get('description', x) if isinstance(provider_models.get(x), dict) else x,
            help=f"选择用于分析的{llm_provider}模型",
            key=f"mobile_{llm_provider}_model_select"
        )
    
    # 高级设置
    st.markdown("---")
    st.markdown("### ⚙️ 高级设置")
    
    enable_memory = st.checkbox(
        "启用记忆功能",
        value=st.session_state.get('enable_memory', True),
        help="启用智能体记忆功能（可能影响性能）"
    )
    
    # 矢量模型配置（简化版）
    st.markdown("#### 🧠 矢量模型配置")
    
    memory_provider_options = list(models_config.keys())
    current_memory_provider = st.session_state.get('memory_provider', llm_provider)
    
    try:
        memory_provider_index = memory_provider_options.index(current_memory_provider) if current_memory_provider in memory_provider_options else 0
    except (ValueError, IndexError):
        memory_provider_index = 0
    
    memory_provider = st.selectbox(
        "矢量模型提供商",
        options=memory_provider_options,
        index=memory_provider_index,
        format_func=lambda x: {
            "dashscope": "🇨🇳 阿里百炼",
            "deepseek": "🚀 DeepSeek V3",
            "google": "🌟 Google AI",
            "openrouter": "🌐 OpenRouter",
            "硅基流动": "🔥 硅基流动"
        }.get(x, x),
        help="为矢量模型选择一个提供商"
    )
    
    # 自动选择默认矢量模型的函数
    def get_default_embedding_model(provider):
        """根据提供商返回默认的矢量模型"""
        defaults = {
            "dashscope": "text-embedding-v4",
            "deepseek": "text-embedding-v1", 
            "openai": "text-embedding-3-small",
            "google": "embedding-001",
            "openrouter": "text-embedding-3",
            "硅基流动": "BAAI/bge-m3",
        }
        return defaults.get(provider, "text-embedding-v4")
    
    # 检查是否需要自动更新矢量模型
    current_memory_model = st.session_state.get('memory_model', '')
    previous_memory_provider = st.session_state.get('previous_memory_provider', '')
    
    # 如果提供商发生变化，自动更新矢量模型
    if memory_provider != previous_memory_provider:
        default_model = get_default_embedding_model(memory_provider)
        st.session_state.memory_model = default_model
        st.session_state.previous_memory_provider = memory_provider
        current_memory_model = default_model
    
    memory_model = st.text_input(
        "矢量模型名称",
        value=current_memory_model,
        placeholder="例如: text-embedding-v4",
        help="输入矢量模型的具体名称，或使用自动选择的默认模型",
        key="mobile_memory_model_input"
    )
    
    # 显示当前自动选择的默认模型
    default_model = get_default_embedding_model(memory_provider)
    if memory_model != default_model:
        st.info(f"💡 {memory_provider} 的推荐模型: {default_model}")
        if st.button(f"🔄 使用推荐模型 ({default_model})", key="use_default_embedding"):
            st.session_state.memory_model = default_model
            st.rerun()
    
    # 更新session state
    st.session_state.llm_provider = llm_provider
    st.session_state.model_category = st.session_state.get('model_category', 'openai')  # 保持现有值或默认
    st.session_state.llm_model = llm_model
    st.session_state.enable_memory = enable_memory
    st.session_state.memory_provider = memory_provider
    st.session_state.memory_model = memory_model
    
    # 保存配置
    st.markdown("---")
    if st.button("💾 保存配置", key="save_config", use_container_width=True):
        try:
            save_model_selection(
                llm_provider,
                st.session_state.get('model_category', 'openai'),
                llm_model,
                memory_provider,
                memory_model
            )
            st.success("✅ 配置已保存")
        except Exception as e:
            st.error(f"❌ 保存配置失败: {e}")
    
    # 显示当前配置信息
    st.markdown("---")
    st.markdown("### 📋 当前配置")
    st.info(f"""
    **LLM提供商**: {llm_provider}
    **LLM模型**: {llm_model}
    **记忆功能**: {'启用' if enable_memory else '禁用'}
    **矢量提供商**: {memory_provider}
    **矢量模型**: {memory_model or '未设置'}
    """)

def render_mobile_css():
    """渲染移动端CSS样式"""
    st.markdown("""
    <style>
    /* 超激进的顶部空白移除 - 终极版本 */
    
    /* 1. 全局重置 */
    * {
        box-sizing: border-box !important;
    }
    
    body {
        margin: 0 !important;
        padding: 0 !important;
    }
    
    /* 2. 应用容器超激进优化 */
    .stApp {
        max-width: 100% !important;
        padding: 0 !important;
        margin: 0 !important;
        margin-top: -5rem !important;
    }
    
    .stApp > div {
        margin: 0 !important;
        padding: 0 !important;
    }
    
    .stApp > div > div {
        margin: 0 !important;
        padding: 0 !important;
    }
    
    /* 3. 主内容区域彻底优化 */
    .main, .main > div, .main .block-container {
        margin: 0 !important;
        padding: 0.2rem !important;
        padding-top: 0 !important;
        max-width: 100% !important;
    }
    
    /* 4. 覆盖所有可能的Streamlit CSS类 */
    [class*="css-"] {
        margin-top: 0 !important;
        padding-top: 0 !important;
    }
    
    [data-testid*="st"] {
        margin-top: 0 !important;
        padding-top: 0 !important;
    }
    
    /* 5. 隐藏所有头部相关元素 */
    header, .stHeader, 
    [data-testid="stHeader"], 
    [data-testid="stToolbar"], 
    [data-testid="stDecoration"],
    .stToolbar {
        display: none !important;
        height: 0 !important;
        min-height: 0 !important;
        visibility: hidden !important;
    }
    
    /* 6. 强制第一个子元素紧贴顶部 */
    body > div:first-child,
    .stApp > div:first-child,
    .main > div:first-child,
    .main .block-container > div:first-child {
        margin: 0 !important;
        padding-top: 0 !important;
    }
    
    /* 按钮样式优化 */
    .stButton > button {
        width: 100% !important;
        border-radius: 8px !important;
        margin: 0.2rem 0 !important;
    }
    
    /* 输入框样式优化 */
    .stTextInput > div > div > input {
        border-radius: 8px !important;
    }
    
    /* 选择框样式优化 */
    .stSelectbox > div > div {
        border-radius: 8px !important;
    }
    
    /* 隐藏Streamlit默认元素 */
    .stDeployButton {
        display: none !important;
    }
    
    header {
        display: none !important;
    }
    
    footer {
        display: none !important;
    }
    
    /* 移动端友好的字体大小和间距 */
    h1, h2, h3 {
        font-size: 1.2rem !important;
        margin-top: 0.2rem !important;
        margin-bottom: 0.3rem !important;
        padding-top: 0 !important;
    }
    
    /* 特别优化第一个标题 */
    h1:first-child, h2:first-child, h3:first-child {
        margin-top: 0 !important;
        padding-top: 0 !important;
    }
    
    /* 进度条样式 */
    .stProgress > div > div > div {
        background-color: #4CAF50 !important;
    }
    
    /* 优化指标显示 - 确保紧凑显示 */
    .stMetric {
        background-color: #f8f9fa !important;
        padding: 0.3rem !important;
        border-radius: 6px !important;
        margin: 0.1rem 0 !important;
        text-align: center !important;
    }
    
    /* 任务统计指标特殊优化 */
    .stMetric > div {
        font-size: 0.85rem !important;
    }
    
    .stMetric [data-testid="metric-container"] {
        padding: 0.2rem !important;
    }
    
    .stMetric [data-testid="metric-container"] > div {
        justify-content: center !important;
    }
    
    /* 标签页样式优化 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.2rem !important;
        margin-top: 0 !important;
        padding-top: 0 !important;
    }
    
    .stTabs [data-baseweb="tab"] {
        padding: 0.5rem 0.8rem !important;
        font-size: 0.9rem !important;
    }
    
    /* 激进的全局顶部空白移除 */
    .stApp .main {
        padding: 0 !important;
        margin: 0 !important;
    }
    
    /* 覆盖所有可能的Streamlit默认样式 */
    .css-1d391kg, .css-18e3th9, .css-1lcbmhc, .css-k1vhr4, .css-12oz5g7 {
        padding: 0 !important;
        margin: 0 !important;
    }
    
    /* 彻底隐藏头部相关元素 */
    .stApp > header, header, .stHeader {
        display: none !important;
        height: 0 !important;
        min-height: 0 !important;
    }
    
    /* 强制内容区域紧贴顶部 */
    section.main, section.main > div, .main > div {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    
    /* 移除iframe和容器的默认间距 */
    .stApp iframe {
        margin-top: 0 !important;
        padding-top: 0 !important;
    }
    
    /* 全局重置可能影响顶部的元素 */
    * {
        box-sizing: border-box;
    }
    
    body {
        margin: 0 !important;
        padding: 0 !important;
    }
    
    /* 特殊处理可能的固定高度元素 */
    .css-1outpf7, .css-16huue1, .css-1v0mbdj {
        height: 0 !important;
        min-height: 0 !important;
        display: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

def main():
    """主函数"""

    # 设置页面配置
    st.set_page_config(
        page_title="TradingAgents-CN 手机版",
        page_icon="📱",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    
    # 设置移动视图标志（手机版默认为True）
    if 'mobile_view' not in st.session_state:
        st.session_state.mobile_view = True
    
    # 获取任务管理器并同步状态
    task_mgr = get_task_manager()
    task_mgr.sync_progress_from_cache()  # 同步进度缓存
    
    # 检查运行中的任务
    all_tasks = task_mgr.get_all_tasks()
    running_tasks = [task for task in all_tasks if task['status'] == 'running']
    
    # 保存当前标签页状态
    if 'current_tab' not in st.session_state:
        st.session_state.current_tab = 0

    # 初始化模型配置
    initialize_model_config()

    # 应用移动端CSS
    render_mobile_css()

    # 渲染头部
    render_mobile_header()

    # 检查是否查看详细结果
    view_task_id = st.session_state.get('view_task_id')
    if view_task_id:
        render_detailed_result(view_task_id)
        return

    # 创建标签页 - 合并为两个标签
    tab_names = ["📊 新建任务", "⚙️ 配置"]
    
    # 如果有运行中的任务，在新建任务标签上显示提示
    if running_tasks:
        tab_names[0] = f"📊 新建任务 ({len(running_tasks)})"
    
    # 创建标签页 - 只有两个标签
    tab1, tab2 = st.tabs(tab_names)
    
    with tab1:
        # 渲染分析表单
        new_task_id = render_mobile_analysis_form()
        if new_task_id:
            # 如果创建了新任务，显示成功消息
            st.success("✅ 任务已创建！请查看下方任务列表")
            st.info("💡 提示：任务将在后台运行，进度会自动更新")
        
        # 添加分隔线
        st.markdown("---")
        
        # 在新建任务下方显示任务列表
        st.markdown("### 📋 任务列表")
        
        # 渲染任务列表
        render_task_list()
        
        # 参考网页版的刷新控制界面
        if running_tasks:
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔄 手动刷新", key="refresh_in_tab", use_container_width=True):
                    st.rerun()
            with col2:
                auto_refresh_key = "mobile_auto_refresh_enabled"
                default_value = st.session_state.get(auto_refresh_key, True)
                auto_refresh = st.checkbox("🔄 自动刷新", value=default_value, key=auto_refresh_key)
                
            # 显示当前运行状态
            st.info(f"🔄 有 {len(running_tasks)} 个任务正在运行中")
            
            # 执行自动刷新
            if auto_refresh:
                # 强制同步进度数据
                task_mgr.sync_progress_from_cache()
                
                import time
                time.sleep(3)  # 3秒间隔
                st.rerun()
        else:
            st.success("✅ 当前没有运行中的任务")

    with tab2:
        # 渲染配置界面
        render_mobile_config()

    # 🎯 任务状态处理和智能刷新
    # 重新获取最新状态 - 确保进度同步
    task_mgr.sync_progress_from_cache()  # 强制同步进度缓存
    all_tasks = task_mgr.get_all_tasks()
    running_tasks = [task for task in all_tasks if task['status'] == 'running']
    
    # 再次同步确保数据一致性
    for task in running_tasks:
        task_mgr.sync_progress_from_cache()

    # 检查是否有刚刚完成的任务（60秒内）
    recent_completed = [task for task in all_tasks
                       if task['status'] == 'completed' and
                       task['completed_at'] and
                       (datetime.now() - task['completed_at']).seconds < 60]

    if recent_completed and 'view_task_id' not in st.session_state:
        st.success("✅ 分析刚刚完成！")
        # 自动显示完成的任务详情
        completed_task = recent_completed[0]
        st.session_state['view_task_id'] = completed_task['id']
        st.rerun()

    # 显示全局状态信息
    if all_tasks:
        st.markdown("---")
        
        # 如果有运行中的任务，显示全局进度状态
        if running_tasks:
            # 计算总体进度
            total_progress = sum(task.get('progress', 0) for task in running_tasks) / len(running_tasks)
            
            st.markdown(f"""
            <div style="text-align: center; padding: 0.8rem; margin: 0.5rem 0;
                        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
                        color: white; border-radius: 8px; font-size: 0.9rem;">
                🔄 有 {len(running_tasks)} 个任务正在运行中 (平均进度: {total_progress:.1f}%)
            </div>
            """, unsafe_allow_html=True)
            
            # 显示每个运行中任务的简要信息
            for task in running_tasks:
                st.info(f"📊 {task['params']['stock_symbol']}: {task.get('progress', 0)}% 完成")
        
        # 添加手动刷新按钮
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 手动刷新", key="refresh_global", use_container_width=True):
                st.rerun()
        
        with col2:
            if st.button("🧹 清理过期任务", key="cleanup_tasks", use_container_width=True, type="secondary"):
                task_mgr.cleanup_old_tasks(hours=1)  # 清理1小时前的任务
                st.success("✅ 已清理过期任务")
                st.rerun()
    
    # 全局自动刷新机制（仅在没有在标签页内刷新时执行）
    if running_tasks:
        # 显示自动刷新状态指示器
        st.markdown("""
        <div style="position: fixed; top: 10px; right: 10px; background: rgba(0,0,0,0.7); 
                    color: white; padding: 5px 10px; border-radius: 5px; font-size: 12px; z-index: 999;">
            🔄 自动刷新中...
        </div>
        """, unsafe_allow_html=True)
        
        # 检查当前是否在任务列表标签页
        # 如果不在任务列表标签页，则执行全局自动刷新
        auto_refresh_key = "mobile_auto_refresh_enabled"
        auto_refresh_enabled = st.session_state.get(auto_refresh_key, True)
        
        # 只有在自动刷新开启且不在任务列表标签页时才执行全局刷新
        # 任务列表标签页有自己的刷新逻辑
        if auto_refresh_enabled:
            # 使用更短的延迟，因为任务列表标签页已经有自己的刷新
            import time
            time.sleep(1)  # 缩短为1秒，避免与标签页刷新冲突
            st.rerun()
    else:
        # 没有运行任务时，保持自动刷新开关状态不变
        pass

if __name__ == "__main__":
    main()
