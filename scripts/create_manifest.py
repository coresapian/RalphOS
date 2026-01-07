#!/usr/bin/env python3
"""
Generate manifest.json from scraped HTML files.
Creates metadata for each scraped vehicle including URL, filename, title, scraped_at, and file_size_bytes.
"""
import json
import os
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup

def extract_title_from_html(html_path):
    """Extract title from HTML file."""
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f.read(), 'html.parser')
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text().strip()
                # Clean up title - remove common suffixes
                for suffix in [' | Gateway Classic Cars', ' - Gateway Classic Cars', '| Gateway Classic Cars']:
                    if title.endswith(suffix):
                        title = title[:-len(suffix)].strip()
                return title
        return None
    except Exception as e:
        print(f"Error extracting title from {html_path}: {e}")
        return None

def create_manifest(output_dir):
    """Create manifest.json from scraped HTML files."""
    output_path = Path(output_dir)
    html_dir = output_path / 'html'
    urls_file = output_path / 'urls.json'

    if not html_dir.exists():
        print(f"HTML directory not found: {html_dir}")
        return

    # Load URLs to get URL-to-slug mapping
    with open(urls_file, 'r') as f:
        urls_data = json.load(f)

    # Create URL lookup from slug to full URL
    slug_to_url = {}
    for url in urls_data.get('urls', []):
        # Extract slug from URL (last part after /)
        slug = url.rstrip('/').split('/')[-1]
        slug_to_url[slug] = url

    manifest = []

    # Process each HTML file
    html_files = sorted(html_dir.glob('*.html'))
    total = len(html_files)

    print(f"Found {total} HTML files")

    for i, html_file in enumerate(html_files, 1):
        slug = html_file.stem
        file_size = html_file.stat().st_size

        # Get URL from slug mapping
        url = slug_to_url.get(slug, f"https://www.gatewayclassiccars.com/vehicles/{slug}")

        # Extract title from HTML
        title = extract_title_from_html(html_file)
        if not title:
            title = slug.replace('-', ' ').title()

        manifest.append({
            "url": url,
            "filename": html_file.name,
            "title": title,
            "scraped_at": datetime.fromtimestamp(html_file.stat().st_mtime).isoformat(),
            "file_size_bytes": file_size
        })

        if i % 100 == 0:
            print(f"Processed {i}/{total} files")

    # Sort manifest by filename for consistency
    manifest.sort(key=lambda x: x['filename'])

    # Write manifest
    manifest_file = output_path / 'manifest.json'
    with open(manifest_file, 'w') as f:
        json.dump(manifest, f, indent=2)

    print(f"\nCreated manifest.json with {len(manifest)} entries")
    print(f"Total size: {sum(m['file_size_bytes'] for m in manifest) / (1024*1024):.1f} MB")

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        output_dir = sys.argv[1]
    else:
        output_dir = 'scraped_builds/gateway_classic_cars'

    create_manifest(output_dir)
