#!/usr/bin/env python3
"""
Ralph's ZAI MCP (Model Context Protocol) Client
===============================================
Provides unified access to ZAI MCP servers for vision analysis,
web search, web reading, and GitHub repository exploration.

MCP Servers Available:
- Vision MCP: Image analysis, OCR, UI generation, error diagnosis
- Web Search MCP: Web search capabilities
- Web Reader MCP: Web page content extraction
- Zread MCP: GitHub repository exploration

Usage:
 from ralph_mcp import get_mcp_client

 mcp = get_mcp_client()

 # Vision analysis
 result = mcp.ui_to_artifact("screenshot.png", "code")

 # Web search
 results = mcp.search_web("DuckDB Python tutorial")

 # GitHub exploration
 structure = mcp.get_repo_structure("https://github.com/duckdb/duckdb")
"""

import json
import os
import subprocess
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

# Try to import ralph_utils logger
try:
 from ralph_utils import logger as ralph_logger
except ImportError:
 ralph_logger = logging.getLogger(__name__)
 logging.basicConfig(level=logging.INFO)


class ZAIMCPClient:
 """
 Unified client for interacting with ZAI MCP servers.

 This client provides access to:
 - Vision MCP: ui_to_artifact, extract_text_from_screenshot, diagnose_error_screenshot,
 understand_technical_diagram, analyze_data_visualization, ui_diff_check
 - Web Search MCP: search_web
 - Web Reader MCP: read_webpage
 - Zread MCP: search_repo_docs, get_repo_structure, read_repo_file
 """

 def __init__(self,
 api_key: str = None,
 mode: str = "ZAI",
 cache_enabled: bool = True,
 cache_dir: str = ".mcp_cache"):
 """
 Initialize ZAI MCP client.

 Args:
 api_key: ZAI API key (reads from Z_AI_API_KEY env var if None)
 mode: Platform mode - 'ZAI' or 'ZHIPU'
 cache_enabled: Whether to cache results
 cache_dir: Directory for cache files
 """
 self.api_key = api_key or os.environ.get("Z_AI_API_KEY", "")
 self.mode = mode
 self.cache_enabled = cache_enabled
 self.cache_dir = Path(cache_dir)

 if cache_enabled:
 self.cache_dir.mkdir(parents=True, exist_ok=True)

 self._log("INFO", "ZAI MCP Client initialized", {"mode": mode, "cache": cache_enabled})

 def _log(self, level: str, message: str, data: Dict = None):
 """Log with ralph_utils or standard logging."""
 if hasattr(ralph_logger, 'log'):
 ralph_logger.log(level, f"[MCP] {message}", data)
 else:
 getattr(ralph_logger, level.lower(), ralph_logger.info)(f"[MCP] {message} {data or ''}")

 def _get_cache_key(self, operation: str, *args) -> str:
 """Generate cache key from operation and arguments."""
 import hashlib
 key_data = json.dumps([operation, args], sort_keys=True)
 return hashlib.md5(key_data.encode()).hexdigest()

 def _get_cached(self, cache_key: str) -> Optional[Dict]:
 """Get cached result if available."""
 if not self.cache_enabled:
 return None

 cache_file = self.cache_dir / f"{cache_key}.json"
 if cache_file.exists():
 try:
 with open(cache_file) as f:
 data = json.load(f)
 # Check cache age (15 minutes default)
 cached_at = datetime.fromisoformat(data.get('cached_at', '2000-01-01'))
 age = (datetime.utcnow() - cached_at).total_seconds()
 if age < 900: # 15 minutes
 self._log("DEBUG", f"Cache hit: {cache_key[:8]}")
 return data.get('result')
 except:
 pass
 return None

 def _set_cached(self, cache_key: str, result: Any):
 """Cache a result."""
 if not self.cache_enabled:
 return

 cache_file = self.cache_dir / f"{cache_key}.json"
 try:
 with open(cache_file, 'w') as f:
 json.dump({
 'cached_at': datetime.utcnow().isoformat(),
 'result': result
 }, f)
 except:
 pass

 # ==========================================
 # VISION MCP TOOLS
 # ==========================================

 def ui_to_artifact(self, image_path: str, output_type: str = "code",
 prompt: str = None) -> Dict[str, Any]:
 """
 Convert UI screenshot to code, prompt, spec, or description.

 Args:
 image_path: Path to UI screenshot
 output_type: 'code', 'prompt', 'spec', or 'description'
 prompt: Additional instructions

 Returns:
 Dict with status and result

 Example:
 result = mcp.ui_to_artifact("design.png", "code")
 """
 if not Path(image_path).exists():
 return {"status": "error", "message": f"Image not found: {image_path}"}

 default_prompts = {
 "code": "Generate React/HTML/CSS code to recreate this UI exactly",
 "prompt": "Create a detailed AI prompt to regenerate this UI",
 "spec": "Extract a detailed design specification from this UI",
 "description": "Provide a comprehensive description of this UI"
 }

 actual_prompt = prompt or default_prompts.get(output_type, default_prompts["description"])

 self._log("INFO", f"ui_to_artifact", {"image": image_path, "type": output_type})

 # This would normally call the MCP server
 # For now, we'll use a placeholder that can be extended
 return self._call_vision_mcp("ui_to_artifact", {
 "image_source": image_path,
 "output_type": output_type,
 "prompt": actual_prompt
 })

 def extract_text_from_screenshot(self, image_path: str,
 language_hint: str = None) -> Dict[str, Any]:
 """
 Extract text from screenshot using OCR.

 Args:
 image_path: Path to screenshot
 language_hint: Programming language hint (e.g., 'python', 'javascript')

 Returns:
 Dict with status and extracted text
 """
 if not Path(image_path).exists():
 return {"status": "error", "message": f"Image not found: {image_path}"}

 prompt = "Extract all visible text from this image, preserving formatting."
 if language_hint:
 prompt += f" The content appears to be {language_hint} code."

 return self._call_vision_mcp("extract_text_from_screenshot", {
 "image_source": image_path,
 "prompt": prompt,
 "programming_language": language_hint or ""})

 def diagnose_error_screenshot(self, image_path: str,
 context: str = None) -> Dict[str, Any]:
 """
 Diagnose error message from screenshot.

 Args:
 image_path: Path to error screenshot
 context: Additional context about when error occurred

 Returns:
 Dict with diagnosis and suggested solutions
 """
 if not Path(image_path).exists():
 return {"status": "error", "message": f"Image not found: {image_path}"}

 prompt = "Analyze this error message and provide: 1) Root cause 2) Suggested solutions 3) Prevention tips"
 if context:
 prompt += f" Context: {context}"

 return self._call_vision_mcp("diagnose_error_screenshot", {
 "image_source": image_path,
 "prompt": prompt,
 "context": context or ""})

 def understand_technical_diagram(self, image_path: str,
 diagram_type: str = None) -> Dict[str, Any]:
 """
 Analyze technical diagram (architecture, flowchart, UML, etc.)

 Args:
 image_path: Path to diagram
 diagram_type: Type hint ('architecture', 'flowchart', 'uml', 'er-diagram')

 Returns:
 Dict with diagram analysis
 """
 if not Path(image_path).exists():
 return {"status": "error", "message": f"Image not found: {image_path}"}

 prompt = "Analyze this technical diagram. Explain its components, relationships, and purpose."

 return self._call_vision_mcp("understand_technical_diagram", {
 "image_source": image_path,
 "prompt": prompt,
 "diagram_type": diagram_type or ""})

 def analyze_data_visualization(self, image_path: str,
 analysis_focus: str = None) -> Dict[str, Any]:
 """
 Analyze chart, graph, or data visualization.

 Args:
 image_path: Path to visualization
 analysis_focus: Focus area ('trends', 'anomalies', 'comparisons')

 Returns:
 Dict with insights from the visualization
 """
 if not Path(image_path).exists():
 return {"status": "error", "message": f"Image not found: {image_path}"}

 prompt = "Analyze this data visualization and extract key insights."
 if analysis_focus:
 prompt += f" Focus on: {analysis_focus}"

 return self._call_vision_mcp("analyze_data_visualization", {
 "image_source": image_path,
 "prompt": prompt,
 "analysis_focus": analysis_focus or ""})

 def ui_diff_check(self, expected_image: str, actual_image: str,
 prompt: str = None) -> Dict[str, Any]:
 """
 Compare two UI screenshots for visual differences.

 Args:
 expected_image: Path to expected/reference UI
 actual_image: Path to actual implementation
 prompt: Specific comparison instructions

 Returns:
 Dict with differences found
 """
 if not Path(expected_image).exists():
 return {"status": "error", "message": f"Expected image not found: {expected_image}"}
 if not Path(actual_image).exists():
 return {"status": "error", "message": f"Actual image not found: {actual_image}"}

 actual_prompt = prompt or "Compare these two UI images and identify all visual differences."

 return self._call_vision_mcp("ui_diff_check", {
 "expected_image_source": expected_image,
 "actual_image_source": actual_image,
 "prompt": actual_prompt
 })

 def analyze_video(self, video_path: str, prompt: str) -> Dict[str, Any]:
 """
 Analyze video content.

 Args:
 video_path: Path to video file
 prompt: What to analyze

 Returns:
 Dict with video analysis
 """
 if not Path(video_path).exists():
 return {"status": "error", "message": f"Video not found: {video_path}"}

 return self._call_vision_mcp("analyze_video", {
 "video_source": video_path,
 "prompt": prompt
 })

 def _call_vision_mcp(self, tool: str, params: Dict) -> Dict[str, Any]:
 """
 Internal method to call Vision MCP server.
 This is a placeholder that can be extended to actual MCP protocol.
 """
 # Cache check
 cache_key = self._get_cache_key(f"vision:{tool}", params)
 cached = self._get_cached(cache_key)
 if cached:
 return cached

 # For now, return a structured placeholder
 # In production, this would call the actual MCP server
 result = {
 "status": "success",
 "tool": tool,
 "params": params,
 "message": f"Vision MCP tool '{tool}' called. Extend _call_vision_mcp for actual implementation."
 }

 self._set_cached(cache_key, result)
 return result

 # ==========================================
 # WEB SEARCH MCP
 # ==========================================

 def search_web(self, query: str, num_results: int = 10) -> Dict[str, Any]:
 """
 Search the web.

 Args:
 query: Search query
 num_results: Number of results to return

 Returns:
 Dict with search results
 """
 cache_key = self._get_cache_key("search_web", query, num_results)
 cached = self._get_cached(cache_key)
 if cached:
 return cached

 self._log("INFO", f"Web search", {"query": query[:50]})

 # Placeholder - extend with actual implementation
 result = {
 "status": "success",
 "query": query,
 "results": [],
 "message": "Web search placeholder. Extend search_web for actual implementation."
 }

 self._set_cached(cache_key, result)
 return result

 # ==========================================
 # WEB READER MCP
 # ==========================================

 def read_webpage(self, url: str, extract_type: str = "text") -> Dict[str, Any]:
 """
 Read and extract content from a webpage.

 Args:
 url: URL to read
 extract_type: 'text', 'html', or 'markdown'

 Returns:
 Dict with page content
 """
 cache_key = self._get_cache_key("read_webpage", url, extract_type)
 cached = self._get_cached(cache_key)
 if cached:
 return cached

 self._log("INFO", f"Reading webpage", {"url": url[:50]})

 # Placeholder - extend with actual implementation
 result = {
 "status": "success",
 "url": url,
 "content": "",
 "message": "Web reader placeholder. Extend read_webpage for actual implementation."
 }

 self._set_cached(cache_key, result)
 return result

 # ==========================================
 # ZREAD MCP (GITHUB)
 # ==========================================

 def search_repo_docs(self, repo_url: str, query: str) -> Dict[str, Any]:
 """
 Search documentation in a GitHub repository.

 Args:
 repo_url: GitHub repository URL
 query: Search query

 Returns:
 Dict with search results
 """
 cache_key = self._get_cache_key("search_repo_docs", repo_url, query)
 cached = self._get_cached(cache_key)
 if cached:
 return cached

 self._log("INFO", f"Searching repo docs", {"repo": repo_url, "query": query[:30]})

 # Placeholder - extend with actual implementation
 result = {
 "status": "success",
 "repo": repo_url,
 "query": query,
 "results": [],
 "message": "Zread search placeholder. Extend search_repo_docs for actual implementation."
 }

 self._set_cached(cache_key, result)
 return result

 def get_repo_structure(self, repo_url: str, path: str = "/") -> Dict[str, Any]:
 """
 Get directory structure of a GitHub repository.

 Args:
 repo_url: GitHub repository URL
 path: Directory path within repo (default: root)

 Returns:
 Dict with directory structure
 """
 cache_key = self._get_cache_key("get_repo_structure", repo_url, path)
 cached = self._get_cached(cache_key)
 if cached:
 return cached

 self._log("INFO", f"Getting repo structure", {"repo": repo_url, "path": path})

 # Placeholder - extend with actual implementation
 result = {
 "status": "success",
 "repo": repo_url,
 "path": path,
 "structure": [],
 "message": "Zread structure placeholder. Extend get_repo_structure for actual implementation."
 }

 self._set_cached(cache_key, result)
 return result

 def read_repo_file(self, repo_url: str, file_path: str) -> Dict[str, Any]:
 """
 Read a specific file from a GitHub repository.

 Args:
 repo_url: GitHub repository URL
 file_path: Path to file within repo

 Returns:
 Dict with file content
 """
 cache_key = self._get_cache_key("read_repo_file", repo_url, file_path)
 cached = self._get_cached(cache_key)
 if cached:
 return cached

 self._log("INFO", f"Reading repo file", {"repo": repo_url, "file": file_path})

 # Placeholder - extend with actual implementation
 result = {
 "status": "success",
 "repo": repo_url,
 "file_path": file_path,
 "content": "",
 "message": "Zread file placeholder. Extend read_repo_file for actual implementation."
 }

 self._set_cached(cache_key, result)
 return result

 # ==========================================
 # GENERAL MCP TOOLS
 # ==========================================

 def chat(self, prompt: str, model: str = "glm-4.7") -> Dict[str, Any]:
 """
 General chat with AI model.

 Args:
 prompt: Chat prompt
 model: Model to use

 Returns:
 Dict with response
 """
 self._log("INFO", f"Chat", {"prompt": prompt[:30], "model": model})

 return {
 "status": "success",
 "prompt": prompt,
 "model": model,
 "response": "",
 "message": "Chat placeholder. Extend chat for actual implementation."
 }

 def generate_code(self, prompt: str, model: str = "glm-4.7") -> Dict[str, Any]:
 """
 Generate code using AI model.

 Args:
 prompt: Code generation prompt
 model: Model to use

 Returns:
 Dict with generated code
 """
 self._log("INFO", f"Generate code", {"prompt": prompt[:30]})

 return {
 "status": "success",
 "prompt": prompt,
 "model": model,
 "code": "",
 "message": "Code generation placeholder. Extend generate_code for actual implementation."
 }

 # ==========================================
 # UTILITY METHODS
 # ==========================================

 def clear_cache(self):
 """Clear the MCP result cache."""
 import shutil
 if self.cache_dir.exists():
 shutil.rmtree(self.cache_dir)
 self.cache_dir.mkdir(parents=True, exist_ok=True)
 self._log("INFO", "MCP cache cleared")

 def get_cache_stats(self) -> Dict[str, Any]:
 """Get cache statistics."""
 if not self.cache_enabled or not self.cache_dir.exists():
 return {"enabled": False}

 cache_files = list(self.cache_dir.glob("*.json"))
 total_size = sum(f.stat().st_size for f in cache_files)

 return {
 "enabled": True,
 "entries": len(cache_files),
 "size_bytes": total_size,
 "size_mb": round(total_size / 1024 / 1024, 2)
 }

 def is_available(self) -> bool:
 """Check if MCP client is ready."""
 return True # Placeholder - add actual health check


