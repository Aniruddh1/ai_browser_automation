"""
Accessibility tree utilities using Chrome DevTools Protocol.
Matches TypeScript implementation for better alignment.
"""

import asyncio
import json
from typing import Dict, List, Any, Optional, Tuple, Union, Set, TYPE_CHECKING
from playwright.async_api import CDPSession, Frame
import weakref

if TYPE_CHECKING:
    from ..core import PlaywrightAIPage

from ..types import EncodedId, AccessibilityNode, TreeResult, DOMNode, BackendIdMaps


# Private Use Area character ranges
PUA_START = 0xE000
PUA_END = 0xF8FF

# Non-breaking space characters
NBSP_CHARS = {0x00A0, 0x202F, 0x2007, 0xFEFF}


def clean_text(input_str: str) -> str:
    """
    Clean a string by removing private-use unicode characters, normalizing whitespace,
    and trimming the result. Matches TypeScript's cleanText function.
    """
    output = ""
    prev_was_space = False
    
    for char in input_str:
        code = ord(char)
        
        # Skip private-use area glyphs
        if PUA_START <= code <= PUA_END:
            continue
            
        # Convert NBSP-family characters to a single space, collapsing repeats
        if code in NBSP_CHARS:
            if not prev_was_space:
                output += " "
                prev_was_space = True
            continue
            
        # Append the character and update space tracker
        output += char
        prev_was_space = char == " "
    
    # Trim leading/trailing spaces before returning
    return output.strip()


def format_simplified_tree(node: AccessibilityNode, level: int = 0) -> str:
    """
    Generate a human-readable, indented outline of an accessibility node tree.
    Matches TypeScript's formatSimplifiedTree function.
    """
    indent = "  " * level
    
    # Use encodedId if available, otherwise fallback to nodeId
    id_label = getattr(node, 'encodedId', None) or node.get('nodeId', '')
    
    # Prepare the formatted name segment if present
    name = node.get('name', '')
    name_part = f": {clean_text(name)}" if name else ""
    
    # Build current line and recurse into child nodes
    current_line = f"{indent}[{id_label}] {node.get('role', '')}:{name_part}\n"
    
    children = node.get('children', [])
    children_lines = "".join(
        format_simplified_tree(child, level + 1) for child in children
    )
    
    return current_line + children_lines


# Memoized lowercase cache
_lower_cache: Dict[str, str] = {}


def lc(raw: str) -> str:
    """Memoized lowercase conversion to avoid repeated .lower() calls."""
    if raw not in _lower_cache:
        _lower_cache[raw] = raw.lower()
    return _lower_cache[raw]


