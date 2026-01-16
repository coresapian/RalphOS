#!/usr/bin/env python3
"""
Ralph's Core Python Utilities
============================
Provides robust, efficient, and logged utilities for all Ralph operations.

Features:
- Atomic file operations (no half-written files)
- Structured JSON logging
- Robust HTTP client with retries
- URL normalization and validation
- Progress tracking and checkpointing
- Batch processing with rate limiting

Usage:
    from ralph_utils import logger, safe_write, get_robust_session

    logger.log("INFO", "Starting task", {"task": "scrape"})
    safe_write("output.json", json.dumps(data))
    session = get_robust_session(retries=3)
"""

import json
import os
import time
import logging
import hashlib
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Callable
from urllib.parse import urlparse, urljoin, urlunparse, parse_qs, urlencode
from datetime import datetime
from functools import wraps
import shutil

# ==========================================
# STRUCTURED LOGGING
# ==========================================

class JSONLogger:
    """
    Outputs logs as JSON Lines (.jsonl) for easy parsing by the Factory Ralph loop.

    Usage:
        from ralph_utils import logger
        logger.log("INFO", "Task started", {"source": "luxury4play"})
        logger.log("ERROR", "Scrape failed", {"url": "...", "status": 403})
    """

    def __init__(self, log_file: str = "ralph_run.jsonl", console: bool = True):
        self.log_file = Path(log_file)
        self.console = console
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def log(self, level: str, message: str, data: Optional[Dict] = None):
        """
        Log a structured message.

        Args:
            level: Log level (INFO, WARNING, ERROR, DEBUG, SUCCESS)
            message: Human-readable message
            data: Optional structured data to include
        """
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level.upper(),
            "message": message,
            "data": data or {}
        }

        # Write to file
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

        # Console output with colors
        if self.console:
            colors = {
                "INFO": "\033[36m",     # Cyan
                "WARNING": "\033[33m",   # Yellow
                "ERROR": "\033[31m",     # Red
                "DEBUG": "\033[90m",     # Gray
                "SUCCESS": "\033[32m",   # Green
            }
            reset = "\033[0m"
            color = colors.get(level.upper(), "")
            print(f"{color}[{level.upper()}]{reset} {message}")

    def info(self, message: str, data: Optional[Dict] = None):
        self.log("INFO", message, data)

    def warning(self, message: str, data: Optional[Dict] = None):
        self.log("WARNING", message, data)

    def error(self, message: str, data: Optional[Dict] = None):
        self.log("ERROR", message, data)

    def debug(self, message: str, data: Optional[Dict] = None):
        self.log("DEBUG", message, data)

    def success(self, message: str, data: Optional[Dict] = None):
        self.log("SUCCESS", message, data)


# Global logger instance
logger = JSONLogger()


# ==========================================
# ATOMIC FILE OPERATIONS
# ==========================================

