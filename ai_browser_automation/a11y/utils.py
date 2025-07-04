"""Accessibility tree utilities using Chrome DevTools Protocol."""

import asyncio
from typing import Dict, List, Any, Optional, Tuple, TYPE_CHECKING
from playwright.async_api import CDPSession
import json

if TYPE_CHECKING:
    from ..core import AIBrowserAutomationPage

from ..dom.xpath import (
    generate_xpath_strategies,
    validate_xpath_uniqueness,
    find_unique_xpath,
    build_positional_xpath,
    escape_xpath_string,
    XPATH_GENERATION_SCRIPT
)
from ..cdp import cdp_manager


class AccessibilityTreeBuilder:
    """Build accessibility trees and XPath mappings using CDP."""
    
    def __init__(self, ai_browser_automation_page: 'AIBrowserAutomationPage'):
        self.ai_browser_automation_page = ai_browser_automation_page
        self.page = ai_browser_automation_page._page
        self.cdp_session: Optional[CDPSession] = None
        self.use_partial_trees = True  # Enable partial tree extraction
        self.batch_cdp_calls = True    # Enable CDP call batching
        
    async def __aenter__(self):
        """Create CDP session using the CDP manager."""
        self.cdp_session = await cdp_manager.get_session(self.page)
        # Don't enable domains here - let each method enable what it needs
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close CDP session."""
        # Don't detach session - let the pool manage it
        # This prevents "Target closed" errors
        pass
            
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
        
        # Enable domains needed for accessibility tree
        try:
            await self.cdp_session.send("DOM.enable")
            await self.cdp_session.send("Accessibility.enable")
        except Exception as e:
            print(f"Warning: Failed to enable CDP domains: {e}")
        
        try:
            # Collect accessibility trees from all frames
            frame_snapshots = await self._collect_frame_snapshots()
            
            # Merge all frame trees into a single tree
            simplified = []
            encoded_xpath_map = {}
            url_map = {}
            
            for snapshot in frame_snapshots:
                # Add frame tree to overall tree
                simplified.extend(snapshot['simplified_tree'])
                
                # Merge XPath mappings with frame prefixes
                for encoded_id, xpath in snapshot['xpath_map'].items():
                    frame_prefix = snapshot.get('frame_xpath', '')
                    if frame_prefix and frame_prefix != '/':
                        # Prepend frame path to XPath
                        encoded_xpath_map[encoded_id] = frame_prefix + xpath
                    else:
                        encoded_xpath_map[encoded_id] = xpath
                
                # Add frame URL to map
                if snapshot.get('frame_id'):
                    url_map[str(snapshot['frame_ordinal'])] = snapshot['frame_url']
                else:
                    url_map['0'] = snapshot['frame_url']  # Main frame
            
            return simplified, encoded_xpath_map, url_map
        finally:
            # Disable domains when done
            try:
                await self.cdp_session.send("DOM.disable")
                await self.cdp_session.send("Accessibility.disable")
            except:
                pass  # Ignore errors during cleanup
            
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
        element_info_map = {}  # Store element info for sophisticated XPath generation
        
        # Get the full DOM tree
        try:
            dom_response = await self.cdp_session.send("DOM.getDocument", {"depth": -1})
            root = dom_response.get("root", {})
            
            def traverse_node(node: Dict[str, Any], parent_xpath: str = "", position_map: Dict[str, int] = None, element_path: List[Dict[str, str]] = None) -> None:
                """Recursively traverse DOM nodes."""
                if position_map is None:
                    position_map = {}
                if element_path is None:
                    element_path = []
                    
                backend_id = node.get("backendNodeId")
                node_type = node.get("nodeType")
                node_name = node.get("nodeName", "").lower()
                attributes = node.get("attributes", [])
                
                # Build XPath for this node
                if node_type == 1:  # ELEMENT_NODE
                    # Calculate position among siblings of same type
                    parent_key = f"{parent_xpath}:{node_name}"
                    position = position_map.get(parent_key, 0) + 1
                    position_map[parent_key] = position
                    
                    # Build element path for positional XPath
                    current_path = element_path + [{'tagName': node_name, 'index': position}]
                    
                    # Build the XPath - use 0-based index for body to match TypeScript
                    if node_name == "body" and parent_xpath == "/html[1]":
                        xpath_segment = f"/{node_name}[0]"
                    else:
                        xpath_segment = f"/{node_name}[{position}]"
                    
                    current_xpath = parent_xpath + xpath_segment
                    
                    if backend_id:
                        tag_name_map[backend_id] = node_name
                        
                        # Parse attributes into dictionary
                        attr_dict = {}
                        for i in range(0, len(attributes), 2):
                            if i + 1 < len(attributes):
                                attr_dict[attributes[i]] = attributes[i + 1]
                        
                        # Store element info for sophisticated XPath generation
                        element_info = {
                            'tagName': node_name,
                            'id': attr_dict.get('id', ''),
                            'class': attr_dict.get('class', ''),
                            'name': attr_dict.get('name', ''),
                            'role': attr_dict.get('role', ''),
                            'text': '',  # Will be populated later if needed
                            'path': current_path,
                            'attributes': attr_dict
                        }
                        
                        # Add data attributes
                        for attr_name in ['data-testid', 'data-test', 'data-qa', 'data-id', 'data-cy']:
                            if attr_name in attr_dict:
                                element_info[attr_name] = attr_dict[attr_name]
                        
                        element_info_map[backend_id] = element_info
                        
                        # Use the current positional XPath for element nodes
                        xpath_map[backend_id] = current_xpath
                        
                    # Traverse children
                    children = node.get("children", [])
                    child_position_map = {}
                    for child in children:
                        traverse_node(child, current_xpath, child_position_map, current_path)
                        
                elif node_type == 3:  # TEXT_NODE
                    # Text nodes get special XPath
                    parent_key = f"{parent_xpath}:text()"
                    position = position_map.get(parent_key, 0) + 1
                    position_map[parent_key] = position
                    
                    xpath = f"{parent_xpath}/text()[{position}]"
                    if backend_id:
                        xpath_map[backend_id] = xpath
                elif node_type == 8:  # COMMENT_NODE
                    # Comment nodes get special XPath
                    parent_key = f"{parent_xpath}:comment()"
                    position = position_map.get(parent_key, 0) + 1
                    position_map[parent_key] = position
                    
                    xpath = f"{parent_xpath}/comment()[{position}]"
                    if backend_id:
                        xpath_map[backend_id] = xpath
                else:
                    # For other node types (like document nodes), still traverse children
                    children = node.get("children", [])
                    for child in children:
                        traverse_node(child, parent_xpath, position_map, element_path)
                        
            traverse_node(root)
            
            # Don't override the positional XPaths - they should match TypeScript exactly
            
        except Exception as e:
            # Log error but continue
            print(f"Error building backend ID maps: {e}")
            
        return tag_name_map, xpath_map
        
    async def _collect_frame_snapshots(self) -> List[Dict[str, Any]]:
        """
        Collect accessibility tree snapshots from all frames.
        
        Returns:
            List of frame snapshots containing tree and mapping data
        """
        snapshots = []
        
        # Process main frame first
        main_frame = self.page.main_frame
        main_snapshot = await self._get_frame_snapshot(main_frame, None, '/', 0)
        if main_snapshot:
            snapshots.append(main_snapshot)
        
        # Process child frames recursively
        frame_ordinal = 1
        for child_frame in main_frame.child_frames:
            child_snapshots = await self._collect_child_frame_snapshots(
                child_frame, frame_ordinal
            )
            snapshots.extend(child_snapshots)
            frame_ordinal += len(child_snapshots)
        
        return snapshots
    
    async def _collect_child_frame_snapshots(
        self, frame: Any, ordinal_start: int
    ) -> List[Dict[str, Any]]:
        """
        Recursively collect snapshots from a frame and its children.
        
        Args:
            frame: The frame to process
            ordinal_start: Starting ordinal number for frames
            
        Returns:
            List of frame snapshots
        """
        snapshots = []
        current_ordinal = ordinal_start
        
        # Get frame's backend node ID and XPath
        try:
            frame_backend_id = await self._get_frame_backend_node_id(frame)
            frame_xpath = await self._get_frame_xpath(frame)
            
            # Get snapshot for this frame
            snapshot = await self._get_frame_snapshot(
                frame, frame_backend_id, frame_xpath, current_ordinal
            )
            if snapshot:
                snapshots.append(snapshot)
                current_ordinal += 1
            
            # Process child frames
            for child_frame in frame.child_frames:
                child_snapshots = await self._collect_child_frame_snapshots(
                    child_frame, current_ordinal
                )
                snapshots.extend(child_snapshots)
                current_ordinal += len(child_snapshots)
                
        except Exception as e:
            print(f"Error processing frame {frame.url}: {e}")
            
        return snapshots
    
    async def _get_frame_snapshot(
        self, frame: Any, backend_node_id: Optional[int], 
        frame_xpath: str, ordinal: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get accessibility tree snapshot for a single frame.
        
        Args:
            frame: The frame to process
            backend_node_id: Backend node ID of the frame element
            frame_xpath: XPath to the frame element
            ordinal: Frame ordinal number
            
        Returns:
            Frame snapshot dictionary or None if failed
        """
        try:
            # Get CDP session from pool for this frame
            frame_session = await cdp_manager.get_session(frame.page, frame)
            
            try:
                # Enable domains on the frame session
                await frame_session.send("DOM.enable")
                await frame_session.send("Accessibility.enable")
                # Get accessibility tree for frame
                ax_response = await frame_session.send("Accessibility.getFullAXTree")
                ax_nodes = ax_response.get("nodes", [])
                
                # Build backend ID mappings for frame
                tag_name_map, xpath_map = await self._build_frame_backend_id_maps(
                    frame_session, frame.url
                )
                
                # Build hierarchical tree
                tree = self._build_hierarchical_tree(ax_nodes)
                
                # Get scrollable elements for this frame
                scrollable_backend_ids = await self._get_scrollable_backend_ids(frame_session)
                
                # Simplify tree with scrollable decoration
                simplified = self._simplify_tree(tree, tag_name_map, scrollable_backend_ids, xpath_map)
                
                # Encode IDs with frame information
                encoded_xpath_map = {}
                frame_id = await self._get_cdp_frame_id(frame)
                
                for backend_id, xpath in xpath_map.items():
                    encoded_id = self.ai_browser_automation_page.encode_with_frame_id(
                        frame_id, backend_id
                    )
                    encoded_xpath_map[encoded_id] = xpath
                
                return {
                    'simplified_tree': simplified,
                    'xpath_map': encoded_xpath_map,
                    'frame_url': frame.url,
                    'frame_xpath': frame_xpath,
                    'frame_id': frame_id,
                    'frame_ordinal': ordinal,
                    'backend_node_id': backend_node_id
                }
                
            finally:
                await frame_session.send("DOM.disable")
                await frame_session.send("Accessibility.disable")
                # Session detach handled by pool
                
        except Exception as e:
            print(f"Error getting frame snapshot: {e}")
            return None
    
    async def _get_frame_backend_node_id(self, frame: Any) -> Optional[int]:
        """
        Get the backend node ID of the iframe element containing a frame.
        
        Args:
            frame: The frame to find the container for
            
        Returns:
            Backend node ID or None if not found
        """
        if frame == self.page.main_frame:
            return None
            
        try:
            # Get CDP frame ID
            frame_id = await self._get_cdp_frame_id(frame)
            if not frame_id:
                return None
                
            # Get frame owner
            response = await self.cdp_session.send("DOM.getFrameOwner", {
                "frameId": frame_id
            })
            return response.get("backendNodeId")
            
        except Exception as e:
            print(f"Error getting frame backend node ID: {e}")
            return None
    
    async def _get_frame_xpath(self, frame: Any) -> str:
        """
        Get the XPath to the iframe element containing a frame.
        
        Args:
            frame: The frame to find the XPath for
            
        Returns:
            XPath string
        """
        if frame == self.page.main_frame:
            return '/'
            
        try:
            # Use frame locator to get XPath
            frame_element = frame.frame_element()
            if frame_element:
                xpath_info = await frame_element.evaluate(XPATH_GENERATION_SCRIPT, frame_element)
                return xpath_info.get('unique_xpath') or xpath_info.get('positional_xpath', '/')
                
        except Exception:
            pass
            
        return '/'
    
    async def _get_cdp_frame_id(self, frame: Any) -> Optional[str]:
        """
        Get the CDP frame ID for a Playwright frame.
        Following TypeScript's getCDPFrameId implementation.
        
        Args:
            frame: The Playwright frame
            
        Returns:
            CDP frame ID or None
        """
        try:
            # For main frame, return None
            if not frame or frame == self.page.main_frame:
                return None
            
            # Get frame tree from CDP
            response = await self.cdp_session.send('Page.getFrameTree')
            frame_tree = response.get('frameTree', {})
            
            # Search for frame by URL and depth
            frame_url = frame.url
            
            # Calculate frame depth
            depth = 0
            parent = frame.parent_frame
            while parent:
                depth += 1
                parent = parent.parent_frame
            
            def find_frame_by_url_depth(node: Dict[str, Any], current_depth: int = 0) -> Optional[str]:
                """Find frame ID by URL and depth in frame tree."""
                frame_info = node.get('frame', {})
                if current_depth == depth and frame_info.get('url') == frame_url:
                    return frame_info.get('id')
                
                # Search children
                for child in node.get('childFrames', []):
                    frame_id = find_frame_by_url_depth(child, current_depth + 1)
                    if frame_id:
                        return frame_id
                
                return None
            
            # Try to find frame in the tree
            frame_id = find_frame_by_url_depth(frame_tree)
            if frame_id:
                return frame_id
            
            # For out-of-process iframes, try creating a new session
            try:
                frame_session = await self.page.context.new_cdp_session(frame)
                frame_response = await frame_session.send('Page.getFrameTree')
                frame_tree = frame_response.get('frameTree', {})
                frame_id = frame_tree.get('frame', {}).get('id')
                await frame_session.detach()
                return frame_id
            except Exception:
                # Frame might not have a separate session
                pass
            
            return None
            
        except Exception as e:
            # Silently fail - frame ID is optional
            return None
    
    async def _build_frame_backend_id_maps(
        self, session: CDPSession, frame_url: str
    ) -> Tuple[Dict[int, str], Dict[int, str]]:
        """
        Build backend ID maps for a specific frame using its CDP session.
        
        Args:
            session: CDP session for the frame
            frame_url: URL of the frame
            
        Returns:
            Tuple of (tag_name_map, xpath_map)
        """
        # Similar to _build_backend_id_maps but uses the frame's session
        try:
            # Use the provided session instead of self.cdp_session
            tag_name_map = {}
            xpath_map = {}
            element_info_map = {}
            
            # Get the full DOM tree for this frame
            dom_response = await session.send("DOM.getDocument", {"depth": -1})
            root = dom_response.get("root", {})
            
            # Use the same traverse_node logic but with frame session
            def traverse_node(node: Dict[str, Any], parent_xpath: str = "", position_map: Dict[str, int] = None, element_path: List[Dict[str, str]] = None) -> None:
                if position_map is None:
                    position_map = {}
                if element_path is None:
                    element_path = []
                    
                backend_id = node.get("backendNodeId")
                node_type = node.get("nodeType")
                node_name = node.get("nodeName", "").lower()
                attributes = node.get("attributes", [])
                
                if node_type == 1:  # ELEMENT_NODE
                    parent_key = f"{parent_xpath}:{node_name}"
                    position = position_map.get(parent_key, 0) + 1
                    position_map[parent_key] = position
                    
                    current_path = element_path + [{'tagName': node_name, 'index': position}]
                    
                    if backend_id:
                        tag_name_map[backend_id] = node_name
                        
                        # Parse attributes
                        attr_dict = {}
                        for i in range(0, len(attributes), 2):
                            if i + 1 < len(attributes):
                                attr_dict[attributes[i]] = attributes[i + 1]
                        
                        element_info = {
                            'tagName': node_name,
                            'id': attr_dict.get('id', ''),
                            'class': attr_dict.get('class', ''),
                            'name': attr_dict.get('name', ''),
                            'role': attr_dict.get('role', ''),
                            'text': '',
                            'path': current_path,
                            'attributes': attr_dict
                        }
                        
                        for attr_name in ['data-testid', 'data-test', 'data-qa', 'data-id', 'data-cy']:
                            if attr_name in attr_dict:
                                element_info[attr_name] = attr_dict[attr_name]
                        
                        element_info_map[backend_id] = element_info
                        
                        # Generate XPath strategies
                        xpaths = generate_xpath_strategies(element_info, node_name)
                        positional_xpath = build_positional_xpath(current_path)
                        xpaths.append(positional_xpath)
                        
                        xpath_map[backend_id] = xpaths[0] if xpaths else positional_xpath
                        
                    # Traverse children
                    children = node.get("children", [])
                    child_position_map = {}
                    for child in children:
                        traverse_node(child, parent_xpath + f"/{node_name}[{position}]", child_position_map, current_path)
                        
                elif node_type == 3:  # TEXT_NODE
                    parent_key = f"{parent_xpath}:text()"
                    position = position_map.get(parent_key, 0) + 1
                    position_map[parent_key] = position
                    
                    xpath = f"{parent_xpath}/text()[{position}]"
                    if backend_id:
                        xpath_map[backend_id] = xpath
                elif node_type == 8:  # COMMENT_NODE
                    parent_key = f"{parent_xpath}:comment()"
                    position = position_map.get(parent_key, 0) + 1
                    position_map[parent_key] = position
                    
                    xpath = f"{parent_xpath}/comment()[{position}]"
                    if backend_id:
                        xpath_map[backend_id] = xpath
                else:
                    children = node.get("children", [])
                    for child in children:
                        traverse_node(child, parent_xpath, position_map, element_path)
                        
            traverse_node(root)
            
            # Validate XPaths for frame context (simplified for now)
            # In a real implementation, we'd need to validate against the frame's document
            
            return tag_name_map, xpath_map
            
        except Exception as e:
            print(f"Error building frame backend ID maps: {e}")
            return {}, {}
    
    async def _get_scrollable_backend_ids(self, session: CDPSession) -> set:
        """
        Get backend IDs of scrollable elements in a frame.
        
        Args:
            session: CDP session for the frame
            
        Returns:
            Set of backend node IDs for scrollable elements
        """
        scrollable_ids = set()
        
        try:
            # Execute script to find scrollable elements
            result = await session.send("Runtime.evaluate", {
                "expression": """
                    (() => {
                        const scrollables = [];
                        const elements = document.querySelectorAll('*');
                        
                        for (const element of elements) {
                            const style = window.getComputedStyle(element);
                            const overflow = style.overflow + style.overflowY + style.overflowX;
                            
                            if (overflow.includes('auto') || overflow.includes('scroll') || overflow.includes('overlay')) {
                                const hasScroll = element.scrollHeight > element.clientHeight || 
                                                element.scrollWidth > element.clientWidth;
                                if (hasScroll) {
                                    // Try to get backend node ID
                                    const backendId = element.__backendNodeId || element.getAttribute('__backendNodeId');
                                    if (backendId) {
                                        scrollables.push(parseInt(backendId));
                                    }
                                }
                            }
                        }
                        
                        return scrollables;
                    })()
                """,
                "returnByValue": True
            })
            
            if result.get('result', {}).get('value'):
                scrollable_ids.update(result['result']['value'])
                
        except Exception as e:
            print(f"Error getting scrollable backend IDs: {e}")
            
        return scrollable_ids
        
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
        
    def _simplify_tree(self, tree: Dict[str, Any], tag_name_map: Dict[int, str], scrollable_backend_ids: Optional[set] = None, xpath_map: Optional[Dict[int, str]] = None) -> List[Dict[str, Any]]:
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
            
            # Skip certain roles (matching TypeScript)
            skip_roles = {"generic", "none", "presentation", "InlineTextBox", "StaticText"}
            if role in skip_roles and not name and not value:
                # Process children directly
                for child in node.get("children", []):
                    flatten(child, depth)
                return
            
            # Also skip text nodes that have text() in their XPath
            if xpath_map and backend_id and backend_id in xpath_map:
                xpath = xpath_map.get(backend_id, "")
                if "/text()[" in xpath:
                    # Skip text nodes entirely
                    return
                
            # Check if node is scrollable and decorate role
            if scrollable_backend_ids and backend_id in scrollable_backend_ids:
                if role and role not in ["generic", "none"]:
                    role = f"scrollable, {role}"
                else:
                    role = "scrollable"
            
            # Create simplified node with encoded ID
            simplified_node = {
                "nodeId": backend_id,
                "encodedId": self.ai_browser_automation_page.encode_with_frame_id(None, backend_id) if backend_id else None,
                "role": role,
                "name": name
            }
            
            # Only add tagName for non-text nodes (matching TypeScript)
            # StaticText nodes represent text content, not HTML elements
            if role != "StaticText":
                simplified_node["tagName"] = tag_name_map.get(backend_id, "div")
            
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