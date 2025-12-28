"""Base agent class."""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from app.config import settings
from app.mcp.servers.mcp_server import mcp_server
import logging

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Base class for all agents."""
    
    def __init__(
        self, 
        name: str, 
        description: str, 
        llm_provider: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None
    ):
        self.name = name
        self.description = description
        self.mcp_server = mcp_server
        
        # Determine LLM provider
        # Use explicit parameter if provided, otherwise use global default
        provider = llm_provider if llm_provider else settings.llm_provider
        
        # Initialize LLM based on provider
        if provider.lower() == "anthropic":
            if not settings.anthropic_api_key:
                logger.warning("Anthropic API key not set, falling back to OpenAI")
                provider = "openai"
            else:
                # Use custom model name if provided, otherwise use default
                model = model_name or settings.anthropic_model
                temp = temperature if temperature is not None else settings.anthropic_temperature
                
                self.llm = ChatAnthropic(
                    model=model,
                    temperature=temp,
                    api_key=settings.anthropic_api_key
                )
                logger.info(f"Initialized {name} agent with Anthropic ({model})")
                return  # Early return to avoid OpenAI initialization
        
        if provider.lower() == "openai" or not hasattr(self, 'llm'):
            if not settings.openai_api_key:
                raise ValueError("OpenAI API key is required when using OpenAI provider")
            
            # Use custom model name if provided, otherwise use default
            model = model_name or settings.openai_model
            temp = temperature if temperature is not None else settings.openai_temperature
            
            self.llm = ChatOpenAI(
                model=model,
                temperature=temp,
                api_key=settings.openai_api_key,
                use_responses_api=settings.use_responses_api
            )
            api_type = "Responses API" if settings.use_responses_api else "Chat Completions API"
            logger.info(f"Initialized {name} agent with OpenAI ({model}) using {api_type}")
    
    async def call_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Call an MCP tool."""
        return await self.mcp_server.call_tool(tool_name, **kwargs)
    
    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute agent's main task."""
        pass
    
    def _format_prompt(self, system_prompt: str, user_prompt: str) -> str:
        """Format prompt for LLM."""
        return f"{system_prompt}\n\n{user_prompt}"
    
    async def _llm_call(self, prompt: str, **kwargs) -> str:
        """Make LLM call."""
        # Both OpenAI and Anthropic use the same message format in LangChain
        messages = [{"role": "user", "content": prompt}]
        response = await self.llm.ainvoke(messages)
        
        # Debug: Log response type and content
        logger.debug(f"LLM response type: {type(response.content)}")
        logger.debug(f"LLM response content (first 500 chars): {str(response.content)[:500]}")
        
        # Handle case where response.content might be a list (OpenAI Responses API)
        if isinstance(response.content, list):
            logger.warning("LLM returned content as list, extracting text content")
            
            # OpenAI Responses API returns a list of content blocks
            # Example: [{'type': 'reasoning', ...}, {'type': 'text', 'text': '...'}]
            # We need to extract the 'text' field from the text block
            
            text_content = ""
            for item in response.content:
                if isinstance(item, dict):
                    # Look for text content
                    if item.get('type') == 'text' and 'text' in item:
                        text_content += item['text']
                    # Some formats might have content in other fields
                    elif 'content' in item:
                        text_content += str(item['content'])
                elif isinstance(item, str):
                    text_content += item
            
            if text_content:
                logger.info(f"Extracted text content from list (length: {len(text_content)})")
                return text_content
            else:
                # Fallback: if no text content found, try to convert to JSON
                logger.warning("No text content found in list, converting entire list to JSON")
                import json
                return json.dumps(response.content)
        
        return response.content
    
    def _get_langchain_tool_decorator(self):
        """Get LangChain tool decorator (supports multiple versions).
        
        Returns:
            tool decorator function, or None if langchain is not available
        """
        try:
            # Try langchain_core.tools first (LangChain 1.x)
            from langchain_core.tools import tool
            return tool
        except ImportError:
            try:
                # Fallback to langchain.tools (older versions)
                from langchain.tools import tool
                return tool
            except ImportError:
                logger.warning("langchain tools not available, tools will not be created")
                return None
    
    def _create_langchain_agent(self, tools: list, system_prompt: str, llm_provider: Optional[str] = None):
        """Create LangChain agent with tools.
        
        Args:
            tools: List of LangChain tools
            system_prompt: System prompt for the agent
            llm_provider: LLM provider name (optional, uses self.llm if not provided)
            
        Returns:
            LangChain agent instance, or None if creation fails
        """
        if not tools:
            logger.info(f"{self.name} initialized without LangChain agent framework (tools not available, using direct method calls)")
            return None
        
        try:
            from langchain.agents import create_agent
            
            # Try to create agent with model string format (like reference example)
            model_str = f"{llm_provider or 'openai'}:{self.llm.model if hasattr(self.llm, 'model') else 'gpt-4o-mini'}"
            try:
                agent = create_agent(
                    model=model_str,
                    tools=tools,
                    system_prompt=system_prompt
                )
                logger.info(f"{self.name} initialized with LangChain agent framework")
                return agent
            except (TypeError, ValueError, AttributeError) as e:
                # Fallback: try with LLM object directly
                try:
                    agent = create_agent(
                        model=self.llm,
                        tools=tools,
                        system_prompt=system_prompt
                    )
                    logger.info(f"{self.name} initialized with LangChain agent framework")
                    return agent
                except Exception as e2:
                    logger.warning(f"Could not create LangChain agent with LLM object: {e2}. Using direct method calls only.")
                    return None
        except (ImportError, Exception) as e:
            logger.warning(f"Could not create LangChain agent: {e}. Using direct method calls only.")
            return None

