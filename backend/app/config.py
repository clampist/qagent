"""Configuration management for QAgent backend."""
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings."""
    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=False
    )
    
    # API Settings
    api_title: str = "QAgent API"
    api_version: str = "0.1.0"
    debug: bool = False
    
    # LLM Provider Selection (global default)
    llm_provider: str = "openai"  # "openai" or "anthropic"
    
    # Per-Agent LLM Provider Configuration (optional, overrides global)
    # Format: "agent_name:provider" (e.g., "requirement_analyzer:openai")
    # If not specified for an agent, uses global llm_provider
    agent_llm_providers: str = ""  # Comma-separated list: "requirement_analyzer:openai,case_designer:anthropic,case_developer:openai"
    
    # OpenAI Settings
    openai_api_key: Optional[str] = None
    # Model options: gpt-5-mini, gpt-5-nano (cheapest), gpt-4o-mini, gpt-4o, o1, o3, etc.
    # See docs/pricing/openai.md for full list
    openai_model: str = "gpt-4o-mini"
    openai_temperature: float = 0.7
    # Use new Responses API instead of Chat Completions API
    use_responses_api: bool = True
    
    # Anthropic Settings
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    anthropic_temperature: float = 0.7
    
    # Test Checker Agent Settings (dedicated model for review)
    # Use a more powerful model for critical review tasks
    # Maps to ANTHROPIC_MODEL_FOR_CHECK in .env
    anthropic_model_for_check: str = "claude-3-5-opus-20241022"  # Opus for better review quality
    # Maps to ANTHROPIC_TEMPERATURE_FOR_CHECK in .env
    anthropic_temperature_for_check: float = 0.3  # Lower temperature for more consistent review
    # Maps to OPENAI_MODEL_FOR_CHECK in .env (if needed, optional)
    openai_model_for_check: Optional[str] = None  # GPT-4o for review (optional)
    # Maps to OPENAI_TEMPERATURE_FOR_CHECK in .env (if needed, optional, defaults to anthropic_temperature_for_check)
    openai_temperature_for_check: Optional[float] = None  # Temperature for OpenAI review (optional)
    
    def get_agent_provider(self, agent_name: str) -> str:
        """Get LLM provider for a specific agent.
        
        Args:
            agent_name: Name of the agent
            
        Returns:
            Provider name ("openai" or "anthropic")
        """
        if not self.agent_llm_providers:
            return self.llm_provider
        
        # Parse agent-specific providers
        for mapping in self.agent_llm_providers.split(","):
            mapping = mapping.strip()
            if ":" in mapping:
                agent, provider = mapping.split(":", 1)
                if agent.strip() == agent_name:
                    return provider.strip()
        
        # Fallback to global provider
        return self.llm_provider
    
    # GitHub Settings
    github_token: Optional[str] = None
    github_webhook_secret: Optional[str] = None
    
    # Redis Settings (for Celery)
    redis_url: str = "redis://localhost:6379/0"
    
    # Database Settings
    database_url: str = "sqlite:///./qagent.db"
    
    # Sandbox Settings
    docker_socket: str = "unix://var/run/docker.sock"
    sandbox_timeout: int = 3600  # seconds
    workspace_base_path: str = "/tmp/qagent_workspaces"
    
    # Cost Control Settings
    max_iterations: int = 10
    max_tokens_per_request: int = 100000
    
    # LangSmith Settings (for LangChain tracing)
    langsmith_tracing: Optional[str] = None  # Enable/disable tracing (e.g., "true", "false")
    langsmith_endpoint: Optional[str] = None  # LangSmith API endpoint
    langsmith_api_key: Optional[str] = None  # LangSmith API key
    langsmith_project: Optional[str] = None  # LangSmith project name


settings = Settings()