async def build_backend_id_maps(
    sp: 'PlaywrightAIPage',
    target_frame: Optional[Frame] = None
) -> BackendIdMaps:
    """
    Build mappings from CDP backendNodeIds to HTML tag names and relative XPaths.
    Matches TypeScript's buildBackendIdMaps function.
    """
    # Choose CDP session
    if not target_frame or target_frame == sp._page.main_frame:
        session = await sp.get_cdp_client()
    else:
        try:
            # Try OOPIF session
            session = await sp._page.context.new_cdp_session(target_frame)
        except:
            # Fallback to main session for same-proc iframe
            session = await sp.get_cdp_client()
    
    # Enable DOM domain
    await sp.enable_cdp("DOM", target_frame if session != await sp.get_cdp_client() else None)
    
    try:
        # Get full DOM tree
        response = await session.send("DOM.getDocument", {"depth": -1, "pierce": True})
        root = response["root"]
        
        # Pick start node + root frame-id
        start_node = root
        root_fid = None
        
        if target_frame and target_frame != sp._page.main_frame:
            # Get frame ID
            root_fid = await get_cdp_frame_id(sp, target_frame)
            
            # For same-proc iframe, walk down to its contentDocument
            if session == await sp.get_cdp_client():
                frame_id = root_fid
                owner_response = await sp.send_cdp("DOM.getFrameOwner", {"frameId": frame_id})
                backend_node_id = owner_response["backendNodeId"]
                
                # Find iframe node in tree
                iframe_node = None
                
                def locate(n: Dict[str, Any]) -> bool:
                    nonlocal iframe_node
                    if n.get("backendNodeId") == backend_node_id:
                        iframe_node = n
                        return True
                    
                    # Check children
                    for child in n.get("children", []):
                        if locate(child):
                            return True
                    
                    # Check content document
                    if "contentDocument" in n:
                        return locate(n["contentDocument"])
                    
                    return False
                
                if not locate(root) or not iframe_node or "contentDocument" not in iframe_node:
                    raise Exception("iframe element or its contentDocument not found")
                
                start_node = iframe_node["contentDocument"]
                root_fid = iframe_node["contentDocument"].get("frameId", frame_id)
        
        # DFS walk: fill maps
        tag_name_map: Dict[EncodedId, str] = {}
        xpath_map: Dict[EncodedId, str] = {}
        
        stack = [(start_node, "", root_fid)]
        seen: Set[EncodedId] = set()
        
        while stack:
            node, path, fid = stack.pop()
            
            backend_id = node.get("backendNodeId")
            if not backend_id:
                continue
                
            enc = sp.encode_with_frame_id(fid, backend_id)
            if enc in seen:
                continue
            seen.add(enc)
            
            tag_name_map[enc] = lc(node.get("nodeName", ""))
            xpath_map[enc] = path
            
            # Recurse into sub-document if <iframe>
            if lc(node.get("nodeName", "")) == "iframe" and "contentDocument" in node:
                child_fid = node["contentDocument"].get("frameId", fid)
                stack.append((node["contentDocument"], "", child_fid))
            
            # Push children
            kids = node.get("children", [])
            if kids:
                # Build per-child XPath segment (L→R)
                segs = []
                ctr = {}
                
                for child in kids:
                    tag = lc(child.get("nodeName", ""))
                    node_type = child.get("nodeType", 1)
                    key = f"{node_type}:{tag}"
                    idx = ctr.get(key, 0) + 1
                    ctr[key] = idx
                    
                    if node_type == 3:  # TEXT_NODE
                        seg = f"text()[{idx}]"
                    elif node_type == 8:  # COMMENT_NODE
                        seg = f"comment()[{idx}]"
                    else:
                        seg = f"{tag}[{idx}]"
                    
                    segs.append(seg)
                
                # Push R→L so traversal remains L→R
                for i in range(len(kids) - 1, -1, -1):
                    stack.append((kids[i], f"{path}/{segs[i]}", fid))
        
        return {"tagNameMap": tag_name_map, "xpathMap": xpath_map}
        
    finally:
        # Disable DOM domain
        await sp.disable_cdp("DOM", target_frame if session != await sp.get_cdp_client() else None)


async def clean_structural_nodes(
    node: AccessibilityNode,
    tag_name_map: Dict[EncodedId, str],
    logger: Optional[Any] = None
) -> Optional[AccessibilityNode]:
    """
    Recursively prune or collapse structural nodes in the AX tree to simplify hierarchy.
    Matches TypeScript's cleanStructuralNodes function.
    """
    # Ignore negative pseudo-nodes
    if int(node.get("nodeId", 0)) < 0:
        return None
    
    # Leaf check
    children = node.get("children", [])
    if not children:
        return None if node.get("role") in ("generic", "none") else node
    
    # Recurse into children
    cleaned_children = []
    for child in children:
        cleaned = await clean_structural_nodes(child, tag_name_map, logger)
        if cleaned:
            cleaned_children.append(cleaned)
    
    # Collapse/prune generic wrappers
    role = node.get("role", "")
    if role in ("generic", "none"):
        if len(cleaned_children) == 1:
            # Collapse single-child structural node
            return cleaned_children[0]
        elif len(cleaned_children) == 0:
            # Remove empty structural node
            return None
    
    # Replace generic role with real tag name (if we know it)
    if role in ("generic", "none") and "encodedId" in node:
        tag_name = tag_name_map.get(node["encodedId"])
        if tag_name:
            node["role"] = tag_name
    
    # Drop redundant StaticText children
    pruned = remove_redundant_static_text_children(node, cleaned_children)
    if not pruned and role in ("generic", "none"):
        return None
    
    # Return updated node
    return {**node, "children": pruned}


def remove_redundant_static_text_children(
    parent: AccessibilityNode,
    children: List[AccessibilityNode]
) -> List[AccessibilityNode]:
    """Remove redundant StaticText children when parent has same text."""
    parent_text = (parent.get("name", "") or "").strip()
    if not parent_text:
        return children
    
    filtered = []
    for child in children:
        # Skip StaticText children that duplicate parent text
        if child.get("role") == "StaticText":
            # Note: at this stage, we've already processed nodes so role is a string
            child_name = child.get("name", "")
            child_text = (child_name if isinstance(child_name, str) else "").strip()
            if child_text == parent_text:
                continue
        filtered.append(child)
    
    return filtered


