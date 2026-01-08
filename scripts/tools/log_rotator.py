#!/usr/bin/env python3
"""
Log Rotation Utility for RalphOS

Rotates log files when they exceed configured size limit.
Reads settings from config.json.

Usage:
    python log_rotator.py              # Rotate if size exceeds limit
    python log_rotator.py --force      # Force rotation regardless of size
    python log_rotator.py --cleanup    # Remove old rotated logs beyond limit
    python log_rotator.py --status     # Show log file sizes and rotation status
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
CONFIG_FILE = PROJECT_ROOT / "scripts" / "ralph" / "config.json"

# Defaults (used if config.json doesn't exist or is missing fields)
DEFAULT_CONFIG = {
    "logging": {
        "logFile": "logs/ralph_output.log",
        "debugLogFile": "logs/ralph_debug.log",
        "maxLogSizeMb": 50,
        "keepRotatedLogs": 5,
        "rotateOnStartup": True
    }
}


def load_config() -> Dict:
    """Load configuration from config.json or use defaults."""
    config = DEFAULT_CONFIG.copy()
    
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                user_config = json.load(f)
            
            # Merge logging config
            if "logging" in user_config:
                config["logging"].update(user_config["logging"])
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not read config.json: {e}", file=sys.stderr)
    
    return config


def get_log_size_mb(log_path: Path) -> float:
    """Get log file size in megabytes."""
    if not log_path.exists():
        return 0.0
    return log_path.stat().st_size / (1024 * 1024)


def rotate_log(log_path: Path, keep_count: int = 5, force: bool = False, max_size_mb: float = 50) -> bool:
    """
    Rotate a log file.
    
    Args:
        log_path: Path to the log file
        keep_count: Number of rotated logs to keep
        force: Force rotation even if size is under limit
        max_size_mb: Maximum size before rotation (ignored if force=True)
    
    Returns:
        True if rotation was performed, False otherwise
    """
    if not log_path.exists():
        return False
    
    # Check size
    current_size_mb = get_log_size_mb(log_path)
    
    if not force and current_size_mb < max_size_mb:
        return False
    
    # Perform rotation
    log_dir = log_path.parent
    log_name = log_path.name
    
    # Delete oldest if it exists and we're at limit
    oldest = log_dir / f"{log_name}.{keep_count}"
    if oldest.exists():
        oldest.unlink()
    
    # Shift existing rotated logs: .4 -> .5, .3 -> .4, etc.
    for i in range(keep_count - 1, 0, -1):
        old_file = log_dir / f"{log_name}.{i}"
        new_file = log_dir / f"{log_name}.{i + 1}"
        if old_file.exists():
            old_file.rename(new_file)
    
    # Move current log to .1
    rotated_file = log_dir / f"{log_name}.1"
    log_path.rename(rotated_file)
    
    # Create new empty log file
    log_path.touch()
    
    return True


def cleanup_old_logs(log_path: Path, keep_count: int = 5) -> int:
    """
    Remove rotated logs beyond the keep limit.
    
    Returns:
        Number of files deleted
    """
    deleted = 0
    log_dir = log_path.parent
    log_name = log_path.name
    
    # Find all rotated logs
    i = keep_count + 1
    while True:
        old_file = log_dir / f"{log_name}.{i}"
        if old_file.exists():
            old_file.unlink()
            deleted += 1
            i += 1
        else:
            break
    
    return deleted


def get_log_status(log_path: Path, max_size_mb: float, keep_count: int) -> Dict:
    """Get status information for a log file."""
    status = {
        "path": str(log_path),
        "exists": log_path.exists(),
        "size_mb": 0.0,
        "max_size_mb": max_size_mb,
        "needs_rotation": False,
        "rotated_files": 0
    }
    
    if log_path.exists():
        status["size_mb"] = round(get_log_size_mb(log_path), 2)
        status["needs_rotation"] = status["size_mb"] >= max_size_mb
    
    # Count rotated files
    log_dir = log_path.parent
    log_name = log_path.name
    for i in range(1, keep_count + 2):
        if (log_dir / f"{log_name}.{i}").exists():
            status["rotated_files"] += 1
        else:
            break
    
    return status


def main():
    parser = argparse.ArgumentParser(description="RalphOS Log Rotator")
    parser.add_argument("--force", "-f", action="store_true",
                       help="Force rotation regardless of size")
    parser.add_argument("--cleanup", "-c", action="store_true",
                       help="Remove old rotated logs beyond limit")
    parser.add_argument("--status", "-s", action="store_true",
                       help="Show log file status")
    parser.add_argument("--quiet", "-q", action="store_true",
                       help="Suppress output (for use in scripts)")
    
    args = parser.parse_args()
    
    # Load config
    config = load_config()
    logging_config = config["logging"]
    
    max_size_mb = logging_config.get("maxLogSizeMb", 50)
    keep_count = logging_config.get("keepRotatedLogs", 5)
    
    # Build log paths
    log_files = []
    
    if logging_config.get("logFile"):
        log_files.append(PROJECT_ROOT / logging_config["logFile"])
    
    if logging_config.get("debugLogFile"):
        log_files.append(PROJECT_ROOT / logging_config["debugLogFile"])
    
    # Ensure logs directory exists
    logs_dir = PROJECT_ROOT / "logs"
    logs_dir.mkdir(exist_ok=True)
    
    if args.status:
        # Show status
        print("Log Rotation Status")
        print("=" * 60)
        for log_path in log_files:
            status = get_log_status(log_path, max_size_mb, keep_count)
            print(f"\nFile: {status['path']}")
            print(f"  Exists: {status['exists']}")
            if status['exists']:
                print(f"  Size: {status['size_mb']} MB / {status['max_size_mb']} MB")
                print(f"  Needs rotation: {'Yes' if status['needs_rotation'] else 'No'}")
                print(f"  Rotated backups: {status['rotated_files']}")
        print()
        return 0
    
    if args.cleanup:
        # Cleanup old logs
        total_deleted = 0
        for log_path in log_files:
            deleted = cleanup_old_logs(log_path, keep_count)
            total_deleted += deleted
            if deleted > 0 and not args.quiet:
                print(f"Cleaned up {deleted} old rotated logs for {log_path.name}")
        
        if not args.quiet:
            if total_deleted == 0:
                print("No old logs to clean up")
            else:
                print(f"Total cleaned: {total_deleted} files")
        return 0
    
    # Default: rotate if needed
    rotated = 0
    for log_path in log_files:
        if rotate_log(log_path, keep_count, args.force, max_size_mb):
            rotated += 1
            if not args.quiet:
                size_mb = get_log_size_mb(log_path.parent / f"{log_path.name}.1")
                print(f"Rotated: {log_path.name} ({size_mb:.1f} MB)")
    
    if not args.quiet and rotated == 0:
        # No output if nothing rotated (quiet by default when called from ralph.sh)
        pass
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

