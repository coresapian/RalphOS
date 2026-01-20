#!/usr/bin/env python3
"""
Unit tests for ParallelProcessor
"""

import asyncio
import tempfile
import time
import unittest

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts', 'ralph'))

from parallel_processor import ParallelProcessor, ScrapingBatchProcessor


class TestParallelProcessor(unittest.TestCase):
    """Test cases for ParallelProcessor class."""
    
    def test_initialization(self):
        """Test parallel processor initialization."""
        processor = ParallelProcessor(max_workers=4, rate_limit=1.0)
        
        self.assertEqual(processor.max_workers, 4)
        self.assertEqual(processor.rate_limit, 1.0)
        self.assertEqual(processor.semaphore._value, 4)
    
    def test_max_workers_capped(self):
        """Test that max_workers is capped at 10."""
        processor = ParallelProcessor(max_workers=20)
        self.assertEqual(processor.max_workers, 10)
    
    def test_min_workers(self):
        """Test that max_workers has minimum of 1."""
        processor = ParallelProcessor(max_workers=0)
        self.assertEqual(processor.max_workers, 1)
    
    def test_rate_limit_capped(self):
        """Test that rate_limit has minimum of 0.1."""
        processor = ParallelProcessor(rate_limit=0.01)
        self.assertEqual(processor.rate_limit, 0.1)
    
    async def _dummy_task(self, value):
        """Dummy async task for testing."""
        await asyncio.sleep(0.1)
        return value * 2
    
    def test_run_single_task(self):
        """Test running a single task."""
        processor = ParallelProcessor(max_workers=2, rate_limit=0.1)
        
        result = asyncio.run(processor.run_task(self._dummy_task, 5))
        self.assertEqual(result, 10)
    
    def test_run_multiple_tasks(self):
        """Test running multiple tasks in parallel."""
        processor = ParallelProcessor(max_workers=3, rate_limit=0.05)
        
        task_list = [
            (self._dummy_task, (i,), {})
            for i in range(5)
        ]
        
        results = asyncio.run(processor.run_tasks(task_list))
        
        expected = [i * 2 for i in range(5)]
        self.assertEqual(results, expected)
    
    def test_rate_limiting(self):
        """Test that rate limiting works."""
        processor = ParallelProcessor(max_workers=2, rate_limit=0.2)
        
        start = time.time()
        
        async def run_many_tasks():
            task_list = [
                (self._dummy_task, (i,), {})
                for i in range(5)
            ]
            return await processor.run_tasks(task_list)
        
        asyncio.run(run_many_tasks())
        
        elapsed = time.time() - start
        # With rate limiting, should take at least 0.2 * ceil(5/2) = 0.6s
        self.assertGreater(elapsed, 0.5)


class TestScrapingBatchProcessor(unittest.TestCase):
    """Test cases for ScrapingBatchProcessor class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.processor = ScrapingBatchProcessor(self.temp_dir, batch_size=10)
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_initialization(self):
        """Test batch processor initialization."""
        self.assertEqual(self.processor.batch_size, 10)
        self.assertEqual(self.processor.output_dir.name, 'scrape_progress.json')
    
    def test_load_urls_no_file(self):
        """Test loading URLs when no file exists."""
        urls = self.processor.load_urls()
        self.assertEqual(urls, [])
    
    def test_get_batches(self):
        """Test splitting URLs into batches."""
        urls = [f"https://example{i}.com" for i in range(25)]
        batches = self.processor.get_batches(urls)
        
        self.assertEqual(len(batches), 3)
        self.assertEqual(len(batches[0]), 10)
        self.assertEqual(len(batches[1]), 10)
        self.assertEqual(len(batches[2]), 5)
    
    def test_get_batches_empty(self):
        """Test batching empty list."""
        batches = self.processor.get_batches([])
        self.assertEqual(batches, [])
    
    def test_get_batches_single_batch(self):
        """Test batching when fewer URLs than batch size."""
        urls = [f"https://example{i}.com" for i in range(5)]
        batches = self.processor.get_batches(urls)
        
        self.assertEqual(len(batches), 1)
        self.assertEqual(len(batches[0]), 5)
    
    def test_load_progress_no_file(self):
        """Test loading progress when no file exists."""
        progress = self.processor.load_progress()
        
        self.assertEqual(progress['total'], 0)
        self.assertEqual(progress['completed'], 0)
        self.assertEqual(progress['failed'], 0)
        self.assertIsNone(progress['last_updated'])
    
    def test_save_progress(self):
        """Test saving progress."""
        progress_data = {
            'total': 100,
            'completed': 50,
            'failed': 5
        }
        
        self.processor.save_progress(progress_data)
        
        # Load and verify
        loaded = self.processor.load_progress()
        self.assertEqual(loaded['total'], 100)
        self.assertEqual(loaded['completed'], 50)
        self.assertEqual(loaded['failed'], 5)
        self.assertIsNotNone(loaded['last_updated'])


if __name__ == '__main__':
    unittest.main()