# ==========================================
# CONVENIENCE FUNCTIONS
# ==========================================

_client_instance = None


def get_mcp_client(api_key: str = None) -> ZAIMCPClient:
 """
 Get a singleton ZAI MCP client instance.

 Args:
 api_key: Optional API key (uses env var if None)

 Returns:
 ZAIMCPClient instance
 """
 global _client_instance
 if _client_instance is None:
 _client_instance = ZAIMCPClient(api_key=api_key)
 return _client_instance


def quick_search(query: str) -> Dict[str, Any]:
 """Quick web search."""
 return get_mcp_client().search_web(query)


def quick_read(url: str) -> Dict[str, Any]:
 """Quick webpage read."""
 return get_mcp_client().read_webpage(url)


# ==========================================
# CLI
# ==========================================

if __name__ == "__main__":
 import sys

 print("ZAI MCP Client Test")
 print("-" * 50)

 mcp = get_mcp_client()

 # Test web search
 print("\nTesting search_web...")
 result = mcp.search_web("DuckDB tutorial")
 print(f"Result: {result}")

 # Test repo structure
 print("\nTesting get_repo_structure...")
 result = mcp.get_repo_structure("https://github.com/duckdb/duckdb")
 print(f"Result: {result}")

 # Cache stats
 print("\nCache stats:")
 print(mcp.get_cache_stats())

 print("\n MCP client test complete")