def safe_write(filepath: str, content: Union[str, bytes], mode: str = 'w') -> bool:
    """
    Write to a file atomically using rename.
    Prevents corruption if the script is killed mid-write.

    Args:
        filepath: Target file path
        content: Content to write (string or bytes)
        mode: Write mode ('w' for text, 'wb' for binary)

    Returns:
        True if successful

    Example:
        safe_write("config.json", json.dumps({"key": "value"}))
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Create temp file in same directory (for atomic rename)
    temp_path = path.with_suffix('.tmp')

    try:
        with open(temp_path, mode) as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())  # Force write to disk

        # Atomic rename
        temp_path.replace(path)
        logger.debug(f"Atomically wrote {path}", {"size": len(content)})
        return True

    except Exception as e:
        logger.error(f"Failed to write {path}: {e}")
        if temp_path.exists():
            temp_path.unlink()
        raise


def safe_write_json(filepath: str, data: Any, indent: int = 2, sort_keys: bool = True) -> bool:
    """
    Atomically write JSON data to a file.

    Args:
        filepath: Target file path
        data: JSON-serializable data
        indent: Indentation level (default 2)
        sort_keys: Whether to sort keys (default True for consistent diffs)

    Returns:
        True if successful
    """
    content = json.dumps(data, indent=indent, sort_keys=sort_keys, ensure_ascii=False)
    return safe_write(filepath, content)


def safe_read_json(filepath: str, default: Any = None) -> Any:
    """
    Safely read and parse a JSON file.

    Args:
        filepath: File path to read
        default: Default value if file doesn't exist or is invalid

    Returns:
        Parsed JSON data or default value
    """
    path = Path(filepath)
    if not path.exists():
        logger.debug(f"File not found, returning default: {filepath}")
        return default

    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {filepath}: {e}")
        return default
    except Exception as e:
        logger.error(f"Failed to read {filepath}: {e}")
        return default


def ensure_directory(path: str) -> Path:
    """
    Ensure a directory exists, creating it if necessary.

    Args:
        path: Directory path

    Returns:
        Path object for the directory
    """
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def atomic_rename(src: str, dst: str) -> bool:
    """
    Atomically rename a file.

    Args:
        src: Source file path
        dst: Destination file path

    Returns:
        True if successful
    """
    try:
        Path(src).replace(Path(dst))
        return True
    except Exception as e:
        logger.error(f"Failed to rename {src} to {dst}: {e}")
        return False


# ==========================================
# URL UTILITIES
# ==========================================

def normalize_url(url: str, remove_fragments: bool = True,
                  remove_tracking: bool = True,
                  lowercase_host: bool = True) -> str:
    """
    Normalize a URL for consistent comparison and deduplication.

    Args:
        url: URL to normalize
        remove_fragments: Remove #fragment parts
        remove_tracking: Remove common tracking parameters (utm_*, fbclid, etc.)
        lowercase_host: Convert hostname to lowercase

    Returns:
        Normalized URL string

    Example:
        normalize_url("HTTPS://Example.COM/Page#section?utm_source=twitter")
        # Returns: "https://example.com/Page"
    """
    if not url:
        return ""

    parsed = urlparse(url.strip())

    # Lowercase scheme and host
    scheme = parsed.scheme.lower() or 'https'
    netloc = parsed.netloc.lower() if lowercase_host else parsed.netloc

    # Remove www. prefix optionally
    if netloc.startswith('www.'):
        netloc = netloc[4:]

    # Handle path
    path = parsed.path.rstrip('/') or '/'

    # Handle query parameters
    query_params = parse_qs(parsed.query, keep_blank_values=True)

    if remove_tracking:
        tracking_params = {
            'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
            'fbclid', 'gclid', 'msclkid', 'ref', 'source', 'mc_cid', 'mc_eid'
        }
        query_params = {k: v for k, v in query_params.items()
                       if k.lower() not in tracking_params}

    # Sort and reconstruct query
    query = urlencode(sorted(query_params.items()), doseq=True) if query_params else ''

    # Handle fragment
    fragment = '' if remove_fragments else parsed.fragment

    return urlunparse((scheme, netloc, path, '', query, fragment))


def extract_domain(url: str, include_subdomain: bool = False) -> str:
    """
    Extract the domain from a URL.

    Args:
        url: URL to parse
        include_subdomain: Whether to include subdomains

    Returns:
        Domain string (e.g., "example.com" or "www.example.com")
    """
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower()

        if not include_subdomain:
            # Simple approach: take last two parts
            parts = host.split('.')
            if len(parts) > 2:
                # Handle .co.uk, .com.au, etc.
                if parts[-2] in ('co', 'com', 'org', 'net', 'gov', 'edu'):
                    return '.'.join(parts[-3:])
                return '.'.join(parts[-2:])

        return host
    except:
        return ""


def url_to_path(url: str, max_length: int = 200) -> str:
    """
    Convert a URL to a safe filesystem path.

    Args:
        url: URL to convert
        max_length: Maximum path length

    Returns:
        Safe path string
    """
    # Parse URL
    parsed = urlparse(url)

    # Build path from components
    path_parts = [
        parsed.netloc.replace('.', '_'),
        parsed.path.strip('/').replace('/', '_')
    ]

    # Clean up
    result = '_'.join(filter(None, path_parts))
    result = re.sub(r'[^\w\-_]', '_', result)
    result = re.sub(r'_+', '_', result)

    # Truncate if needed
    if len(result) > max_length:
        # Keep hash suffix for uniqueness
        hash_suffix = hashlib.md5(url.encode()).hexdigest()[:8]
        result = result[:max_length - 9] + '_' + hash_suffix

    return result


def deduplicate_urls(urls: List[str], normalize: bool = True) -> List[str]:
    """
    Remove duplicate URLs from a list.

    Args:
        urls: List of URLs
        normalize: Whether to normalize URLs before comparing

    Returns:
        Deduplicated list (preserves order)
    """
    seen = set()
    result = []

    for url in urls:
        key = normalize_url(url) if normalize else url
        if key not in seen:
            seen.add(key)
            result.append(url)

    return result


def is_valid_url(url: str) -> bool:
    """
    Check if a string is a valid URL.

    Args:
        url: String to check

    Returns:
        True if valid URL
    """
    try:
        result = urlparse(url)
        return all([result.scheme in ('http', 'https'), result.netloc])
    except:
        return False


# ==========================================
# ROBUST HTTP CLIENT
# ==========================================

def get_robust_session(retries: int = 3,
                       backoff_factor: float = 1.0,
                       timeout: int = 30):
    """
    Create a requests Session with automatic retries and backoff.
    Eliminates the need for try/except blocks for network errors.

    Args:
        retries: Number of retry attempts
        backoff_factor: Multiplier for retry delays
        timeout: Default timeout in seconds

    Returns:
        Configured requests.Session

    Example:
        session = get_robust_session(retries=3)
        response = session.get("https://example.com")
    """
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    session = requests.Session()

    retry = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[500, 502, 503, 504, 429],
        allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
    )

    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)

    # Default headers
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    })

    # Default timeout
    session.request = lambda method, url, **kwargs: requests.Session.request(
        session, method, url,
        timeout=kwargs.pop('timeout', timeout),
        **kwargs
    )

    return session


def is_blocked_response(status_code: int, headers: Dict = None, body: str = None) -> bool:
    """
    Detect if a response indicates blocking (Cloudflare, rate limiting, etc.)

    Args:
        status_code: HTTP status code
        headers: Response headers
        body: Response body text

    Returns:
        True if response indicates blocking
    """
    # Status code checks
    if status_code in (403, 429, 503):
        return True

    # Header checks
    if headers:
        cf_headers = ['cf-ray', 'cf-cache-status', 'cf-request-id']
        if any(h.lower() in headers for h in cf_headers):
            # Cloudflare detected, check for challenge
            if status_code >= 400:
                return True

    # Body checks
    if body:
        block_patterns = [
            'access denied',
            'rate limit',
            'too many requests',
            'cloudflare',
            'please complete the security check',
            'captcha',
            'blocked',
            'forbidden'
        ]
        body_lower = body.lower()
        if any(pattern in body_lower for pattern in block_patterns):
            return True

    return False


# ==========================================
# PROGRESS TRACKING & CHECKPOINTING
# ==========================================

class Checkpoint:
    """
    Manages checkpoints for resumable operations.

    Usage:
        cp = Checkpoint("my_task")
        cp.save("current_page", 5)
        page = cp.load("current_page", default=1)
    """

    def __init__(self, name: str, checkpoint_dir: str = ".checkpoints"):
        self.name = name
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.filepath = self.checkpoint_dir / f"{name}.json"
        self._data = self._load()

    def _load(self) -> Dict:
        if self.filepath.exists():
            try:
                with open(self.filepath) as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save(self, key: str, value: Any) -> None:
        """Save a checkpoint value."""
        self._data[key] = value
        self._data['_updated'] = datetime.utcnow().isoformat()
        safe_write_json(str(self.filepath), self._data)

    def load(self, key: str, default: Any = None) -> Any:
        """Load a checkpoint value."""
        return self._data.get(key, default)

    def clear(self) -> None:
        """Clear all checkpoints."""
        self._data = {}
        if self.filepath.exists():
            self.filepath.unlink()


# ==========================================
# BATCH PROCESSING
# ==========================================

def batch_process(items: List[Any],
                  func: Callable,
                  batch_size: int = 100,
                  delay: float = 0.0,
                  progress_callback: Callable = None) -> List[Any]:
    """
    Process items in batches with optional delay and progress tracking.

    Args:
        items: Items to process
        func: Function to apply to each item
        batch_size: Number of items per batch
        delay: Delay between items in seconds
        progress_callback: Called with (current, total) after each item

    Returns:
        List of results
    """
    results = []
    total = len(items)

    for i, item in enumerate(items):
        try:
            result = func(item)
            results.append(result)
        except Exception as e:
            logger.error(f"Batch processing error on item {i}: {e}")
            results.append(None)

        if progress_callback:
            progress_callback(i + 1, total)

        if delay > 0 and i < total - 1:
            time.sleep(delay)

    return results


def retry_with_backoff(func: Callable,
                       max_retries: int = 3,
                       base_delay: float = 1.0,
                       max_delay: float = 60.0,
                       exceptions: tuple = (Exception,)) -> Any:
    """
    Retry a function with exponential backoff.

    Args:
        func: Function to retry (no arguments)
        max_retries: Maximum retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exceptions: Tuple of exceptions to catch

    Returns:
        Function result

    Example:
        result = retry_with_backoff(lambda: session.get(url), max_retries=3)
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return func()
        except exceptions as e:
            last_exception = e
            if attempt < max_retries:
                delay = min(base_delay * (2 ** attempt), max_delay)
                logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay}s: {e}")
                time.sleep(delay)
            else:
                logger.error(f"All {max_retries + 1} attempts failed: {e}")

    raise last_exception


