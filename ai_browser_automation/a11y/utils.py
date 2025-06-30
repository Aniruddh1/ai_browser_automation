"""Accessibility tree utilities using Chrome DevTools Protocol."""

import asyncio
from typing import Dict, List, Any, Optional, Tuple, TYPE_CHECKING
from playwright.async_api import CDPSession
import json

if TYPE_CHECKING:
    from ..core import AIBrowserAutomationPage


class AccessibilityTreeBuilder:
    """Build accessibility trees and XPath mappings using CDP."""
    
    def __init__(self, ai_browser_automation_page: 'AIBrowserAutomationPage'):
        self.ai_browser_automation_page = ai_browser_automation_page
        self.page = ai_browser_automation_page._page
        self.cdp_session: Optional[CDPSession] = None
        
    async def __aenter__(self):
        """Create CDP session."""
        self.cdp_session = await self.page.context.new_cdp_session(self.page)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close CDP session."""
        if self.cdp_session:
            await self.cdp_session.detach()
            
    async def get_accessibility_tree_with_frames(self) -> Tuple[List[Dict], Dict[str, str], Dict[str, str]]:
        """
        Get accessibility tree with XPath mappings for all frames.
        
        Returns:
            Tuple of (simplified_tree, xpath_map, url_map)
            - simplified_tree: List of accessibility nodes
            - xpath_map: Map from encoded IDs to XPath expressions
            - url_map: Map from frame IDs to URLs
        """
        if not self.cdp_session:
            raise RuntimeError("CDP session not initialized")
            
        # Enable necessary CDP domains
        await self.cdp_session.send("Accessibility.enable")
        await self.cdp_session.send("DOM.enable")
        
        try:
            # Get accessibility tree
            ax_tree_response = await self.cdp_session.send("Accessibility.getFullAXTree")
            ax_nodes = ax_tree_response.get("nodes", [])
            
            # Build backend ID mappings
            tag_name_map, xpath_map = await self._build_backend_id_maps()
            
            # Build hierarchical tree
            tree = self._build_hierarchical_tree(ax_nodes)
            
            # Simplify tree
            simplified = self._simplify_tree(tree, tag_name_map)
            
            # Convert to encoded ID format
            encoded_xpath_map = {}
            for backend_id, xpath in xpath_map.items():
                # For now, assume main frame (None) - we'll enhance this for iframes later
                encoded_id = self.ai_browser_automation_page.encode_with_frame_id(None, backend_id)
                encoded_xpath_map[encoded_id] = xpath
                
            # Build URL map with frame ordinals
            url_map = {}
            for frame_id, ordinal in self.ai_browser_automation_page._frame_ordinals.items():
                url_map[str(ordinal)] = self.page.url  # For now, use main page URL
                
            return simplified, encoded_xpath_map, url_map
            
        finally:
            # Disable CDP domains
            await self.cdp_session.send("Accessibility.disable")
            await self.cdp_session.send("DOM.disable")
            
    async def _build_backend_id_maps(self) -> Tuple[Dict[int, str], Dict[int, str]]:
        """
        Build mappings from backend node IDs to tag names and XPath expressions.
        
        Args:
            root_node_id: Root DOM node ID
            
        Returns:
            Tuple of (tag_name_map, xpath_map)
        """
        tag_name_map = {}
        xpath_map = {}
        
        # Get the full DOM tree
        try:
            dom_response = await self.cdp_session.send("DOM.getDocument", {"depth": -1})
            root = dom_response.get("root", {})
            
            def traverse_node(node: Dict[str, Any], parent_xpath: str = "", position_map: Dict[str, int] = None) -> None:
                """Recursively traverse DOM nodes."""
                if position_map is None:
                    position_map = {}
                    
                backend_id = node.get("backendNodeId")
                node_type = node.get("nodeType")
                node_name = node.get("nodeName", "").lower()
                
                # Build XPath for this node
                if node_type == 1:  # ELEMENT_NODE
                    # Calculate position among siblings of same type
                    parent_key = f"{parent_xpath}:{node_name}"
                    position = position_map.get(parent_key, 0) + 1
                    position_map[parent_key] = position
                    
                    if parent_xpath:
                        xpath = f"{parent_xpath}/{node_name}[{position}]"
                    else:
                        xpath = f"/{node_name}[1]"
                        
                    if backend_id:
                        tag_name_map[backend_id] = node_name
                        xpath_map[backend_id] = xpath
                        
                    # Traverse children
                    children = node.get("children", [])
                    child_position_map = {}
                    for child in children:
                        traverse_node(child, xpath, child_position_map)
                        
                elif node_type == 3:  # TEXT_NODE
                    # Text nodes get special XPath
                    parent_key = f"{parent_xpath}:text()"
                    position = position_map.get(parent_key, 0) + 1
                    position_map[parent_key] = position
                    
                    xpath = f"{parent_xpath}/text()[{position}]"
                    if backend_id:
                        xpath_map[backend_id] = xpath
                else:
                    # For other node types (like document nodes), still traverse children
                    children = node.get("children", [])
                    for child in children:
                        traverse_node(child, parent_xpath, position_map)
                        
            traverse_node(root)
            
        except Exception as e:
            # Log error but continue
            print(f"Error building backend ID maps: {e}")
            
        return tag_name_map, xpath_map
        
    def _build_hierarchical_tree(self, nodes: List[Dict]) -> Dict[str, Any]:
        """
        Build hierarchical tree from flat list of accessibility nodes.
        
        Args:
            nodes: List of accessibility nodes
            
        Returns:
            Root node of hierarchical tree
        """
        node_map = {}
        root = None
        
        # Create node map
        for node in nodes:
            node_id = node.get("nodeId")
            if node_id:
                node_map[node_id] = {
                    **node,
                    "children": []
                }
                
        # Build parent-child relationships
        for node in nodes:
            node_id = node.get("nodeId")
            parent_id = node.get("parentId")
            
            if parent_id and parent_id in node_map:
                node_map[parent_id]["children"].append(node_map[node_id])
            elif not parent_id:
                root = node_map.get(node_id)
                
        return root or {}
        
    def _simplify_tree(self, tree: Dict[str, Any], tag_name_map: Dict[int, str]) -> List[Dict[str, Any]]:
        """
        Simplify accessibility tree by flattening and cleaning.
        
        Args:
            tree: Hierarchical tree
            tag_name_map: Mapping from backend IDs to tag names
            
        Returns:
            Simplified flat list of nodes
        """
        simplified = []
        
        def flatten(node: Dict[str, Any], depth: int = 0) -> None:
            """Recursively flatten tree."""
            if not node:
                return
                
            # Extract relevant properties
            backend_id = node.get("backendDOMNodeId")  # Note: it's backendDOMNodeId, not backendNodeId
            role = node.get("role", {}).get("value", "")
            name = node.get("name", {}).get("value", "")
            value = node.get("value", {}).get("value", "")
            description = node.get("description", {}).get("value", "")
            
            # Skip certain roles
            skip_roles = {"generic", "none", "presentation"}
            if role in skip_roles and not name and not value:
                # Process children directly
                for child in node.get("children", []):
                    flatten(child, depth)
                return
                
            # Create simplified node with encoded ID
            simplified_node = {
                "nodeId": backend_id,
                "encodedId": self.ai_browser_automation_page.encode_with_frame_id(None, backend_id) if backend_id else None,
                "role": role,
                "name": name,
                "tagName": tag_name_map.get(backend_id, "div")
            }
            
            if value:
                simplified_node["value"] = value
            if description:
                simplified_node["description"] = description
                
            simplified.append(simplified_node)
            
            # Process children
            for child in node.get("children", []):
                flatten(child, depth + 1)
                
        flatten(tree)
        return simplified


async def get_accessibility_tree(ai_browser_automation_page: 'AIBrowserAutomationPage') -> Tuple[List[Dict], Dict[str, str], Dict[str, str]]:
    """
    Get accessibility tree with XPath mappings for a page.
    
    Args:
        ai_browser_automation_page: AIBrowserAutomationPage instance
        
    Returns:
        Tuple of (simplified_tree, xpath_map, url_map)
    """
    async with AccessibilityTreeBuilder(ai_browser_automation_page) as builder:
        return await builder.get_accessibility_tree_with_frames()