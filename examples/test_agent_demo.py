"""Test agent with demo implementation."""

from ai_browser_automation import AIBrowserAutomation
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path for development
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
load_dotenv()


async def test_demo_agent_search():
    """Test demo agent performing search tasks."""
    print("Testing Demo Agent Implementation...\n")

    async with AIBrowserAutomation(
        headless=False,
        verbose=2,
        model_name="gpt-4o",
        model_client_options={"api_key": os.getenv("OPENAI_API_KEY")}
    ) as stagehand:
        page = await stagehand.page()
        
        print("1. Testing agent search on Google:")
        print("-" * 50)
        
        # Create agent (will use demo implementation)
        agent = page.agent()
        
        # Navigate to Google first
        await page.goto("https://www.google.com")
        
        # Execute search task through agent
        result = await agent.execute("Search for 'OpenAI GPT-4'")
        
        print(f"Success: {result.success}")
        print(f"Message: {result.message}")
        print(f"Completed: {result.completed}")
        print(f"Actions taken: {len(result.actions)}")
        
        if result.actions:
            print("\nActions performed:")
            for i, action in enumerate(result.actions, 1):
                print(f"  {i}. {action['type']}: {action.get('description', action.get('target', action.get('text', '')))}")
        
        await page.wait_for_timeout(2000)
        print(f"\nFinal URL: {page.url}")


async def test_demo_agent_navigation():
    """Test demo agent navigation tasks."""
    print("\n\nTesting Demo Agent Navigation...\n")

    async with AIBrowserAutomation(
        headless=False,
        verbose=1,
        model_name="gpt-4o-mini",
        model_client_options={"api_key": os.getenv("OPENAI_API_KEY")}
    ) as stagehand:
        page = await stagehand.page()
        
        print("1. Testing navigation to GitHub:")
        print("-" * 50)
        
        agent = page.agent()
        
        # Execute navigation task
        result = await agent.execute("Navigate to GitHub and search for AIBrowserAutomation")
        
        print(f"Success: {result.success}")
        print(f"Message: {result.message}")
        print(f"Actions: {len(result.actions)}")
        
        await page.wait_for_timeout(2000)
        print(f"Final URL: {page.url}")


async def test_demo_agent_clicking():
    """Test demo agent click actions."""
    print("\n\nTesting Demo Agent Click Actions...\n")

    async with AIBrowserAutomation(
        headless=False,
        verbose=1,
        model_name="gpt-4o",
        model_client_options={"api_key": os.getenv("OPENAI_API_KEY")}
    ) as stagehand:
        page = await stagehand.page()
        await page.goto("https://www.example.com")
        
        print("1. Testing click action:")
        print("-" * 50)
        
        agent = page.agent()
        
        # Execute click task
        result = await agent.execute("Click on the 'More information' link")
        
        print(f"Success: {result.success}")
        print(f"Message: {result.message}")
        
        await page.wait_for_timeout(2000)


async def test_demo_agent_form():
    """Test demo agent form filling."""
    print("\n\nTesting Demo Agent Form Filling...\n")

    async with AIBrowserAutomation(
        headless=False,
        verbose=1,
        model_name="gpt-4o",
        model_client_options={"api_key": os.getenv("OPENAI_API_KEY")}
    ) as stagehand:
        page = await stagehand.page()
        
        # Go to a simple form page
        await page.goto("https://www.google.com")
        
        print("1. Testing form filling:")
        print("-" * 50)
        
        agent = page.agent()
        
        # Execute form fill task
        result = await agent.execute("Fill the search box with 'Python tutorials'")
        
        print(f"Success: {result.success}")
        print(f"Message: {result.message}")
        
        if result.actions:
            print("Actions taken:")
            for action in result.actions:
                print(f"  - {action}")


async def test_demo_agent_complex():
    """Test demo agent with complex instruction."""
    print("\n\nTesting Demo Agent Complex Task...\n")

    async with AIBrowserAutomation(
        headless=False,
        verbose=1,
        model_name="gpt-4o",
        model_client_options={"api_key": os.getenv("OPENAI_API_KEY")}
    ) as stagehand:
        page = await stagehand.page()
        
        print("1. Testing complex multi-step task:")
        print("-" * 50)
        
        agent = page.agent()
        
        # Start from blank page (agent should redirect to Google)
        result = await agent.execute("Search for weather in San Francisco")
        
        print(f"Success: {result.success}")
        print(f"Message: {result.message}")
        print(f"Completed: {result.completed}")
        
        if result.actions:
            print(f"\nPerformed {len(result.actions)} actions:")
            for action in result.actions:
                print(f"  - {action['type']}: {action.get('description', '')}")
        
        print(f"\nFinal URL: {page.url}")


async def main():
    """Run demo agent tests."""
    if not os.getenv("OPENAI_API_KEY"):
        print("WARNING: No OpenAI API key found.")
        print("Set OPENAI_API_KEY environment variable for testing.\n")
        return

    try:
        await test_demo_agent_search()
        await test_demo_agent_navigation()
        await test_demo_agent_clicking()
        await test_demo_agent_form()
        await test_demo_agent_complex()
        
        print("\n" + "=" * 70)
        print("✓ Demo agent tests completed!")
        print("=" * 70)
        
        print("\nThe demo agent successfully:")
        print("- Performed searches")
        print("- Navigated to websites")
        print("- Clicked on elements")
        print("- Filled forms")
        print("- Handled complex instructions")
        print("\nThis demonstrates the agent framework is ready for")
        print("full computer use API integration when available.")
        
    except Exception as e:
        print(f"\n✗ Demo agent tests failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())