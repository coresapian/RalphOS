#!/usr/bin/env python3
"""
Checkpoint Manager for RalphOS

Saves and restores Ralph's execution state to enable auto-resume functionality.
Prevents re-running completed iterations on restart.
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path


class CheckpointManager:
 """Manages checkpoint state for RalphOS sessions."""
 
 def __init__(self, checkpoint_dir: str = None):
 """Initialize checkpoint manager.
 
 Args:
 checkpoint_dir: Directory to store checkpoint files
 """
 self.checkpoint_dir = Path(checkpoint_dir or os.path.join(
 os.path.dirname(__file__), "checkpoints"
 ))
 self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
 
 self.current_checkpoint_file = self.checkpoint_dir / "current_checkpoint.json"
 self.history_dir = self.checkpoint_dir / "history"
 self.history_dir.mkdir(exist_ok=True)
 
 def save_checkpoint(self, iteration: int, prd_file: str, 
 sources_file: str, source_id: str = None,
 additional_state: dict = None):
 """Save current execution state.
 
 Args:
 iteration: Current iteration number
 prd_file: Path to current PRD file
 sources_file: Path to sources.json
 source_id: Current source being processed
 additional_state: Additional state to save
 """
 state = {
 "timestamp": datetime.now().isoformat(),
 "iteration": iteration,
 "prd_file": prd_file,
 "sources_file": sources_file,
 "source_id": source_id,
 "additional_state": additional_state or {}
 }
 
 # Save current checkpoint
 with open(self.current_checkpoint_file, 'w') as f:
 json.dump(state, f, indent=2)
 
 # Archive to history
 history_file = self.history_dir / f"checkpoint_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
 with open(history_file, 'w') as f:
 json.dump(state, f, indent=2)
 
 # Keep only last 10 checkpoints in history
 self._cleanup_history(keep=10)
 
 def load_checkpoint(self) -> dict:
 """Load last checkpoint if exists.
 
 Returns:
 Checkpoint state dict, or None if no checkpoint exists
 """
 if not self.current_checkpoint_file.exists():
 return None
 
 with open(self.current_checkpoint_file, 'r') as f:
 return json.load(f)
 
 def has_checkpoint(self) -> bool:
 """Check if a checkpoint exists."""
 return self.current_checkpoint_file.exists()
 
 def clear_checkpoint(self):
 """Clear current checkpoint."""
 if self.current_checkpoint_file.exists():
 self.current_checkpoint_file.unlink()
 
 def get_iteration_info(self) -> dict:
 """Get iteration information from checkpoint.
 
 Returns:
 Dict with iteration info, or empty dict if no checkpoint
 """
 checkpoint = self.load_checkpoint()
 if not checkpoint:
 return {}
 
 return {
 "iteration": checkpoint.get("iteration", 0),
 "source_id": checkpoint.get("source_id"),
 "timestamp": checkpoint.get("timestamp"),
 "prd_file": checkpoint.get("prd_file"),
 "sources_file": checkpoint.get("sources_file")
 }
 
 def _cleanup_history(self, keep: int = 10):
 """Clean up old checkpoint files, keeping only the most recent.
 
 Args:
 keep: Number of checkpoints to keep
 """
 checkpoints = sorted(
 self.history_dir.glob("checkpoint_*.json"),
 key=lambda p: p.stat().st_mtime,
 reverse=True
 )
 
 for old_checkpoint in checkpoints[keep:]:
 old_checkpoint.unlink()
 
 def print_checkpoint_status(self):
 """Print checkpoint status in a formatted way."""
 checkpoint = self.load_checkpoint()
 
 if checkpoint:
 print(f" Checkpoint found:")
 print(f" Iteration: {checkpoint.get('iteration')}")
 print(f" Source: {checkpoint.get('source_id') or 'N/A'}")
 print(f" Timestamp: {checkpoint.get('timestamp')}")
 else:
 print(" No checkpoint found - starting fresh")


def main():
 """CLI interface for checkpoint management."""
 import argparse
 
 parser = argparse.ArgumentParser(description="RalphOS Checkpoint Manager")
 parser.add_argument("action", choices=["save", "load", "clear", "status"],
 help="Action to perform")
 parser.add_argument("--iteration", type=int, help="Iteration number (for save)")
 parser.add_argument("--source-id", help="Source ID (for save)")
 parser.add_argument("--prd-file", help="PRD file path (for save)")
 parser.add_argument("--sources-file", help="Sources file path (for save)")
 
 args = parser.parse_args()
 
 manager = CheckpointManager()
 
 if args.action == "save":
 if not args.iteration:
 print("Error: --iteration required for save action")
 return 1
 
 manager.save_checkpoint(
 iteration=args.iteration,
 prd_file=args.prd_file,
 sources_file=args.sources_file,
 source_id=args.source_id
 )
 print(" Checkpoint saved")
 
 elif args.action == "load":
 checkpoint = manager.load_checkpoint()
 if checkpoint:
 print(json.dumps(checkpoint, indent=2))
 else:
 print("No checkpoint found")
 
 elif args.action == "clear":
 manager.clear_checkpoint()
 print(" Checkpoint cleared")
 
 elif args.action == "status":
 manager.print_checkpoint_status()
 
 return 0


if __name__ == "__main__":
 exit(main())
