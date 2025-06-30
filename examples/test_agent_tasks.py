"""Test agent with real tasks using act/observe functionality."""

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


async def test_agent_youtube_search():
    """Test agent performing YouTube search task."""
    print("Testing Agent with YouTube Search Task...\n")

    async with AIBrowserAutomation(
        headless=False,
        verbose=2,
        model_name="gpt-4o",
        model_client_options={"api_key": os.getenv("OPENAI_API_KEY")}
    ) as stagehand:
        page = await stagehand.page()
        
        print("1. Creating agent and navigating to YouTube:")
        print("-" * 50)
        
        # Create agent
        agent = page.agent()
        
        # Since agent is placeholder, let's simulate its behavior with act/observe
        await page.goto("https://www.youtube.com")
        print(f"Navigated to: {page.url}")
        
        print("\n2. Simulating agent task - Search for 'AIBrowserAutomation automation':")
        print("-" * 50)
        
        # This is what the agent would do internally
        # Step 1: Find search box
        search_elements = await page.observe("Find the search box")
        print(f"Found {len(search_elements)} potential search elements")
        
        # Step 2: Click on search box
        if search_elements:
            await page.act("Click on the search box")
            print("Clicked on search box")
            
            # Step 3: Type search query
            await page.act("Type 'AIBrowserAutomation automation tutorial'")
            print("Typed search query")
            
            # Step 4: Submit search
            await page.act("Press Enter to search")
            print("Submitted search")
            
            # Wait for results
            await page.wait_for_load_state("networkidle")
            print(f"Search results loaded. URL: {page.url}")
            
            # Step 5: Observe results
            results = await page.observe("Find video search results")
            print(f"Found {len(results)} video results")
            
            if results:
                print("\nFirst few results:")
                for i, result in enumerate(results[:3]):
                    print(f"  {i+1}. {result.description[:60]}...")


async def test_agent_google_search():
    """Test agent performing Google search and navigation."""
    print("\n\nTesting Agent with Google Search and Navigation...\n")

    async with AIBrowserAutomation(
        headless=False,
        verbose=1,
        model_name="gpt-4o-mini",
        model_client_options={"api_key": os.getenv("OPENAI_API_KEY")}
    ) as stagehand:
        page = await stagehand.page()
        
        print("1. Multi-step Google search task:")
        print("-" * 50)
        
        # Navigate to Google
        await page.goto("https://www.google.com")
        
        # Perform search
        await page.act("Search for 'OpenAI GPT-4'")
        await page.wait_for_load_state("networkidle")
        
        print(f"Search completed. URL: {page.url}")
        
        # Extract search results
        from pydantic import BaseModel
        from typing import List
        
        class SearchResult(BaseModel):
            title: str
            url: str
            description: str
        
        class SearchResults(BaseModel):
            results: List[SearchResult]
        
        print("\n2. Extracting search results:")
        print("-" * 50)
        
        extracted = await page.extract(
            SearchResults,
            instruction="Extract the top 3 search results"
        )
        
        if extracted.data:
            print(f"Extracted {len(extracted.data.results)} results:")
            for i, result in enumerate(extracted.data.results):
                print(f"\n{i+1}. {result.title}")
                print(f"   URL: {result.url}")
                print(f"   Description: {result.description[:100]}...")
        
        print("\n3. Clicking on first result:")
        print("-" * 50)
        
        if extracted.data and extracted.data.results:
            await page.act(f"Click on the search result titled '{extracted.data.results[0].title}'")
            await page.wait_for_load_state("domcontentloaded")
            print(f"Navigated to: {page.url}")


async def test_agent_form_filling():
    """Test agent filling out a form."""
    print("\n\nTesting Agent with Form Filling...\n")

    async with AIBrowserAutomation(
        headless=False,
        verbose=1,
        model_name="gpt-4o",
        model_client_options={"api_key": os.getenv("OPENAI_API_KEY")}
    ) as stagehand:
        page = await stagehand.page()
        
        print("1. Navigating to example form:")
        print("-" * 50)
        
        # Go to a form example site
        await page.goto("https://www.w3schools.com/html/html_forms.asp")
        
        print("2. Finding and interacting with form elements:")
        print("-" * 50)
        
        # Observe form elements
        form_elements = await page.observe("Find all form input fields in the example")
        print(f"Found {len(form_elements)} form elements")
        
        # Try to fill the example form
        actions = [
            "Fill the first name field with 'John'",
            "Fill the last name field with 'Doe'",
            "Click the submit button"
        ]
        
        for action in actions:
            try:
                result = await page.act(action)
                print(f"✓ {action}: {result.success}")
            except Exception as e:
                print(f"✗ {action}: Failed - {e}")


async def test_agent_workflow():
    """Test a complete workflow that an agent might perform."""
    print("\n\nTesting Complete Agent Workflow...\n")

    async with AIBrowserAutomation(
        headless=False,
        verbose=1,
        model_name="gpt-4o",
        model_client_options={"api_key": os.getenv("OPENAI_API_KEY")},
        enable_caching=True  # Enable caching for efficiency
    ) as stagehand:
        page = await stagehand.page()
        
        print("Simulating agent workflow: Research Python libraries")
        print("=" * 50)
        
        # Step 1: Go to Python.org
        print("\nStep 1: Navigate to Python.org")
        await page.goto("https://www.python.org")
        
        # Step 2: Search for packages
        print("\nStep 2: Search for 'web scraping'")
        await page.act("Click on the search box and type 'web scraping'")
        await page.act("Submit the search")
        await page.wait_for_timeout(2000)
        
        # Step 3: Extract information
        print("\nStep 3: Extract search results")
        
        from pydantic import BaseModel
        
        class SearchInfo(BaseModel):
            query: str
            result_count: int
            top_result_title: str
        
        info = await page.extract(SearchInfo)
        if info.data:
            print(f"Query: {info.data.query}")
            print(f"Results found: {info.data.result_count}")
            print(f"Top result: {info.data.top_result_title}")
        
        # Step 4: Navigate to PyPI
        print("\nStep 4: Navigate to PyPI")
        await page.goto("https://pypi.org")
        
        # Step 5: Search for a specific package
        print("\nStep 5: Search for 'beautifulsoup4'")
        await page.act("Search for 'beautifulsoup4' in the search box")
        await page.wait_for_load_state("networkidle")
        
        # Step 6: Extract package information
        print("\nStep 6: Extract package information")
        
        class PackageInfo(BaseModel):
            name: str
            version: str
            description: str
            
        package = await page.extract(
            PackageInfo,
            instruction="Extract information about the beautifulsoup4 package"
        )
        
        if package.data:
            print(f"Package: {package.data.name}")
            print(f"Version: {package.data.version}")
            print(f"Description: {package.data.description[:100]}...")
        
        print("\n" + "=" * 50)
        print("Workflow completed!")


async def main():
    """Run all agent task tests."""
    if not os.getenv("OPENAI_API_KEY"):
        print("WARNING: No OpenAI API key found.")
        print("Set OPENAI_API_KEY environment variable for testing.\n")
        return

    try:
        # Run individual tests
        await test_agent_youtube_search()
        await test_agent_google_search()
        await test_agent_form_filling()
        await test_agent_workflow()
        
        print("\n" + "=" * 70)
        print("✓ All agent task tests completed!")
        print("=" * 70)
        
        print("\nNote: These tests simulate what a fully-implemented agent would do.")
        print("The agent currently uses act/observe/extract methods internally.")
        print("When computer use APIs are available, the agent will handle these")
        print("tasks autonomously without explicit act/observe calls.")
        
    except Exception as e:
        print(f"\n✗ Agent task tests failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())