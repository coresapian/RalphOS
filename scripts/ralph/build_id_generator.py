#!/usr/bin/env python3
"""
Build ID Generator

Generates deterministic build IDs from URLs using MD5 hash.
Same URL always produces the same build_id (DuckDB compatible).

Usage:
    # As module
    from build_id_generator import url_to_build_id
    build_id = url_to_build_id("https://example.com/build/123")
    
    # Command line
    python build_id_generator.py "https://example.com/build/123"
    python build_id_generator.py --json "https://example.com/build/123"
    python build_id_generator.py --batch urls.txt
"""

import hashlib
import json
import sys
from typing import List, Tuple


def url_to_build_id(url: str) -> int:
    """Convert URL to build_id using modified MD5 hash (DuckDB compatible).
    
    Args:
        url: The source URL for the build
        
    Returns:
        A deterministic 63-bit signed integer ID
    """
    # Trim and compute MD5
    url_trimmed = url.strip()
    md5_hash = hashlib.md5(url_trimmed.encode('utf-8')).digest()
    
    # Get lower 64 bits as unsigned integer (little-endian)
    md5_lower = int.from_bytes(md5_hash[:8], byteorder='little', signed=False)
    
    # Apply modulo 2^63 and convert to signed (DuckDB BIGINT compatible)
    build_id = md5_lower % (1 << 63)
    
    return build_id


def generate_batch(urls: List[str]) -> List[Tuple[str, int]]:
    """Generate build IDs for multiple URLs.
    
    Args:
        urls: List of URLs
        
    Returns:
        List of (url, build_id) tuples
    """
    return [(url, url_to_build_id(url)) for url in urls]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    if sys.argv[1] == "--json":
        # JSON output for piping
        url = " ".join(sys.argv[2:])
        build_id = url_to_build_id(url)
        print(json.dumps({
            "url": url,
            "build_id": build_id
        }))
    
    elif sys.argv[1] == "--batch":
        # Process file of URLs
        if len(sys.argv) < 3:
            print("Usage: python build_id_generator.py --batch <urls_file>")
            sys.exit(1)
        
        with open(sys.argv[2], "r") as f:
            urls = [line.strip() for line in f if line.strip()]
        
        for url, build_id in generate_batch(urls):
            print(f"{build_id}\t{url}")
    
    else:
        # Single URL lookup
        url = " ".join(sys.argv[1:])
        build_id = url_to_build_id(url)
        print(f"URL:      {url}")
        print(f"Build ID: {build_id}")

