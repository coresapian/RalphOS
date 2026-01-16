"""
RalphOS Agent SDK Subagents

This module provides Claude Agent SDK subagents for the RalphOS pipeline:
- URLDetective: Discovers build/vehicle URLs from websites
- (Future) DataExtractor: Extracts structured data from HTML
- (Future) ModCategorizer: Categorizes vehicle modifications
"""

from .url_detective import URLDetectiveAgent, run_url_detective

__all__ = ["URLDetectiveAgent", "run_url_detective"]
