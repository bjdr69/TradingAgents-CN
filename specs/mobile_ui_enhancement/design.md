# 技术设计: 手机UI增强

## 1. 架构概述

本次增强旨在将 TradingAgents-CN 的手机用户界面 (`mobile_app.py`) 功能与 Web 端 (`web/app.py` 及其组件) 对齐。核心变更包括：

1.  **集成与重构配置部分**：在手机UI中引入与Web端侧边栏 (`web/components/sidebar.py`) 相同的AI模型配置、记忆功能等高级设置。
2.  **增强分析表单**：将Web端的分析表单 (`web/components/analysis_form.py`) 功能（股票代码、市场、日期、分析师团队、研究深度）整合到手机UI的分析启动界面。
3.  **完善结果展示**：在手机UI中展示与Web端结果展示 (`web/components/results_display.py`) 相同的详细分析报告内容。
4.  **添加报告导出**：在手机UI中集成与Web端相同的报告导出功能 (`web/utils/report_exporter.py`)，支持PDF下载。

为实现代码复用和保持一致性，将尽可能复用或参考Web端已有的组件和逻辑，特别是模型加载、配置持久化、分析运行和报告生成等核心部分。

## 2. 数据模型/接口设计

### 数据库

*   本项目使用 MongoDB 和 Redis 进行数据存储和缓存。本次增强主要涉及会话状态和分析进度的管理，将复用现有的 `smart_session_manager` 和 `AsyncProgressTracker` 等工具，它们内部会与 MongoDB/Redis 交互。因此，无需新增数据库表或修改现有数据库结构。

### API 端点

*   本次增强不直接新增API端点。核心分析逻辑通过 `web/utils/analysis_runner.py` 中的 `run_stock_analysis` 函数调用，它内部会与各种LLM提供商和数据源API进行交互。手机UI将调用这个函数来启动和获取分析结果，与Web端保持一致。

## 3. 关键组件与测试策略

### 关键组件

1.  **`mobile_app.py` (核心修改)**:
    *   **重构 `render_mobile_analysis_form`**: 集成Web端 `analysis_form.py` 的完整功能，包括市场选择、股票代码输入、分析日期（可选）、分析师团队多选（市场、新闻、社交媒体、基本面）、研究深度选择（快速，基础，标准，深度，全面）。
    *   **新增 `render_mobile_sidebar_config`**: 在手机UI中创建一个新的区域（如表单内的Expander或单独的标签页），用于配置AI模型（提供商、具体模型）、启用记忆功能等，逻辑参考 `web/components/sidebar.py`。
    *   **重构 `render_detailed_result`**: 集成Web端 `results_display.py` 的完整功能，展示市场技术分析、基本面分析、市场情绪分析、新闻事件分析、风险评估、投资建议等详细报告内容。
    *   **集成报告导出**: 在 `render_detailed_result` 中调用 `web/utils/report_exporter.py` 的 `render_export_buttons` 函数，或参考其实现，在手机UI上提供生成PDF并下载的功能。

2.  **`web/components/sidebar.py` (参考/复用)**:
    *   复用其中的模型配置逻辑、配置持久化 (`save_model_selection`, `load_model_selection`) 逻辑。

3.  **`web/components/analysis_form.py` (参考/复用)**:
    *   复用其中的表单元素、分析师选择逻辑、研究深度选择逻辑。

4.  **`web/components/results_display.py` (参考/复用)**:
    *   复用或参考其中的报告内容展示逻辑，特别是 `render_detailed_analysis` 和 `render_decision_summary` 函数。

5.  **`web/utils/report_exporter.py` (参考/复用)**:
    *   复用其中的 `render_export_buttons` 函数，或参考其PDF生成和下载的实现。

### 测试策略

1.  **单元测试**:
    *   由于核心逻辑复用Web端组件，主要依赖现有测试覆盖。新增的UI渲染逻辑部分，可考虑编写简单的单元测试来验证组件渲染是否正确（例如，检查是否渲染了正确的输入框、选择框等）。
2.  **集成测试**:
    *   在真实或模拟的移动设备浏览器上进行端到端测试。
    *   验证完整的流程：配置 -> 启动分析 -> 查看进度 -> 查看报告 -> 导出PDF。
    *   测试不同模型配置、不同分析师组合、不同研究深度下的功能。
    *   验证配置的持久化和恢复功能在移动端是否正常工作。
3.  **手动测试**:
    *   在不同尺寸的移动设备和浏览器模拟器上测试UI的响应式和可用性。
    *   确保所有按钮、输入框在触屏操作下易于使用。