"""Text processing utilities."""


def normalise_spaces(s: str) -> str:
    """
    Collapse consecutive whitespace characters into single spaces.
    Matches TypeScript implementation for consistent text comparison.
    
    Args:
        s: Input string
        
    Returns:
        String with normalized whitespace
    """
    if not s:
        return ""
    
    out = ""
    in_ws = False
    
    for char in s:
        ch_code = ord(char)
        # Check if character is whitespace (space, tab, LF, CR)
        is_ws = ch_code in (32, 9, 10, 13)
        
        if is_ws:
            if not in_ws:
                out += " "
                in_ws = True
        else:
            out += char
            in_ws = False
    
    return out


def clean_text(text: str) -> str:
    """
    Clean text for display and comparison.
    
    Args:
        text: Raw text to clean
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # Remove null bytes and control characters
    cleaned = text.replace('\0', '')
    
    # Normalize whitespace
    cleaned = normalise_spaces(cleaned)
    
    # Trim leading/trailing whitespace
    return cleaned.strip()