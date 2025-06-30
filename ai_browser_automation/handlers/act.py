"""ActHandler implementation for executing browser actions."""

import asyncio
from typing import Union, Dict, Any, Optional, Callable, TYPE_CHECKING

from .base import BaseHandler
from ..types import (
    ActOptions,
    ActResult,
    ObserveResult,
    ActionType,
    LLMMessage,
)
from ..core.errors import ActionFailedError, ElementNotFoundError
from ..dom import wait_for_selector_stable
from .utils.act_utils import perform_playwright_method, clean_selector

if TYPE_CHECKING:
    from ..core.page import AIBrowserAutomationPage


class ActHandler(BaseHandler[ActResult]):
    """
    Handler for executing actions on web pages.
    
    Supports natural language instructions and specific action execution
    with self-healing capabilities.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Method handler mapping
        self.method_handlers: Dict[str, Callable] = {
            ActionType.CLICK: self._handle_click,
            ActionType.FILL: self._handle_fill,
            ActionType.TYPE: self._handle_type,
            ActionType.PRESS: self._handle_press,
            ActionType.SCROLL: self._handle_scroll,
            ActionType.HOVER: self._handle_hover,
            ActionType.DRAG: self._handle_drag,
            ActionType.SCREENSHOT: self._handle_screenshot,
            ActionType.WAIT: self._handle_wait,
            ActionType.NAVIGATE: self._handle_navigate,
        }
    
    async def handle(
        self,
        page: 'AIBrowserAutomationPage',
        action_or_options: Union[str, ActOptions, ObserveResult]
    ) -> ActResult:
        """
        Execute an action on the page.
        
        Args:
            page: AIBrowserAutomationPage instance
            action_or_options: Action specification
            
        Returns:
            ActResult with execution details
        """
        # Parse input into ActOptions
        options = self._parse_action_input(action_or_options)
        
        self._log_info(
            "Executing action",
            action=options.action,
            instruction=isinstance(action_or_options, str) and action_or_options or None,
        )
        
        try:
            # If we have an ObserveResult, execute directly
            if isinstance(action_or_options, ObserveResult):
                return await self._execute_from_observe_result(page, action_or_options, options)
            
            # Otherwise, observe first then act
            return await self._execute_with_observation(page, action_or_options, options)
            
        except Exception as e:
            self._log_error(f"Action failed: {e}", error=str(e))
            return ActResult(
                success=False,
                action=options.action or ActionType.CLICK,
                error=str(e)
            )
    
    def _parse_action_input(
        self,
        action_or_options: Union[str, ActOptions, ObserveResult]
    ) -> ActOptions:
        """Parse various input formats into ActOptions."""
        if isinstance(action_or_options, ActOptions):
            return action_or_options
        
        if isinstance(action_or_options, ObserveResult):
            # Extract action from ObserveResult
            return ActOptions(
                action=action_or_options.action or ActionType.CLICK
            )
        
        # String input - parse for action hints
        instruction = action_or_options.lower()
        original_instruction = action_or_options  # Keep original for value extraction
        action = None
        variable_values = {}
        
        if any(word in instruction for word in ["click", "tap", "press"]):
            action = ActionType.CLICK
        elif any(word in instruction for word in ["type", "fill", "enter", "input"]):
            action = ActionType.FILL
            # Try to extract the text to fill
            import re
            # Look for text in quotes
            quoted_match = re.search(r"['\"]([^'\"]+)['\"]", original_instruction)
            if quoted_match:
                variable_values["value"] = quoted_match.group(1)
            else:
                # Look for text after "with"
                with_match = re.search(r"with\s+(.+?)(?:\s+and|\s+then|$)", original_instruction, re.IGNORECASE)
                if with_match:
                    variable_values["value"] = with_match.group(1).strip()
        elif any(word in instruction for word in ["scroll"]):
            action = ActionType.SCROLL
        elif any(word in instruction for word in ["hover", "mouse over"]):
            action = ActionType.HOVER
        elif any(word in instruction for word in ["wait", "pause"]):
            action = ActionType.WAIT
        elif any(word in instruction for word in ["navigate", "go to", "visit"]):
            action = ActionType.NAVIGATE
        
        return ActOptions(action=action, variable_values=variable_values if variable_values else None)
    
    async def _execute_from_observe_result(
        self,
        page: 'AIBrowserAutomationPage',
        observe_result: ObserveResult,
        options: ActOptions
    ) -> ActResult:
        """Execute action from an ObserveResult."""
        selector = observe_result.selector
        
        # Use method from observe result if available, otherwise map action to method
        if observe_result.method:
            # Use the specific Playwright method from observe
            method = observe_result.method
            arguments = observe_result.arguments or []
            
            self._log_debug(
                "Executing Playwright method from observe result",
                selector=selector,
                method=method,
                arguments=arguments,
            )
            
            # Use improved method handling from utilities
            cleaned_selector = clean_selector(selector)
            
            try:
                await perform_playwright_method(
                    page=page._page,  # Get the raw Playwright page
                    method=method,
                    selector=cleaned_selector,
                    args=arguments,
                    logger=self.logger,
                    dom_settle_timeout=30000,
                )
            except Exception as e:
                self._log_error(f"Method execution failed: {e}", error=str(e))
                raise ActionFailedError(method, str(e))
            
            # Map method back to action type for result
            action_map = {
                "fill": ActionType.FILL,
                "type": ActionType.FILL,
                "click": ActionType.CLICK,
                "press": ActionType.CLICK,
                "hover": ActionType.HOVER,
                "scrollIntoView": ActionType.SCROLL,
            }
            action = action_map.get(method, ActionType.CLICK)
            
            return ActResult(
                success=True,
                action=action,
                selector=selector,
                description=observe_result.description,
                metadata={"method": method, "arguments": arguments}
            )
        else:
            # Fallback to old behavior using action handlers
            action = observe_result.action or options.action or ActionType.CLICK
            
            self._log_debug(
                "Executing from observe result (legacy)",
                selector=selector,
                action=action,
            )
            
            # Get handler for action
            handler = self.method_handlers.get(action)
            if not handler:
                raise ActionFailedError(
                    str(action),
                    f"Unsupported action type: {action}"
                )
            
            # Execute action
            await handler(page, selector, options)
            
            return ActResult(
                success=True,
                action=action,
                selector=selector,
                description=observe_result.description,
            )
    
    async def _execute_with_observation(
        self,
        page: 'AIBrowserAutomationPage',
        instruction: Union[str, ActOptions],
        options: ActOptions
    ) -> ActResult:
        """Execute action by first observing the page."""
        # Convert to string instruction
        if isinstance(instruction, ActOptions):
            instruction_str = f"Find element to {options.action or 'interact with'}"
        else:
            instruction_str = instruction
        
        self._log_debug("Observing page for action", instruction=instruction_str)
        
        # Note: Combined actions like "fill X and click Y" should be handled by the user
        # by calling act() twice, once for each action
        
        # Observe the page with act-specific options
        observe_results = await page.observe(
            instruction=instruction_str,
            model_name=options.model_name,
            return_action=True,
            from_act=True
        )
        
        if not observe_results:
            raise ElementNotFoundError("", instruction_str)
        
        # Use the first result
        observe_result = observe_results[0]
        
        # Execute the action
        return await self._execute_from_observe_result(page, observe_result, options)
    
    async def _attempt_self_healing(
        self,
        page: 'AIBrowserAutomationPage',
        original_instruction: str,
        options: ActOptions,
        original_error: Exception
    ) -> ActResult:
        """Attempt to self-heal when action fails."""
        self._log_info(
            "Attempting self-healing",
            original_error=str(original_error)
        )
        
        # Re-observe with more context
        healing_instruction = f"{original_instruction}. Previous attempt failed: {original_error}"
        
        try:
            return await self._execute_with_observation(page, healing_instruction, options)
        except Exception as e:
            # Self-healing failed
            return ActResult(
                success=False,
                action=options.action or ActionType.CLICK,
                error=f"Original: {original_error}. Self-healing: {e}",
                metadata={"self_healing_attempted": True}
            )
    
    # Action method handlers
    
    async def _handle_click(
        self,
        page: 'AIBrowserAutomationPage',
        selector: str,
        options: ActOptions
    ) -> None:
        """Handle click action using improved JavaScript-based click."""
        cleaned_selector = clean_selector(selector)
        
        # Use the improved click handling from utilities
        await perform_playwright_method(
            page=page._page,
            method="click",
            selector=cleaned_selector,
            args=[],
            logger=self.logger,
            dom_settle_timeout=options.timeout or 30000,
        )
    
    async def _handle_fill(
        self,
        page: 'AIBrowserAutomationPage',
        selector: str,
        options: ActOptions
    ) -> None:
        """Handle fill action."""
        # Need to get the fill value
        if options.variable_values and "value" in options.variable_values:
            value = options.variable_values["value"]
        else:
            # For now, use a placeholder
            value = "test input"
        
        # Wait for element
        await wait_for_selector_stable(page._page, selector, timeout=options.timeout)
        
        # Fill the element
        await page.fill(selector, value)
    
    async def _handle_type(
        self,
        page: 'AIBrowserAutomationPage',
        selector: str,
        options: ActOptions
    ) -> None:
        """Handle type action."""
        # Similar to fill but types character by character
        if options.variable_values and "text" in options.variable_values:
            text = options.variable_values["text"]
        else:
            text = "test input"
        
        await wait_for_selector_stable(page._page, selector, timeout=options.timeout)
        await page.type(selector, text)
    
    async def _handle_press(
        self,
        page: 'AIBrowserAutomationPage',
        selector: str,
        options: ActOptions
    ) -> None:
        """Handle key press action."""
        key = options.variable_values.get("key", "Enter") if options.variable_values else "Enter"
        
        await wait_for_selector_stable(page._page, selector, timeout=options.timeout)
        await page.press(selector, key)
    
    async def _handle_scroll(
        self,
        page: 'AIBrowserAutomationPage',
        selector: str,
        options: ActOptions
    ) -> None:
        """Handle scroll action."""
        # Scroll the element into view
        await page.evaluate(f"""
            document.querySelector('{selector}')?.scrollIntoView({{
                behavior: 'smooth',
                block: 'center'
            }});
        """)
        
        # Wait a bit for scroll to complete
        await asyncio.sleep(0.5)
    
    async def _handle_hover(
        self,
        page: 'AIBrowserAutomationPage',
        selector: str,
        options: ActOptions
    ) -> None:
        """Handle hover action."""
        await wait_for_selector_stable(page._page, selector, timeout=options.timeout)
        await page.hover(selector)
    
    async def _handle_drag(
        self,
        page: 'AIBrowserAutomationPage',
        selector: str,
        options: ActOptions
    ) -> None:
        """Handle drag action."""
        # This would need source and target coordinates
        # For now, just raise not implemented
        raise ActionFailedError("drag", "Drag action not yet implemented")
    
    async def _handle_screenshot(
        self,
        page: 'AIBrowserAutomationPage',
        selector: str,
        options: ActOptions
    ) -> None:
        """Handle screenshot action."""
        # Take screenshot of specific element
        element = await page.wait_for_selector(selector)
        if element:
            await element.screenshot()
    
    async def _handle_wait(
        self,
        page: 'AIBrowserAutomationPage',
        selector: str,
        options: ActOptions
    ) -> None:
        """Handle wait action."""
        # Wait for element to appear
        await page.wait_for_selector(selector, timeout=options.timeout)
    
    async def _handle_navigate(
        self,
        page: 'AIBrowserAutomationPage',
        selector: str,  # Not used for navigate
        options: ActOptions
    ) -> None:
        """Handle navigation action."""
        if options.variable_values and "url" in options.variable_values:
            url = options.variable_values["url"]
            await page.goto(url)
        else:
            raise ActionFailedError("navigate", "No URL provided for navigation")
    
