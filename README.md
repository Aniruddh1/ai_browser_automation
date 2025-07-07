# Playwright AI

AI-powered browser automation for Python, built on Playwright.

## Installation

```bash
pip install playwright-ai
```

## Quick Start

```python
from playwright_ai import PlaywrightAI

async def main():
    async with PlaywrightAI() as playwright_ai:
        page = await playwright_ai.page()
        await page.goto("https://example.com")
        
        # Use natural language to interact
        await page.act("Click the login button")
        
        # Extract structured data
        data = await page.extract({
            "title": str,
            "price": float,
            "in_stock": bool
        })
        
        print(data)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

## Features

- Built on Playwright for robust browser automation
- Natural language actions with `act()`
- Structured data extraction with `extract()`
- Element detection with `observe()`
- Multiple LLM providers (OpenAI, Anthropic, Google)
- Built-in caching for improved performance
- Extensible architecture
- CDP-based element identification with XPath mapping

## How It Works

Playwright AI uses Chrome DevTools Protocol (CDP) for advanced element identification:

1. **Accessibility Tree Analysis** - Gets semantic information about page elements
2. **XPath Generation** - Creates precise XPath selectors for every element
3. **LLM Integration** - Uses AI to understand natural language instructions
4. **Reliable Execution** - Executes actions with exact element targeting

For technical details, see:
- [CDP & XPath Implementation](docs/CDP_XPATH_IMPLEMENTATION.md)
- [Workflow Diagrams](docs/CDP_WORKFLOW_DIAGRAM.md)
- [Quick Reference](docs/CDP_QUICK_REFERENCE.md)

## Examples

Check out the `examples/` directory for:
- `cdp_demo.py` - Demonstrates CDP functionality
- `test_extract.py` - Data extraction examples
- `test_fill_fix.py` - Form filling examples

## Documentation

Full documentation available at [docs.playwright-ai.dev](https://docs.playwright-ai.dev)

## License

MIT