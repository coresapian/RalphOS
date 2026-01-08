#!/usr/bin/env python3
"""
Unit tests for CheckpointManager
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from datetime import datetime

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts', 'ralph'))

from checkpoint_manager import CheckpointManager


class TestCheckpointManager(unittest.TestCase):
    """Test cases for CheckpointManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = CheckpointManager(self.temp_dir)
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_initialization(self):
        """Test checkpoint manager initialization."""
        self.assertTrue(self.manager.checkpoint_dir.exists())
        self.assertTrue(self.manager.history_dir.exists())
    
    def test_save_checkpoint(self):
        """Test saving a checkpoint."""
        self.manager.save_checkpoint(
            iteration=5,
            prd_file="/path/to/prd.json",
            sources_file="/path/to/sources.json",
            source_id="test_source",
            additional_state={"test": "data"}
        )
        
        # Check that checkpoint file was created
        self.assertTrue(self.manager.current_checkpoint_file.exists())
        
        # Verify checkpoint content
        with open(self.manager.current_checkpoint_file, 'r') as f:
            checkpoint = json.load(f)
        
        self.assertEqual(checkpoint['iteration'], 5)
        self.assertEqual(checkpoint['source_id'], 'test_source')
        self.assertEqual(checkpoint['prd_file'], '/path/to/prd.json')
        self.assertEqual(checkpoint['sources_file'], '/path/to/sources.json')
        self.assertEqual(checkpoint['additional_state'], {"test": "data"})
    
    def test_load_checkpoint(self):
        """Test loading a checkpoint."""
        # Save a checkpoint
        self.manager.save_checkpoint(
            iteration=10,
            prd_file="/path/to/prd.json",
            sources_file="/path/to/sources.json",
            source_id="test_source"
        )
        
        # Load the checkpoint
        loaded = self.manager.load_checkpoint()
        
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded['iteration'], 10)
        self.assertEqual(loaded['source_id'], 'test_source')
    
    def test_has_checkpoint(self):
        """Test checking if checkpoint exists."""
        # Initially no checkpoint
        self.assertFalse(self.manager.has_checkpoint())
        
        # Save a checkpoint
        self.manager.save_checkpoint(
            iteration=1,
            prd_file="/path/to/prd.json",
            sources_file="/path/to/sources.json"
        )
        
        # Now checkpoint should exist
        self.assertTrue(self.manager.has_checkpoint())
    
    def test_clear_checkpoint(self):
        """Test clearing checkpoint."""
        # Save a checkpoint
        self.manager.save_checkpoint(
            iteration=1,
            prd_file="/path/to/prd.json",
            sources_file="/path/to/sources.json"
        )
        self.assertTrue(self.manager.has_checkpoint())
        
        # Clear checkpoint
        self.manager.clear_checkpoint()
        
        # Checkpoint should be gone
        self.assertFalse(self.manager.has_checkpoint())
    
    def test_get_iteration_info(self):
        """Test getting iteration info from checkpoint."""
        self.manager.save_checkpoint(
            iteration=7,
            prd_file="/path/to/prd.json",
            sources_file="/path/to/sources.json",
            source_id="test_source"
        )
        
        info = self.manager.get_iteration_info()
        
        self.assertEqual(info['iteration'], 7)
        self.assertEqual(info['source_id'], 'test_source')
        self.assertIn('timestamp', info)
        self.assertEqual(info['prd_file'], '/path/to/prd.json')
    
    def test_history_cleanup(self):
        """Test that old checkpoints are cleaned up."""
        # Save 15 checkpoints
        for i in range(15):
            self.manager.save_checkpoint(
                iteration=i,
                prd_file="/path/to/prd.json",
                sources_file="/path/to/sources.json"
            )
        
        # Check that only 10 checkpoints remain in history
        history_files = list(self.manager.history_dir.glob("checkpoint_*.json"))
        self.assertEqual(len(history_files), 10)
    
    def test_iteration_info_empty(self):
        """Test iteration info returns empty dict when no checkpoint."""
        info = self.manager.get_iteration_info()
        self.assertEqual(info, {})


if __name__ == '__main__':
    unittest.main()
