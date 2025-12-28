"""FastAPI application entry point."""
import logging
import os
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api import webhooks, tasks

# Configure logging
def setup_logging():
    """Configure application logging with file and console handlers."""
    # Create logs directory if it doesn't exist
    logs_dir = Path(__file__).parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True)
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Clear existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_formatter = logging.Formatter(
        '[%(levelname)s] %(name)s:%(lineno)d - %(message)s'
    )
    
    # File handler with rotation (by size: 10MB, keep 5 backups)
    log_file = logs_dir / "app.log"
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(file_handler)
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # Error log file with rotation (by time: daily, keep 7 days)
    error_log_file = logs_dir / "app.error.log"
    error_file_handler = TimedRotatingFileHandler(
        error_log_file,
        when='midnight',
        interval=1,
        backupCount=7,
        encoding='utf-8'
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(error_file_handler)
    
    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info("=" * 70)
    logger.info("QAgent Backend Application Starting")
    logger.info("=" * 70)
    logger.info(f"Log file: {log_file}")
    logger.info(f"Error log file: {error_log_file}")
    logger.info(f"Log level: INFO")
    logger.info("=" * 70)

# Setup logging before creating app
setup_logging()

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    debug=settings.debug
)

logger.info(f"FastAPI app initialized: {settings.api_title} v{settings.api_version}")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["webhooks"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])

# Compatibility route for GitHub webhook (legacy URL: /github/)
# This allows GitHub webhooks configured with the old URL to still work
from fastapi import Request, Header, HTTPException
from typing import Optional

@app.api_route("/github", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
@app.api_route("/github/", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def github_webhook_compat(
    request: Request,
    x_github_event: str = Header(..., alias="X-GitHub-Event"),
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256")
):
    """Compatibility route for GitHub webhook at /github/ (forwards to /api/webhooks/github)."""
    # Use the same handler logic as the main webhook endpoint
    from app.api.webhooks import verify_github_signature
    from app.orchestration.workflow import WorkflowManager
    import json
    
    payload = await request.body()
    workflow_manager = WorkflowManager()
    
    # Verify signature if secret is configured
    if settings.github_webhook_secret:
        if not await verify_github_signature(
            payload,
            x_hub_signature_256,
            settings.github_webhook_secret
        ):
            raise HTTPException(status_code=401, detail="Invalid signature")
    
    event_data = json.loads(payload)
    
    # Handle pull request events
    if x_github_event == "pull_request":
        action = event_data.get("action")
        
        if action in ["opened", "synchronize"]:
            pr_data = event_data.get("pull_request", {})
            pr_number = pr_data.get("number")
            repo_full_name = event_data.get("repository", {}).get("full_name")
            
            # Trigger workflow
            result = await workflow_manager.start_pr_workflow(
                pr_number=pr_number,
                repo_full_name=repo_full_name,
                pr_data=pr_data
            )
            task_id = result["task_id"]
            
            return {
                "status": "accepted",
                "task_id": task_id,
                "message": f"Workflow started for PR #{pr_number}"
            }
    
    return {"status": "ignored", "event": x_github_event}


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "version": settings.api_version}


@app.get("/health")
async def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "version": settings.api_version,
        "services": {
            "api": "ok",
            "redis": "checking...",  # TODO: implement actual health checks
            "database": "checking..."
        }
    }

