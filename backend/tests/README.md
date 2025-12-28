# QAgent 后端测试

使用 pytest 的 QAgent 后端综合测试套件。

## 概述

本文档概述了QAgent后端的测试策略和指南。QAgent是一个多Agent系统，能够从PR自动生成E2E测试用例。

## 测试金字塔

```
        /\
       /  \  E2E测试（少量、慢速、真实服务）
      /----\
     /      \  集成测试（中等数量、中等速度、Mock服务）
    /--------\
   /          \  单元测试（大量、快速、独立组件）
  /------------\
```

## 测试结构

```
tests/
├── conftest.py                    # 共享fixtures和测试工具
├── unit/                          # 单元测试（独立组件）
│   ├── test_mcp_tools.py         # MCP工具测试
│   ├── test_agents.py            # Agent测试
│   └── test_infrastructure.py    # 基础设施层测试
├── integration/                   # 集成测试
│   ├── test_01_permission_check.py      # 权限检查测试
│   ├── test_02_workspace_clone.py       # Workspace克隆测试
│   ├── test_03_requirement_analyzer.py  # 需求分析Agent测试
│   ├── test_04_framework_detector.py    # 框架检测Agent测试
│   ├── test_05_case_designer.py         # 测试设计Agent测试
│   ├── test_06_case_developer.py        # 用例开发Agent测试
│   ├── test_07_workflow_execution.py    # 工作流执行测试
│   ├── test_webhook_api.py              # Webhook API测试
│   └── test_workflow.py                 # 工作流编排测试
├── e2e/                           # 端到端测试
│   └── test_workflow_e2e.py      # 完整工作流E2E测试
└── utils/                         # 测试工具
    └── test_helpers.py            # 辅助函数
```

## 测试分类

### 1. 单元测试 (`@pytest.mark.unit`)

**目的**：测试独立组件

**测试范围**：
- **MCP工具**：Git工具、搜索工具、测试工具、成本控制、时间工具等
- **Agent基础功能**：RequirementAnalyzer、CaseDesigner、CaseDeveloper、CaseChecker等的基础方法
- **基础设施**：Sandbox、Workspace、GitHub Client的基础方法
- **模型和工具**：Task模型、工具函数等

**特点**：
- 快速执行（< 1秒/测试）
- 无外部依赖
- 全面Mock
- 高覆盖率目标（>80%）

**示例**：
```python
@pytest.mark.unit
async def test_git_clone_success():
    tool = GitCloneTool()
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(returncode=0)
        result = await tool.execute(...)
        assert result["success"] is True
```

**测试文件**：
- `test_mcp_tools.py` - MCP工具单元测试
- `test_agents.py` - Agent基础方法单元测试
- `test_infrastructure.py` - 基础设施单元测试

### 2. 集成测试 (`@pytest.mark.integration`)

**目的**：测试组件交互和API端点

**测试范围**：
- **API端点**：Webhooks（GitHub webhook处理）、Tasks（任务管理API）
- **工作流编排**：LangGraph工作流的各个节点
- **Agent协作**：多个Agent协同工作
- **MCP工具集成**：工具在实际场景中的使用
- **完整工作流节点**：
  - 权限检查（`test_01_permission_check.py`）
  - Workspace克隆（`test_02_workspace_clone.py`）
  - 需求分析（`test_03_requirement_analyzer.py`）
  - 框架检测（`test_04_framework_detector.py`）
  - 测试设计（`test_05_case_designer.py`）
  - 用例开发（`test_06_case_developer.py`）
  - 工作流执行（`test_07_workflow_execution.py`）

**特点**：
- 中等速度（1-5秒/测试）
- Mock外部服务（GitHub、Docker、LLM）
- 测试真实组件交互
- 使用TestClient进行API测试
- 测试Agent的execute方法（支持自然语言提示）

**示例**：
```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_requirement_analyzer_with_prompt():
    analyzer = RequirementAnalyzer()
    result = await analyzer.execute(
        prompt="分析这个PR的需求",
        pr_data=sample_pr_data,
        workspace_path=workspace_path
    )
    analysis = extract_from_agent_result(result, "analysis")
    assert analysis is not None
```

