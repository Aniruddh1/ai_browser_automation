"""Test mock LLM responses directly."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for development
sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright_ai.llm import MockLLMClient
from playwright_ai.types import LLMMessage
from playwright_ai.utils.logger import configure_logging, PlaywrightAILogger


async def main():
    """Test mock LLM client."""
    logger = PlaywrightAILogger(configure_logging(2), 2)
    client = MockLLMClient("gpt-4o", None, logger)
    
    print("Testing mock LLM client responses...\n")
    
    # Test 1: Observe/analyze prompt
    print("--- Test 1: Observe/Analyze ---")
    response = await client.create_chat_completion([
        LLMMessage(role="user", content="Analyze the following web page and identify interactive elements.")
    ])
    print(f"Response: {response.choices[0].message.content}\n")
    
    # Test 2: Find links
    print("--- Test 2: Find Links ---")
    response = await client.create_chat_completion([
        LLMMessage(role="user", content="Find all links on the page")
    ])
    print(f"Response: {response.choices[0].message.content}\n")
    
    # Test 3: Extract
    print("--- Test 3: Extract ---")
    response = await client.create_chat_completion([
        LLMMessage(role="user", content="Extract data from the page")
    ])
    print(f"Response: {response.choices[0].message.content}\n")
    
    # Test 4: Click (without observe)
    print("--- Test 4: Click ---")
    response = await client.create_chat_completion([
        LLMMessage(role="user", content="Click the button")
    ])
    print(f"Response: {response.choices[0].message.content}\n")


if __name__ == "__main__":
    asyncio.run(main())