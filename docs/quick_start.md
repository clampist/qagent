# 快速开始指南

本指南将帮助你在5分钟内启动并运行QAgent。

## 前置要求

- Python 3.12+
- pyenv (推荐，用于虚拟环境管理)
- Git
- 至少一个LLM API密钥（OpenAI 或 Anthropic）

## 1. 克隆项目

```bash
git clone <repository-url>
cd QAgent
```

## 2. 配置环境

### 2.1 创建虚拟环境（使用pyenv）

```bash
# 安装Python 3.12（如果还没有）
pyenv install 3.12.7

# 创建qagent虚拟环境
pyenv virtualenv 3.12.7 qagent

# 激活虚拟环境
pyenv activate qagent
```

### 2.2 配置环境变量

```bash
cd backend
cp .env.example .env
```

编辑 `.env` 文件，至少配置以下内容：

```bash
# 选择LLM提供商：openai 或 anthropic
LLM_PROVIDER=openai

# OpenAI配置（如果使用OpenAI）
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
OPENAI_TEMPERATURE=0.7

# Anthropic配置（如果使用Anthropic）
ANTHROPIC_API_KEY=your_anthropic_api_key_here
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
ANTHROPIC_TEMPERATURE=0.7

# GitHub配置（必需）
GITHUB_TOKEN=your_github_token_here

# LangSmith配置（可选，用于可观测性）
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_langsmith_api_key_here
LANGSMITH_PROJECT=qagent
```

## 3. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

## 4. 启动服务

### 方式1：使用启动脚本（推荐）

```bash
cd backend
./start.sh
```

启动脚本会自动：
- 检查并创建`.env`文件
- 验证Python环境和虚拟环境
- 检查并安装依赖
- 验证环境配置
- 启动FastAPI服务

### 方式2：手动启动

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

服务启动后，访问：
- API文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

## 5. 配置GitHub Webhook

### 5.1 在目标仓库中配置Webhook

1. 进入目标GitHub仓库
2. 进入 Settings → Webhooks → Add webhook
3. 配置如下：
   - **Payload URL**: `http://your-server:8000/api/webhooks/github`
   - **Content type**: `application/json`
   - **Events**: 选择 `Pull requests` 和 `Pushes`
   - **Secret**: (可选) 如果设置了`GITHUB_WEBHOOK_SECRET`，需要在这里配置相同的secret

### 5.2 测试Webhook

```bash
# 使用提供的测试脚本
cd backend
./test_webhook.sh
```

或者手动发送测试请求：

```bash
curl -X POST http://localhost:8000/api/webhooks/github \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: pull_request" \
  -d '{
    "action": "opened",
    "pull_request": {
      "number": 1,
      "title": "Test PR",
      "body": "Test description"
    },
    "repository": {
      "full_name": "owner/repo"
    }
  }'
```

## 6. 触发第一个工作流

### 方式1：通过GitHub PR

1. 在目标仓库创建一个PR
2. QAgent会自动接收Webhook并开始工作流
3. 查看响应中的`task_id`和`langsmith_trace_url`

### 方式2：通过API直接触发

```bash
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "pr_number": 1,
    "repo_full_name": "owner/repo"
  }'
```

## 7. 查看结果

### 7.1 查看任务状态

```bash
# 获取任务状态
curl http://localhost:8000/api/tasks/{task_id}
```

### 7.2 查看LangSmith Trace

工作流执行后，可以通过以下方式查看详细trace：

1. **立即查看**：Webhook响应中包含`langsmith_trace_url`
2. **完成后查看**：查看服务日志，会打印完整的trace URL

LangSmith trace包含：
- 每个Agent的完整对话
- LLM的输入输出
- 工具调用详情
- 执行时间和成本

### 7.3 查看生成的测试用例

工作流完成后，测试用例会生成在目标仓库的workspace中。你可以：

1. 查看生成的PR（如果配置了自动创建PR）
2. 直接查看workspace目录（通常在`/tmp/qagent_workspaces/`下）

## 8. 常见问题

### Q: 服务启动失败，提示缺少依赖？

A: 确保已安装所有依赖：
```bash
pip install -r requirements.txt
```

### Q: Webhook接收不到请求？

A: 检查：
1. 服务是否正常运行（访问 http://localhost:8000/health）
2. Webhook URL是否正确
3. 网络是否可达（如果是本地开发，需要使用ngrok等工具暴露服务）

### Q: LLM调用失败？

A: 检查：
1. API密钥是否正确配置
2. API密钥是否有足够的额度
3. 模型名称是否正确（参考 [OpenAI模型列表](docs/pricing/openai.md)）

### Q: 如何查看详细日志？

A: 日志文件位置：
- 应用日志：`backend/logs/app.log`
- 错误日志：`backend/logs/app.error.log`
- 控制台输出：直接查看启动服务的终端

### Q: 如何配置不同Agent使用不同LLM？

A: 在`.env`中配置：
```bash
# 全局默认
LLM_PROVIDER=openai

# 按Agent配置
AGENT_LLM_PROVIDERS=requirement_analyzer:openai,case_designer:anthropic,case_developer:openai
```

详细配置请参考 [LLM Provider Setup](backend/docs/LLM_PROVIDER_SETUP.md)

## 下一步

- 阅读 [项目结构说明](project_structure.md) 了解代码组织
- 查看 [后端README](backend/README.md) 了解详细功能
- 参考 [测试策略](backend/tests/README.md) 了解如何运行测试

## 获取帮助

如果遇到问题，请：
1. 查看日志文件
2. 检查LangSmith trace（如果已配置）
3. 查看相关文档
4. 提交Issue（如果适用）

