#!/usr/bin/env python3
"""
MartiniWorks Build Thread URL Scraper
Scrapes all build thread URLs from the gallery page with infinite scroll handling.
"""

import json
import time
import sys
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin, urlparse

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
except ImportError:
    print("Error: selenium not installed. Run: pip install selenium")
    sys.exit(1)


class MartiniWorksScraper:
    BASE_URL = "https://martiniworks.com/build-threads"
    OUTPUT_FILE = Path("scraped_builds/urls.json")
    SCROLL_PAUSE_TIME = 2  # Seconds to wait between scrolls
    MAX_SCROLL_ATTEMPTS = 500  # Safety limit to prevent infinite loop
    BUILD_CARD_SELECTOR = "a[href*='/build-threads/']"

    def __init__(self, headless: bool = True):
        self.urls_seen = set()
        self.driver = None
        self.setup_driver(headless)

    def setup_driver(self, headless: bool):
        """Initialize Chrome WebDriver with appropriate options."""
        options = Options()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")

        try:
            self.driver = webdriver.Chrome(options=options)
            self.driver.set_window_size(1920, 1080)
        except Exception as e:
            print(f"Error initializing WebDriver: {e}")
            print("Make sure Chrome browser and chromedriver are installed.")
            sys.exit(1)

    def extract_urls_from_page(self) -> set:
        """Extract all unique build thread URLs from current page state."""
        urls = set()
        try:
            links = self.driver.find_elements(By.CSS_SELECTOR, self.BUILD_CARD_SELECTOR)
            for link in links:
                href = link.get_attribute("href")
                if href and "/build-threads/" in href:
                    # Normalize URL
                    parsed = urlparse(href)
                    clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                    # Exclude the main gallery page
                    if clean_url != self.BASE_URL and clean_url != f"{self.BASE_URL}/":
                        urls.add(clean_url)
        except Exception as e:
            print(f"Error extracting URLs: {e}")
        return urls

    def scroll_to_load_all(self):
        """Handle infinite scroll by scrolling until no new content loads."""
        print("Handling infinite scroll...")
        last_height = 0
        scroll_attempts = 0
        no_new_content_count = 0

        while scroll_attempts < self.MAX_SCROLL_ATTEMPTS:
            # Scroll to bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(self.SCROLL_PAUSE_TIME)

            # Get new scroll height
            new_height = self.driver.execute_script("return document.body.scrollHeight")

            # Extract URLs from current view
            current_urls = self.extract_urls_from_page()
            new_urls = current_urls - self.urls_seen

            if new_urls:
                self.urls_seen.update(new_urls)
                print(f"  Scroll {scroll_attempts + 1}: Found {len(new_urls)} new URLs (total: {len(self.urls_seen)})")
                no_new_content_count = 0
            else:
                no_new_content_count += 1
                print(f"  Scroll {scroll_attempts + 1}: No new URLs (consecutive: {no_new_content_count})")

            # Check if we've reached the bottom
            if new_height == last_height:
                no_new_content_count += 1
                if no_new_content_count >= 3:
                    print("  Reached bottom of page (no new content for 3 scrolls)")
                    break

            last_height = new_height
            scroll_attempts += 1

        if scroll_attempts >= self.MAX_SCROLL_ATTEMPTS:
            print(f"  Warning: Reached maximum scroll attempts ({self.MAX_SCROLL_ATTEMPTS})")

    def scrape_urls(self):
        """Main scraping method."""
        print(f"Starting scrape of {self.BASE_URL}")
        print("-" * 50)

        try:
            self.driver.get(self.BASE_URL)
            time.sleep(3)  # Initial wait for page load

            # Wait for build cards to appear
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, self.BUILD_CARD_SELECTOR))
            )

            # Handle infinite scroll
            self.scroll_to_load_all()

        except TimeoutException:
            print("Error: Page load timeout")
        except Exception as e:
            print(f"Error during scraping: {e}")

        return self.urls_seen

    def save_urls(self, urls: set):
        """Save URLs to JSON file."""
        urls_list = sorted(list(urls))  # Sort for consistency

        data = {
            "urls": urls_list,
            "lastUpdated": datetime.now().isoformat(),
            "totalCount": len(urls_list)
        }

        self.OUTPUT_FILE.write_text(json.dumps(data, indent=2))
        print("-" * 50)
        print(f"Saved {len(urls_list)} URLs to {self.OUTPUT_FILE}")

    def close(self):
        """Clean up WebDriver."""
        if self.driver:
            self.driver.quit()


def main():
    print("=" * 50)
    print("MartiniWorks Build Thread URL Scraper")
    print("=" * 50)

    scraper = MartiniWorksScraper(headless=True)

    try:
        urls = scraper.scrape_urls()
        scraper.save_urls(urls)

        print("\n" + "=" * 50)
        print("SCRAPING COMPLETE")
        print("=" * 50)
        print(f"Total URLs discovered: {len(urls)}")
        print(f"Output file: {scraper.OUTPUT_FILE}")
        print("=" * 50)

    finally:
        scraper.close()


if __name__ == "__main__":
    main()