**测试文件说明**：
- `test_01_permission_check.py` - GitHub权限检查集成测试
- `test_02_workspace_clone.py` - Workspace克隆集成测试（包括WorkspaceAgent）
- `test_03_requirement_analyzer.py` - 需求分析Agent集成测试（包括Agent execute方法）
- `test_04_framework_detector.py` - 框架检测Agent集成测试
- `test_05_case_designer.py` - 测试设计Agent集成测试
- `test_06_case_developer.py` - 用例开发Agent集成测试
- `test_07_workflow_execution.py` - 完整工作流执行测试（包括Self-Refine机制）
- `test_webhook_api.py` - GitHub Webhook API端点测试
- `test_workflow.py` - 工作流编排基础测试

**集成测试文件命名**：
集成测试文件使用数字前缀表示执行顺序和依赖关系：
- `test_01_*` - 基础功能（权限、克隆）
- `test_02_*` - Workspace相关
- `test_03_*` - 需求分析
- `test_04_*` - 框架检测
- `test_05_*` - 测试设计
- `test_06_*` - 用例开发
- `test_07_*` - 完整工作流

### 3. E2E测试 (`@pytest.mark.e2e`)

**目的**：测试完整工作流，从PR到测试生成

**测试范围**：
- 完整PR → 测试生成工作流
- 真实服务集成（可选）
- 用户场景

**特点**：
- 慢速执行（10+秒/测试）
- 可能需要外部服务
- 标记为 `@pytest.mark.slow`
- 在CI中合并到main时运行

**示例**：
```python
@pytest.mark.e2e
@pytest.mark.slow
async def test_complete_pr_to_test_workflow():
    # 从webhook到完成的完整工作流
    task_id = await workflow_manager.start_pr_workflow(...)
    # 等待工作流完成
    # 验证测试用例已生成
    ...
```

**测试文件**：
- `test_workflow_e2e.py` - 完整工作流E2E测试

## 运行测试

### 运行所有测试

```bash
pytest
```

### 按分类运行

```bash
# 仅运行单元测试
pytest -m unit

# 仅运行集成测试
pytest -m integration

# 仅运行E2E测试
pytest -m e2e
```

### 运行并生成覆盖率报告

```bash
pytest --cov=app --cov-report=html
```

覆盖率报告将生成在 `htmlcov/` 目录下。

### 运行特定测试文件

```bash
# 运行特定文件
pytest tests/unit/test_mcp_tools.py

# 运行特定测试类
pytest tests/integration/test_03_requirement_analyzer.py::TestRequirementAnalyzerIntegration

# 运行特定测试方法
pytest tests/unit/test_mcp_tools.py::TestGitTools::test_git_clone_success
```

### 运行并显示详细输出

```bash
# 显示详细输出
pytest -v

# 显示print输出
pytest -s

# 显示最慢的10个测试
pytest --durations=10
```

## 测试标记（Markers）

- `@pytest.mark.unit` - 单元测试
- `@pytest.mark.integration` - 集成测试
- `@pytest.mark.e2e` - 端到端测试
- `@pytest.mark.slow` - 慢速测试
- `@pytest.mark.asyncio` - 异步测试
- `@pytest.mark.requires_api` - 需要外部API（可选）
- `@pytest.mark.requires_docker` - 需要Docker（可选）
- `@pytest.mark.requires_github` - 需要GitHub访问（可选）

## Mock策略

### 外部服务

1. **OpenAI/Anthropic LLM**
   - 在LangChain层面Mock
   - 使用 `mock_llm` fixture
   - 支持动态切换OpenAI和Anthropic
   - 返回可预测的响应

2. **GitHub API**
   - Mock PyGithub客户端
   - 使用 `mock_github_client` fixture
   - 模拟PR操作、仓库操作、权限检查等

3. **Docker**
   - Mock docker客户端
   - 使用 `mock_docker_client` fixture（如需要）
   - 模拟容器操作

4. **文件系统**
   - 使用临时目录
   - `temp_workspace` fixture
   - 自动清理
   - 支持测试工具函数（`create_test_repo_structure`、`create_mock_pr_files`等）

### 内部组件

- Mock层间依赖
- 尽可能使用依赖注入
- 测试接口，而非实现

## 测试Fixtures

`conftest.py` 中的关键fixtures：

- `test_settings` - 测试配置（Settings对象）
- `mock_llm` - Mock的LangChain LLM（支持OpenAI和Anthropic）
- `mock_github_client` - Mock的GitHub客户端
- `mock_docker_client` - Mock的Docker客户端（如需要）
- `temp_workspace` - 临时workspace目录
- `sample_pr_data` - 示例PR数据
- `sample_task` - 示例Task对象
- `mock_workflow_state` - Mock工作流状态
- `extract_from_agent_result` - 从Agent执行结果中提取数据的辅助函数

## 测试数据管理

### Fixtures

