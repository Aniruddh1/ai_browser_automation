# CDP and XPath Quick Reference

## Quick Start

### Basic Usage
```python
# User perspective - nothing changes!
await page.act("Click the submit button")
await page.observe("Find all form inputs")
```

### What Happens Behind the Scenes
1. **CDP connects** to browser internals
2. **Accessibility tree** provides semantic info
3. **XPath mapping** creates precise selectors
4. **LLM identifies** the right element
5. **Action executes** with XPath selector

## Key Files

| File | Purpose |
|------|---------|
| `ai_browser_automation/a11y/utils.py` | CDP session & accessibility tree building |
| `ai_browser_automation/core/page.py` | Frame ordinal tracking |
| `ai_browser_automation/handlers/observe.py` | LLM prompting & XPath resolution |
| `ai_browser_automation/handlers/utils/act_utils.py` | XPath selector cleaning |

## Important Functions

### 1. Get Accessibility Tree
```python
from ai_browser_automation.a11y import get_accessibility_tree

# Returns: (simplified_tree, xpath_map, url_map)
nodes, xpaths, urls = await get_accessibility_tree(ai_browser_automation_page)
```

### 2. Frame Ordinal Encoding
```python
# In AIBrowserAutomationPage
encoded_id = page.encode_with_frame_id(frame_id=None, backend_id=123)
# Returns: "0-123" for main frame
```

### 3. Clean XPath Selector
```python
from ai_browser_automation.handlers.utils.act_utils import clean_selector

cleaned = clean_selector("xpath=/html/body/button[1]")
# Returns: "/html/body/button[1]"
```

## CDP Commands Used

```python
# Enable domains
await cdp.send("DOM.enable")
await cdp.send("Accessibility.enable")

# Get trees
dom = await cdp.send("DOM.getDocument", {"depth": -1})
a11y = await cdp.send("Accessibility.getFullAXTree")

# Clean up
await cdp.send("DOM.disable")
await cdp.send("Accessibility.disable")
```

## Data Formats

### Encoded ID
```
Format: "{frameOrdinal}-{backendNodeId}"
Example: "0-456" = main frame, node 456
```

### XPath Selector
```
Format: "xpath={full_xpath}"
Example: "xpath=/html[1]/body[1]/div[2]/button[1]"
```

### LLM Element ID
```json
{
  "elementId": "0-456",  // Must match encoded ID
  "method": "click",
  "arguments": []
}
```

## Common Patterns

### 1. Observe → Act Flow
```python
# Observe finds elements
results = await page.observe("Find login button")
# Returns: [ObserveResult(selector="xpath=/html/body/button[1]", ...)]

# Act uses the selector
await page.act(results[0])
```

### 2. Direct Action
```python
# All-in-one - observe + act internally
await page.act("Click the login button")
```

### 3. Debugging CDP
```python
# Enable verbose logging
browser = AIBrowserAutomation(verbose=2)

# Check if CDP is working
try:
    nodes, xpaths, urls = await get_accessibility_tree(page)
    print(f"CDP working: {len(nodes)} nodes, {len(xpaths)} xpaths")
except Exception as e:
    print(f"CDP failed: {e}")
```

## Troubleshooting

### Issue: "No XPath found for element"
```python
# Check if element has encoded ID
print(f"Element encoded ID: {element.encoded_id}")
print(f"XPath map has: {element.encoded_id in xpath_map}")
```

### Issue: "Invalid XPath expression"
```python
# XPath must be valid syntax
# Bad:  /a:contains('text')  ← jQuery style
# Good: /a[contains(text(),'text')]  ← Valid XPath
```

### Issue: "Element not found"
```python
# Element might have changed - re-observe
results = await page.observe("Find element again")
```

## Performance Tips

1. **CDP is fast** (~100-200ms overhead)
2. **XPaths are cached** in memory during session
3. **Fallback exists** if CDP fails (DOM scraping)
4. **One CDP session** per page (reused)

## Implementation Details

| Feature | Description |
|---------|-------------|
| CDP Access | Via Playwright CDP |
| Frame Tracking | Per-page state management |
| XPath Building | Recursive algorithm |
| Error Handling | Graceful fallback to DOM |

## Example: Complete Debug Trace

```python
# What you write
await page.act("Click submit")

# What happens (with verbose=2)
# [INFO] Starting observation
# [DEBUG] Getting accessibility tree with XPath mappings
# [DEBUG] Got 45 nodes from accessibility tree
# [INFO] Observation completed, found_count=1
# [DEBUG] LLM returned elementId: 0-789
# [DEBUG] Found XPath: /html[1]/body[1]/form[1]/button[1]
# [INFO] Action completed, success=True
```

## Best Practices

1. **Let CDP work** - Don't override with CSS selectors
2. **Trust the XPath** - Generated from actual DOM
3. **Check logs** - Verbose mode shows the flow
4. **Handle failures** - CDP might not work on all sites

## Next Steps

- See `CDP_XPATH_IMPLEMENTATION.md` for deep dive
- See `CDP_WORKFLOW_DIAGRAM.md` for visual flow
- Run `examples/cdp_demo.py` for working example