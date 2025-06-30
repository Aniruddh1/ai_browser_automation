"""Test agent functionality."""

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


async def test_basic_agent():
    """Test basic agent functionality."""
    print("Testing Agent System...\n")

    async with AIBrowserAutomation(
        headless=False,
        verbose=2,
        model_name="gpt-4o",
        model_client_options={"api_key": os.getenv("OPENAI_API_KEY")}
    ) as stagehand:
        page = await stagehand.page()
        
        print("1. Testing agent creation:")
        print("-" * 50)
        
        # Create agent with default model
        agent = page.agent()
        print(f"Agent created with model: {agent.agent.get_model_name()}")
        print(f"Agent type: {agent.agent.get_agent_type()}")

        print("\n2. Testing simple agent task:")
        print("-" * 50)
        
        # Execute a simple task
        result = await agent.execute("Search for 'OpenAI' on Google")
        
        print(f"Success: {result.success}")
        print(f"Message: {result.message}")
        print(f"Completed: {result.completed}")
        print(f"Actions taken: {len(result.actions)}")
        if result.metadata:
            print(f"Metadata: {result.metadata}")

        print("\n3. Testing agent with specific model:")
        print("-" * 50)
        
        # Create agent with specific model
        claude_agent = page.agent("claude-3-sonnet")
        print(f"Agent created with model: {claude_agent.agent.get_model_name()}")
        print(f"Agent type: {claude_agent.agent.get_agent_type()}")

        print("\n4. Testing agent with options:")
        print("-" * 50)
        
        # Create agent with options
        custom_agent = page.agent(
            model_name="gpt-4o",
            max_steps=15,
            wait_between_actions=2000,
        )
        
        # Execute with full options
        from ai_browser_automation.types.agent import AgentExecuteOptions
        
        options = AgentExecuteOptions(
            instruction="Navigate to GitHub and search for AIBrowserAutomation",
            max_steps=10,
            context="Focus on finding the official AIBrowserAutomation repository"
        )
        
        result2 = await custom_agent.execute(options)
        print(f"Success: {result2.success}")
        print(f"Message: {result2.message}")


async def test_agent_error_handling():
    """Test agent error handling."""
    print("\n\nTesting Agent Error Handling...\n")

    async with AIBrowserAutomation(
        headless=False,
        verbose=1,
        model_name="gpt-4o-mini",
        model_client_options={"api_key": os.getenv("OPENAI_API_KEY")}
    ) as stagehand:
        page = await stagehand.page()
        
        print("1. Testing with empty page:")
        print("-" * 50)
        
        # Agent should redirect to Google when page is empty
        agent = page.agent()
        result = await agent.execute("Search for Python tutorials")
        
        print(f"Success: {result.success}")
        print(f"Current URL: {page.url}")


async def test_agent_models():
    """Test different agent models."""
    print("\n\nTesting Different Agent Models...\n")

    async with AIBrowserAutomation(
        headless=False,
        verbose=1,
        model_name="gpt-4o",
        model_client_options={"api_key": os.getenv("OPENAI_API_KEY")}
    ) as stagehand:
        page = await stagehand.page()
        await page.goto("https://www.example.com")
        
        # Test model detection
        models_to_test = [
            ("gpt-4o", "openai"),
            ("gpt-3.5-turbo", "openai"),
            ("claude-3-opus", "anthropic"),
            ("claude-3-sonnet", "anthropic"),
        ]
        
        for model_name, expected_type in models_to_test:
            print(f"\nTesting model: {model_name}")
            print("-" * 30)
            
            agent = page.agent(model_name)
            detected_type = agent.agent.get_agent_type()
            
            print(f"Expected type: {expected_type}")
            print(f"Detected type: {detected_type}")
            print(f"Match: {'✓' if detected_type == expected_type else '✗'}")


async def main():
    """Run the tests."""
    if not os.getenv("OPENAI_API_KEY"):
        print("WARNING: No OpenAI API key found.")
        print("Agent functionality is limited without API keys.")
        print("Set OPENAI_API_KEY environment variable for full testing.\n")

    try:
        await test_basic_agent()
        await test_agent_error_handling()
        await test_agent_models()
        
        print("\n✓ Agent tests completed!")
        print("\nNote: The agent implementations are currently placeholders.")
        print("Full computer use functionality will be added when the APIs are available.")
        
    except Exception as e:
        print(f"\n✗ Agent tests failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())