def extract_url_from_ax_node(node: AccessibilityNode) -> Optional[str]:
    """Extract URL from accessibility node if it's a link."""
    # Extract role from object structure
    role_obj = node.get("role", {})
    role_value = role_obj.get("value", "") if isinstance(role_obj, dict) else ""
    
    if role_value != "link":
        return None
    
    # Check for URL in value
    value = node.get("value", {})
    if isinstance(value, dict) and value.get("type") == "url":
        return value.get("value")
    
    # Check for href in properties
    props = node.get("properties", [])
    if isinstance(props, list):
        for prop in props:
            if isinstance(prop, dict) and prop.get("name") == "href":
                prop_value = prop.get("value", {})
                if isinstance(prop_value, dict) and prop_value.get("type") == "string":
                    return prop_value.get("value")
    
    return None


async def build_hierarchical_tree(
    nodes: List[AccessibilityNode],
    tag_name_map: Dict[EncodedId, str],
    logger: Optional[Any] = None,
    xpath_map: Optional[Dict[EncodedId, str]] = None
) -> TreeResult:
    """
    Convert a flat array of AccessibilityNodes into a cleaned, hierarchical tree.
    Matches TypeScript's buildHierarchicalTree function.
    """
    # EncodedId → URL (only if the backend-id is unique)
    id_to_url: Dict[EncodedId, str] = {}
    
    # nodeId → mutable copy of the AX node we keep
    node_map: Dict[str, AccessibilityNode] = {}
    
    # List of iframe AX nodes
    iframe_list: List[AccessibilityNode] = []
    
    # Helper: keep only roles that matter to the LLM
    def is_interactive(n: AccessibilityNode) -> bool:
        role_obj = n.get("role", {})
        role_value = role_obj.get("value", "") if isinstance(role_obj, dict) else ""
        return role_value not in ("none", "generic", "InlineTextBox")
    
    # Build "backendId → EncodedId[]" lookup from tagNameMap keys
    backend_to_ids: Dict[int, List[EncodedId]] = {}
    for enc in tag_name_map.keys():
        # Split "ff-bb" format
        parts = enc.split("-")
        if len(parts) == 2:
            backend = int(parts[1])
            if backend not in backend_to_ids:
                backend_to_ids[backend] = []
            backend_to_ids[backend].append(enc)
    
    # Pass 1 – copy/filter CDP nodes we want to keep
    for node in nodes:
        node_id = node.get("nodeId", "")
        if int(node_id) < 0:  # Skip pseudo-nodes
            continue
        
        url = extract_url_from_ax_node(node)
        
        # Keep node if it has name, children, or is interactive
        # Note: node.name is an object with a 'value' property, not a string
        name_obj = node.get("name", {})
        name_value = name_obj.get("value", "") if isinstance(name_obj, dict) else ""
        keep = (
            name_value.strip() or
            node.get("childIds", []) or
            is_interactive(node)
        )
        
        if not keep:
            continue
        
        # Resolve our EncodedId (unique per backendId)
        encoded_id = None
        backend_id = node.get("backendDOMNodeId")
        if backend_id is not None:
            matches = backend_to_ids.get(backend_id, [])
            if len(matches) == 1:
                encoded_id = matches[0]  # Unique → keep
        
        # Store URL only when we have an unambiguous EncodedId
        if url and encoded_id:
            id_to_url[encoded_id] = url
        
        # Create rich node
        # Extract role value (role is an object with 'value' property)
        role_obj = node.get("role", {})
        role_value = role_obj.get("value", "") if isinstance(role_obj, dict) else ""
        
        rich_node = {
            "nodeId": node_id,
            "role": role_value,
        }
        
        if encoded_id:
            rich_node["encodedId"] = encoded_id
            
        # Extract string values from property objects
        name_obj = node.get("name")
        if name_obj and isinstance(name_obj, dict):
            rich_node["name"] = name_obj.get("value", "")
            
        desc_obj = node.get("description")
        if desc_obj and isinstance(desc_obj, dict):
            rich_node["description"] = desc_obj.get("value", "")
            
        value_obj = node.get("value")
        if value_obj and isinstance(value_obj, dict):
            rich_node["value"] = value_obj.get("value", "")
            
        if backend_id is not None:
            rich_node["backendDOMNodeId"] = backend_id
        
        node_map[node_id] = rich_node
    
    # Pass 2 – parent-child wiring
    for node in nodes:
        node_id = node.get("nodeId", "")
        role_obj = node.get("role", {})
        role_value = role_obj.get("value", "") if isinstance(role_obj, dict) else ""
        
        if role_value == "Iframe":
            iframe_list.append({"role": role_value, "nodeId": node_id})
        
        parent_id = node.get("parentId")
        if not parent_id:
            continue
            
        parent = node_map.get(parent_id)
        current = node_map.get(node_id)
        
        if parent and current:
            if "children" not in parent:
                parent["children"] = []
            parent["children"].append(current)
    
    # Pass 3 – prune structural wrappers & tidy tree
    roots = []
    for node in nodes:
        if not node.get("parentId") and node.get("nodeId", "") in node_map:
            roots.append(node_map[node["nodeId"]])
    
    cleaned_roots = []
    for root in roots:
        cleaned = await clean_structural_nodes(root, tag_name_map, logger)
        if cleaned:
            cleaned_roots.append(cleaned)
    
    # Pretty outline for logging/LLM input
    simplified = "\n".join(format_simplified_tree(root) for root in cleaned_roots)
    
    return {
        "tree": cleaned_roots,
        "simplified": simplified,
        "iframes": iframe_list,
        "idToUrl": id_to_url,
        "xpathMap": xpath_map,
    }


