#!/bin/bash
# Scrape Total Cost Involved vehicle URLs using curl and grep

BASE_URL="https://totalcostinvolved.com/customer-showcase/"
OUTPUT_DIR="../../../data/total_cost_involved"
OUTPUT_FILE="$OUTPUT_DIR/urls.jsonl"

echo "Fetching page content..."
HTML=$(curl -s -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36" "$BASE_URL")

# Extract all hrefs from anchor tags
echo "$HTML" | grep -oE 'href="[^"]*"' | sed 's/href="//; s/"$//' | while read -r url; do
    # Skip external URLs and certain paths
    case "$url" in
        *facebook.com*|*twitter.com*|*instagram.com*|*youtube.com*) continue ;;
        /shop/*|/product/*|/cart/*|/checkout/*|/my-account/*) continue ;;
        /customer-showcase*|/news/*|/blog/*|/contact/*|/about/*) continue ;;
        \#*) continue ;;
    esac

    # Convert relative URLs to absolute
    if [[ "$url" =~ ^/ ]]; then
        url="https://totalcostinvolved.com$url"
    fi

    # Only keep totalcostinvolved.com URLs
    if [[ "$url" =~ ^https://totalcostinvolved.com/ ]]; then
        # Extract slug for filename
        slug=$(echo "$url" | sed -E 's|https://totalcostinvolved.com/||' | sed 's|/$||' | tr '/' '-')
        if [[ -z "$slug" ]]; then
            slug="vehicle"
        fi
        filename="${slug}.html"

        # Output JSONL
        echo "{\"url\":\"$url\",\"filename\":\"$filename\"}"
    fi
done | sort -u > "$OUTPUT_FILE"

# Count URLs
COUNT=$(wc -l < "$OUTPUT_FILE")
echo "Found $COUNT unique vehicle URLs"
echo "Saved to $OUTPUT_FILE"

# Show sample
echo ""
echo "First 10 URLs:"
head -10 "$OUTPUT_FILE"
