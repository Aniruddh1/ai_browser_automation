"""Demo agent client that uses act/observe/extract internally."""

from typing import Dict, Any, Optional, TYPE_CHECKING, List
import logging
import asyncio
import re

from .base_multi_step_client import BaseMultiStepClient
from ..types.agent import (
    AgentType,
    AgentResult,
    AgentExecutionOptions,
    AgentAction,
    ResponseInputItem,
    StepResult,
    AgentUsageMetrics,
)

if TYPE_CHECKING:
    from ..utils.logger import PlaywrightAILogger


class DemoAgentClient(BaseMultiStepClient):
    """
    Demo agent client implementation with multi-step execution.
    
    Uses PlaywrightAI's act/observe/extract methods to demonstrate
    autonomous task execution with proper state management.
    """
    
    def __init__(
        self,
        model_name: str,
        client_options: Dict[str, Any],
        user_provided_instructions: Optional[str] = None,
        logger: Optional['PlaywrightAILogger'] = None,
    ):
        """
        Initialize demo agent client.
        
        Args:
            model_name: Model to use
            client_options: Client configuration
            user_provided_instructions: Additional instructions
            logger: Logger instance
        """
        super().__init__("openai", model_name, user_provided_instructions)
        self.client_options = client_options
        self.logger = logger or logging.getLogger(__name__)
        self._page = None  # Will be set by handler
    
    def set_page(self, page: Any) -> None:
        """Set the page instance for act/observe/extract."""
        self._page = page
    
    async def execute_step(
        self,
        input_items: List[ResponseInputItem],
        previous_response_id: Optional[str],
        logger: 'PlaywrightAILogger'
    ) -> StepResult:
        """
        Execute a single step with multi-step reasoning.
        
        Args:
            input_items: Conversation history
            previous_response_id: Not used in demo
            logger: Logger instance
            
        Returns:
            Step result
        """
        if not self._page:
            return StepResult(
                actions=[],
                message="No page instance available",
                completed=True,
                next_input_items=input_items,
                response_id=None,
                usage=AgentUsageMetrics(input_tokens=0, output_tokens=0, inference_time_ms=0)
            )
        
        # Extract current state from conversation
        state = self._extract_state(input_items)
        instruction = state.get('instruction', '')
        previous_actions = state.get('previous_actions', [])
        
        # Plan next action based on current state
        actions: List[AgentAction] = []
        message = ""
        completed = False
        next_input_items = list(input_items)
        
        try:
            # Analyze what needs to be done next
            if self._needs_search_box(state):
                # Observe to find search box
                self._log_info("agent:demo", "Looking for search box")
                elements = await self._page.observe("Find the search box")
                
                if elements:
                    actions.append({
                        "type": "observe",
                        "description": "Found search box",
                        "success": True
                    })
                    message = "Found search box on page"
                    
                    # Add observation result to conversation
                    next_input_items.append({
                        "type": "tool_result",
                        "content": "Found search box element on the page"
                    })
                else:
                    message = "Could not find search box"
                    completed = True
                    
            elif self._needs_click_search(state):
                # Click on search box
                self._log_info("agent:demo", "Clicking search box")
                await self._page.act("Click on the search box")
                
                actions.append({
                    "type": "click",
                    "target": "search box",
                    "success": True
                })
                message = "Clicked on search box"
                
                next_input_items.append({
                    "type": "tool_result",
                    "content": "Clicked on search box, ready for input"
                })
                
            elif self._needs_type_query(state):
                # Type search query
                query = self._extract_search_query(instruction)
                if query:
                    self._log_info("agent:demo", f"Typing search query: {query}")
                    await self._page.act(f"Type '{query}'")
                    
                    actions.append({
                        "type": "type",
                        "text": query,
                        "success": True
                    })
                    message = f"Typed search query: {query}"
                    
                    next_input_items.append({
                        "type": "tool_result",
                        "content": f"Typed '{query}' in search box"
                    })
                    
            elif self._needs_submit(state):
                # Submit search
                self._log_info("agent:demo", "Submitting search")
                await self._page.act("Press Enter")
                
                actions.append({
                    "type": "key",
                    "key": "Enter",
                    "success": True
                })
                message = "Search submitted successfully"
                completed = True
                
                # Wait for results
                await asyncio.sleep(1)
                
            elif self._needs_navigation(state):
                # Handle navigation
                url = self._extract_url(instruction)
                if url:
                    self._log_info("agent:demo", f"Navigating to {url}")
                    await self._page.goto(url)
                    
                    actions.append({
                        "type": "navigate",
                        "url": url,
                        "success": True
                    })
                    message = f"Navigated to {url}"
                    
                    # Check if more actions needed after navigation
                    if "search" not in instruction.lower():
                        completed = True
                    else:
                        next_input_items.append({
                            "type": "tool_result",
                            "content": f"Successfully navigated to {url}"
                        })
                        
            else:
                # Default action
                self._log_info("agent:demo", "Executing default action")
                result = await self._page.act(instruction)
                
                actions.append({
                    "type": "action",
                    "description": instruction,
                    "success": result.success
                })
                message = result.description or "Action completed"
                completed = True
                
        except Exception as e:
            self._log_error("agent:demo", f"Error in step: {e}")
            message = f"Error: {str(e)}"
            completed = True
        
        return StepResult(
            actions=actions,
            message=message,
            completed=completed,
            next_input_items=next_input_items,
            response_id=None,
            usage=AgentUsageMetrics(
                input_tokens=len(str(input_items)),
                output_tokens=len(message),
                inference_time_ms=100
            )
        )
    
    def create_initial_input_items(self, instruction: str) -> List[ResponseInputItem]:
        """
        Create initial conversation items.
        
        Args:
            instruction: User instruction
            
        Returns:
            Initial input items
        """
        items: List[ResponseInputItem] = []
        
        # Add system message if we have instructions
        if self.user_provided_instructions:
            items.append({
                "role": "system",
                "content": self.user_provided_instructions
            })
        
        # Add user instruction
        items.append({
            "role": "user",
            "content": instruction
        })
        
        return items
    
    async def get_action(
        self,
        input_items: List[ResponseInputItem],
        previous_response_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get next action from analysis of current state.
        
        This is a simplified version that analyzes the conversation
        to determine the next action.
        """
        # Not used in demo - actions are determined in execute_step
        return {"actions": []}
    
    async def take_action(
        self,
        output: List[Any],
        logger: 'PlaywrightAILogger'
    ) -> List[ResponseInputItem]:
        """
        Execute actions and prepare results.
        
        This is handled directly in execute_step for the demo.
        """
        # Not used in demo - actions are executed in execute_step
        return []
    
    def _extract_search_query(self, instruction: str) -> Optional[str]:
        """Extract search query from instruction."""
        # Simple extraction - look for quoted text
        quoted = re.findall(r"['\"]([^'\"]+)['\"]", instruction)
        if quoted:
            return quoted[0]
        
        # Or extract after "for"
        if " for " in instruction:
            return instruction.split(" for ", 1)[1].strip()
        
        # Or extract after "search"
        if "search" in instruction.lower():
            parts = instruction.lower().split("search")
            if len(parts) > 1:
                return parts[1].strip().strip("'\"")
        
        return None
    
    def _extract_state(self, input_items: List[ResponseInputItem]) -> Dict[str, Any]:
        """Extract current state from conversation history."""
        state = {
            "instruction": "",
            "previous_actions": [],
            "last_result": None
        }
        
        for item in input_items:
            if item.get("role") == "user" and item.get("content"):
                # Get the original instruction
                if not state["instruction"]:
                    state["instruction"] = str(item["content"])
            elif item.get("type") == "tool_result":
                # Track previous results
                state["last_result"] = item.get("content")
                
                # Parse actions from results
                content = str(item.get("content", "")).lower()
                if "found search box" in content:
                    state["previous_actions"].append("observe")
                elif "clicked" in content:
                    state["previous_actions"].append("click")
                elif "typed" in content:
                    state["previous_actions"].append("type")
                elif "navigated" in content:
                    state["previous_actions"].append("navigate")
        
        return state
    
    def _needs_search_box(self, state: Dict[str, Any]) -> bool:
        """Check if we need to find search box."""
        instruction = state.get("instruction", "").lower()
        previous = state.get("previous_actions", [])
        
        return (
            "search" in instruction and
            "observe" not in previous and
            "navigate" not in instruction
        )
    
    def _needs_click_search(self, state: Dict[str, Any]) -> bool:
        """Check if we need to click search box."""
        previous = state.get("previous_actions", [])
        last_result = str(state.get("last_result", "")).lower()
        
        return (
            "observe" in previous and
            "click" not in previous and
            "found search box" in last_result
        )
    
    def _needs_type_query(self, state: Dict[str, Any]) -> bool:
        """Check if we need to type search query."""
        previous = state.get("previous_actions", [])
        last_result = str(state.get("last_result", "")).lower()
        
        return (
            "click" in previous and
            "type" not in previous and
            ("clicked" in last_result or "ready for input" in last_result)
        )
    
    def _needs_submit(self, state: Dict[str, Any]) -> bool:
        """Check if we need to submit search."""
        previous = state.get("previous_actions", [])
        last_result = str(state.get("last_result", "")).lower()
        
        return (
            "type" in previous and
            "typed" in last_result
        )
    
    def _needs_navigation(self, state: Dict[str, Any]) -> bool:
        """Check if we need to navigate."""
        instruction = state.get("instruction", "").lower()
        previous = state.get("previous_actions", [])
        
        return (
            ("navigate" in instruction or "go to" in instruction) and
            "navigate" not in previous
        )
    
    def _extract_url(self, instruction: str) -> Optional[str]:
        """Extract URL from instruction."""
        instruction_lower = instruction.lower()
        
        # Check for common sites
        if "github" in instruction_lower:
            return "https://github.com"
        elif "google" in instruction_lower:
            return "https://google.com"
        elif "stackoverflow" in instruction_lower:
            return "https://stackoverflow.com"
        
        # Look for URLs
        url_pattern = re.compile(r'https?://[^\s]+')  
        urls = url_pattern.findall(instruction)
        if urls:
            return urls[0]
        
        return None
    
    async def capture_screenshot(self, options: Optional[Dict[str, Any]] = None) -> Any:
        """
        Capture a screenshot.
        
        Args:
            options: Screenshot options
            
        Returns:
            Screenshot data
        """
        if self._screenshot_provider:
            return await self._screenshot_provider()
        return None