async def get_cdp_frame_id(
    sp: 'PlaywrightAIPage',
    frame: Optional[Frame] = None
) -> Optional[str]:
    """
    Resolve the CDP frame identifier for a Playwright Frame.
    Matches TypeScript's getCDPFrameId function.
    """
    if not frame or frame == sp._page.main_frame:
        return None
    
    # 1. Same-proc search in the page-session tree
    root_resp = await sp.send_cdp("Page.getFrameTree")
    frame_tree = root_resp["frameTree"]
    
    url = frame.url
    depth = 0
    p = frame.parent_frame
    while p:
        depth += 1
        p = p.parent_frame
    
    def find_by_url_depth(node: Dict[str, Any], lvl: int = 0) -> Optional[str]:
        if lvl == depth and node["frame"]["url"] == url:
            return node["frame"]["id"]
        
        for child in node.get("childFrames", []):
            frame_id = find_by_url_depth(child, lvl + 1)
            if frame_id:
                return frame_id
        
        return None
    
    same_proc_id = find_by_url_depth(frame_tree)
    if same_proc_id:
        return same_proc_id  # Found in page tree
    
    # 2. OOPIF path: open its own target
    try:
        sess = await sp._page.context.new_cdp_session(frame)
        own_resp = await sess.send("Page.getFrameTree")
        own_tree = own_resp["frameTree"]
        return own_tree["frame"]["id"]  # Root of OOPIF
    except Exception as err:
        raise Exception(f"Failed to get frame ID for {url}: {err}")


async def find_scrollable_element_ids(
    stagehand_page: 'PlaywrightAIPage',
    target_frame: Optional[Frame] = None
) -> Set[int]:
    """
    Find backend node IDs of scrollable elements.
    Matches TypeScript's findScrollableElementIds function.
    """
    # Get scrollable element XPaths from injected DOM script
    if target_frame:
        xpaths = await target_frame.evaluate("() => window.getScrollableElementXpaths ? window.getScrollableElementXpaths() : []")
    else:
        xpaths = await stagehand_page._page.evaluate("() => window.getScrollableElementXpaths ? window.getScrollableElementXpaths() : []")
    
    backend_ids = set()
    
    for xpath in xpaths:
        if not xpath:
            continue
            
        try:
            # Resolve XPath to object ID
            object_id = await resolve_object_id_for_xpath(stagehand_page, xpath, target_frame)
            
            if object_id:
                # Get backend node ID
                response = await stagehand_page.send_cdp(
                    "DOM.describeNode",
                    {"objectId": object_id},
                    target_frame
                )
                node = response.get("node", {})
                backend_id = node.get("backendNodeId")
                if backend_id:
                    backend_ids.add(backend_id)
        except:
            # Skip failed XPath resolutions
            pass
    
    return backend_ids


async def resolve_object_id_for_xpath(
    page: 'PlaywrightAIPage',
    xpath: str,
    target_frame: Optional[Frame] = None
) -> Optional[str]:
    """
    Resolve an XPath to a Chrome DevTools Protocol remote object ID.
    Matches TypeScript's resolveObjectIdForXPath function.
    """
    expression = f"""
        (() => {{
          const res = document.evaluate(
            {json.dumps(xpath)},
            document,
            null,
            XPathResult.FIRST_ORDERED_NODE_TYPE,
            null
          );
          return res.singleNodeValue;
        }})();
    """
    
    response = await page.send_cdp(
        "Runtime.evaluate",
        {
            "expression": expression,
            "returnByValue": False
        },
        target_frame
    )
    
    result = response.get("result", {})
    return result.get("objectId")