- `conftest.py` 中的可复用测试数据
- 示例PR数据、任务、工作流状态
- 外部服务的Mock对象

### 测试辅助函数

`utils/test_helpers.py` 中的辅助函数：

- `create_test_repo_structure()` - 创建Mock仓库结构
- `create_mock_pr_files()` - 创建PR文件
- `extract_from_agent_result()` - 从Agent执行结果中提取数据
  - 支持多种响应格式（ToolMessage、AIMessage、直接dict等）
  - 包含fallback机制，确保数据提取的健壮性

## 特殊考虑

### 异步代码

- 使用 `pytest-asyncio`
- 异步测试标记为 `@pytest.mark.asyncio`
- 使用 `AsyncMock` 进行异步Mock

### Agent测试

所有业务Agent都实现了 `execute` 方法，支持：
- **自然语言提示**：通过prompt参数传入自然语言查询
- **直接调用**：通过action参数直接调用工具方法
- **Fallback**：如果Agent框架不可用，自动fallback到直接方法调用

**测试execute方法**：
- 集成测试中重点测试Agent的execute方法
- 测试Agent对自然语言提示的处理能力
- 使用 `extract_from_agent_result` 辅助函数从Agent响应中提取数据
- 支持多种响应格式（ToolMessage、AIMessage、直接dict等）
- 如果Agent框架不可用，fallback到直接方法调用

**结果提取**：
由于Agent可能返回多种格式的响应，使用 `extract_from_agent_result` 辅助函数：
- 检查ToolMessage内容
- 检查AIMessage内容
- 检查直接dict访问
- 支持JSON解析
- 包含多个fallback机制

**测试覆盖**：
集成测试应覆盖：
- Agent的execute方法（自然语言提示）
- Agent的直接方法调用
- Agent之间的协作
- 工作流中的Agent调用

### 状态管理

- 每个测试应该是独立的
- 使用fixtures进行setup/teardown
- 在fixtures中清理资源

### 不稳定测试

- 避免时间相关的测试
- 使用确定性Mock
- 标记不稳定测试并调查原因

### Self-Refine机制测试

- 测试CaseChecker的review功能
- 测试失败时的反馈机制
- 测试重试逻辑（最多N次）
- 验证反馈是否正确传递回CaseDeveloper

## 命名约定

- 测试文件：`test_*.py`
- 测试类：`Test*`
- 测试函数：`test_*`
- Fixtures：`*_fixture` 或描述性名称

## 持续集成

测试应在CI/CD流水线中运行：

- **每次提交**：运行单元测试
- **PR时**：运行单元测试 + 集成测试
- **合并到main**：运行所有测试，包括E2E测试

## 覆盖率目标

- **总体**：>80%代码覆盖率
- **关键路径**：>90%覆盖率
- **单元测试**：>80%覆盖率，覆盖所有业务逻辑
- **集成测试**：覆盖所有API端点和主要工作流节点
- **E2E测试**：覆盖关键用户工作流

## 最佳实践

1. ✅ **AAA模式**：Arrange（准备）、Act（执行）、Assert（断言）
2. ✅ **描述性名称**：清晰的测试名称
3. ✅ **单一断言**：每个测试一个概念
4. ✅ **快速测试**：保持单元测试快速
5. ✅ **隔离性**：测试之间不应相互依赖
6. ✅ **Mock外部**：Mock所有外部依赖
7. ✅ **测试边界情况**：测试错误条件
8. ✅ **维护测试**：保持测试最新
9. ✅ **测试Agent execute**：集成测试中测试Agent的execute方法
10. ✅ **健壮的结果提取**：使用辅助函数处理多种响应格式
11. ✅ **使用Fixtures**：使用fixtures进行通用设置
12. ✅ **具体断言**：使用具体的断言，而不是通用断言
13. ✅ **资源清理**：在fixtures中清理资源

## 反模式避免

1. ❌ 测试实现细节
2. ❌ 测试之间共享可变状态
3. ❌ 慢速单元测试
4. ❌ 需要手动设置的测试
5. ❌ 忽略不稳定测试
6. ❌ 测试框架代码
7. ❌ 过度Mock（测试Mock而非代码）
8. ❌ 硬编码Agent响应格式（应使用辅助函数处理多种格式）

## 持续改进

1. **监控覆盖率**：跟踪覆盖率趋势
2. **审查测试**：定期进行测试代码审查
3. **重构**：保持测试可维护性
4. **文档**：记录复杂的测试场景
5. **性能**：监控测试执行时间
