#!/usr/bin/env python3
"""
Integration tests for RalphOS
Tests the full pipeline workflow
"""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts', 'ralph'))

from checkpoint_manager import CheckpointManager
from source_discovery import SourceDiscovery, SourceStatus


class TestRalphOSIntegration(unittest.TestCase):
    """Integration tests for RalphOS."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.sources_file = os.path.join(self.temp_dir, 'sources.json')
        self.checkpoint_dir = os.path.join(self.temp_dir, 'checkpoints')
        
        # Create test sources file
        self.test_sources = {
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
                    "id": "test_source1",
                    "name": "Test Source 1",
                    "url": "https://test1.com",
                    "outputDir": "data/test_source1",
                    "status": "pending",
                    "priority": 1,
                    "attempted": 0,
                    "lastAttempted": None,
                    "pipeline": {
                        "expectedUrls": 10,
                        "urlsFound": 0,
                        "htmlScraped": 0,
                        "htmlFailed": 0,
                        "htmlBlocked": 0,
                        "builds": 0,
                        "mods": 0
                    }
                },
                {
                    "id": "test_source2",
                    "name": "Test Source 2",
                    "url": "https://test2.com",
                    "outputDir": "data/test_source2",
                    "status": "pending",
                    "priority": 2,
                    "attempted": 0,
                    "lastAttempted": None,
                    "pipeline": {
                        "expectedUrls": 20,
                        "urlsFound": 0,
                        "htmlScraped": 0,
                        "htmlFailed": 0,
                        "htmlBlocked": 0,
                        "builds": 0,
                        "mods": 0
                    }
                }
            ]
        }
        
        with open(self.sources_file, 'w') as f:
            json.dump(self.test_sources, f, indent=2)
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_checkpoint_and_resume_workflow(self):
        """Test checkpoint creation and resume workflow."""
        # Initialize checkpoint manager
        checkpoint_manager = CheckpointManager(self.checkpoint_dir)
        
        # Save initial checkpoint
        checkpoint_manager.save_checkpoint(
            iteration=5,
            prd_file=os.path.join(self.temp_dir, 'prd.json'),
            sources_file=self.sources_file,
            source_id='test_source1'
        )
        
        # Verify checkpoint exists
        self.assertTrue(checkpoint_manager.has_checkpoint())
        
        # Load checkpoint
        loaded = checkpoint_manager.load_checkpoint()
        self.assertEqual(loaded['iteration'], 5)
        self.assertEqual(loaded['source_id'], 'test_source1')
        
        # Clear checkpoint
        checkpoint_manager.clear_checkpoint()
        self.assertFalse(checkpoint_manager.has_checkpoint())
    
    def test_source_discovery_workflow(self):
        """Test source discovery and priority workflow."""
        # Initialize source discovery
        discovery = SourceDiscovery(self.sources_file)
        
        # Get next source (should be test_source1 with priority 1)
        next_source = discovery.get_next_source()
        self.assertEqual(next_source['id'], 'test_source1')
        self.assertEqual(next_source['priority'], 1)
        
        # Update status to in_progress
        discovery.update_source_status(
            'test_source1',
            SourceStatus.IN_PROGRESS
        )
        
        # Next source should now be test_source2
        next_source = discovery.get_next_source()
        self.assertEqual(next_source['id'], 'test_source2')
        
        # Update pipeline progress
        discovery.update_pipeline_progress(
            'test_source1',
            urlsFound=10,
            htmlScraped=5
        )
        
        # Verify updates
        source = discovery.get_source_by_id('test_source1')
        self.assertEqual(source['pipeline']['urlsFound'], 10)
        self.assertEqual(source['pipeline']['htmlScraped'], 5)
    
    def test_auto_prioritize_workflow(self):
        """Test automatic prioritization workflow."""
        discovery = SourceDiscovery(self.sources_file)
        
        # Run auto-prioritize
        discovery.auto_prioritize()
        
        # Source with URLs discovered should get higher priority
        discovery.update_pipeline_progress(
            'test_source1',
            urlsFound=10,
            htmlScraped=0
        )
        
        # Get next source should prioritize test_source1
        next_source = discovery.get_next_source()
        self.assertEqual(next_source['id'], 'test_source1')
    
    def test_pipeline_summary_workflow(self):
        """Test pipeline summary generation."""
        discovery = SourceDiscovery(self.sources_file)
        
        # Update some progress
        discovery.update_pipeline_progress(
            'test_source1',
            urlsFound=10,
            htmlScraped=5,
            builds=3
        )
        
        discovery.update_pipeline_progress(
            'test_source2',
            urlsFound=20,
            htmlScraped=15,
            builds=10
        )
        
        # Get summary
        summary = discovery.get_pipeline_summary()
        
        self.assertEqual(summary['total_sources'], 2)
        self.assertEqual(summary['pending'], 2)
        self.assertEqual(summary['total_urls_found'], 30)
        self.assertEqual(summary['total_html_scraped'], 20)
        self.assertEqual(summary['total_builds'], 13)
    
    def test_blocked_source_workflow(self):
        """Test handling of blocked sources."""
        discovery = SourceDiscovery(self.sources_file)
        
        # Mark a source as blocked
        discovery.update_source_status(
            'test_source1',
            SourceStatus.BLOCKED,
            attempted=3
        )
        
        # Get next source should skip blocked
        next_source = discovery.get_next_source(skip_blocked=True)
        self.assertEqual(next_source['id'], 'test_source2')
        
        # Get blocked sources
        blocked = discovery.get_sources_by_status(SourceStatus.BLOCKED)
        self.assertEqual(len(blocked), 1)
        self.assertEqual(blocked[0]['id'], 'test_source1')
    
    def test_checkpoint_with_source_info(self):
        """Test checkpoint with source discovery integration."""
        checkpoint_manager = CheckpointManager(self.checkpoint_dir)
        discovery = SourceDiscovery(self.sources_file)
        
        # Get current source
        next_source = discovery.get_next_source()
        
        # Save checkpoint with source info
        checkpoint_manager.save_checkpoint(
            iteration=3,
            prd_file=os.path.join(self.temp_dir, 'prd.json'),
            sources_file=self.sources_file,
            source_id=next_source['id'],
            additional_state={
                'source_name': next_source['name'],
                'source_url': next_source['url']
            }
        )
        
        # Load and verify
        loaded = checkpoint_manager.load_checkpoint()
        self.assertEqual(loaded['source_id'], 'test_source1')
        self.assertEqual(loaded['additional_state']['source_name'], 'Test Source 1')
    
    def test_full_workflow_simulation(self):
        """Simulate a full workflow: source selection -> work -> checkpoint -> resume."""
        # Setup
        checkpoint_manager = CheckpointManager(self.checkpoint_dir)
        discovery = SourceDiscovery(self.sources_file)
        
        # Step 1: Select source
        source = discovery.get_next_source()
        self.assertEqual(source['id'], 'test_source1')
        
        # Step 2: Mark as in_progress
        discovery.update_source_status(source['id'], SourceStatus.IN_PROGRESS)
        
        # Step 3: Do some work (update pipeline)
        discovery.update_pipeline_progress(
            source['id'],
            urlsFound=10,
            htmlScraped=5
        )
        
        # Step 4: Save checkpoint
        checkpoint_manager.save_checkpoint(
            iteration=1,
            prd_file=os.path.join(self.temp_dir, 'prd.json'),
            sources_file=self.sources_file,
            source_id=source['id']
        )
        
        # Step 5: Simulate restart - reload checkpoint
        loaded = checkpoint_manager.load_checkpoint()
        self.assertEqual(loaded['iteration'], 1)
        
        # Step 6: Continue from checkpoint
        discovery_resume = SourceDiscovery(self.sources_file)
        source_resume = discovery_resume.get_source_by_id(loaded['source_id'])
        self.assertEqual(source_resume['status'], 'in_progress')
        self.assertEqual(source_resume['pipeline']['urlsFound'], 10)
        
        # Step 7: Mark as completed
        discovery_resume.update_source_status(source['id'], SourceStatus.COMPLETED)
        source_final = discovery_resume.get_source_by_id(source['id'])
        self.assertEqual(source_final['status'], 'completed')


if __name__ == '__main__':
    unittest.main()
