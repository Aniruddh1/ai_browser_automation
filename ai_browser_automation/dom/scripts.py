"""Browser-side DOM scripts for element detection and manipulation."""

# JavaScript functions that need to be injected into the browser
DOM_SCRIPTS = """
// Mark that AIBrowserAutomation scripts have been injected
window.__aiBrowserAutomationInjected = true;

// Utility to get node from XPath
window.getNodeFromXpath = function(xpath) {
    return document.evaluate(
        xpath,
        document.documentElement,
        null,
        XPathResult.FIRST_ORDERED_NODE_TYPE,
        null
    ).singleNodeValue;
};

// Check if element can scroll
window.canElementScroll = function(elem) {
    if (typeof elem.scrollTo !== "function") {
        return false;
    }
    
    try {
        const originalTop = elem.scrollTop;
        
        // Try to scroll
        elem.scrollTo({
            top: originalTop + 100,
            left: 0,
            behavior: "instant"
        });
        
        // If scrollTop never changed, consider it unscrollable
        if (elem.scrollTop === originalTop) {
            return false;
        }
        
        // Scroll back to original place
        elem.scrollTo({
            top: originalTop,
            left: 0,
            behavior: "instant"
        });
        
        return true;
    } catch (error) {
        return false;
    }
};

// Get scrollable elements
window.getScrollableElements = function(topN) {
    const docEl = document.documentElement;
    const scrollableElements = [docEl];
    
    const allElements = document.querySelectorAll("*");
    for (const elem of allElements) {
        const style = window.getComputedStyle(elem);
        const overflowY = style.overflowY;
        
        const isPotentiallyScrollable = 
            overflowY === "auto" || overflowY === "scroll" || overflowY === "overlay";
            
        if (isPotentiallyScrollable) {
            const candidateScrollDiff = elem.scrollHeight - elem.clientHeight;
            if (candidateScrollDiff > 0 && window.canElementScroll(elem)) {
                scrollableElements.push(elem);
            }
        }
    }
    
    // Sort by scrollHeight descending
    scrollableElements.sort((a, b) => b.scrollHeight - a.scrollHeight);
    
    if (topN !== undefined) {
        return scrollableElements.slice(0, topN);
    }
    
    return scrollableElements;
};

// Get scrollable element XPaths - matches TypeScript getScrollableElementXpaths
window.getScrollableElementXpaths = async function(topN) {
    const scrollableElems = window.getScrollableElements(topN);
    const xpaths = [];
    
    for (const elem of scrollableElems) {
        const allXPaths = await window.generateXPathsForElement(elem);
        const firstXPath = allXPaths?.[0] || "";
        xpaths.push(firstXPath);
    }
    
    return xpaths;
};

// Wait for element scroll to end
window.waitForElementScrollEnd = function(element, idleMs = 100) {
    return new Promise((resolve) => {
        let scrollEndTimer;
        
        const handleScroll = () => {
            clearTimeout(scrollEndTimer);
            scrollEndTimer = setTimeout(() => {
                element.removeEventListener("scroll", handleScroll);
                resolve();
            }, idleMs);
        };
        
        element.addEventListener("scroll", handleScroll, { passive: true });
        handleScroll();
    });
};

// Generate XPath for element - matches TypeScript implementation
window.generateXPath = function(element) {
    if (!element) return '';
    
    if (element.id) {
        return `//*[@id="${element.id}"]`;
    }
    
    if (element === document.body) {
        return '/html/body';
    }
    
    const siblings = element.parentNode ? Array.from(element.parentNode.childNodes) : [];
    const nodeIndex = siblings.indexOf(element) + 1;
    
    const tagName = element.tagName ? element.tagName.toLowerCase() : '';
    const parentXPath = element.parentNode ? window.generateXPath(element.parentNode) : '';
    
    return `${parentXPath}/${tagName}[${nodeIndex}]`;
};

// Generate XPaths for element - matches TypeScript generateXPathsForElement
window.generateXPathsForElement = async function(element) {
    if (!element) return [];
    
    const [complexXPath, standardXPath, idBasedXPath] = await Promise.all([
        generateComplexXPath(element),
        generateStandardXPath(element),
        generateIdBasedXPath(element)
    ]);
    
    // Return in order from most accurate to most cacheable
    const xpaths = [standardXPath];
    if (idBasedXPath) {
        xpaths.push(idBasedXPath);
    }
    xpaths.push(complexXPath);
    
    return xpaths;
};

// Generate complex XPath with attribute combinations
window.generateComplexXPath = async function(element) {
    const tagName = element.tagName.toLowerCase();
    
    // List of attributes to consider for uniqueness
    const attributePriority = [
        "data-qa",
        "data-component",
        "data-role",
        "role",
        "aria-role",
        "type",
        "name",
        "aria-label",
        "placeholder",
        "title",
        "alt"
    ];
    
    // Collect attributes present on the element
    const attributes = [];
    for (const attr of attributePriority) {
        const value = element.getAttribute(attr);
        if (value) {
            attributes.push({ attr, value });
        }
    }
    
    // Try to find unique selector
    let uniqueSelector = "";
    
    // Helper to escape XPath strings
    const escapeXPathString = (value) => {
        if (value.includes("'")) {
            if (value.includes('"')) {
                // Contains both quotes - use concat
                return "concat(" + value.split(/('+)/).map(part => {
                    if (part === "'") return '"\\'"\';
                    else if (part.startsWith("'") && part.endsWith("'")) return `"${part}"`;
                    else return `'${part}'`;
                }).join(",") + ")";
            } else {
                return `"${value}"`;
            }
        } else {
            return `'${value}'`;
        }
    };
    
    // Try combinations of attributes
    for (let i = 1; i <= attributes.length; i++) {
        const combos = getCombinations(attributes, i);
        for (const combo of combos) {
            const conditions = combo.map(a => `@${a.attr}=${escapeXPathString(a.value)}`).join(" and ");
            const xpath = `//${tagName}[${conditions}]`;
            
            // Check if unique
            try {
                const result = document.evaluate(xpath, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
                if (result.snapshotLength === 1 && result.snapshotItem(0) === element) {
                    uniqueSelector = xpath;
                    break;
                }
            } catch (e) {
                // Invalid XPath, continue
            }
        }
        if (uniqueSelector) break;
    }
    
    if (uniqueSelector) {
        return uniqueSelector.replace('//', '');
    }
    
    // Fallback to positional
    return generateStandardXPath(element);
};

// Generate standard positional XPath
window.generateStandardXPath = async function(element) {
    const parts = [];
    let current = element;
    
    while (current && (current.nodeType === 1 || current.nodeType === 3)) {
        let index = 0;
        let hasSameTypeSiblings = false;
        const siblings = current.parentElement ? Array.from(current.parentElement.childNodes) : [];
        
        for (let i = 0; i < siblings.length; i++) {
            const sibling = siblings[i];
            if (sibling.nodeType === current.nodeType && sibling.nodeName === current.nodeName) {
                index++;
                hasSameTypeSiblings = true;
                if (sibling === current) {
                    break;
                }
            }
        }
        
        // Text nodes are selected differently
        if (current.nodeName !== '#text') {
            const tagName = current.nodeName.toLowerCase();
            const pathIndex = hasSameTypeSiblings ? `[${index}]` : '';
            parts.unshift(`${tagName}${pathIndex}`);
        }
        
        current = current.parentElement;
    }
    
    return parts.length ? `/${parts.join('/')}` : '';
};

// Generate ID-based XPath
window.generateIdBasedXPath = async function(element) {
    if (element.id) {
        return `//*[@id='${element.id}']`;
    }
    return null;
};

// Helper to get combinations
window.getCombinations = function(arr, size) {
    const results = [];
    
    function helper(start, combo) {
        if (combo.length === size) {
            results.push([...combo]);
            return;
        }
        for (let i = start; i < arr.length; i++) {
            combo.push(arr[i]);
            helper(i + 1, combo);
            combo.pop();
        }
    }
    
    helper(0, []);
    return results;
};

// Enhanced element detection for complex sites
window.getInteractiveElements = function() {
    const interactiveSelectors = [
        'a[href]',
        'button',
        'input:not([type="hidden"])',
        'select',
        'textarea',
        '[role="button"]',
        '[role="link"]',
        '[role="checkbox"]',
        '[role="radio"]',
        '[role="combobox"]',
        '[role="textbox"]',
        '[role="searchbox"]',
        '[role="slider"]',
        '[role="spinbutton"]',
        '[role="switch"]',
        '[role="tab"]',
        '[role="menuitem"]',
        '[tabindex]:not([tabindex="-1"])',
        '[contenteditable="true"]',
        '[onclick]',
        '[ng-click]',
        '[data-action]',
        '[data-click]'
    ];
    
    const elements = [];
    const seen = new Set();
    
    for (const selector of interactiveSelectors) {
        try {
            const matches = document.querySelectorAll(selector);
            for (const elem of matches) {
                if (!seen.has(elem) && isElementVisible(elem)) {
                    seen.add(elem);
                    elements.push({
                        element: elem,
                        selector: generateUniqueSelector(elem),
                        tagName: elem.tagName.toLowerCase(),
                        text: getElementText(elem),
                        type: getElementType(elem),
                        attributes: getElementAttributes(elem)
                    });
                }
            }
        } catch (e) {
            console.warn('Error with selector:', selector, e);
        }
    }
    
    return elements;
};

// Check if element is visible
window.isElementVisible = function(elem) {
    if (!elem) return false;
    
    const style = window.getComputedStyle(elem);
    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
        return false;
    }
    
    const rect = elem.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) {
        return false;
    }
    
    // Check if element is in viewport
    const inViewport = (
        rect.top < window.innerHeight &&
        rect.bottom > 0 &&
        rect.left < window.innerWidth &&
        rect.right > 0
    );
    
    return inViewport;
};

// Get element text
window.getElementText = function(elem) {
    // For input elements, try to get placeholder or value
    if (elem.tagName === 'INPUT' || elem.tagName === 'TEXTAREA') {
        return elem.placeholder || elem.value || elem.getAttribute('aria-label') || '';
    }
    
    // For images, get alt text
    if (elem.tagName === 'IMG') {
        return elem.alt || elem.title || '';
    }
    
    // Get text content, limited to direct text to avoid nested elements
    let text = elem.textContent || elem.innerText || '';
    
    // If no text, try aria-label
    if (!text.trim()) {
        text = elem.getAttribute('aria-label') || elem.getAttribute('title') || '';
    }
    
    // Limit length and clean up
    return text.trim().substring(0, 100).replace(/\s+/g, ' ');
};

// Get element type
window.getElementType = function(elem) {
    if (elem.tagName === 'A') return 'link';
    if (elem.tagName === 'BUTTON') return 'button';
    if (elem.tagName === 'INPUT') return elem.type || 'text';
    if (elem.tagName === 'SELECT') return 'select';
    if (elem.tagName === 'TEXTAREA') return 'textarea';
    if (elem.getAttribute('role')) return elem.getAttribute('role');
    return elem.tagName.toLowerCase();
};

// Get element attributes
window.getElementAttributes = function(elem) {
    const attrs = {};
    const importantAttrs = ['id', 'class', 'name', 'type', 'placeholder', 'href', 'src', 'alt', 'title', 'aria-label', 'role', 'data-testid'];
    
    for (const attr of importantAttrs) {
        const value = elem.getAttribute(attr);
        if (value) {
            attrs[attr] = value;
        }
    }
    
    return attrs;
};

// Generate unique selector for element
window.generateUniqueSelector = function(elem) {
    // Try ID first
    if (elem.id) {
        return `#${elem.id}`;
    }
    
    // Try unique attributes
    const uniqueAttrs = ['name', 'data-testid', 'aria-label'];
    for (const attr of uniqueAttrs) {
        const value = elem.getAttribute(attr);
        if (value) {
            const selector = `${elem.tagName.toLowerCase()}[${attr}="${value}"]`;
            if (document.querySelectorAll(selector).length === 1) {
                return selector;
            }
        }
    }
    
    // Try class combinations
    if (elem.className) {
        const classes = elem.className.split(' ').filter(c => c.trim());
        if (classes.length > 0) {
            const selector = `${elem.tagName.toLowerCase()}.${classes.join('.')}`;
            const matches = document.querySelectorAll(selector);
            if (matches.length === 1) {
                return selector;
            }
            
            // If multiple matches, return XPath instead
            if (matches.length > 1) {
                return window.generateXPath(elem);
            }
        }
    }
    
    // Fallback to XPath
    return window.generateXPath(elem);
};

// Helper function to get CDP backend node ID (if available)
window.__getCDPNodeId = function(element) {
    // This would be set by CDP if available
    return element.__backendNodeId || null;
};

// Store frame information
window.__frameInfo = {
    url: window.location.href,
    frameId: window.frameElement ? null : 'main',
    isMainFrame: !window.frameElement
};

console.log('AIBrowserAutomation DOM scripts injected successfully');
"""