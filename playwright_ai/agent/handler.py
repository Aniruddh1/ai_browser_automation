"""Agent handler for PlaywrightAIPage integration."""

import asyncio
from typing import Union, TYPE_CHECKING, Optional, Dict, Any
import base64

from ..types.agent import (
    AgentExecuteOptions,
    AgentResult,
    AgentHandlerOptions,
    AgentAction,
    ActionExecutionResult,
)
from .provider import AgentProvider
from .ai_browser_automation_agent import PlaywrightAIAgent
from .client import AgentClient

if TYPE_CHECKING:
    from ..core.playwright_ai import PlaywrightAI
    from ..core.page import PlaywrightAIPage
    from ..utils.logger import PlaywrightAILogger


class AgentHandler:
    """
    Handler for agent operations on a page.
    
    Integrates agent functionality with PlaywrightAIPage.
    """
    
    def __init__(
        self,
        playwright_ai: 'PlaywrightAI',
        ai_browser_automation_page: 'PlaywrightAIPage',
        logger: 'PlaywrightAILogger',
        options: AgentHandlerOptions,
    ):
        """
        Initialize agent handler.
        
        Args:
            playwright_ai: PlaywrightAI instance
            ai_browser_automation_page: PlaywrightAIPage instance
            logger: Logger instance
            options: Handler configuration options
        """
        self.playwright_ai = playwright_ai
        self.ai_browser_automation_page = ai_browser_automation_page
        self.logger = logger
        self.options = options
        
        # Initialize provider
        self.provider = AgentProvider(logger)
        
        # Create client
        self.agent_client = self.provider.get_client(
            model_name=options.model_name,
            client_options=options.client_options,
            user_provided_instructions=options.user_provided_instructions,
        )
        
        # Setup client
        self._setup_agent_client()
        
        # If using demo client, set the page
        if hasattr(self.agent_client, 'set_page'):
            self.agent_client.set_page(ai_browser_automation_page)
        
        # Create agent
        self.agent = PlaywrightAIAgent(self.agent_client, logger)
    
    def _setup_agent_client(self) -> None:
        """Set up agent client with page-specific functionality."""
        # Set up screenshot provider
        async def screenshot_provider() -> str:
            """Take screenshot and return as base64."""
            screenshot_bytes = await self.ai_browser_automation_page.screenshot(full_page=False)
            return base64.b64encode(screenshot_bytes).decode('utf-8')
        
        self.agent_client.set_screenshot_provider(screenshot_provider)
        
        # Set up action handler
        async def action_handler(action: AgentAction) -> None:
            """Execute an action on the page."""
            # Default delay between actions
            default_delay = 1000
            wait_between_actions = (
                self.options.client_options.get('wait_between_actions', default_delay)
                if self.options.client_options
                else default_delay
            )
            
            try:
                # Try to inject cursor before action
                try:
                    await self._inject_cursor()
                except Exception:
                    # Ignore cursor injection failures
                    pass
                
                # Small delay before action for visibility
                await asyncio.sleep(0.5)
                
                # Execute the action
                await self._execute_action(action)
                
                # Delay after action
                await asyncio.sleep(wait_between_actions / 1000)
                
                # Take screenshot after action
                try:
                    await self._capture_and_send_screenshot()
                except Exception as e:
                    self.logger.warn(
                        "agent",
                        f"Failed to take screenshot after action: {e}. Continuing execution."
                    )
            
            except Exception as e:
                self.logger.error(
                    "agent",
                    f"Error executing action {action['type']}: {e}"
                )
                raise
        
        self.agent_client.set_action_handler(action_handler)
        
        # Update viewport and URL
        self._update_client_viewport()
        self._update_client_url()
    
    async def execute(
        self,
        options_or_instruction: Union[AgentExecuteOptions, str]
    ) -> AgentResult:
        """
        Execute a task with the agent.
        
        Args:
            options_or_instruction: Task options or instruction string
            
        Returns:
            Agent execution result
        """
        # Convert string to options if needed
        if isinstance(options_or_instruction, str):
            options = AgentExecuteOptions(instruction=options_or_instruction)
        else:
            options = options_or_instruction
        
        # Redirect to Google if page is empty
        current_url = self.ai_browser_automation_page.url
        if not current_url or current_url == "about:blank":
            self.logger.info(
                "agent",
                "Page URL is empty or about:blank. Redirecting to www.google.com..."
            )
            await self.ai_browser_automation_page.goto("https://www.google.com")
        
        self.logger.info(
            "agent",
            f"Executing agent task: {options.instruction}"
        )
        
        # Execute through agent
        return await self.agent.execute(options)
    
    async def _execute_action(self, action: AgentAction) -> ActionExecutionResult:
        """
        Execute a single action on the page.
        
        Args:
            action: Action to execute
            
        Returns:
            Action execution result
        """
        try:
            action_type = action.get('type', '').lower()
            
            if action_type == 'click':
                # Enhanced click with position and button support
                x = action.get('x')
                y = action.get('y')
                button = action.get('button', 'left')
                selector = action.get('selector')
                
                if x is not None and y is not None:
                    # Update cursor position first
                    await self._update_cursor_position(x, y)
                    # Animate the click
                    await self._animate_click(x, y)
                    # Small delay to see animation
                    await asyncio.sleep(0.3)
                    # Perform actual click
                    await self.ai_browser_automation_page.mouse.click(x, y, button=button)
                elif selector:
                    await self.ai_browser_automation_page.click(selector)
                else:
                    raise ValueError("Click action requires either x/y coordinates or selector")
                    
            elif action_type in ['double_click', 'doubleclick']:
                # Double click support
                x = action.get('x', 0)
                y = action.get('y', 0)
                
                # Update cursor position
                await self._update_cursor_position(x, y)
                # Animate both clicks
                await self._animate_click(x, y)
                await asyncio.sleep(0.2)
                await self._animate_click(x, y)
                await asyncio.sleep(0.2)
                # Perform double click
                await self.ai_browser_automation_page.mouse.dblclick(x, y)
                
            elif action_type == 'type':
                # Type text
                text = action.get('text', '')
                await self.ai_browser_automation_page.keyboard.type(text)
                
            elif action_type == 'fill':
                # Fill form field
                selector = action.get('selector', '')
                text = action.get('text', '')
                if selector:
                    await self.ai_browser_automation_page.fill(selector, text)
                else:
                    # If no selector, just type
                    await self.ai_browser_automation_page.keyboard.type(text)
                    
            elif action_type in ['key', 'keypress']:
                # Handle key press
                key = action.get('key') or action.get('text', '')
                keys = action.get('keys', [])
                
                if keys:
                    # Handle multiple keys
                    for k in keys:
                        mapped_key = self._convert_key_name(k)
                        await self.ai_browser_automation_page.keyboard.press(mapped_key)
                elif key:
                    # Single key
                    mapped_key = self._convert_key_name(key)
                    await self.ai_browser_automation_page.keyboard.press(mapped_key)
                    
            elif action_type == 'scroll':
                # Enhanced scroll with x/y support
                x = action.get('x', 0)
                y = action.get('y', 0)
                scroll_x = action.get('scroll_x', 0)
                scroll_y = action.get('scroll_y', 0)
                
                # Move to position first
                if x or y:
                    await self.ai_browser_automation_page.mouse.move(x, y)
                
                # Scroll
                if scroll_x or scroll_y:
                    await self.ai_browser_automation_page.evaluate(
                        f"window.scrollBy({scroll_x}, {scroll_y})"
                    )
                elif action.get('direction'):
                    # Legacy direction-based scrolling
                    direction = action.get('direction', 'down')
                    amount = action.get('amount', 100)
                    if direction == 'down':
                        await self.ai_browser_automation_page.evaluate(f"window.scrollBy(0, {amount})")
                    elif direction == 'up':
                        await self.ai_browser_automation_page.evaluate(f"window.scrollBy(0, -{amount})")
                    elif direction == 'right':
                        await self.ai_browser_automation_page.evaluate(f"window.scrollBy({amount}, 0)")
                    elif direction == 'left':
                        await self.ai_browser_automation_page.evaluate(f"window.scrollBy(-{amount}, 0)")
                        
            elif action_type == 'drag':
                # Drag with path support
                path = action.get('path', [])
                if len(path) >= 2:
                    start = path[0]
                    
                    # Update cursor for start
                    await self._update_cursor_position(start['x'], start['y'])
                    await self.ai_browser_automation_page.mouse.move(start['x'], start['y'])
                    await self.ai_browser_automation_page.mouse.down()
                    
                    # Move through path
                    for point in path[1:]:
                        await self._update_cursor_position(point['x'], point['y'])
                        await self.ai_browser_automation_page.mouse.move(point['x'], point['y'])
                    
                    await self.ai_browser_automation_page.mouse.up()
                else:
                    raise ValueError("Drag action requires path with at least 2 points")
                    
            elif action_type == 'move':
                # Move cursor
                x = action.get('x', 0)
                y = action.get('y', 0)
                await self._update_cursor_position(x, y)
                await self.ai_browser_automation_page.mouse.move(x, y)
                
            elif action_type == 'wait':
                # Wait action
                timeout = action.get('timeout', 1000)
                await asyncio.sleep(timeout / 1000)
                
            elif action_type == 'screenshot':
                # Screenshot is handled automatically by agent client
                await self._capture_and_send_screenshot()
                
            elif action_type in ['navigate', 'goto']:
                # Navigation
                url = action.get('url', '')
                await self.ai_browser_automation_page.goto(url)
                self._update_client_url()
                
            elif action_type == 'function':
                # Function calls
                name = action.get('name', '')
                args = action.get('arguments', {})
                
                if name == 'goto' and 'url' in args:
                    await self.ai_browser_automation_page.goto(args['url'])
                    self._update_client_url()
                elif name == 'back':
                    await self.ai_browser_automation_page.go_back()
                    self._update_client_url()
                elif name == 'forward':
                    await self.ai_browser_automation_page.go_forward()
                    self._update_client_url()
                elif name == 'reload':
                    await self.ai_browser_automation_page.reload()
                    self._update_client_url()
                else:
                    raise ValueError(f"Unsupported function: {name}")
                    
            else:
                raise ValueError(f"Unknown action type: {action_type}")
            
            return ActionExecutionResult(success=True)
            
        except Exception as e:
            self.logger.error(
                "agent",
                f"Error executing action {action.get('type', 'unknown')}: {e}"
            )
            return ActionExecutionResult(
                success=False,
                error=str(e)
            )
    
    async def _inject_cursor(self) -> None:
        """Inject cursor visualization into the page."""
        try:
            # Define constants for cursor and highlight element IDs
            CURSOR_ID = "playwright_ai-cursor"
            HIGHLIGHT_ID = "playwright_ai-highlight"
            
            # Check if cursor already exists
            cursor_exists = await self.ai_browser_automation_page.evaluate(
                f"!!document.getElementById('{CURSOR_ID}')"
            )
            
            if cursor_exists:
                return
            
            # Inject cursor and highlight elements
            await self.ai_browser_automation_page.evaluate(f"""
            (function() {{
                // Create cursor element
                const cursor = document.createElement('div');
                cursor.id = '{CURSOR_ID}';
                
                // Use SVG for custom cursor
                cursor.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" version="1.1" viewBox="0 0 28 28" width="28" height="28">
                    <polygon fill="#000000" points="9.2,7.3 9.2,18.5 12.2,15.6 12.6,15.5 17.4,15.5"/>
                    <rect x="12.5" y="13.6" transform="matrix(0.9221 -0.3871 0.3871 0.9221 -5.7605 6.5909)" width="2" height="8" fill="#000000"/>
                </svg>
                `;
                
                // Style the cursor
                cursor.style.position = 'absolute';
                cursor.style.top = '0';
                cursor.style.left = '0';
                cursor.style.width = '28px';
                cursor.style.height = '28px';
                cursor.style.pointerEvents = 'none';
                cursor.style.zIndex = '9999999';
                cursor.style.transform = 'translate(-4px, -4px)';
                
                // Create highlight element for click animation
                const highlight = document.createElement('div');
                highlight.id = '{HIGHLIGHT_ID}';
                highlight.style.position = 'absolute';
                highlight.style.width = '20px';
                highlight.style.height = '20px';
                highlight.style.borderRadius = '50%';
                highlight.style.backgroundColor = 'rgba(66, 134, 244, 0)';
                highlight.style.transform = 'translate(-50%, -50%) scale(0)';
                highlight.style.pointerEvents = 'none';
                highlight.style.zIndex = '9999998';
                highlight.style.transition = 'transform 0.3s ease-out, opacity 0.3s ease-out';
                highlight.style.opacity = '0';
                
                // Add elements to document
                document.body.appendChild(cursor);
                document.body.appendChild(highlight);
                
                // Add functions to window
                window.__updateCursorPosition = function(x, y) {{
                    if (cursor) {{
                        cursor.style.transform = `translate(${{x - 4}}px, ${{y - 4}}px)`;
                    }}
                }};
                
                window.__animateClick = function(x, y) {{
                    if (highlight) {{
                        highlight.style.left = `${{x}}px`;
                        highlight.style.top = `${{y}}px`;
                        highlight.style.transform = 'translate(-50%, -50%) scale(1)';
                        highlight.style.opacity = '1';
                        
                        setTimeout(() => {{
                            highlight.style.transform = 'translate(-50%, -50%) scale(0)';
                            highlight.style.opacity = '0';
                        }}, 300);
                    }}
                }};
            }})();
            """)
            
            self.logger.info(
                "agent",
                "Cursor injected for visual feedback"
            )
        except Exception as e:
            self.logger.info(
                "agent",
                f"Failed to inject cursor: {e}"
            )
    
    async def _capture_and_send_screenshot(self) -> None:
        """Capture and send screenshot to agent."""
        if self.agent_client._screenshot_provider:
            screenshot = await self.agent_client._screenshot_provider()
            # Screenshot is automatically used by the agent client
    
    def _update_client_viewport(self) -> None:
        """Update agent client with current viewport size."""
        viewport = self.ai_browser_automation_page.viewport_size
        if viewport:
            self.agent_client.set_viewport(viewport['width'], viewport['height'])
    
    def _update_client_url(self) -> None:
        """Update agent client with current page URL."""
        url = self.ai_browser_automation_page.url
        self.agent_client.set_current_url(url)
    
    async def _update_cursor_position(self, x: float, y: float) -> None:
        """Update cursor position on the page."""
        try:
            await self.ai_browser_automation_page.evaluate(
                f"""
                if (window.__updateCursorPosition) {{
                    window.__updateCursorPosition({x}, {y});
                }}
                """
            )
        except:
            # Silently fail if cursor update fails
            pass
    
    async def _animate_click(self, x: float, y: float) -> None:
        """Animate a click at the given position."""
        try:
            await self.ai_browser_automation_page.evaluate(
                f"""
                if (window.__animateClick) {{
                    window.__animateClick({x}, {y});
                }}
                """
            )
        except:
            # Silently fail if animation fails
            pass
    
    def _convert_key_name(self, key: str) -> str:
        """Convert key names to Playwright format."""
        # Map of common key names
        key_map = {
            "ENTER": "Enter",
            "RETURN": "Enter",
            "ESCAPE": "Escape",
            "ESC": "Escape",
            "BACKSPACE": "Backspace",
            "TAB": "Tab",
            "SPACE": " ",
            "ARROWUP": "ArrowUp",
            "ARROWDOWN": "ArrowDown",
            "ARROWLEFT": "ArrowLeft",
            "ARROWRIGHT": "ArrowRight",
            "UP": "ArrowUp",
            "DOWN": "ArrowDown",
            "LEFT": "ArrowLeft",
            "RIGHT": "ArrowRight",
            "DELETE": "Delete",
            "DEL": "Delete",
            "HOME": "Home",
            "END": "End",
            "PAGEUP": "PageUp",
            "PAGEDOWN": "PageDown",
            "SHIFT": "Shift",
            "CONTROL": "Control",
            "CTRL": "Control",
            "ALT": "Alt",
            "META": "Meta",
            "COMMAND": "Meta",
            "CMD": "Meta",
        }
        
        # Convert to uppercase for case-insensitive matching
        upper_key = key.upper()
        
        # Return mapped key or original
        return key_map.get(upper_key, key)