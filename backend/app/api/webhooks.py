"""GitHub webhook handlers."""
from fastapi import APIRouter, Request, HTTPException, Header
from typing import Optional
import hmac
import hashlib
import json
from app.config import settings
from app.orchestration.workflow import WorkflowManager

router = APIRouter()
workflow_manager = WorkflowManager()


async def verify_github_signature(
    payload: bytes,
    signature: Optional[str],
    secret: str
) -> bool:
    """Verify GitHub webhook signature."""
    if not signature:
        return False
    
    expected_signature = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(f"sha256={expected_signature}", signature)


@router.post("/github")
async def github_webhook(
    request: Request,
    x_github_event: str = Header(...),
    x_hub_signature_256: Optional[str] = Header(None)
):
    """Handle GitHub webhook events."""
    payload = await request.body()
    
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
            
            response = {
                "status": "accepted",
                "task_id": result["task_id"],
                "message": f"Workflow started for PR #{pr_number}"
            }
            
            # Add LangSmith trace URL if available
            if result.get("langsmith_trace_url"):
                response["langsmith_trace_url"] = result["langsmith_trace_url"]
            
            return response
    
    # Handle push events
    if x_github_event == "push":
        repo_full_name = event_data.get("repository", {}).get("full_name")
        ref = event_data.get("ref", "")
        
        # Extract branch name from ref (e.g., "refs/heads/feature/add-medium-risk" -> "feature/add-medium-risk")
        if ref.startswith("refs/heads/"):
            branch_name = ref.replace("refs/heads/", "")
            
            # Try to find PR associated with this branch
            try:
                from app.agents.business.github_agent import GithubAgent
                github_agent = GithubAgent()
                
                # Search for open PRs with this branch as head
                # Note: This requires GitHub API access. If not available, we'll skip.
                github_client = github_agent.github_client
                if github_client and github_client.client:
                    repo = github_client.client.get_repo(repo_full_name)
                    # Format: "owner:branch" for head parameter
                    owner = repo_full_name.split('/')[0]
                    pulls = repo.get_pulls(state="open", head=f"{owner}:{branch_name}")
                    
                    # Get the first matching PR (if any)
                    for pr in pulls:
                        pr_number = pr.number
                        pr_data = {
                            "number": pr.number,
                            "title": pr.title,
                            "body": pr.body,
                            "state": pr.state,
                            "head": {
                                "ref": pr.head.ref,
                                "sha": pr.head.sha
                            },
                            "base": {
                                "ref": pr.base.ref,
                                "sha": pr.base.sha
                            },
                            "user": pr.user.login if pr.user else None
                        }
                        
                        # Trigger workflow for this PR
                        result = await workflow_manager.start_pr_workflow(
                            pr_number=pr_number,
                            repo_full_name=repo_full_name,
                            pr_data=pr_data
                        )
                        
                        response = {
                            "status": "accepted",
                            "task_id": result["task_id"],
                            "message": f"Workflow started for PR #{pr_number} (triggered by push to {branch_name})"
                        }
                        
                        # Add LangSmith trace URL if available
                        if result.get("langsmith_trace_url"):
                            response["langsmith_trace_url"] = result["langsmith_trace_url"]
                        
                        return response
                    
                    # No open PR found for this branch
                    return {
                        "status": "ignored",
                        "event": x_github_event,
                        "message": f"No open PR found for branch {branch_name}"
                    }
                else:
                    # GitHub client not available, log and ignore
                    return {
                        "status": "ignored",
                        "event": x_github_event,
                        "message": "GitHub client not configured, cannot find PR for push event"
                    }
            except Exception as e:
                # Log error but don't fail the webhook
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Error processing push event: {e}")
                return {
                    "status": "ignored",
                    "event": x_github_event,
                    "message": f"Error finding PR for push event: {str(e)}"
                }
        else:
            # Not a branch push (could be tag, etc.)
            return {
                "status": "ignored",
                "event": x_github_event,
                "message": f"Push event is not for a branch: {ref}"
            }
    
    return {"status": "ignored", "event": x_github_event}


@router.get("/github/test")
async def test_webhook():
    """Test endpoint for webhook configuration."""
    return {"message": "Webhook endpoint is active"}

