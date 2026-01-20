#!/usr/bin/env python3
"""
Parallel Processing Utility for RalphOS

Manages parallel execution of scraping tasks with rate limiting and progress tracking.
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Callable, Optional
from datetime import datetime
import subprocess


class ParallelProcessor:
    """Manages parallel execution of scraping tasks."""
    
    def __init__(self, max_workers: int = 4, rate_limit: float = 1.0):
        """Initialize parallel processor.
        
        Args:
            max_workers: Maximum number of concurrent workers
            rate_limit: Minimum delay between requests in seconds
        """
        self.max_workers = max(1, min(max_workers, 10))  # Cap at 10
        self.rate_limit = max(0.1, rate_limit)
        self.semaphore = asyncio.Semaphore(self.max_workers)
        self.request_times = []
    
    async def _rate_limit(self):
        """Apply rate limiting between requests."""
        now = time.time()
        
        # Keep only recent timestamps (last rate_limit seconds)
        self.request_times = [t for t in self.request_times if now - t < self.rate_limit]
        
        # If at capacity, wait
        if len(self.request_times) >= self.max_workers:
            sleep_time = self.rate_limit - (now - min(self.request_times))
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
        
        self.request_times.append(now)
    
    async def run_task(self, task_func: Callable, *args, **kwargs):
        """Run a single task with rate limiting.
        
        Args:
            task_func: Async function to execute
            *args: Positional args for task_func
            **kwargs: Keyword args for task_func
            
        Returns:
            Task result
        """
        async with self.semaphore:
            await self._rate_limit()
            return await task_func(*args, **kwargs)
    
    async def run_tasks(self, task_list: List[tuple]) -> List:
        """Run multiple tasks in parallel.
        
        Args:
            task_list: List of (task_func, args, kwargs) tuples
            
        Returns:
            List of results
        """
        tasks = []
        for task_func, args, kwargs in task_list:
            task = self.run_task(task_func, *args, **kwargs)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results
    
    async def run_subprocess(self, command: List[str], cwd: str = None) -> Dict:
        """Run a subprocess task.
        
        Args:
            command: Command to execute
            cwd: Working directory
            
        Returns:
            Dict with returncode, stdout, stderr
        """
        async with self.semaphore:
            await self._rate_limit()
            
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            return {
                'returncode': process.returncode,
                'stdout': stdout.decode('utf-8'),
                'stderr': stderr.decode('utf-8'),
                'command': ' '.join(command)
            }
    
    async def run_scrape_tasks(self, urls: List[str], 
                               output_dir: str,
                               script_path: str) -> List[Dict]:
        """Run multiple scrape tasks in parallel.
        
        Args:
            urls: List of URLs to scrape
            output_dir: Output directory for scraped data
            script_path: Path to scrape script
            
        Returns:
            List of task results
        """
        tasks = []
        for url in urls:
            task = self.run_subprocess(
                ['python3', script_path, '--url', url, '--output', output_dir],
                cwd=os.path.dirname(script_path)
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results


class ScrapingBatchProcessor:
    """Batch processor for scraping URLs with progress tracking."""
    
    def __init__(self, output_dir: str, batch_size: int = 100):
        """Initialize batch processor.
        
        Args:
            output_dir: Output directory
            batch_size: Number of URLs per batch
        """
        self.output_dir = Path(output_dir)
        self.batch_size = batch_size
        self.progress_file = self.output_dir / "scrape_progress.json"
    
    def load_urls(self) -> List[str]:
        """Load URLs from urls.json.
        
        Returns:
            List of URLs
        """
        urls_file = self.output_dir / "urls.json"
        
        if not urls_file.exists():
            return []
        
        with open(urls_file, 'r') as f:
            data = json.load(f)
        
        return data.get('urls', [])
    
    def load_progress(self) -> Dict:
        """Load scraping progress.
        
        Returns:
            Progress dict
        """
        if not self.progress_file.exists():
            return {
                'total': 0,
                'completed': 0,
                'failed': 0,
                'last_updated': None
            }
        
        with open(self.progress_file, 'r') as f:
            return json.load(f)
    
    def save_progress(self, progress: Dict):
        """Save scraping progress.
        
        Args:
            progress: Progress dict
        """
        progress['last_updated'] = datetime.now().isoformat()
        
        with open(self.progress_file, 'w') as f:
            json.dump(progress, f, indent=2)
    
    def get_batches(self, urls: List[str]) -> List[List[str]]:
        """Split URLs into batches.
        
        Args:
            urls: List of URLs
            
        Returns:
            List of URL batches
        """
        batches = []
        for i in range(0, len(urls), self.batch_size):
            batch = urls[i:i + self.batch_size]
            batches.append(batch)
        return batches
    
    def get_remaining_urls(self) -> List[str]:
        """Get URLs that haven't been scraped yet.
        
        Returns:
            List of URLs to scrape
        """
        urls = self.load_urls()
        progress = self.load_progress()
        
        # Load existing HTML files
        html_dir = self.output_dir / "html"
        scraped_urls = set()
        
        if html_dir.exists():
            for html_file in html_dir.glob("*.html"):
                # Extract URL from filename or metadata
                # For now, just count files
                pass
        
        # Return URLs that haven't been scraped
        # This is a simplified version - you'd need proper tracking
        return urls[progress.get('completed', 0):]


async def scrape_urls_parallel(urls: List[str],
                               output_dir: str,
                               script_path: str,
                               max_workers: int = 4,
                               rate_limit: float = 1.0) -> Dict:
    """Scrape multiple URLs in parallel.
    
    Args:
        urls: List of URLs to scrape
        output_dir: Output directory
        script_path: Path to scrape script
        max_workers: Maximum concurrent workers
        rate_limit: Delay between requests
        
    Returns:
        Result summary
    """
    processor = ParallelProcessor(max_workers=max_workers, rate_limit=rate_limit)
    
    start_time = time.time()
    results = await processor.run_scrape_tasks(urls, output_dir, script_path)
    elapsed = time.time() - start_time
    
    success = sum(1 for r in results if isinstance(r, dict) and r.get('returncode') == 0)
    failed = len(results) - success
    
    return {
        'total': len(urls),
        'success': success,
        'failed': failed,
        'elapsed': elapsed,
        'avg_time': elapsed / len(urls) if urls else 0
    }


def main():
    """CLI interface for parallel processing."""
    import argparse
    
    parser = argparse.ArgumentParser(description="RalphOS Parallel Processor")
    parser.add_argument("action", choices=[
        "scrape", "batch", "progress"
    ], help="Action to perform")
    parser.add_argument("--urls-file", help="Path to urls.json")
    parser.add_argument("--output-dir", help="Output directory")
    parser.add_argument("--script", help="Path to scrape script")
    parser.add_argument("--workers", type=int, default=4, 
                       help="Number of parallel workers")
    parser.add_argument("--rate-limit", type=float, default=1.0,
                       help="Delay between requests (seconds)")
    parser.add_argument("--batch-size", type=int, default=100,
                       help="Number of URLs per batch")
    
    args = parser.parse_args()
    
    if args.action == "scrape":
        if not args.urls_file or not args.output_dir or not args.script:
            print("Error: --urls-file, --output-dir, and --script required for scrape")
            return 1
        
        with open(args.urls_file, 'r') as f:
            data = json.load(f)
        
        urls = data.get('urls', [])
        
        print(f"Scraping {len(urls)} URLs with {args.workers} workers...")
        result = asyncio.run(scrape_urls_parallel(
            urls, args.output_dir, args.script,
            args.workers, args.rate_limit
        ))
        
        print(f"Completed: {result['success']}/{result['total']}")
        print(f"Failed: {result['failed']}")
        print(f"Time: {result['elapsed']:.2f}s")
        print(f"Avg: {result['avg_time']:.2f}s per URL")
    
    elif args.action == "batch":
        if not args.urls_file or not args.output_dir:
            print("Error: --urls-file and --output-dir required for batch")
            return 1
        
        processor = ScrapingBatchProcessor(args.output_dir, args.batch_size)
        urls = processor.load_urls()
        batches = processor.get_batches(urls)
        
        print(f"Total URLs: {len(urls)}")
        print(f"Batch size: {args.batch_size}")
        print(f"Number of batches: {len(batches)}")
    
    elif args.action == "progress":
        if not args.output_dir:
            print("Error: --output-dir required for progress")
            return 1
        
        processor = ScrapingBatchProcessor(args.output_dir)
        progress = processor.load_progress()
        
        print(json.dumps(progress, indent=2))
    
    return 0


if __name__ == "__main__":
    exit(main())
