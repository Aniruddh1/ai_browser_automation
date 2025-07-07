"""Accessibility tree utilities."""

from .utils_v2 import (
    get_accessibility_tree,
    build_backend_id_maps,
    get_accessibility_tree_with_frames,
    inject_subtrees,
    resolve_frame_chain,
)

__all__ = [
    "get_accessibility_tree",
    "build_backend_id_maps",
    "get_accessibility_tree_with_frames",
    "inject_subtrees",
    "resolve_frame_chain",
]