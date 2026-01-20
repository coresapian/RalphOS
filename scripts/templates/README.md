# RalphOS Source Templates

Pre-built templates for common website types to speed up new source onboarding.

## Available Templates

| Template | Use Case | Key Features |
|----------|----------|--------------|
| `wordpress_gallery.py` | WordPress-based galleries, portfolios | REST API integration, pagination, featured images |
| `paginated_listing.py` | Classic paginated listing pages | Page number extraction, next/prev links |
| `infinite_scroll.py` | JavaScript-loaded infinite scroll | Scroll simulation, AJAX endpoint detection |
| `auction_site.py` | Auction/marketplace sites | Bid data, sale status, lot numbers |

## Usage

1. Copy the appropriate template to your source's data directory:
   ```bash
   cp scripts/templates/wordpress_gallery.py data/my_source/discover_urls.py
   ```

2. Edit the configuration section at the top of the file:
   ```python
   # Configuration - EDIT THESE VALUES
   BASE_URL = "https://example.com"
   GALLERY_PATH = "/gallery/"
   OUTPUT_FILE = "urls.json"
   ```

3. Run the script:
   ```bash
   python data/my_source/discover_urls.py
   ```

## Template Structure

Each template follows the same structure:
- Configuration section (edit this)
- URL discovery logic
- Pagination handling
- Output to urls.json format

## Creating New Templates

When adding a new template:
1. Follow the existing naming convention
2. Include clear configuration section
3. Handle pagination/loading gracefully
4. Output in standard urls.json format:
   ```json
   {
     "urls": ["..."],
     "lastUpdated": "ISO8601",
     "totalCount": N
   }
   ```