def decorate_roles(nodes: List[Dict[str, Any]], scrollable_ids: Set[int]) -> List[Dict[str, Any]]:
    """
    Decorate accessibility nodes with scrollable indicator.
    Matches TypeScript's decorateRoles function.
    """
    decorated = []
    for node in nodes:
        decorated_node = node.copy()
        backend_id = node.get("backendDOMNodeId")
        
        if backend_id and backend_id in scrollable_ids:
            role = node.get("role", {}).get("value", "")
            if role and role not in ("generic", "none"):
                decorated_node["role"]["value"] = f"scrollable, {role}"
            else:
                decorated_node["role"]["value"] = "scrollable"
        
        decorated.append(decorated_node)
    
    return decorated


async def get_accessibility_tree(
    stagehand_page: 'PlaywrightAIPage',
    logger: Optional[Any] = None,
    selector: Optional[str] = None,
    target_frame: Optional[Frame] = None
) -> TreeResult:
    """
    Retrieve and build a cleaned accessibility tree for a document or specific iframe.
    Matches TypeScript's getAccessibilityTree function.
    """
    # 0. DOM helpers (maps, xpath)
    backend_maps = await build_backend_id_maps(stagehand_page, target_frame)
    tag_name_map = backend_maps["tagNameMap"]
    xpath_map = backend_maps["xpathMap"]
    
    # Enable accessibility
    await stagehand_page.enable_cdp("Accessibility", target_frame)
    
    try:
        # Determine params and session for CDP call
        snapshot_params = {}
        session_frame = target_frame  # default: talk to that frame
        
        if target_frame and target_frame != stagehand_page._page.main_frame:
            # Try opening a CDP session: succeeds only for OOPIFs
            is_oopif = True
            try:
                await stagehand_page._page.context.new_cdp_session(target_frame)
            except:
                is_oopif = False
            
            if not is_oopif:
                # Same-proc iframe -> use page session + frameId
                frame_id = await get_cdp_frame_id(stagehand_page, target_frame)
                if logger:
                    logger({
                        "message": f"same-proc iframe: frameId={frame_id}. Using existing CDP session.",
                        "level": 1
                    })
                if frame_id:
                    snapshot_params = {"frameId": frame_id}
                session_frame = None  # Use page session
            else:
                if logger:
                    logger({"message": "OOPIF iframe: using frame-specific CDP session", "level": 1})
                snapshot_params = {}  # No frameId allowed
                session_frame = target_frame  # Talk to OOPIF session
        
        # If selector provided, resolve to backend node ID
        if selector:
            # TODO: Implement selector resolution
            pass
        
        # Get the accessibility tree
        response = await stagehand_page.send_cdp(
            "Accessibility.getFullAXTree",
            snapshot_params,
            session_frame
        )
        
        nodes = response.get("nodes", [])
        
        # Get scrollable elements
        scrollable_ids = await find_scrollable_element_ids(stagehand_page, target_frame)
        
        # Decorate nodes with scrollable info
        decorated_nodes = decorate_roles(nodes, scrollable_ids)
        
        # Build hierarchical tree
        tree_result = await build_hierarchical_tree(
            decorated_nodes,
            tag_name_map,
            logger,
            xpath_map
        )
        
        # Return the tree_result dict directly
        # It contains: tree, simplified, iframes, idToUrl, xpathMap
        return tree_result
        
    finally:
        # Disable accessibility
        await stagehand_page.disable_cdp("Accessibility", target_frame)


