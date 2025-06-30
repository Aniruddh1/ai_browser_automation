"""Test script for multi-step agent execution."""

import asyncio
from ai_browser_automation import AIBrowserAutomation


async def test_demo_agent():
    """Test demo agent with multi-step execution."""
    print("\n=== Testing Demo Agent with Multi-Step Execution ===\n")
    
    # Initialize AIBrowserAutomation
    stagehand = AIBrowserAutomation(
        env="LOCAL",
        verbose=2,
        headless=False,
    )
    
    await stagehand.init()
    
    # Create a page
    page = await stagehand.page()
    
    # Navigate to Google
    await page.goto("https://google.com")
    
    # Create agent with demo client (default)
    agent = page.agent(
        model_name="gpt-4o",  # Will use demo client
        client_options={
            "wait_between_actions": 500
        }
    )
    
    print("\n--- Testing Multi-Step Search ---\n")
    
    # Execute multi-step search task
    result = await agent.execute("Search for 'OpenAI'")
    
    print(f"\nAgent Result:")
    print(f"  Success: {result.success}")
    print(f"  Completed: {result.completed}")
    print(f"  Message: {result.message}")
    print(f"  Actions performed: {len(result.actions)}")
    
    for i, action in enumerate(result.actions):
        print(f"  Step {i+1}: {action.get('type')} - {action.get('description', action.get('target', action.get('text', '')))}")
    
    if result.usage:
        print(f"\nUsage:")
        print(f"  Input tokens: {result.usage.get('input_tokens', 0)}")
        print(f"  Output tokens: {result.usage.get('output_tokens', 0)}")
        print(f"  Inference time: {result.usage.get('inference_time_ms', 0)}ms")
    
    await asyncio.sleep(3)
    
    print("\n--- Testing Navigation with Search ---\n")
    
    # Test navigation with search
    result2 = await agent.execute("Navigate to GitHub and search for 'stagehand'")
    
    print(f"\nAgent Result:")
    print(f"  Success: {result2.success}")
    print(f"  Completed: {result2.completed}")
    print(f"  Message: {result2.message}")
    print(f"  Actions performed: {len(result2.actions)}")
    
    for i, action in enumerate(result2.actions):
        print(f"  Step {i+1}: {action.get('type')} - {action.get('description', action.get('url', action.get('text', '')))}")
    
    await asyncio.sleep(3)
    
    await stagehand.close()
    print("\n=== Demo Agent Test Complete ===\n")


async def test_computer_use_models():
    """Test with computer use models (placeholder mode)."""
    print("\n=== Testing Computer Use Models (Placeholder Mode) ===\n")
    
    # Initialize AIBrowserAutomation
    stagehand = AIBrowserAutomation(
        env="LOCAL",
        verbose=2,
        headless=False,
    )
    
    await stagehand.init()
    
    # Create a page
    page = await stagehand.page()
    
    # Navigate to a test page
    await page.goto("https://example.com")
    
    print("\n--- Testing OpenAI Computer Use Model ---\n")
    
    # Test OpenAI computer use model
    agent_openai = page.agent(
        model_name="computer-use-preview",
        client_options={
            "api_key": "sk-placeholder",
            "environment": "browser"
        }
    )
    
    result = await agent_openai.execute("Click on the 'More information' link")
    print(f"OpenAI Agent Result: Success={result.success}, Message={result.message}")
    
    print("\n--- Testing Anthropic Computer Use Model ---\n")
    
    # Test Anthropic computer use model
    agent_anthropic = page.agent(
        model_name="claude-3-5-sonnet-20240620",
        client_options={
            "api_key": "sk-ant-placeholder",
            "thinking_budget": 1000
        }
    )
    
    result = await agent_anthropic.execute("Click on the 'More information' link")
    print(f"Anthropic Agent Result: Success={result.success}, Message={result.message}")
    
    await stagehand.close()
    print("\n=== Computer Use Models Test Complete ===\n")


async def main():
    """Run all tests."""
    # Test demo agent with multi-step execution
    await test_demo_agent()
    
    # Test computer use models
    await test_computer_use_models()


if __name__ == "__main__":
    asyncio.run(main())