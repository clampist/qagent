# 项目结构说明

本文档详细说明QAgent项目的代码组织结构。

## 整体结构

```
QAgent/
├── backend/                 # 后端服务（Python FastAPI）
│   ├── app/                # 应用主代码
│   ├── tests/              # 测试代码
│   ├── docs/               # 后端相关文档
│   ├── logs/               # 日志文件
│   ├── requirements.txt    # Python依赖
│   ├── start.sh            # 启动脚本
│   └── README.md           # 后端README
├── frontend/               # 前端代码（如果有）
├── docs/                   # 项目文档
│   ├── quick_start.md      # 快速开始（本文档）
│   ├── project_structure.md # 项目结构（本文档）
│   └── pricing/           # 定价信息
└── README.md               # 项目主README
```

## Backend 详细结构

### app/ - 应用主代码

```
app/
├── main.py                 # FastAPI应用入口
├── config.py              # 配置管理（Pydantic Settings）
│
├── api/                   # API路由
│   ├── webhooks.py        # GitHub Webhook处理器
│   └── tasks.py           # 任务管理API
│
├── agents/                # Agent实现
│   ├── base.py            # Agent基类（LLM初始化、工具创建）
│   └── business/          # 业务Agent
│       ├── requirement_analyzer.py  # 需求分析Agent
│       ├── case_designer.py         # 测试设计Agent
│       ├── case_developer.py       # 用例开发Agent
│       ├── case_checker.py         # 结果检查Agent
│       ├── framework_detector.py   # 框架检测Agent
│       ├── github_agent.py         # GitHub操作Agent
│       └── workspace_agent.py      # Workspace管理Agent
│
├── orchestration/         # 工作流编排
│   └── workflow.py        # LangGraph工作流定义
│
├── mcp/                   # MCP工具层
│   ├── base.py            # MCP工具基类
│   ├── servers/           # MCP服务器
│   │   └── mcp_server.py  # MCP工具注册和管理
│   └── tools/             # 工具实现
│       ├── high_level/    # 高级工具（业务逻辑）
│       │   ├── case_runner.py        # 测试执行
│       │   ├── case_result_checker.py # 结果检查
│       │   ├── e2e_env_setup.py     # E2E环境设置
│       │   ├── pr_creator.py         # PR创建
│       │   └── service_startup.py   # 服务启动
│       ├── mid_level/     # 中级工具（通用功能）
│       │   ├── file_tools.py        # 文件操作
│       │   ├── search_tools.py      # 搜索工具
│       │   ├── git_tools.py         # Git操作
│       │   ├── test_tools.py         # 测试工具
│       │   ├── framework_tools.py   # 框架检测工具
│       │   ├── cost_control.py      # 成本控制
│       │   ├── environment.py      # 环境管理
│       │   └── project_structure_analyzer.py # 项目结构分析
│       └── low_level/     # 低级工具（基础功能）
│           ├── code_tools.py       # 代码处理
│           ├── string_tools.py     # 字符串处理
│           ├── path_tools.py       # 路径处理
│           ├── keyword_tools.py    # 关键词处理
│           ├── format_tools.py     # 格式化工具
│           └── time_tools.py      # 时间工具
│
├── infrastructure/        # 基础设施服务
│   ├── github.py         # GitHub客户端
│   ├── workspace.py      # Workspace管理
│   └── sandbox.py        # 沙盒管理（Docker）
│
└── models/               # 数据模型
    └── task.py           # 任务模型（Task, TaskStatus, TaskStage）
```

### tests/ - 测试代码

```
tests/
├── conftest.py           # pytest配置和fixtures
├── README.md             # 测试说明文档
├── TESTING_STRATEGY.md   # 测试策略文档
│
├── unit/                 # 单元测试
│   ├── test_agents.py    # Agent单元测试
│   ├── test_infrastructure.py # 基础设施测试
│   └── test_mcp_tools.py # MCP工具测试
│
├── integration/          # 集成测试
│   ├── test_01_permission_check.py    # 权限检查
│   ├── test_02_workspace_clone.py     # Workspace克隆
│   ├── test_03_requirement_analyzer.py # 需求分析
│   ├── test_04_framework_detector.py   # 框架检测
│   ├── test_05_case_designer.py        # 测试设计
│   ├── test_06_case_developer.py       # 用例开发
│   ├── test_07_workflow_execution.py   # 工作流执行
│   ├── test_webhook_api.py             # Webhook API
│   └── test_workflow.py                # 工作流测试
│
├── e2e/                  # 端到端测试
│   └── test_workflow_e2e.py # 完整工作流E2E测试
│
└── utils/                # 测试工具
    └── test_helpers.py   # 测试辅助函数
```

## 核心组件说明

### 1. Workflow Orchestration (workflow.py)

使用LangGraph定义的工作流，包含以下节点：

