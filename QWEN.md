# Qwen Code 上下文配置文件 (TradingAgents-CN)

## 项目概述

这是一个基于多智能体大语言模型的**中文金融交易决策框架**，名为 TradingAgents-CN。该项目是 [Tauric Research](https://github.com/TauricResearch) 的 [TradingAgents](https://github.com/TauricResearch/TradingAgents) 项目的中文增强版，专为中文用户优化，提供完整的A股/港股/美股分析能力。

### 核心技术栈

- **语言**: Python 3.10+
- **框架**: LangChain, LangGraph, Streamlit
- **AI模型**: 支持多种提供商，包括阿里百炼(DashScope), DeepSeek, Google AI, OpenAI, Anthropic (通过OpenRouter)
- **数据源**: Tushare (A股), AkShare, FinnHub, Yahoo Finance
- **数据库**: MongoDB (持久化), Redis (缓存)
- **部署**: Docker, Docker Compose

### 主要特性

- **多智能体协作**: 市场分析师、基本面分析师、新闻分析师、研究员(看涨/看跌)、交易员等角色协同工作。
- **多LLM支持**: 集成国内外主流大语言模型提供商，支持超过60种模型。
- **多市场覆盖**: 支持A股、港股、美股的行情和基本面分析。
- **智能新闻分析**: (v0.1.12新增) AI驱动的新闻过滤、质量评估和相关性分析。
- **Web界面**: 基于Streamlit的现代化Web应用，提供配置、分析和报告导出功能。
- **专业报告导出**: 支持导出为Markdown, Word (.docx), PDF格式。
- **容器化部署**: 通过Docker Compose一键部署包含Web应用、MongoDB、Redis及其管理界面的完整环境。

## 项目结构

```
D:\AI\TradingAgents\
├── cli/              # 命令行接口
├── config/           # 配置文件
├── data/             # 本地数据存储
├── docs/             # 详细的中文文档体系 (50,000+字)
├── examples/         # 使用示例
├── logs/             # 日志文件
├── reports/          # 生成的分析报告
├── scripts/          # 脚本文件 (启动, 部署, 维护)
├── tests/            # 测试文件
├── tradingagents/    # 核心源代码库
│   ├── agents/       # 各类智能体实现
│   ├── graph/        # LangGraph流程定义
│   ├── llm/          # LLM集成和适配器
│   ├── tools/        # 智能体可调用的工具
│   └── utils/        # 通用工具模块
├── web/              # Streamlit Web应用
├── .env.example      # 环境变量配置示例
├── docker-compose.yml # Docker编排文件
├── Dockerfile        # Docker镜像构建文件
├── pyproject.toml    # 项目元数据和依赖声明 (推荐安装方式)
├── requirements.txt  # 旧版依赖文件 (已弃用)
├── main.py           # 代码调用入口示例
├── start_web.py      # 本地部署启动脚本
└── README.md         # 项目主文档
```

## 构建、运行和测试

### 环境准备

- Python 3.10+
- (可选) Docker 和 Docker Compose (推荐用于部署)

### 依赖管理

项目使用 `pyproject.toml` 管理依赖。推荐使用 `pip install -e .` 进行可编辑安装，这会安装项目及其所有依赖。

```bash
# 升级pip
python -m pip install --upgrade pip

# 安装项目及其依赖 (推荐)
pip install -e .
```

### 本地部署启动

```bash
# 方法1: 使用简化启动脚本 (推荐)
python start_web.py

# 方法2: 直接使用Streamlit
streamlit run web/app.py --server.port 8501 --server.address localhost
```

### Docker部署启动

```bash
# 一键构建并启动所有服务 (推荐)
docker-compose up -d --build

# 仅启动已构建的服务
docker-compose up -d
```

访问地址:
- Web应用: `http://localhost:8501`
- MongoDB管理界面 (需启用management profile): `http://localhost:8082`
- Redis管理界面: `http://localhost:8081`

### 代码调用示例

可以直接在Python代码中调用核心分析功能：

```python
# main.py 示例
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

# Create a custom config
config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "google"
config["deep_think_llm"] = "gemini-2.0-flash"
config["quick_think_llm"] = "gemini-2.0-flash"

# Initialize with custom config
ta = TradingAgentsGraph(debug=True, config=config)

# forward propagate
_, decision = ta.propagate("NVDA", "2024-05-10")
print(decision)
```

### CLI交互式使用

```bash
# 启动交互式命令行界面
python -m cli.main
```

## 开发约定

- **依赖管理**: 使用 `pyproject.toml` 管理项目依赖。
- **安装方式**: 推荐使用 `pip install -e .` 进行开发安装。
- **代码结构**: 核心逻辑位于 `tradingagents/` 目录下，按功能模块划分。
- **Web界面**: 使用 Streamlit 构建，代码位于 `web/` 目录。
- **配置管理**: 通过 `.env` 文件和 `config/` 目录进行配置。
- **日志管理**: 使用统一的日志管理器，日志输出到 `logs/` 目录。
- **文档**: 拥有非常完善的中文文档体系，位于 `docs/` 目录。
- **测试**: 代码测试位于 `tests/` 目录。
