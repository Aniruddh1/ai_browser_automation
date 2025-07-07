"""Intelligent demo agent client with dynamic decision making."""

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


class IntelligentDemoClient(BaseMultiStepClient):
    """
    Intelligent demo agent that simulates AI-based decision making.
    
    This implementation analyzes page state and makes dynamic decisions
    similar to how the real OpenAI/Anthropic agents work.
    """
    
    def __init__(
        self,
        model_name: str,
        client_options: Dict[str, Any],
        user_provided_instructions: Optional[str] = None,
        logger: Optional['PlaywrightAILogger'] = None,
    ):
        """Initialize intelligent demo client."""
        super().__init__("demo", model_name, user_provided_instructions)
        self.client_options = client_options
        self._logger = logger or logging.getLogger(__name__)
        self._page = None
        self._current_state = {}
        self._action_history = []
    
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
        Execute a single step with intelligent decision making.
        
        This simulates how a real AI agent would:
        1. Analyze the current page state
        2. Understand what has been done so far
        3. Decide the next best action
        4. Execute and verify the action
        """
        if not self._page:
            return self._create_error_result("No page instance available")
        
        try:
            # Extract instruction and conversation history
            instruction = self._extract_instruction(input_items)
            conversation = self._build_conversation_context(input_items)
            
            # Analyze current page state (simulate screenshot analysis)
            page_analysis = await self._analyze_page_state()
            
            # Make intelligent decision about next action
            decision = await self._decide_next_action(
                instruction, 
                conversation, 
                page_analysis
            )
            
            # Execute the decided action
            if decision['action'] == 'complete':
                return self._create_completion_result(decision['message'])
            
            action_result = await self._execute_decided_action(decision)
            
            # Create response
            return StepResult(
                actions=[action_result['action']],
                message=action_result['message'],
                completed=False,
                next_input_items=self._create_next_input_items(
                    input_items, 
                    action_result
                ),
                response_id=None,
                usage=self._calculate_usage()
            )
            
        except Exception as e:
            self._log_error("agent:intelligent", f"Error in step: {e}")
            return self._create_error_result(str(e))
    
    async def _analyze_page_state(self) -> Dict[str, Any]:
        """
        Analyze current page state (simulates screenshot analysis).
        
        In a real implementation, this would:
        1. Take a screenshot
        2. Send it to an AI model
        3. Get back understanding of what's on the page
        
        For demo, we use act/observe to understand the page.
        """
        state = {
            'url': self._page.url if hasattr(self._page, 'url') else 'unknown',
            'title': '',
            'has_search_box': False,
            'has_results': False,
            'elements': []
        }
        
        # Get page title
        try:
            title = await self._page.evaluate("document.title")
            state['title'] = title
        except:
            pass
        
        # Check for common elements
        try:
            # Look for search box
            search_elements = await self._page.observe("search box, search input, search field")
            state['has_search_box'] = bool(search_elements)
            
            # Look for results
            result_elements = await self._page.observe("search results, result items, product listings")
            state['has_results'] = bool(result_elements)
            
            # Get visible elements
            visible_elements = await self._page.observe("clickable elements, buttons, links")
            state['elements'] = visible_elements or []
            
        except Exception as e:
            self._log_info("agent:intelligent", f"Error analyzing page: {e}")
        
        return state
    
    async def _decide_next_action(
        self, 
        instruction: str, 
        conversation: List[Dict[str, str]], 
        page_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Make intelligent decision about next action.
        
        This simulates AI reasoning by:
        1. Understanding the goal
        2. Checking current progress
        3. Deciding best next step
        """
        instruction_lower = instruction.lower()
        url = page_state.get('url', '').lower()
        
        # Parse instruction to understand the task
        task_components = self._parse_instruction(instruction)
        
        # Check what we've already done
        completed_actions = self._get_completed_actions(conversation)
        
        # Decision tree based on task and state
        
        # 1. Do we need to navigate somewhere first?
        if task_components['target_site'] and task_components['target_site'] not in url:
            return {
                'action': 'navigate',
                'target': task_components['target_site'],
                'reason': f"Need to go to {task_components['target_site']} first"
            }
        
        # 2. Do we need to search for something?
        if task_components['search_query'] and 'searched' not in completed_actions:
            # Are we on the right page?
            if task_components['target_site'] and task_components['target_site'] in url:
                # Do we see a search box?
                if page_state['has_search_box']:
                    # Have we clicked the search box?
                    if 'clicked_search' not in completed_actions:
                        return {
                            'action': 'click_search',
                            'reason': "Need to click search box before typing"
                        }
                    # Have we typed the query?
                    elif 'typed_query' not in completed_actions:
                        return {
                            'action': 'type_query',
                            'query': task_components['search_query'],
                            'reason': f"Type search query: {task_components['search_query']}"
                        }
                    # Have we submitted?
                    elif 'submitted_search' not in completed_actions:
                        return {
                            'action': 'submit_search',
                            'reason': "Submit the search"
                        }
                else:
                    # No search box visible, might need to look for it
                    return {
                        'action': 'find_search',
                        'reason': "Looking for search functionality"
                    }
        
        # 3. Do we need to click on results?
        if task_components['click_result'] and page_state['has_results']:
            if 'clicked_result' not in completed_actions:
                return {
                    'action': 'click_result',
                    'position': task_components.get('result_position', 'first'),
                    'reason': "Click on search result"
                }
        
        # 4. Do we need to add to cart?
        if task_components['add_to_cart'] and 'added_to_cart' not in completed_actions:
            return {
                'action': 'add_to_cart',
                'reason': "Add item to cart"
            }
        
        # 5. Generic action execution
        if not any(completed_actions):
            return {
                'action': 'execute_generic',
                'instruction': instruction,
                'reason': "Execute the instruction directly"
            }
        
        # If we get here, task might be complete
        return {
            'action': 'complete',
            'message': "Task completed successfully"
        }
    
    def _parse_instruction(self, instruction: str) -> Dict[str, Any]:
        """Parse instruction to understand task components."""
        instruction_lower = instruction.lower()
        
        components = {
            'target_site': None,
            'search_query': None,
            'click_result': False,
            'result_position': 'first',
            'add_to_cart': False,
            'navigate_only': False
        }
        
        # Extract target site
        site_patterns = {
            'github': 'https://github.com',
            'google': 'https://google.com',
            'amazon': 'https://amazon.com',
            'stackoverflow': 'https://stackoverflow.com'
        }
        
        for site, url in site_patterns.items():
            if site in instruction_lower:
                components['target_site'] = url
                break
        
        # Extract explicit URLs
        url_match = re.search(r'https?://[^\s]+', instruction)
        if url_match:
            components['target_site'] = url_match.group(0)
        
        # Extract search query
        search_patterns = [
            r"search for ['\"]?([^'\"]+)['\"]?",
            r"search ['\"]?([^'\"]+)['\"]?",
            r"find ['\"]?([^'\"]+)['\"]?",
            r"look for ['\"]?([^'\"]+)['\"]?"
        ]
        
        for pattern in search_patterns:
            match = re.search(pattern, instruction_lower)
            if match:
                components['search_query'] = match.group(1).strip()
                # Clean up query
                if ' and ' in components['search_query']:
                    components['search_query'] = components['search_query'].split(' and ')[0]
                break
        
        # Check for click instructions
        if 'click' in instruction_lower:
            components['click_result'] = True
            if 'first' in instruction_lower:
                components['result_position'] = 'first'
            elif 'second' in instruction_lower:
                components['result_position'] = 'second'
        
        # Check for cart operations
        if 'add to cart' in instruction_lower or 'cart' in instruction_lower:
            components['add_to_cart'] = True
        
        # Check if it's just navigation
        if ('go to' in instruction_lower or 'navigate' in instruction_lower) and \
           not components['search_query'] and not components['click_result']:
            components['navigate_only'] = True
        
        return components
    
    def _get_completed_actions(self, conversation: List[Dict[str, str]]) -> List[str]:
        """Extract what actions have been completed from conversation."""
        completed = []
        
        for item in conversation:
            content = item.get('content', '').lower()
            
            if 'navigated to' in content:
                completed.append('navigated')
            if 'found search box' in content:
                completed.append('found_search')
            if 'clicked on search box' in content or 'clicked search box' in content:
                completed.append('clicked_search')
            if 'typed' in content and 'search' in content:
                completed.append('typed_query')
            if 'search submitted' in content or 'submitted search' in content:
                completed.append('submitted_search')
            if 'searched for' in content:
                completed.append('searched')
            if 'clicked on' in content and 'result' in content:
                completed.append('clicked_result')
            if 'added to cart' in content:
                completed.append('added_to_cart')
        
        return completed
    
    async def _execute_decided_action(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the action decided by our analysis."""
        action_type = decision['action']
        
        try:
            if action_type == 'navigate':
                url = decision['target']
                await self._page.goto(url)
                return {
                    'action': AgentAction(type='navigate', url=url, success=True),
                    'message': f"Navigated to {url}",
                    'success': True
                }
            
            elif action_type == 'find_search':
                elements = await self._page.observe("Find search box or search input")
                success = bool(elements)
                return {
                    'action': AgentAction(type='observe', description='Find search box', success=success),
                    'message': "Found search box" if success else "Could not find search box",
                    'success': success
                }
            
            elif action_type == 'click_search':
                await self._page.act("Click on the search box")
                return {
                    'action': AgentAction(type='click', target='search box', success=True),
                    'message': "Clicked on search box",
                    'success': True
                }
            
            elif action_type == 'type_query':
                query = decision['query']
                await self._page.act(f"Type '{query}'")
                return {
                    'action': AgentAction(type='type', text=query, success=True),
                    'message': f"Typed search query: {query}",
                    'success': True
                }
            
            elif action_type == 'submit_search':
                await self._page.act("Press Enter")
                await asyncio.sleep(1)  # Wait for results
                return {
                    'action': AgentAction(type='key', key='Enter', success=True),
                    'message': "Search submitted",
                    'success': True
                }
            
            elif action_type == 'click_result':
                position = decision.get('position', 'first')
                await self._page.act(f"Click on the {position} search result")
                return {
                    'action': AgentAction(type='click', target=f'{position} result', success=True),
                    'message': f"Clicked on {position} result",
                    'success': True
                }
            
            elif action_type == 'add_to_cart':
                await self._page.act("Click on 'Add to Cart' button")
                return {
                    'action': AgentAction(type='click', target='Add to Cart', success=True),
                    'message': "Added item to cart",
                    'success': True
                }
            
            elif action_type == 'execute_generic':
                result = await self._page.act(decision['instruction'])
                return {
                    'action': AgentAction(
                        type='action', 
                        description=decision['instruction'],
                        success=result.success
                    ),
                    'message': result.description or "Action completed",
                    'success': result.success
                }
            
            else:
                return {
                    'action': AgentAction(type='unknown', success=False),
                    'message': f"Unknown action type: {action_type}",
                    'success': False
                }
                
        except Exception as e:
            return {
                'action': AgentAction(type=action_type, success=False, error=str(e)),
                'message': f"Error executing {action_type}: {str(e)}",
                'success': False
            }
    
    def _extract_instruction(self, input_items: List[ResponseInputItem]) -> str:
        """Extract the original instruction from input items."""
        for item in input_items:
            if item.get('role') == 'user' and item.get('content'):
                return str(item['content'])
        return ""
    
    def _build_conversation_context(self, input_items: List[ResponseInputItem]) -> List[Dict[str, str]]:
        """Build conversation context from input items."""
        conversation = []
        
        for item in input_items:
            if item.get('role'):
                conversation.append({
                    'role': item['role'],
                    'content': str(item.get('content', ''))
                })
            elif item.get('type') == 'tool_result':
                conversation.append({
                    'role': 'assistant',
                    'content': str(item.get('content', ''))
                })
        
        return conversation
    
    def _create_next_input_items(
        self, 
        current_items: List[ResponseInputItem], 
        action_result: Dict[str, Any]
    ) -> List[ResponseInputItem]:
        """Create input items for next step."""
        next_items = list(current_items)
        
        # Add the result of this action
        next_items.append({
            'type': 'tool_result',
            'content': action_result['message']
        })
        
        return next_items
    
    def _create_completion_result(self, message: str) -> StepResult:
        """Create a completion result."""
        return StepResult(
            actions=[],
            message=message,
            completed=True,
            next_input_items=[],
            response_id=None,
            usage=self._calculate_usage()
        )
    
    def _create_error_result(self, error: str) -> StepResult:
        """Create an error result."""
        return StepResult(
            actions=[],
            message=f"Error: {error}",
            completed=True,
            next_input_items=[],
            response_id=None,
            usage=self._calculate_usage()
        )
    
    def _calculate_usage(self) -> AgentUsageMetrics:
        """Calculate simulated usage metrics."""
        return AgentUsageMetrics(
            input_tokens=100,
            output_tokens=50,
            inference_time_ms=200
        )
    
    def create_initial_input_items(self, instruction: str) -> List[ResponseInputItem]:
        """Create initial conversation items."""
        items: List[ResponseInputItem] = []
        
        if self.user_provided_instructions:
            items.append({
                'role': 'system',
                'content': self.user_provided_instructions
            })
        
        items.append({
            'role': 'user',
            'content': instruction
        })
        
        return items
    
    async def get_action(
        self,
        input_items: List[ResponseInputItem],
        previous_response_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Not used in this implementation."""
        return {'actions': []}
    
    async def take_action(
        self,
        output: List[Any],
        logger: 'PlaywrightAILogger'
    ) -> List[ResponseInputItem]:
        """Not used in this implementation."""
        return []
    
    async def capture_screenshot(self, options: Optional[Dict[str, Any]] = None) -> str:
        """
        Capture a screenshot.
        
        Args:
            options: Screenshot options
            
        Returns:
            Screenshot data URL
        """
        if self._screenshot_provider:
            base64_image = await self._screenshot_provider()
            return f"data:image/png;base64,{base64_image}"
        return "data:image/png;base64,placeholder"