- `initialize`: 初始化工作流状态
- `create_sandbox`: 创建沙盒环境
- `check_permissions`: 检查GitHub权限
- `clone_repo`: 克隆目标仓库
- `analyze_requirements`: 分析PR需求
- `startup_service`: 启动服务（如需要）
- `detect_framework`: 检测测试框架
- `design_tests`: 设计测试用例
- `develop_cases`: 开发测试代码
- `setup_e2e_environment`: 设置E2E环境
- `run_tests`: 执行测试
- `check_results`: 检查测试结果
- `agent_chain_review`: Agent链式审查（Self-Refine）
- `create_pr`: 创建PR
- `handle_error`: 错误处理

### 2. Business Agents

每个业务Agent都继承自`BaseAgent`，具备以下能力：

- **LLM集成**：支持OpenAI和Anthropic
- **工具封装**：将业务方法封装为LangChain工具
- **Agent创建**：创建LangChain Agent（如果可用）
- **统一接口**：`execute`方法支持自然语言提示或直接调用

**主要Agent**：

- **RequirementAnalyzer**: 分析PR需求，提取测试点
- **CaseDesigner**: 设计测试用例，生成测试方案
- **CaseDeveloper**: 开发具体测试代码（Playwright/Cypress等）
- **CaseChecker**: 检查测试结果，提供反馈
- **FrameworkDetector**: 检测现有测试框架
- **GithubAgent**: GitHub操作（获取PR、创建PR等）
- **WorkspaceAgent**: Workspace管理（克隆、清理等）

### 3. MCP Tools

MCP工具分为三个层次：

**High Level (高级工具)**：
- 包含业务逻辑
- 通常由Agent直接调用
- 例如：测试执行、结果检查、PR创建

**Mid Level (中级工具)**：
- 通用功能
- 可被多个Agent复用
- 例如：文件操作、搜索、Git操作

**Low Level (低级工具)**：
- 基础功能
- 纯函数，无副作用
- 例如：字符串处理、路径处理、格式化

### 4. Infrastructure Services

**GitHub Client** (`github.py`):
- 封装GitHub API操作
- 获取PR信息、创建PR、检查权限等

**Workspace Manager** (`workspace.py`):
- 管理独立的workspace目录
- 克隆仓库、清理workspace等

**Sandbox Manager** (`sandbox.py`):
- Docker沙盒管理（未来功能）
- 隔离测试执行环境

## 数据流

```
GitHub Webhook
    ↓
FastAPI Router (webhooks.py)
    ↓
WorkflowManager.start_pr_workflow()
    ↓
LangGraph Workflow
    ├─→ RequirementAnalyzer (分析需求)
    ├─→ FrameworkDetector (检测框架)
    ├─→ CaseDesigner (设计用例)
    ├─→ CaseDeveloper (开发代码)
    ├─→ CaseRunner (执行测试)
    └─→ CaseChecker (检查结果)
         ├─→ 通过 → CreatePR
         └─→ 失败 → 反馈 → CaseDeveloper (重试)
    ↓
返回结果 (task_id, langsmith_trace_url)
```

## 配置管理

配置通过`app/config.py`中的`Settings`类管理，使用Pydantic Settings从`.env`文件加载：

- **LLM配置**：提供商、模型、温度等
- **API配置**：API密钥、端点等
- **GitHub配置**：Token、Webhook Secret等
- **LangSmith配置**：Tracing、API Key、Project等

## 日志系统

日志配置在`app/main.py`的`setup_logging`函数中：

- **控制台输出**：StreamHandler，INFO级别
- **应用日志**：RotatingFileHandler，`logs/app.log`，10MB轮转，保留5个备份
- **错误日志**：TimedRotatingFileHandler，`logs/app.error.log`，每日轮转，保留7天

## 测试策略

采用三层测试金字塔：

1. **Unit Tests**: 快速测试独立组件
2. **Integration Tests**: 测试组件协作
3. **E2E Tests**: 完整工作流测试

详细说明请参考 [backend/tests/README.md](../backend/tests/README.md)

## 扩展指南

### 添加新的Agent

1. 在`app/agents/business/`下创建新文件
2. 继承`BaseAgent`
3. 实现业务方法
4. 在`__init__`中创建工具和Agent
5. 实现`execute`方法

### 添加新的MCP工具

1. 确定工具层级（high/mid/low）
2. 在对应目录下创建文件
3. 继承`MCPTool`或使用`@tool`装饰器
4. 在`mcp_server.py`中注册

### 修改工作流

1. 在`workflow.py`的`_build_graph`中添加/修改节点
2. 实现对应的节点方法
3. 添加/修改边和条件边

## 相关文档

- [快速开始指南](quick_start.md)
- [后端README](../backend/README.md)
- [测试策略](../backend/tests/README.md)
- [LLM Provider Setup](../backend/docs/LLM_PROVIDER_SETUP.md)

