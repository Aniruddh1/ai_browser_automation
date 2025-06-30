"""Browser-specific type definitions."""

from typing import Optional, Dict, Any, List, Literal
from pydantic import BaseModel, Field


class Viewport(BaseModel):
    """Browser viewport configuration."""
    width: int
    height: int


class BrowserContextOptions(BaseModel):
    """Options for creating a browser context."""
    viewport: Optional[Viewport] = None
    user_agent: Optional[str] = None
    bypass_csp: bool = False
    java_script_enabled: bool = True
    timezone_id: Optional[str] = None
    locale: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)
    extra_http_headers: Dict[str, str] = Field(default_factory=dict)
    offline: bool = False
    color_scheme: Optional[Literal["light", "dark", "no-preference"]] = None
    device_scale_factor: Optional[float] = None
    is_mobile: Optional[bool] = None
    has_touch: Optional[bool] = None


class CDPSession(BaseModel):
    """Chrome DevTools Protocol session info."""
    session_id: str
    target_id: str
    target_type: str
    frame_id: Optional[str] = None


class FrameInfo(BaseModel):
    """Information about a frame."""
    frame_id: str
    parent_frame_id: Optional[str] = None
    url: str
    name: Optional[str] = None
    backend_node_id: Optional[int] = None
    xpath: Optional[str] = None
    ordinal: int


class DOMNode(BaseModel):
    """Represents a DOM node from CDP."""
    node_id: int
    backend_node_id: int
    node_type: int
    node_name: str
    node_value: Optional[str] = None
    parent_id: Optional[int] = None
    child_node_count: Optional[int] = None
    attributes: Dict[str, str] = Field(default_factory=dict)
    children: List['DOMNode'] = Field(default_factory=list)
    frame_id: Optional[str] = None
    content_document: Optional['DOMNode'] = None
    shadow_roots: List['DOMNode'] = Field(default_factory=list)


class NetworkRequest(BaseModel):
    """Represents a network request."""
    request_id: str
    url: str
    method: str
    timestamp: float
    frame_id: Optional[str] = None
    resource_type: Optional[str] = None
    status: Optional[int] = None
    response_time: Optional[float] = None


class Screenshot(BaseModel):
    """Screenshot data."""
    data: bytes
    format: Literal["png", "jpeg"] = "png"
    full_page: bool = False
    timestamp: float
    viewport: Optional[Viewport] = None


class MousePosition(BaseModel):
    """Mouse cursor position."""
    x: float
    y: float
    viewport_x: Optional[float] = None
    viewport_y: Optional[float] = None


class KeyboardModifiers(BaseModel):
    """Keyboard modifier keys state."""
    alt: bool = False
    ctrl: bool = False
    meta: bool = False
    shift: bool = False


class BrowserEvent(BaseModel):
    """Browser event data."""
    type: str
    timestamp: float
    data: Dict[str, Any] = Field(default_factory=dict)
    frame_id: Optional[str] = None
    target_id: Optional[str] = None


class TreeResult(BaseModel):
    """Result of accessibility tree building."""
    tree: List[Dict[str, Any]]  # List of AccessibilityNode
    simplified: str
    iframes: List[Dict[str, Any]]  # List of iframe nodes
    idToUrl: Dict[str, str]  # EncodedId to URL mapping
    xpathMap: Optional[Dict[str, str]] = None  # EncodedId to XPath mapping


class BackendIdMaps(BaseModel):
    """Mappings from backend node IDs."""
    tagNameMap: Dict[str, str]  # EncodedId to tag name
    xpathMap: Dict[str, str]  # EncodedId to XPath


# Update forward references
DOMNode.model_rebuild()