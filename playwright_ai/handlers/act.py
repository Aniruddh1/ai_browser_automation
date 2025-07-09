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
    from ..core.page import PlaywrightAIPage


class ActHandler(BaseHandler[ActResult]):
    """
    Handler for executing actions on web pages.
    
    Supports natural language instructions and specific action execution
    with self-healing capabilities.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Extract self_heal configuration
        self.self_heal = kwargs.get('self_heal', True)
        self.max_retries = kwargs.get('max_retries', 3)
        
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
        page: 'PlaywrightAIPage',
        action_or_options: Union[str, ActOptions, ObserveResult]
    ) -> ActResult:
        """
        Execute an action on the page.
        
        Args:
            page: PlaywrightAIPage instance
            action_or_options: Action specification
            
        Returns:
            ActResult with execution details
        """
        # Parse input into ActOptions
        options = self._parse_action_input(action_or_options)
        
        # Determine the action string for logging
        if isinstance(action_or_options, str):
            action_str = action_or_options
        elif isinstance(action_or_options, ObserveResult):
            action_str = action_or_options.description or "act from ObserveResult"
        else:
            action_str = f"{options.action or 'perform action'}"
        
        # Log the action start
        self.logger.log({
            "category": "act",
            "message": f"starting action: {action_str}",
            "level": 1,
            "auxiliary": {
                "action": {"value": action_str, "type": "string"},
                "method": {"value": str(options.action) if options.action else "unknown", "type": "string"}
            }
        })
        
        # Wait for DOM to settle before acting (matching observe handler)
        await page._wait_for_settled_dom()
        
        try:
            # If we have an ObserveResult, execute directly
            if isinstance(action_or_options, ObserveResult):
                self.logger.log({
                    "category": "act",
                    "message": "executing from ObserveResult",
                    "level": 2,
                    "auxiliary": {
                        "selector": {"value": action_or_options.selector, "type": "string"},
                        "method": {"value": action_or_options.method or "unknown", "type": "string"}
                    }
                })
                return await self._execute_from_observe_result(page, action_or_options, options, retry_count=0)
            
            # Otherwise, observe first then act
            self.logger.log({
                "category": "act",
                "message": "observing page before action",
                "level": 2,
                "auxiliary": {
                    "instruction": {"value": action_str, "type": "string"}
                }
            })
            return await self._execute_with_observation(page, action_or_options, options)
            
        except Exception as e:
            self.logger.log({
                "category": "act", 
                "message": "action failed",
                "level": 1,
                "auxiliary": {
                    "error": {"value": str(e), "type": "string"},
                    "action": {"value": action_str, "type": "string"}
                }
            })
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
        page: 'PlaywrightAIPage',
        observe_result: ObserveResult,
        options: ActOptions,
        retry_count: int = 0
    ) -> ActResult:
        """Execute action from an ObserveResult with self-healing."""
        selector = observe_result.selector
        
        # Use method from observe result if available, otherwise map action to method
        if observe_result.method:
            # Check if method is supported
            if observe_result.method == "not-supported":
                self._log_warning(
                    "Cannot execute ObserveResult with unsupported method",
                    method=observe_result.method
                )
                return ActResult(
                    success=False,
                    action=options.action or ActionType.CLICK,
                    error=f"The method '{observe_result.method}' is not supported",
                    description=observe_result.description
                )
            
            # Use the specific Playwright method from observe
            method = observe_result.method
            arguments = observe_result.arguments or []
            
            self.logger.log({
                "category": "act",
                "message": f"performing {method}",
                "level": 1,
                "auxiliary": {
                    "method": {"value": method, "type": "string"},
                    "selector": {"value": selector, "type": "string"},
                    "arguments": {"value": str(arguments), "type": "object"}
                }
            })
            
            # Use improved method handling from utilities
            cleaned_selector = clean_selector(selector)
            
            try:
                await perform_playwright_method(
                    page=page._page,  # Get the raw Playwright page
                    method=method,
                    selector=cleaned_selector,
                    args=arguments,
                    logger=self.logger,
                    dom_settle_timeout=options.dom_settle_timeout or 30000,
                )
                
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
                
            except Exception as e:
                self._log_error(f"Method execution failed: {e}", error=str(e))
                
                # Self-healing: if enabled and not at max retries, try again
                if self.self_heal and retry_count < self.max_retries:
                    self._log_info(
                        "Attempting self-healing",
                        retry_count=retry_count + 1,
                        max_retries=self.max_retries,
                        original_error=str(e)
                    )
                    
                    # Try re-observing and acting with the description
                    return await self._attempt_self_healing(
                        page=page,
                        original_instruction=observe_result.description,
                        options=options,
                        original_error=e,
                        retry_count=retry_count + 1
                    )
                
                # If self-healing disabled or failed, return error
                return ActResult(
                    success=False,
                    action=options.action or ActionType.CLICK,
                    error=str(e),
                    description=observe_result.description
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
            
            try:
                # Execute action
                await handler(page, selector, options)
                
                return ActResult(
                    success=True,
                    action=action,
                    selector=selector,
                    description=observe_result.description,
                )
            except Exception as e:
                if self.self_heal and retry_count < self.max_retries:
                    return await self._attempt_self_healing(
                        page=page,
                        original_instruction=observe_result.description,
                        options=options,
                        original_error=e,
                        retry_count=retry_count + 1
                    )
                return ActResult(
                    success=False,
                    action=action,
                    error=str(e),
                    description=observe_result.description
                )
    
    async def _execute_with_observation(
        self,
        page: 'PlaywrightAIPage',
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
        from ..types import ObserveOptions
        observe_options = ObserveOptions(
            instruction=instruction_str,
            model_name=options.model_name,
            return_action=True,
            from_act=True
        )
        observe_results = await page.observe(observe_options)
        
        if not observe_results:
            raise ElementNotFoundError("", instruction_str)
        
        # Use the first result
        observe_result = observe_results[0]
        
        # Execute the action
        return await self._execute_from_observe_result(page, observe_result, options)
    
    async def _attempt_self_healing(
        self,
        page: 'PlaywrightAIPage',
        original_instruction: str,
        options: ActOptions,
        original_error: Exception,
        retry_count: int = 1
    ) -> ActResult:
        """Attempt to self-heal when action fails."""
        self._log_info(
            "Attempting self-healing",
            original_error=str(original_error),
            retry_count=retry_count
        )
        
        # Wait a bit before retrying
        await asyncio.sleep(0.5 * retry_count)  # Exponential backoff
        
        # Refresh the page state
        await page._wait_for_settled_dom()
        
        # Build a more specific instruction based on the error
        if "timeout" in str(original_error).lower():
            healing_instruction = f"{original_instruction}. The element might be loading slowly or hidden. Look for alternative ways to perform this action."
        elif "not found" in str(original_error).lower() or "no element" in str(original_error).lower():
            healing_instruction = f"{original_instruction}. The element was not found. Look for similar elements or alternative ways to achieve this action."
        elif "not clickable" in str(original_error).lower() or "intercepted" in str(original_error).lower():
            healing_instruction = f"{original_instruction}. The element might be covered by another element. Try scrolling or look for alternative elements."
        else:
            healing_instruction = f"{original_instruction}. Previous attempt failed with: {str(original_error)}. Try a different approach."
        
        try:
            # Re-observe with enhanced instruction
            from ..types import ObserveOptions
            observe_options = ObserveOptions(
                instruction=healing_instruction,
                model_name=options.model_name,
                return_action=True,
                from_act=True
            )
            
            observe_results = await page.observe(observe_options)
            
            if not observe_results:
                return ActResult(
                    success=False,
                    action=options.action or ActionType.CLICK,
                    error=f"Self-healing failed: No elements found. Original error: {original_error}",
                    metadata={"self_healing_attempted": True, "retry_count": retry_count}
                )
            
            # Try with the new observation result
            new_result = observe_results[0]
            
            # Apply any variable substitutions if needed
            if options.variable_values:
                for key, value in options.variable_values.items():
                    if new_result.arguments:
                        new_result.arguments = [
                            arg.replace(f"%{key}%", value) if isinstance(arg, str) else arg
                            for arg in new_result.arguments
                        ]
            
            # Execute with the new observation
            return await self._execute_from_observe_result(
                page, 
                new_result, 
                options,
                retry_count=retry_count
            )
            
        except Exception as e:
            # Self-healing failed
            self._log_error(
                "Self-healing failed",
                error=str(e),
                original_error=str(original_error),
                retry_count=retry_count
            )
            
            return ActResult(
                success=False,
                action=options.action or ActionType.CLICK,
                error=f"Original error: {original_error}. Self-healing attempt {retry_count} failed: {e}",
                metadata={"self_healing_attempted": True, "retry_count": retry_count}
            )
    
    # Action method handlers
    
    async def _handle_click(
        self,
        page: 'PlaywrightAIPage',
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
        page: 'PlaywrightAIPage',
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
        await page._page.fill(selector, value)
    
    async def _handle_type(
        self,
        page: 'PlaywrightAIPage',
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
        await page._page.type(selector, text)
    
    async def _handle_press(
        self,
        page: 'PlaywrightAIPage',
        selector: str,
        options: ActOptions
    ) -> None:
        """Handle key press action."""
        key = options.variable_values.get("key", "Enter") if options.variable_values else "Enter"
        
        await wait_for_selector_stable(page._page, selector, timeout=options.timeout)
        await page._page.press(selector, key)
    
    async def _handle_scroll(
        self,
        page: 'PlaywrightAIPage',
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
        page: 'PlaywrightAIPage',
        selector: str,
        options: ActOptions
    ) -> None:
        """Handle hover action."""
        await wait_for_selector_stable(page._page, selector, timeout=options.timeout)
        await page._page.hover(selector)
    
    async def _handle_drag(
        self,
        page: 'PlaywrightAIPage',
        selector: str,
        options: ActOptions
    ) -> None:
        """Handle drag action."""
        # This would need source and target coordinates
        # For now, just raise not implemented
        raise ActionFailedError("drag", "Drag action not yet implemented")
    
    async def _handle_screenshot(
        self,
        page: 'PlaywrightAIPage',
        selector: str,
        options: ActOptions
    ) -> None:
        """Handle screenshot action."""
        # Take screenshot of specific element
        element = await page._page.wait_for_selector(selector)
        if element:
            await element.screenshot()
    
    async def _handle_wait(
        self,
        page: 'PlaywrightAIPage',
        selector: str,
        options: ActOptions
    ) -> None:
        """Handle wait action."""
        # Wait for element to appear
        await page._page.wait_for_selector(selector, timeout=options.timeout)
    
    async def _handle_navigate(
        self,
        page: 'PlaywrightAIPage',
        selector: str,  # Not used for navigate
        options: ActOptions
    ) -> None:
        """Handle navigation action."""
        if options.variable_values and "url" in options.variable_values:
            url = options.variable_values["url"]
            await page._page.goto(url)
        else:
            raise ActionFailedError("navigate", "No URL provided for navigation")
    
