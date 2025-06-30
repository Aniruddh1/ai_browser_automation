#!/usr/bin/env python3
"""
Demo of advanced CDP features in AI Browser Automation.
"""

import asyncio
from ai_browser_automation import AIBrowserAutomation


async def main():
    """Demonstrate CDP features."""
    browser = AIBrowserAutomation(
        headless=False,
        debug_dom=True
    )
    await browser.init()
    
    try:
        page = await browser.page
        
        print("=== CDP Feature Demo ===\n")
        
        # 1. Performance Metrics
        print("1. Getting performance metrics...")
        await page.goto("https://example.com")
        metrics = await page.get_performance_metrics()
        print(f"   JS Heap Size: {metrics.get('JSHeapUsedSize', 0) / 1024 / 1024:.2f} MB")
        print(f"   Documents: {metrics.get('Documents', 0)}")
        print(f"   Layout Count: {metrics.get('LayoutCount', 0)}")
        
        # 2. Console Log Monitoring
        print("\n2. Monitoring console logs...")
        logs = []
        
        async def log_handler(level, message):
            logs.append(f"[{level}] {message}")
            print(f"   Console: [{level}] {message}")
        
        await page.monitor_console_logs(log_handler)
        
        # Trigger some console logs
        await page.evaluate("console.log('Hello from CDP!')")
        await page.evaluate("console.warn('This is a warning')")
        await page.evaluate("console.error('This is an error')")
        
        await asyncio.sleep(0.5)  # Give time for logs to arrive
        
        # 3. Network Request Monitoring
        print("\n3. Monitoring network requests...")
        requests = []
        
        async def request_handler(params):
            url = params.get('request', {}).get('url', '')
            method = params.get('request', {}).get('method', '')
            requests.append(f"{method} {url}")
            print(f"   Request: {method} {url}")
        
        await page.add_cdp_listener('Network.requestWillBeSent', request_handler)
        
        # Enable Network domain
        await page.execute_cdp_command('Network.enable')
        
        # Navigate to trigger requests
        await page.goto("https://httpbin.org/html")
        
        # 4. DOM Snapshot
        print("\n4. Capturing DOM snapshot...")
        snapshot = await page.capture_snapshot()
        print(f"   Snapshot size: {len(snapshot)} characters")
        
        # 5. Resource Tree
        print("\n5. Getting resource tree...")
        tree = await page.get_resource_tree()
        frame_tree = tree.get('frameTree', {})
        main_frame = frame_tree.get('frame', {})
        print(f"   Main frame URL: {main_frame.get('url', 'N/A')}")
        print(f"   Child frames: {len(frame_tree.get('childFrames', []))}")
        
        # 6. Partial Tree Observation (Performance)
        print("\n6. Testing partial tree observation...")
        
        # Traditional full tree
        start = asyncio.get_event_loop().time()
        elements = await page.observe("Find all buttons")
        full_time = asyncio.get_event_loop().time() - start
        print(f"   Full tree observation: {len(elements)} elements in {full_time:.3f}s")
        
        # Partial tree (faster for focused searches)
        start = asyncio.get_event_loop().time()
        elements_partial = await page.observe_with_partial_tree("Find all buttons", max_depth=3)
        partial_time = asyncio.get_event_loop().time() - start
        print(f"   Partial tree observation: {len(elements_partial)} elements in {partial_time:.3f}s")
        print(f"   Speed improvement: {(full_time / partial_time - 1) * 100:.1f}%")
        
        # 7. Network Conditions Emulation
        print("\n7. Testing network conditions...")
        
        # Emulate slow 3G
        await page.emulate_network_conditions(
            offline=False,
            latency=400,  # 400ms latency
            download_throughput=50 * 1024,  # 50KB/s
            upload_throughput=20 * 1024     # 20KB/s
        )
        
        start = asyncio.get_event_loop().time()
        await page.goto("https://httpbin.org/delay/1")
        slow_time = asyncio.get_event_loop().time() - start
        print(f"   Page load with slow 3G: {slow_time:.2f}s")
        
        # Reset network conditions
        await page.emulate_network_conditions()
        
        # 8. CDP Batch Execution Demo
        print("\n8. Testing CDP batch execution...")
        
        # Execute multiple CDP commands
        start = asyncio.get_event_loop().time()
        results = await asyncio.gather(
            page.execute_cdp_command('Runtime.evaluate', {
                'expression': '1 + 1'
            }),
            page.execute_cdp_command('Runtime.evaluate', {
                'expression': '2 + 2'
            }),
            page.execute_cdp_command('Runtime.evaluate', {
                'expression': '3 + 3'
            })
        )
        batch_time = asyncio.get_event_loop().time() - start
        print(f"   Batched 3 CDP calls in {batch_time:.3f}s")
        print(f"   Results: {[r['result']['value'] for r in results]}")
        
        print("\n=== CDP Features Demo Complete ===")
        
    finally:
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())