def inject_subtrees(tree: str, id_to_tree: Dict[EncodedId, str]) -> str:
    """
    Inject simplified subtree outlines into the main frame outline for nested iframes.
    Walks the main tree text, looks for EncodedId labels, and inserts matching subtrees.
    Matches TypeScript's injectSubtrees.
    
    Args:
        tree: The indented AX outline of the main frame
        id_to_tree: Map of EncodedId to subtree outlines for nested frames
        
    Returns:
        A single combined text outline with iframe subtrees injected
    """
    def unique_by_backend(backend_id: int) -> Optional[EncodedId]:
        """
        Return the *only* EncodedId that ends with this backend-id.
        If several frames share that backend-id we return None
        (avoids guessing the wrong subtree).
        """
        found: Optional[EncodedId] = None
        hit = 0
        for enc in id_to_tree.keys():
            # Split "ff-bb" format
            parts = enc.split("-")
            if len(parts) == 2:
                backend = int(parts[1])
                if backend == backend_id:
                    hit += 1
                    if hit > 1:
                        return None  # collision → abort
                    found = enc
        return found if hit == 1 else None
    
    # Stack frame for DFS injection
    class StackFrame:
        def __init__(self, lines: List[str], idx: int, indent: str):
            self.lines = lines
            self.idx = idx
            self.indent = indent
    
    stack = [StackFrame(tree.split("\n"), 0, "")]
    out: List[str] = []
    visited: Set[EncodedId] = set()  # avoid infinite loops
    
    # Depth-first injection walk
    while stack:
        top = stack[-1]
        
        if top.idx >= len(top.lines):
            stack.pop()
            continue
        
        raw = top.lines[top.idx]
        top.idx += 1
        line = top.indent + raw
        out.append(line)
        
        # grab whatever sits inside the first brackets, e.g. "[0-42]" or "[42]"
        import re
        m = re.match(r'^\s*\[([^\]]+)]', raw)
        if not m:
            continue
        
        label = m.group(1)  # could be "1-13" or "13"
        enc: Optional[EncodedId] = None
        child: Optional[str] = None
        
        # 1 exact match ("<ordinal>-<backend>") or fallback by backend ID
        if label in id_to_tree:
            enc = label
            child = id_to_tree.get(enc)
        else:
            # attempt to extract backendId from "<ordinal>-<backend>" or pure numeric label
            backend_id: Optional[int] = None
            # Check if it matches encoded ID pattern
            if re.match(r'^\d+-\d+$', label):
                backend_id = int(label.split("-")[1])
            elif label.isdigit():
                backend_id = int(label)
            
            if backend_id is not None:
                alt = unique_by_backend(backend_id)
                if alt:
                    enc = alt
                    child = id_to_tree.get(alt)
        
        if not enc or not child or enc in visited:
            continue
        
        visited.add(enc)
        # Get indent from the line
        indent_match = re.match(r'^(\s*)', line)
        indent = indent_match.group(0) if indent_match else ""
        stack.append(StackFrame(child.split("\n"), 0, indent + "  "))
    
    return "\n".join(out)


async def resolve_frame_chain(
    sp: 'PlaywrightAIPage',
    abs_path: str  # must start with '/'
) -> Tuple[List[Frame], str]:
    """
    Resolve a chain of iframe frames from an absolute XPath, returning the frame sequence and inner XPath.
    Matches TypeScript's resolveFrameChain.
    
    This helper walks an XPath expression containing iframe steps (e.g., '/html/body/iframe[2]/...'),
    descending into each matching iframe element to build a frame chain, and returns the leftover
    XPath segment to evaluate within the context of the last iframe.
    
    Args:
        sp: The PlaywrightAIPage instance for evaluating XPath and locating frames
        abs_path: An absolute XPath expression starting with '/', potentially including iframe steps
        
    Returns:
        Tuple containing:
            frames: List of Frame objects representing each iframe in the chain
            rest: The remaining XPath string to evaluate inside the final iframe
            
    Raises:
        Error if an iframe cannot be found or the final XPath cannot be resolved
    """
    import re
    
    IFRAME_STEP_RE = re.compile(r'iframe\[\d+]$', re.IGNORECASE)
    
    path = abs_path if abs_path.startswith("/") else "/" + abs_path
    ctx_frame: Optional[Frame] = None  # current frame
    chain: List[Frame] = []  # collected frames
    
    while True:
        # Does the whole path already resolve inside the current frame?
        try:
            await resolve_object_id_for_xpath(sp, path, ctx_frame)
            return chain, path  # we're done
        except:
            # keep walking
            pass
        
        # Otherwise: accumulate steps until we include an <iframe> step
        steps = [s for s in path.split("/") if s]
        buf: List[str] = []
        
        for i, step in enumerate(steps):
            buf.append(step)
            
            if IFRAME_STEP_RE.search(step):
                # "/…/iframe[k]" found – descend into that frame
                selector = "xpath=/" + "/".join(buf)
                current_frame = ctx_frame or sp._page.main_frame
                handle = current_frame.locator(selector)
                
                # Get the frame from the element
                element = await handle.element_handle()
                if not element:
                    raise Exception(f"Frame element not found: {selector}")
                    
                frame = await element.content_frame()
                if not frame:
                    raise Exception(f"Content frame not found for: {selector}")
                
                chain.append(frame)
                ctx_frame = frame
                path = "/" + "/".join(steps[i + 1:])  # remainder
                break
        else:
            # Last step processed – but no iframe found → dead-end
            raise Exception(f"XPath resolution failed: {abs_path}")


