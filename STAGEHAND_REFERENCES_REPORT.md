# Stagehand References Report

This report lists all remaining references to "stagehand" (case-insensitive) in the codebase that haven't been replaced with "ai_browser_automation" or "AIBrowserAutomation".

## Summary

Found references in the following categories:
1. **Variable names** - Used as variable names in tests and examples
2. **Parameter names** - Used as parameter names in core classes
3. **Method names** - One method name still contains "stagehand"
4. **Documentation** - References in markdown documentation files
5. **String literals** - One string literal in a test

## Detailed Findings

### 1. Variable Names (High Priority)

These variable names should be renamed from `stagehand` to `ai_automation` or similar:

#### Test Files:
- `test_multi_step_agent.py`:
  - Line 12: `stagehand = AIBrowserAutomation(...)`
  - Line 18: `await stagehand.init()`
  - Line 21: `page = await stagehand.page()`
  - Line 72: `await stagehand.close()`
  - Line 81: `stagehand = AIBrowserAutomation(...)`
  - Line 87: `await stagehand.init()`
  - Line 90: `page = await stagehand.page()`
  - Line 123: `await stagehand.close()`

- `test_agent_amazon.py`:
  - Line 12: `stagehand = AIBrowserAutomation(...)`
  - Line 18: `await stagehand.init()`
  - Line 21: `page = await stagehand.page()`
  - Line 47: `await stagehand.close()`

#### Example Files (30+ files):
All example files use `as stagehand:` in context managers. These should be renamed to `as ai_automation:` or similar. Files include:
- `examples/test_fill_fix.py` (line 26)
- `examples/test_improved_click.py` (line 22)
- `examples/test_agent.py` (lines 26, 91, 114)
- `examples/simple_search_test.py` (line 26)
- `examples/cdp_demo.py` (line 29)
- `examples/test_cdp_xpath.py` (line 21)
- `examples/test_xpath_click.py` (line 21)
- `examples/detailed_test.py` (line 42)
- `examples/test_cdp_xpath_simple.py` (line 21)
- `examples/google_test.py` (line 35)
- `examples/youtube_test.py` (line 26)
- `examples/basic_test.py` (line 23)
- `examples/test_agent_tasks.py` (lines 26, 83, 143, 184)
- `examples/google_search_test.py` (line 26)
- `examples/openai_test.py` (line 35)
- `examples/debug_observe.py` (line 21)
- `examples/dom_test.py` (line 20)
- `examples/test_cdp_xpath_debug2.py` (line 21)
- `examples/handler_test.py` (line 34)
- `examples/test_caching.py` (lines 28, 118)
- `examples/llm_test.py` (lines 39, 52, 65, 73, 88)
- `examples/test_agent_demo.py` (lines 26, 64, 92, 119, 151)

### 2. Parameter Names (High Priority)

- `ai_browser_automation/core/context.py`:
  - Line 22: `def __init__(self, context: BrowserContext, stagehand: 'AIBrowserAutomation'):`
  - Line 28: Comment: `stagehand: Parent AIBrowserAutomation instance`
  - Line 31: `self._stagehand = stagehand`
  - Line 32: `self._logger = stagehand.logger.child(component="context")`
  - Line 48: `return self._stagehand`

### 3. Method Names (High Priority)

- `ai_browser_automation/core/page.py`:
  - Line 453: `async def _ensure_stagehand_scripts(self) -> None:`
  - Should be renamed to `_ensure_ai_automation_scripts` or similar

### 4. String Literals (Medium Priority)

- `test_multi_step_agent.py`:
  - Line 59: `result2 = await agent.execute("Navigate to GitHub and search for 'stagehand'")`
  - This is a search query string that might be intentional but could be updated

### 5. Documentation Files (Low Priority)

Documentation files in `docs/` directory contain references that should be updated:

- `docs/CDP_QUICK_REFERENCE.md`:
  - Line 23: `| stagehand/a11y/utils.py | CDP session & accessibility tree building |`
  - Line 24: `| stagehand/core/page.py | Frame ordinal tracking |`
  - Line 25: `| stagehand/handlers/observe.py | LLM prompting & XPath resolution |`
  - Line 26: `| stagehand/handlers/utils/act_utils.py | XPath selector cleaning |`
  - Line 32: `from stagehand.a11y import get_accessibility_tree`
  - Line 35: `nodes, xpaths, urls = await get_accessibility_tree(stagehand_page)`
  - Line 40: `# In StagehandPage`
  - Line 47: `from stagehand.handlers.utils.act_utils import clean_selector`
  - Line 113: `stagehand = Stagehand(verbose=2)`

- `docs/CDP_WORKFLOW_DIAGRAM.md`:
  - Line 8: `participant StagehandPage`
  - Line 15: `User->>StagehandPage: page.act("Click submit button")`
  - Line 16: `StagehandPage->>ActHandler: handle(action)`
  - Line 49: `ActHandler->>StagehandPage: page.click("xpath=/html/body/button[1]")`
  - Line 50: `StagehandPage-->>User: ActResult(success=True)`

- `docs/CDP_XPATH_IMPLEMENTATION.md`:
  - Line 5: Description mentions "Stagehand-py"
  - Line 11: `│   StagehandPage │`
  - Line 41: `# In StagehandPage`

### 6. Property Access References

- `examples/detailed_test.py`:
  - Line 61: `logger=stagehand.logger.child(component="page")`
  - Line 62: `llm_provider=stagehand.llm_provider`
  
- `examples/basic_test.py`:
  - Line 24: `print(f"✓ AIBrowserAutomation created with session ID: {stagehand.session_id}")`

## Recommendations

1. **High Priority**: Rename all variable names `stagehand` to `ai_automation` or `browser` in test and example files
2. **High Priority**: Rename parameter name `stagehand` to `ai_automation` in `context.py`
3. **High Priority**: Rename method `_ensure_stagehand_scripts` to `_ensure_ai_automation_scripts` in `page.py`
4. **Medium Priority**: Update string literal in test that searches for 'stagehand'
5. **Low Priority**: Update documentation files to replace Stagehand references with AIBrowserAutomation

Total files affected: ~40 files (mostly examples and tests)