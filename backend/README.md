# QAgent 后端服务

QAgent后端服务 - 从PR自动生成E2E测试用例。

## 架构

- **FastAPI**: Web框架，提供API端点
- **LangGraph**: 多Agent编排和工作流管理
- **MCP工具**: Model Context Protocol工具（高/中/低层级）
- **业务Agent**: 需求分析、测试设计、用例开发、结果检查
- **基础设施**: 沙盒管理、Workspace管理、GitHub集成

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境

```bash
cp .env.example .env
# 编辑 .env 文件，配置API密钥和设置
# 设置 LLM_PROVIDER 为 "openai" 或 "anthropic"
# 配置对应的API密钥（OPENAI_API_KEY 或 ANTHROPIC_API_KEY）
```

**必需配置**：
- `LLM_PROVIDER`: LLM提供商（"openai" 或 "anthropic"）
- `OPENAI_API_KEY` 或 `ANTHROPIC_API_KEY`: 至少配置一个LLM API密钥
- `GITHUB_TOKEN`: GitHub访问令牌

**可选配置**：
- `LANGSMITH_TRACING`: 是否启用LangSmith追踪（"true"/"false"）
- `LANGSMITH_API_KEY`: LangSmith API密钥
- `LANGSMITH_PROJECT`: LangSmith项目名称

详细配置说明请参考 [LLM Provider Setup](docs/LLM_PROVIDER_SETUP.md)

### 3. 运行应用

**方式1：使用启动脚本（推荐）**

```bash
cd backend
./start.sh
```

启动脚本 (`start.sh`) 会自动：
- 检查并创建 `.env` 文件（从 `.env.example` 复制，如需要）
- 验证Python 3.12和pyenv qagent虚拟环境
- 检查并安装依赖（如需要）
- 验证环境配置
- 创建logs目录
- 启动FastAPI服务器（带自动重载）

**方式2：手动启动**

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

服务启动后，访问：
- API文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

## API端点

### 健康检查

- `GET /`: 基础健康检查
- `GET /health`: 详细健康状态

### Webhook端点

- `POST /api/webhooks/github`: GitHub Webhook处理器
  - 接收PR和Push事件
  - 自动触发工作流
  - 返回 `task_id` 和 `langsmith_trace_url`
- `GET /api/webhooks/github/test`: Webhook测试端点

### 任务管理

- `GET /api/tasks/{task_id}`: 获取任务状态
- `GET /api/tasks`: 列出任务（支持 `limit` 和 `offset` 参数）
- `POST /api/tasks/{task_id}/cancel`: 取消运行中的任务

## 项目结构

```
backend/
├── app/
│   ├── api/                    # FastAPI路由
│   │   ├── webhooks.py         # GitHub Webhook处理器
│   │   └── tasks.py            # 任务管理API
│   ├── agents/                 # Agent实现
│   │   ├── base.py             # Agent基类（LLM初始化、工具创建）
│   │   └── business/           # 业务Agent
│   │       ├── requirement_analyzer.py  # 需求分析Agent
│   │       ├── case_designer.py         # 测试设计Agent
│   │       ├── case_developer.py        # 用例开发Agent
│   │       ├── case_checker.py         # 结果检查Agent
│   │       ├── framework_detector.py    # 框架检测Agent
│   │       ├── github_agent.py         # GitHub操作Agent
│   │       └── workspace_agent.py      # Workspace管理Agent
│   ├── orchestration/          # 工作流编排
│   │   └── workflow.py         # LangGraph工作流定义
│   ├── mcp/                    # MCP工具层
│   │   ├── base.py            # MCP工具基类
│   │   ├── servers/           # MCP服务器
│   │   │   └── mcp_server.py  # MCP工具注册和管理
│   │   └── tools/             # 工具实现
│   │       ├── high_level/    # 高级工具（业务逻辑）
│   │       ├── mid_level/     # 中级工具（通用功能）
│   │       └── low_level/     # 低级工具（基础功能）
│   ├── infrastructure/        # 基础设施服务
│   │   ├── github.py         # GitHub客户端
│   │   ├── workspace.py      # Workspace管理
│   │   └── sandbox.py        # 沙盒管理（Docker）
│   ├── models/               # 数据模型
│   │   └── task.py           # 任务模型（Task, TaskStatus, TaskStage）
│   ├── config.py             # 配置管理（Pydantic Settings）
│   └── main.py               # FastAPI应用入口
├── tests/                     # 测试代码
│   ├── unit/                 # 单元测试
│   ├── integration/          # 集成测试
│   ├── e2e/                  # E2E测试
│   └── README.md             # 测试文档
├── docs/                      # 后端相关文档
├── logs/                      # 日志文件
│   ├── app.log               # 应用日志（轮转，10MB，保留5个备份）
│   └── app.error.log         # 错误日志（每日轮转，保留7天）
├── requirements.txt          # Python依赖
├── start.sh                  # 启动脚本
└── README.md                 # 本文档
```

## 工作流

工作流使用LangGraph进行编排，包含以下阶段：