class RateLimiter:
    """
    Simple rate limiter for API calls.

    Usage:
        limiter = RateLimiter(requests_per_second=2)
        for url in urls:
            limiter.wait()
            response = session.get(url)
    """

    def __init__(self, requests_per_second: float = 1.0):
        self.min_interval = 1.0 / requests_per_second
        self.last_request = 0

    def wait(self):
        """Wait if necessary to maintain rate limit."""
        now = time.time()
        elapsed = now - self.last_request
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_request = time.time()


# ==========================================
# DATA EXTRACTION HELPERS
# ==========================================

def extract_text(html: str, preserve_structure: bool = False) -> str:
    """
    Extract visible text from HTML.

    Args:
        html: HTML string
        preserve_structure: Keep some formatting (newlines for blocks)

    Returns:
        Extracted text
    """
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')

        # Remove script and style elements
        for element in soup(['script', 'style', 'head', 'meta', 'noscript']):
            element.decompose()

        if preserve_structure:
            # Add newlines for block elements
            for tag in soup.find_all(['p', 'div', 'br', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li']):
                tag.insert_after('\n')
            text = soup.get_text(separator=' ')
        else:
            text = soup.get_text(separator=' ')

        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    except ImportError:
        # Fallback without BeautifulSoup
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text


def extract_links(html: str, base_url: str = None) -> List[Dict[str, str]]:
    """
    Extract all links from HTML.

    Args:
        html: HTML string
        base_url: Base URL for resolving relative links

    Returns:
        List of dicts with 'href' and 'text' keys
    """
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')

        links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if base_url:
                href = urljoin(base_url, href)

            links.append({
                'href': href,
                'text': a.get_text(strip=True) or '',
                'title': a.get('title', '')
            })

        return links

    except ImportError:
        # Fallback with regex
        pattern = r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]*)</a>'
        matches = re.findall(pattern, html, re.IGNORECASE)

        links = []
        for href, text in matches:
            if base_url:
                href = urljoin(base_url, href)
            links.append({'href': href, 'text': text.strip()})

        return links


