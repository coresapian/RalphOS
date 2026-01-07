#!/usr/bin/env python3
"""
Generate manifest.json for Custom Wheel Offset scraped HTML files.
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
                # Clean up title - remove common suffixes for Custom Wheel Offset
                for suffix in [' | Custom Wheel Offset', ' - Custom Wheel Offset', '| Custom Wheel Offset']:
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

    # Load URLs to build URL lookup
    with open(urls_file, 'r') as f:
        urls_data = json.load(f)

    # Create URL lookup from ID to full URL
    # Custom Wheel Offset URL pattern: https://www.customwheeloffset.com/wheel-offset-gallery/{id}/{description}
    id_to_url = {}
    for url in urls_data.get('urls', []):
        parts = url.rstrip('/').split('/')
        if len(parts) >= 2:
            vehicle_id = parts[-2]
            id_to_url[vehicle_id] = url

    manifest = []

    # Process each HTML file
    html_files = sorted(html_dir.glob('*.html'))
    total = len(html_files)

    print(f"Found {total} HTML files")

    for i, html_file in enumerate(html_files, 1):
        # Extract vehicle ID from filename: {id}_{description}.html
        stem = html_file.stem
        vehicle_id = stem.split('_')[0] if '_' in stem else stem

        file_size = html_file.stat().st_size

        # Get URL from ID mapping
        url = id_to_url.get(vehicle_id, f"https://www.customwheeloffset.com/wheel-offset-gallery/{vehicle_id}")

        # Extract title from HTML
        title = extract_title_from_html(html_file)
        if not title:
            title = stem.replace('-', ' ').replace('_', ' ').title()

        manifest.append({
            "url": url,
            "filename": html_file.name,
            "title": title,
            "scraped_at": datetime.fromtimestamp(html_file.stat().st_mtime).isoformat(),
            "file_size_bytes": file_size
        })

        if i % 10 == 0:
            print(f"Processed {i}/{total} files")

    # Sort manifest by filename for consistency
    manifest.sort(key=lambda x: x['filename'])

    # Write manifest
    manifest_file = output_path / 'manifest.json'
    with open(manifest_file, 'w') as f:
        json.dump(manifest, f, indent=2)

    total_size = sum(m['file_size_bytes'] for m in manifest)
    print(f"\nCreated manifest.json with {len(manifest)} entries")
    print(f"Total size: {total_size / (1024*1024):.1f} MB")

    return manifest

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        output_dir = sys.argv[1]
    else:
        output_dir = '/Users/core/MOTORMIA/Documents-data/GitHub/RalphOS/scraped_builds/custom_wheel_offset'

    create_manifest(output_dir)