1. **初始化** → 接收PR事件，创建任务
2. **创建沙盒** → 创建隔离环境（可选）
3. **权限检查** → 验证GitHub权限
4. **克隆仓库** → 克隆目标仓库到独立workspace
5. **分析需求** → RequirementAnalyzer分析PR需求
6. **启动服务** → 启动前端服务（如需要）
7. **检测框架** → FrameworkDetector检测现有测试框架
8. **设计测试** → CaseDesigner设计测试用例
9. **开发用例** → CaseDeveloper生成测试代码
10. **设置环境** → 设置E2E测试环境
11. **执行测试** → 运行测试用例
12. **检查结果** → 基础结果检查
13. **Agent链式审查** → CaseChecker进行LLM审查（Self-Refine机制）
14. **创建PR** → 创建包含测试用例的PR（如通过）
15. **完成/重试** → 根据审查结果决定完成或重试

**测试框架检测**：在分析需求后，系统会自动检测项目中现有的测试框架（Playwright、Cypress、Selenium等）。如果未检测到框架，默认使用Playwright。

**Self-Refine机制**：如果测试结果检查失败，CaseChecker会提供详细反馈，系统会自动重试（最多N次），将反馈传递给CaseDeveloper进行改进。

## 日志系统

应用配置了完整的日志系统：

- **控制台输出**：StreamHandler，INFO级别
- **应用日志**：`logs/app.log`，RotatingFileHandler
  - 最大大小：10MB
  - 备份数量：5个
  - 级别：INFO
- **错误日志**：`logs/app.error.log`，TimedRotatingFileHandler
  - 轮转频率：每日
  - 保留天数：7天
  - 级别：ERROR

日志格式包含时间戳、级别、模块、行号和消息。

## LLM配置

### 全局配置

在 `.env` 文件中设置：

```bash
# 全局默认LLM提供商
LLM_PROVIDER=openai

# OpenAI配置
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
OPENAI_TEMPERATURE=0.7
USE_RESPONSES_API=true

# Anthropic配置
ANTHROPIC_API_KEY=your_anthropic_api_key_here
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
ANTHROPIC_TEMPERATURE=0.7
```

### 按Agent配置

可以为不同Agent配置不同的LLM提供商：

```bash
# 格式：agent_name:provider（逗号分隔）
AGENT_LLM_PROVIDERS=requirement_analyzer:openai,case_designer:anthropic,case_developer:openai
```

### 专用模型配置

CaseChecker使用专用模型进行关键审查任务：

```bash
# CaseChecker专用模型（更强大、更稳定）
ANTHROPIC_MODEL_FOR_CHECK=claude-3-5-opus-20241022
ANTHROPIC_TEMPERATURE_FOR_CHECK=0.3
OPENAI_MODEL_FOR_CHECK=gpt-4o
OPENAI_TEMPERATURE_FOR_CHECK=0.3
```

详细配置说明请参考 [LLM Provider Setup](docs/LLM_PROVIDER_SETUP.md)

## 开发

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定分类
pytest -m unit
pytest -m integration
pytest -m e2e

# 运行并生成覆盖率报告
pytest --cov=app --cov-report=html
```

详细测试说明请参考 [tests/README.md](tests/README.md)

### 代码结构

- **Agent模式**：所有业务Agent都继承自 `BaseAgent`，支持：
  - LLM集成（OpenAI/Anthropic）
  - 工具封装（将业务方法封装为LangChain工具）
  - Agent创建（创建LangChain Agent，如果可用）
  - 统一接口（`execute` 方法支持自然语言提示或直接调用）

- **MCP工具分层**：
  - **High Level**: 业务逻辑工具（测试执行、结果检查、PR创建等）
  - **Mid Level**: 通用功能工具（文件操作、搜索、Git操作等）
  - **Low Level**: 基础功能工具（字符串处理、路径处理等）

- **工作流编排**：使用LangGraph定义状态机，支持条件边和循环（Self-Refine）

## 环境变量

主要环境变量（完整列表请参考 `.env.example`）：

### 必需变量

- `LLM_PROVIDER`: LLM提供商（"openai" 或 "anthropic"）
- `OPENAI_API_KEY` 或 `ANTHROPIC_API_KEY`: 至少配置一个
- `GITHUB_TOKEN`: GitHub访问令牌

### 可选变量

- `LANGSMITH_TRACING`: 是否启用LangSmith追踪
- `LANGSMITH_API_KEY`: LangSmith API密钥
- `LANGSMITH_PROJECT`: LangSmith项目名称
- `GITHUB_WEBHOOK_SECRET`: GitHub Webhook签名密钥
- `WORKSPACE_BASE_PATH`: Workspace基础路径（默认：临时目录）

## 相关文档

- [项目主README](../README.md) - 项目整体说明
- [快速开始指南](../docs/quick_start.md) - 快速上手
- [项目结构说明](../docs/project_structure.md) - 详细代码组织
- [测试文档](tests/README.md) - 测试策略和指南
- [LLM Provider Setup](docs/LLM_PROVIDER_SETUP.md) - LLM配置详细说明
