#!/usr/bin/env python3
"""
Build and bundle DOM scripts for injection.
Build and bundle DOM scripts for better performance
"""

import os
import json
from pathlib import Path


def build_dom_scripts():
    """
    Build DOM scripts into a bundled format for better performance.
    """
    # Get the directory of this script
    dom_dir = Path(__file__).parent
    
    # Read all script components
    scripts = {
        'core': '',
        'scrollable': '',
        'interactive': '',
        'xpath': '',
        'utils': ''
    }
    
    # Read the main scripts.py file
    scripts_file = dom_dir / 'scripts.py'
    if scripts_file.exists():
        with open(scripts_file, 'r') as f:
            content = f.read()
            # Extract the JavaScript from the Python string
            start = content.find('DOM_SCRIPTS = """') + len('DOM_SCRIPTS = """')
            end = content.rfind('"""')
            if start > 0 and end > start:
                scripts['core'] = content[start:end]
    
    # Add scrollable detection from scrollable.py
    scrollable_file = dom_dir / 'scrollable.py'
    if scrollable_file.exists():
        with open(scrollable_file, 'r') as f:
            content = f.read()
            # Extract scrollable detection script
            start = content.find('SCROLLABLE_DETECTION_SCRIPT = """') + len('SCROLLABLE_DETECTION_SCRIPT = """')
            end = content.find('"""', start)
            if start > 0 and end > start:
                scripts['scrollable'] = content[start:end]
    
    # Add XPath generation script
    xpath_file = dom_dir / 'xpath.py'
    if xpath_file.exists():
        with open(xpath_file, 'r') as f:
            content = f.read()
            # Extract XPath generation script
            start = content.find('XPATH_GENERATION_SCRIPT = """') + len('XPATH_GENERATION_SCRIPT = """')
            end = content.find('"""', start)
            if start > 0 and end > start:
                scripts['xpath'] = content[start:end]
    
    # Bundle all scripts together
    bundled_script = f"""
// AI Browser Automation Bundled DOM Scripts
// Auto-generated - do not edit directly

(function() {{
    'use strict';
    
    // Core functionality
    {scripts['core']}
    
    // Scrollable detection
    {scripts['scrollable']}
    
    // XPath utilities
    {scripts['xpath']}
    
    // Mark bundle as loaded
    window.__aiBrowserAutomationBundled = true;
}})();
"""
    
    # Write bundled script
    output_file = dom_dir / 'bundled_scripts.js'
    with open(output_file, 'w') as f:
        f.write(bundled_script)
    
    # Also create a Python module with the bundled content
    python_output = dom_dir / 'bundled_scripts.py'
    with open(python_output, 'w') as f:
        f.write('"""Auto-generated bundled DOM scripts."""\n\n')
        f.write(f'BUNDLED_DOM_SCRIPTS = """{bundled_script}"""\n')
    
    print(f"✓ Bundled DOM scripts to {output_file}")
    print(f"✓ Created Python module at {python_output}")
    
    # Create minified version (basic minification)
    minified = bundled_script.replace('\n    ', '\n')  # Remove indentation
    minified = '\n'.join(line.strip() for line in minified.split('\n') if line.strip())  # Remove empty lines
    
    minified_file = dom_dir / 'bundled_scripts.min.js'
    with open(minified_file, 'w') as f:
        f.write(minified)
    
    print(f"✓ Created minified version at {minified_file}")
    
    # Generate script content module
    script_content = f'export const scriptContent = {json.dumps(minified)};'
    
    script_content_file = dom_dir / 'scriptContent.py'
    with open(script_content_file, 'w') as f:
        f.write('"""Script content for injection."""\n\n')
        f.write(f'SCRIPT_CONTENT = {json.dumps(minified)}\n')
    
    print(f"✓ Created script content module at {script_content_file}")


if __name__ == '__main__':
    build_dom_scripts()