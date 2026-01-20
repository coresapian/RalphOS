#!/usr/bin/env python3
"""
Checkpoint Manager for RalphOS

Saves and restores iteration state for auto-resume capability.
"""
import json
import os
from pathlib import Path
from datetime import datetime

# Configuration
RALPH_DIR = Path(__file__).parent
CHECKPOINT_FILE = RALPH_DIR / "checkpoint.json"
LOG_FILE = RALPH_DIR / "checkpoint.log"


class CheckpointManager:
 """Manage RalphOS iteration checkpoints."""
 
 def __init__(self):
 self.checkpoint_file = CHECKPOINT_FILE
 self.log_file = LOG_FILE
 self.state = self._load_state()
 
 def _load_state(self) -> dict:
 """Load checkpoint state from file."""
 if self.checkpoint_file.exists():
 try:
 with open(self.checkpoint_file) as f:
 return json.load(f)
 except Exception as e:
 self._log(f"Error loading checkpoint: {e}")
 return {
 "iteration": 0,
 "current_source": None,
 "current_stage": None,
 "start_time": None,
 "last_update": None,
 "status": "idle"
 }
 
 def save(self):
 """Save current checkpoint state."""
 self.state["last_update"] = datetime.now().isoformat()
 
 # Ensure directory exists
 self.checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
 
 # Atomic write (write to temp, then rename)
 temp_file = self.checkpoint_file.with_suffix('.tmp')
 with open(temp_file, 'w') as f:
 json.dump(self.state, f, indent=2)
 temp_file.replace(self.checkpoint_file)
 
 self._log(f"Checkpoint saved: iteration={self.state['iteration']}, status={self.state['status']}")
 
 def update_iteration(self, iteration: int):
 """Update iteration number."""
 self.state["iteration"] = iteration
 self.save()
 
 def update_source(self, source_id: str, stage: str):
 """Update current source and stage."""
 self.state["current_source"] = source_id
 self.state["current_stage"] = stage
 self.save()
 
 def update_status(self, status: str):
 """Update RalphOS status."""
 self.state["status"] = status
 if status == "running" and self.state["start_time"] is None:
 self.state["start_time"] = datetime.now().isoformat()
 self.save()
 
 def reset(self):
 """Reset checkpoint state."""
 self.state = {
 "iteration": 0,
 "current_source": None,
 "current_stage": None,
 "start_time": None,
 "last_update": None,
 "status": "idle"
 }
 self.save()
 self._log("Checkpoint reset")
 
 def _log(self, message: str):
 """Log checkpoint activity."""
 timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
 log_line = f"[{timestamp}] {message}\n"
 with open(self.log_file, 'a') as f:
 f.write(log_line)
 
 def get_resume_info(self) -> dict:
 """Get resume information."""
 if self.state["status"] == "running" or self.state["status"] == "paused":
 elapsed = datetime.now() - datetime.fromisoformat(self.state["start_time"])
 return {
 "can_resume": True,
 "iteration": self.state["iteration"],
 "current_source": self.state["current_source"],
 "current_stage": self.state["current_stage"],
 "elapsed_time": str(elapsed).split(".")[0],
 "last_update": self.state["last_update"]
 }
 return {
 "can_resume": False,
 "reason": f"Status is '{self.state['status']}', not running/paused"
 }
 
 def print_status(self):
 """Print checkpoint status."""
 print("\n" + "=" * 60)
 print("RalphOS Checkpoint Status")
 print("=" * 60)
 
 for key, value in self.state.items():
 print(f" {key}: {value}")
 
 print("\nResume Info:")
 resume_info = self.get_resume_info()
 for key, value in resume_info.items():
 print(f" {key}: {value}")
 
 print("=" * 60 + "\n")


def main():
 """CLI interface for checkpoint management."""
 import argparse
 
 parser = argparse.ArgumentParser(description="RalphOS Checkpoint Manager")
 parser.add_argument("command", choices=["save", "load", "reset", "status"],
 help="Checkpoint command")
 parser.add_argument("--iteration", type=int, help="Iteration number")
 parser.add_argument("--source", type=str, help="Current source ID")
 parser.add_argument("--stage", type=str, help="Current stage")
 parser.add_argument("--status", type=str, help="RalphOS status")
 
 args = parser.parse_args()
 
 cm = CheckpointManager()
 
 if args.command == "save":
 if args.iteration:
 cm.update_iteration(args.iteration)
 if args.source and args.stage:
 cm.update_source(args.source, args.stage)
 if args.status:
 cm.update_status(args.status)
 print(" Checkpoint saved")
 
 elif args.command == "load":
 info = cm.get_resume_info()
 if info["can_resume"]:
 print(f" Can resume from iteration {info['iteration']}")
 print(f" Last: {info['current_source']} - {info['current_stage']}")
 else:
 print(f" {info['reason']}")
 
 elif args.command == "reset":
 cm.reset()
 print(" Checkpoint reset")
 
 elif args.command == "status":
 cm.print_status()


if __name__ == "__main__":
 main()
