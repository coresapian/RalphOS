#!/usr/bin/env python3
"""
Unit tests for SourceDiscovery
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts', 'ralph'))

from source_discovery import SourceDiscovery, SourceStatus


class TestSourceDiscovery(unittest.TestCase):
    """Test cases for SourceDiscovery class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        self.temp_file.close()
        
        # Create test sources data
        self.test_data = {
            "description": "Test sources",
            "validStatuses": {
                "pending": "Not started yet",
                "in_progress": "Currently being worked on",
                "blocked": "Scraping blocked",
                "completed": "ALL URLs attempted"
            },
            "pipelineFields": {
                "expectedUrls": "Total URLs",
                "urlsFound": "URLs discovered",
                "htmlScraped": "HTML files downloaded"
            },
            "sources": [
                {
                    "id": "source1",
                    "name": "Source 1",
                    "url": "https://example1.com",
                    "outputDir": "data/source1",
                    "status": "pending",
                    "priority": 1,
                    "pipeline": {
                        "urlsFound": 10,
                        "htmlScraped": 0,
                        "builds": 0,
                        "mods": 0
                    }
                },
                {
                    "id": "source2",
                    "name": "Source 2",
                    "url": "https://example2.com",
                    "outputDir": "data/source2",
                    "status": "in_progress",
                    "priority": 2,
                    "pipeline": {
                        "urlsFound": 20,
                        "htmlScraped": 5,
                        "builds": 0,
                        "mods": 0
                    }
                },
                {
                    "id": "source3",
                    "name": "Source 3",
                    "url": "https://example3.com",
                    "outputDir": "data/source3",
                    "status": "blocked",
                    "priority": 3,
                    "pipeline": {
                        "urlsFound": 30,
                        "htmlScraped": 0,
                        "htmlBlocked": 5,
                        "builds": 0,
                        "mods": 0
                    }
                },
                {
                    "id": "source4",
                    "name": "Source 4",
                    "url": "https://example4.com",
                    "outputDir": "data/source4",
                    "status": "completed",
                    "priority": 4,
                    "pipeline": {
                        "urlsFound": 40,
                        "htmlScraped": 40,
                        "builds": 40,
                        "mods": 40
                    }
                }
            ]
        }
        
        with open(self.temp_file.name, 'w') as f:
            json.dump(self.test_data, f)
        
        self.discovery = SourceDiscovery(self.temp_file.name)
    
    def tearDown(self):
        """Clean up test fixtures."""
        os.unlink(self.temp_file.name)
    
    def test_initialization(self):
        """Test source discovery initialization."""
        self.assertEqual(len(self.discovery.sources), 4)
        self.assertEqual(self.discovery.sources[0]['id'], 'source1')
    
    def test_get_next_source_pending(self):
        """Test getting next pending source."""
        next_source = self.discovery.get_next_source(
            status_filter=[SourceStatus.PENDING]
        )
        
        self.assertIsNotNone(next_source)
        self.assertEqual(next_source['id'], 'source1')
        self.assertEqual(next_source['priority'], 1)
    
    def test_get_next_source_in_progress(self):
        """Test getting next in_progress source."""
        next_source = self.discovery.get_next_source(
            status_filter=[SourceStatus.IN_PROGRESS]
        )
        
        self.assertIsNotNone(next_source)
        self.assertEqual(next_source['id'], 'source2')
    
    def test_get_next_source_skip_blocked(self):
        """Test getting next source while skipping blocked."""
        next_source = self.discovery.get_next_source(
            status_filter=[SourceStatus.PENDING, SourceStatus.IN_PROGRESS, SourceStatus.BLOCKED],
            skip_blocked=True
        )
        
        # Should return source1 (priority 1, pending)
        self.assertIsNotNone(next_source)
        self.assertEqual(next_source['id'], 'source1')
    
    def test_get_source_by_id(self):
        """Test getting source by ID."""
        source = self.discovery.get_source_by_id('source3')
        
        self.assertIsNotNone(source)
        self.assertEqual(source['name'], 'Source 3')
        self.assertEqual(source['status'], 'blocked')
    
    def test_get_source_by_id_not_found(self):
        """Test getting non-existent source."""
        source = self.discovery.get_source_by_id('nonexistent')
        self.assertIsNone(source)
    
    def test_update_source_status(self):
        """Test updating source status."""
        self.discovery.update_source_status(
            'source1', 
            SourceStatus.IN_PROGRESS
        )
        
        # Reload sources
        source = self.discovery.get_source_by_id('source1')
        self.assertEqual(source['status'], 'in_progress')
    
    def test_set_source_priority(self):
        """Test setting source priority."""
        self.discovery.set_source_priority('source1', 10)
        
        # Reload sources
        source = self.discovery.get_source_by_id('source1')
        self.assertEqual(source['priority'], 10)
    
    def test_update_pipeline_progress(self):
        """Test updating pipeline progress."""
        self.discovery.update_pipeline_progress(
            'source1',
            htmlScraped=5,
            builds=2
        )
        
        # Reload sources
        source = self.discovery.get_source_by_id('source1')
        self.assertEqual(source['pipeline']['htmlScraped'], 5)
        self.assertEqual(source['pipeline']['builds'], 2)
    
    def test_get_sources_by_status(self):
        """Test getting sources by status."""
        pending = self.discovery.get_sources_by_status(SourceStatus.PENDING)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]['id'], 'source1')
        
        blocked = self.discovery.get_sources_by_status(SourceStatus.BLOCKED)
        self.assertEqual(len(blocked), 1)
        self.assertEqual(blocked[0]['id'], 'source3')
    
    def test_get_pipeline_summary(self):
        """Test getting pipeline summary."""
        summary = self.discovery.get_pipeline_summary()
        
        self.assertEqual(summary['total_sources'], 4)
        self.assertEqual(summary['pending'], 1)
        self.assertEqual(summary['in_progress'], 1)
        self.assertEqual(summary['blocked'], 1)
        self.assertEqual(summary['completed'], 1)
        
        self.assertEqual(summary['total_urls_found'], 100)
        self.assertEqual(summary['total_html_scraped'], 45)
        self.assertEqual(summary['total_builds'], 40)
        self.assertEqual(summary['total_mods'], 40)
    
    def test_auto_prioritize(self):
        """Test automatic source prioritization."""
        self.discovery.auto_prioritize()
        
        # Source with URLs but no HTML should get priority 1
        source1 = self.discovery.get_source_by_id('source1')
        self.assertEqual(source1['priority'], 1)
        
        # Pending sources should have priority 5
        source2 = self.discovery.get_source_by_id('source2')
        self.assertEqual(source2['priority'], 2)  # Already set
    
    def test_sort_by_priority(self):
        """Test that sources are sorted by priority."""
        next_source = self.discovery.get_next_source()
        
        # Should return source1 (priority 1)
        self.assertEqual(next_source['id'], 'source1')
        self.assertEqual(next_source['priority'], 1)


if __name__ == '__main__':
    unittest.main()
