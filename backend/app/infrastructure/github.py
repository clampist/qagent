"""GitHub client for repository operations."""
from typing import Dict, Any, Optional
from github import Github, Auth
from app.config import settings


class GitHubClient:
    """GitHub API client."""
    
    def __init__(self):
        self.client = None
        if settings.github_token:
            auth = Auth.Token(settings.github_token)
            self.client = Github(auth=auth)
    
    async def get_pr(self, repo_full_name: str, pr_number: int) -> Dict[str, Any]:
        """Get PR information."""
        if not self.client:
            return {}
        
        try:
            repo = self.client.get_repo(repo_full_name)
            pr = repo.get_pull(pr_number)
            
            return {
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
        except Exception as e:
            return {"error": str(e)}
    
    async def create_pr(
        self,
        repo_full_name: str,
        title: str,
        body: str,
        head: str,
        base: str = "main"
    ) -> Dict[str, Any]:
        """Create a new pull request."""
        if not self.client:
            return {"error": "GitHub client not initialized"}
        
        try:
            repo = self.client.get_repo(repo_full_name)
            pr = repo.create_pull(
                title=title,
                body=body,
                head=head,
                base=base
            )
            
            return {
                "success": True,
                "number": pr.number,
                "url": pr.html_url,
                "state": pr.state
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def check_permissions(
        self,
        repo_full_name: str,
        required_permissions: list = None
    ) -> Dict[str, Any]:
        """Check repository permissions."""
        if not self.client:
            return {"has_permission": False, "error": "GitHub client not initialized"}
        
        try:
            repo = self.client.get_repo(repo_full_name)
            user = self.client.get_user()
            
            # Check if user has access
            permissions = repo.permissions
            
            required = required_permissions or ["read", "write"]
            has_permission = all(
                getattr(permissions, perm, False) for perm in required
            )
            
            return {
                "has_permission": has_permission,
                "permissions": {
                    "admin": permissions.admin,
                    "push": permissions.push,
                    "pull": permissions.pull
                }
            }
        except Exception as e:
            return {"has_permission": False, "error": str(e)}