async def get_frame_root_backend_node_id(
    sp: 'PlaywrightAIPage',
    frame: Optional[Frame]
) -> Optional[int]:
    """
    Get the backendNodeId of the iframe element that contains a given Playwright.Frame.
    Matches TypeScript's getFrameRootBackendNodeId.
    
    Args:
        sp: The StagehandPage instance for issuing CDP commands
        frame: The Playwright.Frame whose host iframe element to locate
        
    Returns:
        The backendNodeId of the iframe element, or None if not applicable
    """
    # Return None for top-level or undefined frames
    if not frame or frame == sp._page.main_frame:
        return None
    
    # Resolve the CDP frameId for the target iframe frame
    fid = await get_cdp_frame_id(sp, frame)
    if not fid:
        return None
    
    # Retrieve the DOM node that owns the frame via CDP
    response = await sp.send_cdp("DOM.getFrameOwner", {"frameId": fid})
    return response.get("backendNodeId")


async def get_frame_root_xpath(frame: Optional[Frame]) -> str:
    """
    Compute the absolute XPath for the iframe element hosting a given Playwright.Frame.
    Matches TypeScript's getFrameRootXpath.
    
    Args:
        frame: The Playwright.Frame whose iframe element to locate
        
    Returns:
        The XPath of the iframe element, or "/" if no frame provided
    """
    # Return root path when no frame context is provided
    if not frame:
        return "/"
    
    # Obtain the element handle of the iframe in the embedding document
    handle = await frame.frame_element()
    if not handle:
        return "/"
        
    # Evaluate the element's absolute XPath within the page context
    return await handle.evaluate("""
        (node) => {
            const pos = (el) => {
                let i = 1;
                for (let sib = el.previousElementSibling; sib; sib = sib.previousElementSibling) {
                    if (sib.tagName === el.tagName) i += 1;
                }
                return i;
            };
            const segs = [];
            for (let el = node; el; el = el.parentElement) {
                segs.unshift(`${el.tagName.toLowerCase()}[${pos(el)}]`);
            }
            return `/${segs.join("/")}`;
        }
    """)


class FrameSnapshot:
    """Container for frame snapshot data."""
    def __init__(
        self,
        tree: str,
        xpath_map: Dict[EncodedId, str],
        url_map: Dict[EncodedId, str],
        frame_xpath: str,
        backend_node_id: Optional[int],
        parent_frame: Optional[Frame],
        frame_id: Optional[str]
    ):
        self.tree = tree
        self.xpath_map = xpath_map
        self.url_map = url_map
        self.frame_xpath = frame_xpath
        self.backend_node_id = backend_node_id
        self.parent_frame = parent_frame
        self.frame_id = frame_id


