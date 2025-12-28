#!/bin/bash
# QAgent Backend Startup Script
# This script starts the FastAPI backend server with proper environment setup

# Don't use set -e here, we'll handle errors manually
# set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}QAgent Backend Startup${NC}"
echo -e "${GREEN}========================================${NC}"

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Warning: .env file not found${NC}"
    if [ -f ".env.example" ]; then
        echo -e "${YELLOW}Copying .env.example to .env...${NC}"
        cp .env.example .env || {
            echo -e "${RED}Error: Failed to copy .env.example${NC}"
            exit 1
        }
        echo -e "${YELLOW}Please edit .env file with your API keys and configuration${NC}"
    else
        echo -e "${RED}Error: .env.example not found. Please create .env file manually.${NC}"
        exit 1
    fi
fi

# Check Python version
echo -e "\n${GREEN}Checking Python environment...${NC}"
if ! command -v python3.12 &> /dev/null; then
    echo -e "${RED}Error: python3.12 not found${NC}"
    exit 1
fi
PYTHON_VERSION=$(python3.12 --version 2>&1 | awk '{print $2}')
echo -e "Python version: ${GREEN}$PYTHON_VERSION${NC}"

# Check if pyenv qagent environment exists
if command -v pyenv &> /dev/null; then
    if pyenv versions | grep -q "qagent"; then
        echo -e "Activating pyenv qagent environment...${NC}"
        eval "$(pyenv init -)"
        pyenv activate qagent 2>/dev/null || {
            # If activate doesn't work, set local version
            pyenv local qagent
            eval "$(pyenv init -)"
        }
        echo -e "${GREEN}✓ Using qagent virtual environment${NC}"
    else
        echo -e "${YELLOW}Warning: qagent virtual environment not found${NC}"
        echo -e "${YELLOW}Creating qagent virtual environment...${NC}"
        pyenv virtualenv 3.12.7 qagent
        pyenv local qagent
        eval "$(pyenv init -)"
        echo -e "${GREEN}✓ Created and activated qagent virtual environment${NC}"
    fi
fi

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ] && [ -z "$PYENV_VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}Warning: No virtual environment detected${NC}"
    echo -e "${YELLOW}Continuing with system Python...${NC}"
fi

# Check if dependencies are installed
echo -e "\n${GREEN}Checking dependencies...${NC}"
if ! python3.12 -c "import uvicorn" 2>/dev/null; then
    echo -e "${YELLOW}Dependencies not installed. Installing from requirements.txt...${NC}"
    pip install -r requirements.txt
    echo -e "${GREEN}✓ Dependencies installed${NC}"
else
    echo -e "${GREEN}✓ Dependencies check passed${NC}"
fi

# Check required environment variables
echo -e "\n${GREEN}Checking environment configuration...${NC}"
# Load .env file safely (export variables without executing commands)
if [ -f ".env" ]; then
    set -a  # Automatically export all variables
    # Source .env but ignore any errors
    source .env 2>/dev/null || true
    set +a  # Stop automatically exporting
fi

# Check for at least one LLM API key
if [ -z "$OPENAI_API_KEY" ] && [ -z "$ANTHROPIC_API_KEY" ]; then
    echo -e "${YELLOW}Warning: Neither OPENAI_API_KEY nor ANTHROPIC_API_KEY is set${NC}"
    echo -e "${YELLOW}Please set at least one in .env file${NC}"
fi

# Check GitHub token
if [ -z "$GITHUB_TOKEN" ]; then
    echo -e "${YELLOW}Warning: GITHUB_TOKEN is not set${NC}"
    echo -e "${YELLOW}GitHub integration features will be limited${NC}"
fi

# Create logs directory if it doesn't exist
if [ ! -d "logs" ]; then
    mkdir -p logs
    echo -e "${GREEN}✓ Created logs directory${NC}"
fi

# Start the server
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}Starting QAgent Backend Server${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "Server will be available at: ${GREEN}http://localhost:8000${NC}"
echo -e "API docs will be available at: ${GREEN}http://localhost:8000/docs${NC}"
echo -e "\n${GREEN}Logging Configuration:${NC}"
echo -e "  - Application logs: ${GREEN}logs/app.log${NC} (rotates at 10MB, keeps 5 backups)"
echo -e "  - Error logs: ${GREEN}logs/app.error.log${NC} (daily rotation, keeps 7 days)"
echo -e "  - Console output: ${GREEN}Enabled${NC}"
echo -e "\nPress ${YELLOW}Ctrl+C${NC} to stop the server\n"

# Start uvicorn with reload for development
exec python3.12 -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    --log-level debug

