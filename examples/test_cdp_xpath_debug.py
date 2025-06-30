"""Debug CDP XPath mapping in detail."""

from playwright.async_api import async_playwright
import asyncio


async def test_cdp_xpath_debug():
    """Test CDP XPath mapping step by step."""
    print("Testing CDP XPath Mapping Debug...\n")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        await page.goto("https://example.com")
        await page.wait_for_load_state("domcontentloaded")
        
        # Create CDP session
        print("Creating CDP session...")
        cdp_session = await context.new_cdp_session(page)
        
        # Enable domains
        await cdp_session.send("Accessibility.enable")
        await cdp_session.send("DOM.enable")
        
        # Get DOM document
        print("\n1. Getting DOM document...")
        dom_response = await cdp_session.send("DOM.getDocument", {"depth": -1})
        root = dom_response.get("root", {})
        
        print(f"Root node ID: {root.get('nodeId')}")
        print(f"Root backend ID: {root.get('backendNodeId')}")
        print(f"Root node name: {root.get('nodeName')}")
        
        # Count nodes
        def count_nodes(node):
            count = 1
            for child in node.get("children", []):
                count += count_nodes(child)
            return count
            
        total_nodes = count_nodes(root)
        print(f"Total DOM nodes: {total_nodes}")
        
        # Get accessibility tree
        print("\n2. Getting accessibility tree...")
        ax_response = await cdp_session.send("Accessibility.getFullAXTree")
        ax_nodes = ax_response.get("nodes", [])
        print(f"Total accessibility nodes: {len(ax_nodes)}")
        
        # Check first few accessibility nodes
        print("\nFirst 5 accessibility nodes:")
        for i, node in enumerate(ax_nodes[:5]):
            backend_id = node.get("backendDOMNodeId")
            role = node.get("role", {}).get("value", "")
            name = node.get("name", {}).get("value", "")
            print(f"  Node {i}: backendDOMNodeId={backend_id}, role={role}, name={name[:30]}")
        
        # Check mapping process
        print("\n3. Building backend ID to XPath map...")
        backend_id_map = {}
        
        def traverse_dom(node, path="", position_map=None, depth=0):
            if position_map is None:
                position_map = {}
                
            backend_id = node.get("backendNodeId")
            node_type = node.get("nodeType")
            node_name = node.get("nodeName", "").lower()
            
            if depth < 3:
                print(f"{'  ' * depth}Node: name={node_name}, type={node_type}, backendId={backend_id}")
            
            if node_type == 1:  # ELEMENT_NODE
                # Calculate position
                parent_key = f"{path}:{node_name}"
                position = position_map.get(parent_key, 0) + 1
                position_map[parent_key] = position
                
                if path:
                    xpath = f"{path}/{node_name}[{position}]"
                else:
                    xpath = f"/{node_name}[1]"
                    
                if backend_id is not None:
                    backend_id_map[backend_id] = xpath
                    if len(backend_id_map) <= 5:
                        print(f"    Added mapping: {backend_id} -> {xpath}")
                    
                # Traverse children
                child_position_map = {}
                for child in node.get("children", []):
                    traverse_dom(child, xpath, child_position_map, depth + 1)
            else:
                # For non-element nodes, still traverse children
                for child in node.get("children", []):
                    traverse_dom(child, path, position_map, depth + 1)
                    
        traverse_dom(root)
        print(f"Built {len(backend_id_map)} backend ID to XPath mappings")
        
        # Print first few mappings
        print("\nFirst 5 XPath mappings:")
        for i, (backend_id, xpath) in enumerate(list(backend_id_map.items())[:5]):
            print(f"  {backend_id}: {xpath}")
        
        # Check if accessibility nodes have matching backend IDs
        print("\n4. Checking accessibility nodes with XPath mappings:")
        matched = 0
        for node in ax_nodes:
            backend_id = node.get("backendDOMNodeId")
            if backend_id and backend_id in backend_id_map:
                matched += 1
                
        print(f"Matched {matched}/{len(ax_nodes)} accessibility nodes to XPath mappings")
        
        # Cleanup
        await cdp_session.detach()
        await browser.close()


async def main():
    """Run the test."""
    await test_cdp_xpath_debug()
    print("\n✓ CDP XPath debug completed!")


if __name__ == "__main__":
    asyncio.run(main())