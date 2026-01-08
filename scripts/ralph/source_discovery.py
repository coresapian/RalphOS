#!/usr/bin/env python3
"""
Source Discovery with Priority Queue System

Manages source selection with priority-based optimization.
Supports automatic source selection, priority management, and status tracking.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum


class SourceStatus(Enum):
    """Source status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"


class SourceDiscovery:
    """Manages source discovery with priority queue."""
    
    def __init__(self, sources_file: str = None):
        """Initialize source discovery manager.
        
        Args:
            sources_file: Path to sources.json file
        """
        self.sources_file = Path(sources_file or os.path.join(
            os.path.dirname(__file__), "sources.json"
        ))
        
        # Validate file exists
        if not self.sources_file.exists():
            raise FileNotFoundError(f"Sources file not found: {self.sources_file}")
        
        self.sources = self._load_sources()
    
    def _load_sources(self) -> List[Dict]:
        """Load sources from JSON file.
        
        Returns:
            List of source dictionaries
        """
        with open(self.sources_file, 'r') as f:
            data = json.load(f)
        return data.get('sources', [])
    
    def _save_sources(self):
        """Save sources to JSON file."""
        data = {
            "description": "Master source list for Ralph. Each source tracks scraping pipeline progress.",
            "validStatuses": {
                "pending": "Not started yet",
                "in_progress": "Currently being worked on",
                "blocked": "Scraping blocked (403/429/Cloudflare) - needs stealth scraper",
                "completed": "ALL URLs attempted (100%) + builds extracted + no blocks"
            },
            "pipelineFields": {
                "expectedUrls": "Total URLs on domain (null = unknown)",
                "urlsFound": "URLs discovered and saved to urls.json",
                "htmlScraped": "HTML files successfully downloaded",
                "htmlFailed": "Non-block failures (404, timeouts, parse errors)",
                "htmlBlocked": "Blocked by 403/429/Cloudflare",
                "builds": "Structured build records extracted",
                "mods": "Individual modifications extracted"
            },
            "sources": self.sources
        }
        
        with open(self.sources_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def get_next_source(self, 
                       status_filter: List[SourceStatus] = None,
                       skip_blocked: bool = True) -> Optional[Dict]:
        """Get next source based on priority and status.
        
        Args:
            status_filter: List of statuses to consider (default: pending, in_progress)
            skip_blocked: Whether to skip blocked sources
            
        Returns:
            Next source dict, or None if no sources match
        """
        if status_filter is None:
            status_filter = [SourceStatus.PENDING, SourceStatus.IN_PROGRESS]
        
        # Filter sources by status
        status_values = [s.value for s in status_filter]
        filtered = [s for s in self.sources if s.get('status') in status_values]
        
        # Skip blocked if requested
        if skip_blocked:
            filtered = [s for s in filtered if s.get('status') != SourceStatus.BLOCKED.value]
        
        if not filtered:
            return None
        
        # Sort by priority (lower = higher priority), then by name
        filtered.sort(key=lambda s: (s.get('priority', 999), s.get('name')))
        
        return filtered[0]
    
    def get_source_by_id(self, source_id: str) -> Optional[Dict]:
        """Get source by ID.
        
        Args:
            source_id: Source ID
            
        Returns:
            Source dict, or None if not found
        """
        for source in self.sources:
            if source.get('id') == source_id:
                return source
        return None
    
    def update_source_status(self, source_id: str, status: SourceStatus,
                           attempted: int = None, last_attempted: str = None):
        """Update source status.
        
        Args:
            source_id: Source ID
            status: New status
            attempted: Number of attempts (for blocked sources)
            last_attempted: ISO timestamp of last attempt
        """
        for source in self.sources:
            if source.get('id') == source_id:
                source['status'] = status.value
                if attempted is not None:
                    source['attempted'] = attempted
                if last_attempted is not None:
                    source['lastAttempted'] = last_attempted
                break
        
        self._save_sources()
    
    def set_source_priority(self, source_id: str, priority: int):
        """Set source priority.
        
        Args:
            source_id: Source ID
            priority: Priority (1-10, lower = higher priority)
        """
        for source in self.sources:
            if source.get('id') == source_id:
                source['priority'] = priority
                break
        
        self._save_sources()
    
    def update_pipeline_progress(self, source_id: str, **kwargs):
        """Update pipeline progress for a source.
        
        Args:
            source_id: Source ID
            **kwargs: Pipeline fields to update (urlsFound, htmlScraped, etc.)
        """
        for source in self.sources:
            if source.get('id') == source_id:
                if 'pipeline' not in source:
                    source['pipeline'] = {}
                source['pipeline'].update(kwargs)
                break
        
        self._save_sources()
    
    def get_sources_by_status(self, status: SourceStatus) -> List[Dict]:
        """Get all sources with a specific status.
        
        Args:
            status: Status to filter by
            
        Returns:
            List of source dicts
        """
        return [s for s in self.sources if s.get('status') == status.value]
    
    def get_pipeline_summary(self) -> Dict:
        """Get summary of pipeline progress across all sources.
        
        Returns:
            Summary dict with counts and stats
        """
        summary = {
            "total_sources": len(self.sources),
            "pending": 0,
            "in_progress": 0,
            "blocked": 0,
            "completed": 0,
            "total_urls_found": 0,
            "total_html_scraped": 0,
            "total_builds": 0,
            "total_mods": 0,
            "blocked_sources": []
        }
        
        for source in self.sources:
            status = source.get('status', 'pending')
            
            if status in summary:
                summary[status] += 1
            
            pipeline = source.get('pipeline', {})
            summary['total_urls_found'] += pipeline.get('urlsFound', 0)
            summary['total_html_scraped'] += pipeline.get('htmlScraped', 0)
            summary['total_builds'] += pipeline.get('builds', 0) or 0
            summary['total_mods'] += pipeline.get('mods', 0) or 0
            
            if status == 'blocked':
                summary['blocked_sources'].append({
                    'id': source.get('id'),
                    'name': source.get('name'),
                    'pipeline': pipeline
                })
        
        return summary
    
    def auto_prioritize(self):
        """Automatically prioritize sources based on complexity and status."""
        for source in self.sources:
            pipeline = source.get('pipeline', {})
            
            # Higher priority for sources with URLs discovered but not scraped
            if pipeline.get('urlsFound', 0) > 0 and pipeline.get('htmlScraped', 0) == 0:
                source['priority'] = 1  # Highest priority
            
            # Lower priority for sources that are blocked
            elif source.get('status') == 'blocked':
                # Don't change priority, but mark for attention
            
            # Medium priority for pending sources
            elif source.get('status') == 'pending':
                source.setdefault('priority', 5)
        
        self._save_sources()
    
    def print_status(self):
        """Print current status of all sources."""
        summary = self.get_pipeline_summary()
        
        print(f"\n{'='*60}")
        print("Source Discovery Status")
        print(f"{'='*60}")
        print(f"Total Sources: {summary['total_sources']}")
        print(f"  Pending:    {summary['pending']}")
        print(f"  In Progress: {summary['in_progress']}")
        print(f"  Blocked:     {summary['blocked']}")
        print(f"  Completed:   {summary['completed']}")
        print(f"\nPipeline Progress:")
        print(f"  URLs Found:     {summary['total_urls_found']}")
        print(f"  HTML Scraped:   {summary['total_html_scraped']}")
        print(f"  Builds:         {summary['total_builds']}")
        print(f"  Mods:           {summary['total_mods']}")
        
        if summary['blocked_sources']:
            print(f"\nBlocked Sources:")
            for bs in summary['blocked_sources']:
                print(f"  - {bs['name']} ({bs['id']})")
                print(f"    URLs: {bs['pipeline'].get('urlsFound', 0)}")
                print(f"    Scraped: {bs['pipeline'].get('htmlScraped', 0)}")
                print(f"    Blocked: {bs['pipeline'].get('htmlBlocked', 0)}")
        
        print(f"{'='*60}\n")


def main():
    """CLI interface for source discovery."""
    import argparse
    
    parser = argparse.ArgumentParser(description="RalphOS Source Discovery Manager")
    parser.add_argument("action", choices=[
        "next", "status", "update-status", "set-priority", 
        "auto-prioritize", "summary"
    ], help="Action to perform")
    parser.add_argument("--source-id", help="Source ID (for update-status, set-priority)")
    parser.add_argument("--status", help="New status (for update-status)")
    parser.add_argument("--priority", type=int, help="Priority (for set-priority)")
    parser.add_argument("--sources-file", help="Path to sources.json")
    
    args = parser.parse_args()
    
    try:
        discovery = SourceDiscovery(args.sources_file)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    
    if args.action == "next":
        source = discovery.get_next_source()
        if source:
            print(json.dumps(source, indent=2))
        else:
            print("No sources available")
    
    elif args.action == "status":
        discovery.print_status()
    
    elif args.action == "update-status":
        if not args.source_id or not args.status:
            print("Error: --source-id and --status required for update-status")
            return 1
        
        try:
            status = SourceStatus(args.status)
        except ValueError:
            print(f"Error: Invalid status '{args.status}'")
            print(f"Valid statuses: {', '.join([s.value for s in SourceStatus])}")
            return 1
        
        discovery.update_source_status(args.source_id, status)
        print(f"✓ Updated {args.source_id} to {args.status}")
    
    elif args.action == "set-priority":
        if not args.source_id or args.priority is None:
            print("Error: --source-id and --priority required for set-priority")
            return 1
        
        discovery.set_source_priority(args.source_id, args.priority)
        print(f"✓ Set {args.source_id} priority to {args.priority}")
    
    elif args.action == "auto-prioritize":
        discovery.auto_prioritize()
        print("✓ Auto-prioritized sources")
    
    elif args.action == "summary":
        summary = discovery.get_pipeline_summary()
        print(json.dumps(summary, indent=2))
    
    return 0


if __name__ == "__main__":
    exit(main())
