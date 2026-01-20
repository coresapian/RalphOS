You are analyzing a website to create a scraping PRD (Product Requirements Document).

TARGET SITE: Wheel Specialists
URL: https://wheelspecialists.com
OUTPUT DIR: data/wheelspecialists

YOUR TASK:
1. Use the browser tools to navigate to https://wheelspecialists.com
2. Take a snapshot to understand the site structure
3. Identify:
   - What type of content is on this site (vehicle listings, build threads, gallery, etc.)
   - How to find all vehicle/build URLs (pagination, infinite scroll, categories)
   - What data can be extracted (year, make, model, mods, images, etc.)
   - Any anti-bot protections (Cloudflare, rate limiting)

4. Create a PRD file at scripts/ralph/prd.json with appropriate user stories

IMPORTANT: 
- Use browser_navigate to go to the URL
- Use browser_snapshot to see the page structure
- Create realistic, actionable user stories based on what you find
- If the site has anti-bot protection, note to use aggressive_stealth_scraper.py

After analysis, write the PRD to: scripts/ralph/prd.json

The PRD format should be:
{
  "projectName": "Wheel Specialists Scraping",
  "sourceId": "wheelspecialists",
  "branchName": "main", 
  "targetUrl": "https://wheelspecialists.com",
  "outputDir": "data/wheelspecialists",
  "userStories": [
    {
      "id": "URL-001",
      "title": "Discover all vehicle/build URLs",
      "acceptanceCriteria": ["..."],
      "priority": 1,
      "passes": false,
      "notes": "Based on site analysis..."
    }
  ],
  "siteAnalysis": {
    "contentType": "...",
    "paginationType": "...",
    "antiBot": "...",
    "dataFields": ["..."]
  }
}

START by navigating to the URL and taking a snapshot.
