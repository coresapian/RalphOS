/**
 * RALPH BROWSER HELPER
 * ====================
 * High-performance DOM utilities for browser automation.
 * Inject this into the browser context using browser_evaluate.
 *
 * Features:
 * - Fast text/element extraction
 * - React/Vue state inspection
 * - Efficient waiting via MutationObserver
 * - Form automation helpers
 * - Screenshot-friendly element highlighting
 *
 * Usage:
 *   // Inject into browser context
 *   browser_evaluate(script=<contents of this file>)
 *
 *   // Then use RALPH.* functions
 *   browser_evaluate(script="RALPH.findByText('Submit').click()")
 */

(function(window) {
    'use strict';

    // Avoid re-injection
    if (window.RALPH) {
        console.log('RALPH helper already loaded');
        return;
    }

    window.RALPH = {
        version: '1.0.0',

        // ==========================================
        // TEXT EXTRACTION
        // ==========================================

        /**
         * Get clean text from multiple elements matching a selector.
         * Returns an array of strings.
         *
         * @param {string} selector - CSS selector
         * @returns {string[]} Array of text content
         *
         * @example
         * RALPH.getTextList('.product-title')
         * // ['iPhone 15', 'MacBook Pro', 'iPad Air']
         */
        getTextList: function(selector) {
            const els = document.querySelectorAll(selector);
            return Array.from(els)
                .map(el => el.innerText.trim())
                .filter(t => t.length > 0);
        },

        /**
         * Get all visible text on the page.
         * Useful for quick content verification.
         *
         * @param {number} maxLength - Maximum characters to return (default 10000)
         * @returns {string} Page text content
         */
        getAllText: function(maxLength = 10000) {
            const walker = document.createTreeWalker(
                document.body,
                NodeFilter.SHOW_TEXT,
                {
                    acceptNode: function(node) {
                        const parent = node.parentElement;
                        if (!parent) return NodeFilter.FILTER_REJECT;

                        // Skip hidden elements
                        const style = window.getComputedStyle(parent);
                        if (style.display === 'none' || style.visibility === 'hidden') {
                            return NodeFilter.FILTER_REJECT;
                        }

                        // Skip scripts and styles
                        const tag = parent.tagName.toLowerCase();
                        if (['script', 'style', 'noscript', 'meta'].includes(tag)) {
                            return NodeFilter.FILTER_REJECT;
                        }

                        return node.textContent.trim() ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
                    }
                }
            );

            const texts = [];
            let totalLength = 0;

            while (walker.nextNode() && totalLength < maxLength) {
                const text = walker.currentNode.textContent.trim();
                if (text) {
                    texts.push(text);
                    totalLength += text.length;
                }
            }

            return texts.join(' ').substring(0, maxLength);
        },

        // ==========================================
        // ELEMENT FINDING
        // ==========================================

        /**
         * Find an element that contains specific text.
         * Useful when selectors are dynamic or unknown.
         *
         * @param {string} text - Text to search for
         * @param {string} tag - HTML tag to search (default '*')
         * @returns {Element|null} Found element or null
         *
         * @example
         * RALPH.findByText('Submit').click()
         * RALPH.findByText('Add to Cart', 'button').click()
         */
        findByText: function(text, tag = '*') {
            const els = document.querySelectorAll(tag);
            for (let el of els) {
                // Check direct text content (not children)
                const directText = Array.from(el.childNodes)
                    .filter(n => n.nodeType === Node.TEXT_NODE)
                    .map(n => n.textContent.trim())
                    .join(' ');

                if (directText.includes(text)) return el;

                // Fallback to innerText
                if (el.innerText && el.innerText.trim() === text) return el;
            }
            return null;
        },

        /**
         * Find all elements containing specific text.
         *
         * @param {string} text - Text to search for
         * @param {string} tag - HTML tag to search
         * @returns {Element[]} Array of matching elements
         */
        findAllByText: function(text, tag = '*') {
            const els = document.querySelectorAll(tag);
            const results = [];

            for (let el of els) {
                if (el.innerText && el.innerText.includes(text)) {
                    results.push(el);
                }
            }

            return results;
        },

        /**
         * Find element by aria-label or data attribute.
         *
         * @param {string} label - Label value to search for
         * @returns {Element|null} Found element or null
         */
        findByLabel: function(label) {
            // Try aria-label first
            let el = document.querySelector(`[aria-label="${label}"]`);
            if (el) return el;

            // Try title
            el = document.querySelector(`[title="${label}"]`);
            if (el) return el;

            // Try data-testid (common in React apps)
            el = document.querySelector(`[data-testid="${label}"]`);
            if (el) return el;

            // Try data-test
            el = document.querySelector(`[data-test="${label}"]`);
            if (el) return el;

            return null;
        },

        /**
         * Find the nearest clickable element (button, link, etc.)
         * from a given element or selector.
         *
         * @param {Element|string} target - Element or selector
         * @returns {Element|null} Clickable element or null
         */
        findClickable: function(target) {
            const el = typeof target === 'string' ? document.querySelector(target) : target;
            if (!el) return null;

            // Check if element itself is clickable
            const clickableTags = ['a', 'button', 'input', 'select', 'textarea'];
            if (clickableTags.includes(el.tagName.toLowerCase())) return el;

            // Check for role="button"
            if (el.getAttribute('role') === 'button') return el;

            // Check for onclick
            if (el.onclick || el.getAttribute('onclick')) return el;

            // Look up the tree
            let parent = el.parentElement;
            while (parent && parent !== document.body) {
                if (clickableTags.includes(parent.tagName.toLowerCase()) ||
                    parent.getAttribute('role') === 'button') {
                    return parent;
                }
                parent = parent.parentElement;
            }

            return el; // Return original if nothing better found
        },

        // ==========================================
        // WAITING
        // ==========================================

        /**
         * Wait for an element efficiently using MutationObserver.
         * Returns a Promise that resolves when the element appears.
         *
         * @param {string} selector - CSS selector to wait for
         * @param {number} timeout - Max wait time in ms (default 5000)
         * @returns {Promise<Element>} Promise resolving to element
         *
         * @example
         * await RALPH.waitFor('.modal-content')
         * await RALPH.waitFor('#results', 10000)
         */
        waitFor: function(selector, timeout = 5000) {
            return new Promise((resolve, reject) => {
                // Check if already exists
                const existing = document.querySelector(selector);
                if (existing) return resolve(existing);

                const observer = new MutationObserver(() => {
                    const el = document.querySelector(selector);
                    if (el) {
                        observer.disconnect();
                        resolve(el);
                    }
                });

                observer.observe(document.body, {
                    childList: true,
                    subtree: true,
                    attributes: true
                });

                // Timeout
                setTimeout(() => {
                    observer.disconnect();
                    reject(new Error(`Timeout waiting for ${selector}`));
                }, timeout);
            });
        },

        /**
         * Wait for text to appear on the page.
         *
         * @param {string} text - Text to wait for
         * @param {number} timeout - Max wait time in ms
         * @returns {Promise<boolean>} Promise resolving to true
         */
        waitForText: function(text, timeout = 5000) {
            return new Promise((resolve, reject) => {
                const check = () => document.body.innerText.includes(text);

                if (check()) return resolve(true);

                const observer = new MutationObserver(() => {
                    if (check()) {
                        observer.disconnect();
                        resolve(true);
                    }
                });

                observer.observe(document.body, {
                    childList: true,
                    subtree: true,
                    characterData: true
                });

                setTimeout(() => {
                    observer.disconnect();
                    reject(new Error(`Timeout waiting for text: "${text}"`));
                }, timeout);
            });
        },

        /**
         * Wait for network idle (no pending requests).
         * Useful for SPAs after navigation.
         *
         * @param {number} idleTime - Time with no requests to consider idle (ms)
         * @param {number} timeout - Max wait time in ms
         * @returns {Promise<void>}
         */
        waitForNetworkIdle: function(idleTime = 500, timeout = 10000) {
            return new Promise((resolve, reject) => {
                let lastActivity = Date.now();
                let timeoutId;

                const checkIdle = () => {
                    if (Date.now() - lastActivity >= idleTime) {
                        resolve();
                    } else {
                        timeoutId = setTimeout(checkIdle, 100);
                    }
                };

                // Monitor XHR
                const origXHROpen = XMLHttpRequest.prototype.open;
                const origXHRSend = XMLHttpRequest.prototype.send;

                XMLHttpRequest.prototype.open = function() {
                    this._ralphTracked = true;
                    return origXHROpen.apply(this, arguments);
                };

                XMLHttpRequest.prototype.send = function() {
                    if (this._ralphTracked) {
                        lastActivity = Date.now();
                        this.addEventListener('loadend', () => {
                            lastActivity = Date.now();
                        });
                    }
                    return origXHRSend.apply(this, arguments);
                };

                // Start checking
                checkIdle();

                // Overall timeout
                setTimeout(() => {
                    clearTimeout(timeoutId);
                    // Restore originals
                    XMLHttpRequest.prototype.open = origXHROpen;
                    XMLHttpRequest.prototype.send = origXHRSend;
                    reject(new Error('Network idle timeout'));
                }, timeout);
            });
        },

        // ==========================================
        // INTERACTION
        // ==========================================

        /**
         * Click an element and wait briefly for effects.
         *
         * @param {string|Element} target - Selector or element
         * @param {number} waitMs - Time to wait after click (default 100)
         * @returns {Promise<void>}
         */
        clickAndWait: async function(target, waitMs = 100) {
            const el = typeof target === 'string' ? document.querySelector(target) : target;
            if (!el) throw new Error(`Element not found: ${target}`);

            el.click();
            await new Promise(r => setTimeout(r, waitMs));
        },

        /**
         * Fill a form field with proper event dispatch.
         *
         * @param {string|Element} target - Selector or element
         * @param {string} value - Value to set
         */
        fillField: function(target, value) {
            const el = typeof target === 'string' ? document.querySelector(target) : target;
            if (!el) throw new Error(`Element not found: ${target}`);

            // Focus
            el.focus();

            // Clear existing
            el.value = '';

            // Set new value
            el.value = value;

            // Dispatch events for React/Vue
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        },

        /**
         * Fill multiple form fields at once.
         *
         * @param {Object} fields - Object mapping selector to value
         *
         * @example
         * RALPH.fillForm({
         *   '#email': 'test@example.com',
         *   '#password': 'secret123'
         * })
         */
        fillForm: function(fields) {
            for (const [selector, value] of Object.entries(fields)) {
                this.fillField(selector, value);
            }
        },

        /**
         * Select an option from a <select> element.
         *
         * @param {string|Element} target - Selector or element
         * @param {string} value - Option value to select
         */
        selectOption: function(target, value) {
            const el = typeof target === 'string' ? document.querySelector(target) : target;
            if (!el) throw new Error(`Element not found: ${target}`);

            el.value = value;
            el.dispatchEvent(new Event('change', { bubbles: true }));
        },

        // ==========================================
        // REACT/VUE INSPECTION
        // ==========================================

        /**
         * Extract React props from a component instance.
         * Essential for debugging SPAs.
         *
         * @param {string|Element} target - Selector or element
         * @returns {Object|null} React props or null
         */
        getReactProps: function(target) {
            const el = typeof target === 'string' ? document.querySelector(target) : target;
            if (!el) return null;

            // React 18+
            const key = Object.keys(el).find(k => k.startsWith('__reactProps'));
            if (key) return el[key];

            // React 16/17
            const fiberKey = Object.keys(el).find(k => k.startsWith('__reactFiber'));
            if (fiberKey) {
                const fiber = el[fiberKey];
                return fiber?.memoizedProps || fiber?.pendingProps || null;
            }

            return null;
        },

        /**
         * Get React component state.
         *
         * @param {string|Element} target - Selector or element
         * @returns {Object|null} Component state or null
         */
        getReactState: function(target) {
            const el = typeof target === 'string' ? document.querySelector(target) : target;
            if (!el) return null;

            const fiberKey = Object.keys(el).find(k => k.startsWith('__reactFiber'));
            if (fiberKey) {
                const fiber = el[fiberKey];
                return fiber?.memoizedState || null;
            }

            return null;
        },

        /**
         * Get Vue component data.
         *
         * @param {string|Element} target - Selector or element
         * @returns {Object|null} Vue data or null
         */
        getVueData: function(target) {
            const el = typeof target === 'string' ? document.querySelector(target) : target;
            if (!el) return null;

            // Vue 3
            if (el.__vueParentComponent) {
                return el.__vueParentComponent.data;
            }

            // Vue 2
            if (el.__vue__) {
                return el.__vue__.$data;
            }

            return null;
        },

        // ==========================================
        // TABLE EXTRACTION
        // ==========================================

        /**
         * Extract data from an HTML table.
         *
         * @param {string|Element} target - Table selector or element
         * @returns {Object} Object with headers and rows arrays
         *
         * @example
         * const data = RALPH.extractTable('table.results')
         * // { headers: ['Name', 'Price'], rows: [['iPhone', '$999'], ...] }
         */
        extractTable: function(target) {
            const table = typeof target === 'string' ? document.querySelector(target) : target;
            if (!table) return { headers: [], rows: [] };

            // Get headers
            const headers = [];
            const headerRow = table.querySelector('thead tr') || table.querySelector('tr');
            if (headerRow) {
                headerRow.querySelectorAll('th, td').forEach(cell => {
                    headers.push(cell.innerText.trim());
                });
            }

            // Get rows
            const rows = [];
            const bodyRows = table.querySelectorAll('tbody tr') ||
                            Array.from(table.querySelectorAll('tr')).slice(1);

            bodyRows.forEach(row => {
                const cells = [];
                row.querySelectorAll('td').forEach(cell => {
                    cells.push(cell.innerText.trim());
                });
                if (cells.length > 0) {
                    rows.push(cells);
                }
            });

            return { headers, rows };
        },

        /**
         * Extract all tables from the page.
         *
         * @returns {Object[]} Array of table data objects
         */
        extractAllTables: function() {
            const tables = document.querySelectorAll('table');
            return Array.from(tables).map(t => this.extractTable(t));
        },

        // ==========================================
        // LINK EXTRACTION
        // ==========================================

        /**
         * Get all links from the page.
         *
         * @param {Object} options - Filter options
         * @returns {Object[]} Array of link objects
         */
        getLinks: function(options = {}) {
            const {
                internal = true,     // Include internal links
                external = true,     // Include external links
                unique = true,       // Deduplicate
                selector = 'a[href]' // Custom selector
            } = options;

            const links = [];
            const seen = new Set();
            const currentHost = window.location.hostname;

            document.querySelectorAll(selector).forEach(a => {
                try {
                    const href = a.href;
                    if (!href || href.startsWith('javascript:')) return;

                    const url = new URL(href);
                    const isInternal = url.hostname === currentHost;

                    if ((isInternal && !internal) || (!isInternal && !external)) return;

                    if (unique && seen.has(href)) return;
                    seen.add(href);

                    links.push({
                        href,
                        text: a.innerText.trim(),
                        title: a.title || '',
                        internal: isInternal
                    });
                } catch (e) {
                    // Invalid URL, skip
                }
            });

            return links;
        },

        // ==========================================
        // SCROLLING
        // ==========================================

        /**
         * Scroll to bottom of page (for infinite scroll).
         *
         * @param {number} delay - Delay between scrolls (ms)
         * @param {number} maxScrolls - Maximum scroll attempts
         * @returns {Promise<number>} Final scroll position
         */
        scrollToBottom: async function(delay = 500, maxScrolls = 50) {
            let lastHeight = 0;
            let scrolls = 0;

            while (scrolls < maxScrolls) {
                window.scrollTo(0, document.body.scrollHeight);
                await new Promise(r => setTimeout(r, delay));

                const newHeight = document.body.scrollHeight;
                if (newHeight === lastHeight) break;

                lastHeight = newHeight;
                scrolls++;
            }

            return lastHeight;
        },

        /**
         * Scroll element into view smoothly.
         *
         * @param {string|Element} target - Selector or element
         */
        scrollIntoView: function(target) {
            const el = typeof target === 'string' ? document.querySelector(target) : target;
            if (el) {
                el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        },

        // ==========================================
        // UTILITIES
        // ==========================================

        /**
         * Highlight an element for debugging/screenshots.
         *
         * @param {string|Element} target - Selector or element
         * @param {string} color - Border color (default 'red')
         */
        highlight: function(target, color = 'red') {
            const el = typeof target === 'string' ? document.querySelector(target) : target;
            if (el) {
                el.style.outline = `3px solid ${color}`;
                el.style.outlineOffset = '2px';
            }
        },

        /**
         * Remove all highlights.
         */
        clearHighlights: function() {
            document.querySelectorAll('[style*="outline"]').forEach(el => {
                el.style.outline = '';
                el.style.outlineOffset = '';
            });
        },

        /**
         * Get page metadata.
         *
         * @returns {Object} Page metadata
         */
        getPageInfo: function() {
            return {
                url: window.location.href,
                title: document.title,
                description: document.querySelector('meta[name="description"]')?.content || '',
                canonical: document.querySelector('link[rel="canonical"]')?.href || '',
                ogTitle: document.querySelector('meta[property="og:title"]')?.content || '',
                ogImage: document.querySelector('meta[property="og:image"]')?.content || ''
            };
        },

        /**
         * Check if page has specific text.
         *
         * @param {string} text - Text to search for
         * @returns {boolean} True if text found
         */
        hasText: function(text) {
            return document.body.innerText.includes(text);
        },

        /**
         * Count elements matching a selector.
         *
         * @param {string} selector - CSS selector
         * @returns {number} Element count
         */
        count: function(selector) {
            return document.querySelectorAll(selector).length;
        }
    };

    console.log('✅ RALPH Browser Helper v' + window.RALPH.version + ' loaded');

})(window);
