# QAgent Backend

Backend service for QAgent - Automated E2E test generation from PRs.

## Architecture

- **FastAPI**: Web framework for API endpoints
- **LangGraph**: Multi-agent orchestration and workflow management
- **MCP Tools**: Model Context Protocol tools (high/mid/low level)
- **Business Agents**: Requirement analysis, test design, case development
- **Infrastructure**: Sandbox management, workspace management, GitHub integration

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment:
```bash
cp .env.example .env
# Edit .env with your API keys and configuration
# Set LLM_PROVIDER to "openai" or "anthropic"
# Configure corresponding API keys (OPENAI_API_KEY or ANTHROPIC_API_KEY)
```

3. Run the application:

**Option 1: Using the startup script (Recommended)**
```bash
cd backend
./start.sh
```

**Option 2: Manual start**
```bash
cd backend
uvicorn app.main:app --reload
```

The startup script (`start.sh`) will:
- Check and create `.env` file from `.env.example` if needed
- Verify Python 3.12 and pyenv qagent virtual environment
- Check and install dependencies if needed
- Validate environment configuration
- Start the FastAPI server with auto-reload

## API Endpoints

- `GET /`: Health check
- `GET /health`: Detailed health status
- `POST /api/webhooks/github`: GitHub webhook handler
- `GET /api/tasks/{task_id}`: Get task status
- `GET /api/tasks`: List tasks
- `POST /api/tasks/{task_id}/cancel`: Cancel task

## Project Structure

```
backend/
├── app/
│   ├── api/              # FastAPI routes
│   ├── agents/           # Agent implementations
│   │   ├── base.py       # Base agent class
│   │   └── business/     # Business agents
│   ├── mcp/              # MCP tools
│   │   ├── base.py       # MCP tool base
│   │   ├── servers/      # MCP server
│   │   └── tools/        # Tool implementations
│   ├── orchestration/    # LangGraph workflows
│   ├── infrastructure/   # Infrastructure services
│   ├── models/           # Data models
│   ├── config.py         # Configuration
│   └── main.py           # FastAPI app
├── requirements.txt
└── README.md
```

## Development

The workflow is orchestrated using LangGraph:

1. PR received → Initialize
2. Create sandbox → Check permissions
3. Clone repository → Analyze requirements
4. Detect test framework → Design tests
5. Develop cases → Run tests
6. Check results → Create PR → Complete

**Test Framework Detection**: After analyzing requirements, the system automatically detects the existing test framework (Playwright, Cypress, Selenium, etc.) in the project. If no framework is found, it defaults to Playwright.