def find_emails(text: str) -> List[str]:
    """
    Find email addresses in text.

    Args:
        text: Text to search

    Returns:
        List of unique email addresses
    """
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails = re.findall(pattern, text)
    return list(set(emails))


def find_urls(text: str) -> List[str]:
    """
    Find URLs in text.

    Args:
        text: Text to search

    Returns:
        List of unique URLs
    """
    pattern = r'https?://[^\s<>"\']+(?=[^\s<>"\'])'
    urls = re.findall(pattern, text)
    return list(set(urls))


# ==========================================
# VALIDATION
# ==========================================

def validate_json_schema(data: Any, schema: Dict) -> tuple:
    """
    Validate data against a JSON schema.

    Args:
        data: Data to validate
        schema: JSON Schema dict

    Returns:
        Tuple of (is_valid, errors_list)
    """
    try:
        import jsonschema
        validator = jsonschema.Draft7Validator(schema)
        errors = list(validator.iter_errors(data))
        return len(errors) == 0, [str(e.message) for e in errors]
    except ImportError:
        logger.warning("jsonschema not installed, skipping validation")
        return True, []


def validate_url(url: str) -> bool:
    """Validate that a string is a proper URL."""
    return is_valid_url(url)


def validate_email(email: str) -> bool:
    """Validate that a string is a proper email address."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


# ==========================================
# CONVENIENCE EXPORTS
# ==========================================

__all__ = [
    # Logging
    'JSONLogger', 'logger',

    # File operations
    'safe_write', 'safe_write_json', 'safe_read_json',
    'ensure_directory', 'atomic_rename',

    # URL utilities
    'normalize_url', 'extract_domain', 'url_to_path',
    'deduplicate_urls', 'is_valid_url',

    # HTTP
    'get_robust_session', 'is_blocked_response',

    # Progress tracking
    'Checkpoint',

    # Batch processing
    'batch_process', 'retry_with_backoff', 'RateLimiter',

    # Data extraction
    'extract_text', 'extract_links', 'find_emails', 'find_urls',

    # Validation
    'validate_json_schema', 'validate_url', 'validate_email',
]


if __name__ == "__main__":
    # Quick self-test
    print("Testing ralph_utils...")

    # Test logging
    logger.info("Test info message", {"test": True})
    logger.success("Test success message")

    # Test URL normalization
    test_url = "HTTPS://WWW.Example.COM/path?utm_source=test#section"
    normalized = normalize_url(test_url)
    print(f"Normalized: {normalized}")

    # Test safe write
    safe_write("/tmp/ralph_test.json", json.dumps({"test": "data"}))
    print("Safe write: OK")

    print("\n✅ All tests passed!")