async def get_accessibility_tree_with_frames(
    stagehand_page: 'PlaywrightAIPage',
    logger: Optional[Any] = None,
    root_xpath: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retrieve and merge accessibility trees for the main document and nested iframes.
    Walks through frame chains if a root XPath is provided, then stitches subtree outlines.
    Matches TypeScript's getAccessibilityTreeWithFrames.
    
    Args:
        stagehand_page: The PlaywrightAIPage instance for Playwright and CDP interaction
        logger: Logging function for diagnostics and performance
        root_xpath: Optional absolute XPath to focus the crawl on a subtree across frames
        
    Returns:
        Dict with combined tree text, xpath map, and URL map
    """
    # 0. main-frame bookkeeping
    main = stagehand_page._page.main_frame
    
    # 1. "focus XPath" → frame chain + inner XPath
    target_frames: Optional[List[Frame]] = None  # full chain, main-first
    inner_xpath: Optional[str] = None
    
    if root_xpath and root_xpath.strip():
        frames, rest = await resolve_frame_chain(stagehand_page, root_xpath.strip())
        target_frames = frames if frames else None  # empty → None
        inner_xpath = rest
    
    main_only_filter = bool(inner_xpath and not target_frames)
    
    # 2. depth-first walk – collect snapshots
    snapshots: List[FrameSnapshot] = []
    frame_stack: List[Frame] = [main]
    
    print(f"DEBUG: Starting frame walk. Main frame: {main.url}")
    print(f"DEBUG: Main frame has {len(main.child_frames)} child frames")
    
    while frame_stack:
        frame = frame_stack.pop()
        print(f"DEBUG: Processing frame: {frame.url}")
        
        # unconditional: enqueue children so we can reach deep targets
        frame_stack.extend(frame.child_frames)
        print(f"DEBUG: Frame has {len(frame.child_frames)} child frames")
        
        # skip frames that are outside the requested chain / slice
        if target_frames and frame not in target_frames:
            continue
        # Only skip child frames if we have a specific inner_xpath to search for
        if not target_frames and frame != main and inner_xpath:
            continue
        
        # selector to forward (unchanged)
        selector = None
        if target_frames:
            if frame == target_frames[-1]:
                selector = inner_xpath
        else:
            if frame == main:
                selector = inner_xpath
        
        try:
            print(f"DEBUG: Getting accessibility tree for frame: {frame.url}")
            res = await get_accessibility_tree(
                stagehand_page,
                logger,
                selector,
                frame
            )
            print(f"DEBUG: Got tree with {len(res.get('tree', []))} nodes")
            
            # guard: main frame has no backendNodeId
            backend_id = None
            if frame != main:
                backend_id = await get_frame_root_backend_node_id(stagehand_page, frame)
            
            frame_xpath = "/" if frame == main else await get_frame_root_xpath(frame)
            
            # Resolve the CDP frameId for this Playwright Frame (None for main)
            frame_id = await get_cdp_frame_id(stagehand_page, frame)
            
            snapshot = FrameSnapshot(
                tree=res["simplified"].rstrip(),
                xpath_map=res.get("xpathMap", {}),
                url_map=res.get("idToUrl", {}),
                frame_xpath=frame_xpath,
                backend_node_id=backend_id,
                parent_frame=frame.parent_frame,
                frame_id=frame_id
            )
            snapshots.append(snapshot)
            print(f"DEBUG: Added snapshot for frame {frame.url[:50]}... with tree length {len(snapshot.tree)}")
            
            if main_only_filter:
                break  # nothing else to fetch
                
        except Exception as err:
            print(f"DEBUG: Error getting accessibility tree for frame: {err}")
            if logger:
                logger({
                    "category": "observation",
                    "message": f"⚠️ failed to get AX tree for {'main frame' if frame == main else f'iframe ({frame.url})'}",
                    "level": 1,
                    "auxiliary": {"error": {"value": str(err), "type": "string"}}
                })
    
    # 3. merge per-frame maps
    combined_xpath_map: Dict[EncodedId, str] = {}
    combined_url_map: Dict[EncodedId, str] = {}
    
    seg: Dict[Optional[Frame], str] = {}
    for s in snapshots:
        seg[s.parent_frame] = s.frame_xpath
    
    # recursively build the full prefix for a frame
    def full_prefix(f: Optional[Frame]) -> str:
        if not f:
            return ""  # reached main
        parent = f.parent_frame
        above = full_prefix(parent)
        hop = seg.get(parent, "")
        if hop == "/":
            return above
        elif above:
            return f"{above.rstrip('/')}/{hop.lstrip('/')}"
        else:
            return hop
    
    for snap in snapshots:
        prefix = ""
        if snap.frame_xpath != "/":
            prefix = f"{full_prefix(snap.parent_frame)}{snap.frame_xpath}"
        
        for enc, local in snap.xpath_map.items():
            if local == "":
                combined_xpath_map[enc] = prefix or "/"
            elif prefix:
                combined_xpath_map[enc] = f"{prefix.rstrip('/')}/{local.lstrip('/')}"
            else:
                combined_xpath_map[enc] = local
        
        combined_url_map.update(snap.url_map)
    
    # 4. EncodedId → subtree map (skip main)
    id_to_tree: Dict[EncodedId, str] = {}
    for snap in snapshots:
        if snap.backend_node_id is not None and snap.frame_id is not None:
            # ignore main frame and snapshots without a CDP frameId
            enc = stagehand_page.encode_with_frame_id(snap.frame_id, snap.backend_node_id)
            id_to_tree[enc] = snap.tree
    
    # 5. stitch everything together
    print(f"DEBUG: Total snapshots collected: {len(snapshots)}")
    print(f"DEBUG: id_to_tree entries: {len(id_to_tree)}")
    
    root_snap = next((s for s in snapshots if s.frame_xpath == "/"), None)
    if root_snap:
        print(f"DEBUG: Found root snapshot with tree length: {len(root_snap.tree)}")
        combined_tree = inject_subtrees(root_snap.tree, id_to_tree)
        print(f"DEBUG: Combined tree length after injection: {len(combined_tree)}")
    else:
        combined_tree = snapshots[0].tree if snapshots else ""
        print(f"DEBUG: No root snapshot, using first snapshot")
    
    result = {
        "combinedTree": combined_tree,
        "combinedXpathMap": combined_xpath_map,
        "combinedUrlMap": combined_url_map
    }
    
    print(f"DEBUG: Returning result with combinedTree length: {len(result['combinedTree'])}")
    return result