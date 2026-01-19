#!/usr/bin/env python3
"""
Ralph Dashboard Server
A simple HTTP server that provides real-time status data for the Ralph dashboard.

Performance optimizations:
- Caching with TTL to reduce file reads
- Cached subprocess results for pgrep/tail
- Lazy HTML file counting (cached)
- ThreadPoolExecutor for non-blocking operations
"""

import json
import os
import subprocess
import http.server
import socketserver
import threading
import time
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

# Configuration
PORT = 8765
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
SOURCES_FILE = PROJECT_ROOT / "scripts" / "ralph" / "sources.json"
LOG_FILE = PROJECT_ROOT / "logs" / "ralph_output.log"
PRD_FILE = PROJECT_ROOT / "scripts" / "ralph" / "prd.json"
DATA_DIR = PROJECT_ROOT / "data"

# Cache configuration
CACHE_TTL = 5  # seconds
HTML_COUNT_CACHE_TTL = 30  # HTML count changes slowly, cache longer


class Cache:
    """Simple TTL cache for expensive operations"""
    def __init__(self):
        self._cache = {}
        self._lock = threading.Lock()

    def get(self, key, ttl, loader):
        """Get cached value or load it if expired/missing"""
        now = time.time()
        with self._lock:
            if key in self._cache:
                value, timestamp = self._cache[key]
                if now - timestamp < ttl:
                    return value
            # Load new value
            try:
                value = loader()
                self._cache[key] = (value, now)
                return value
            except Exception:
                # Return stale value if available
                if key in self._cache:
                    return self._cache[key][0]
                return None

    def invalidate(self, key=None):
        """Invalidate cache entry or all entries"""
        with self._lock:
            if key:
                self._cache.pop(key, None)
            else:
                self._cache.clear()


# Global cache instance
cache = Cache()

# Thread pool for background tasks
executor = ThreadPoolExecutor(max_workers=2)


class DashboardHandler(http.server.BaseHTTPRequestHandler):
    # Increase timeout for slow operations
    timeout = 30

    def log_message(self, format, *args):
        # Suppress default logging to reduce I/O
        pass

    def send_json(self, data, status=200):
        response = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(response))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(response)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path

        if path == '/status':
            self.handle_status()
        elif path == '/log':
            self.handle_log()
        elif path == '/sources':
            self.handle_sources()
        elif path == '/':
            self.serve_dashboard()
        else:
            self.send_json({'error': 'Not found'}, 404)

    def serve_dashboard(self):
        """Serve the dashboard HTML file"""
        dashboard_path = SCRIPT_DIR / "dashboard.html"
        if dashboard_path.exists():
            content = dashboard_path.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_json({'error': 'Dashboard not found'}, 404)

    def handle_status(self):
        """Return comprehensive status data with caching"""
        data = {
            'timestamp': datetime.now().isoformat(),
            'running': self._check_ralph_running(),
            'sources': self._get_sources_summary(),
            'current_source': self._get_current_source(),
            'all_sources': self._get_all_sources(),
            'html_files': self._count_html_files(),
            'log_tail': self._get_log_tail(100)
        }
        self.send_json(data)

    def handle_log(self):
        """Return log tail"""
        lines = 50
        if '?lines=' in self.path:
            try:
                lines = int(self.path.split('?lines=')[-1])
                lines = min(lines, 500)  # Cap at 500 lines
            except ValueError:
                pass
        self.send_json({'log': self._get_log_tail(lines)})

    def handle_sources(self):
        """Return all sources"""
        self.send_json({'sources': self._get_all_sources()})

    def _check_ralph_running(self):
        """Check if ralph.sh is running (cached)"""
        def loader():
            try:
                result = subprocess.run(
                    ['pgrep', '-f', 'ralph.sh'],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                return result.returncode == 0
            except (subprocess.TimeoutExpired, Exception):
                return False
        return cache.get('ralph_running', CACHE_TTL, loader) or False

    def _get_sources_summary(self):
        """Get summary counts of sources by status"""
        sources = self._load_sources()
        summary = {
            'total': len(sources),
            'completed': 0,
            'in_progress': 0,
            'pending': 0,
            'blocked': 0
        }
        for source in sources:
            status = source.get('status', 'pending')
            if status in summary:
                summary[status] += 1
        return summary

    def _get_current_source(self):
        """Get the currently active source from PRD (cached)"""
        def loader():
            try:
                if not PRD_FILE.exists():
                    return None
                prd = json.loads(PRD_FILE.read_text())
                source_id = prd.get('sourceId') or prd.get('outputDir', '').split('/')[-1]

                sources = self._load_sources()
                for source in sources:
                    if source.get('id') == source_id or source.get('outputDir', '').endswith(source_id):
                        return {
                            'id': source.get('id'),
                            'name': source.get('name'),
                            'url': source.get('url'),
                            'pipeline': source.get('pipeline', {}),
                            'status': source.get('status')
                        }

                return {
                    'id': source_id,
                    'name': prd.get('projectName', 'Unknown'),
                    'url': prd.get('targetUrl', ''),
                    'pipeline': {},
                    'status': 'in_progress'
                }
            except Exception:
                return None

        return cache.get('current_source', CACHE_TTL, loader)

    def _get_all_sources(self):
        """Get all sources with their pipeline data"""
        sources = self._load_sources()
        return [{
            'id': s.get('id'),
            'name': s.get('name'),
            'url': s.get('url'),
            'status': s.get('status'),
            'pipeline': s.get('pipeline', {})
        } for s in sources]

    def _load_sources(self):
        """Load sources from sources.json (cached)"""
        def loader():
            try:
                if SOURCES_FILE.exists():
                    data = json.loads(SOURCES_FILE.read_text())
                    return data.get('sources', [])
            except Exception:
                pass
            return []
        return cache.get('sources', CACHE_TTL, loader) or []

    def _count_html_files(self):
        """Count total HTML files (cached with longer TTL)"""
        def loader():
            total = 0
            try:
                if DATA_DIR.exists():
                    # Use os.scandir for faster directory iteration
                    for entry in os.scandir(DATA_DIR):
                        if entry.is_dir():
                            html_dir = Path(entry.path) / 'html'
                            if html_dir.exists():
                                # Count files directly without glob overhead
                                try:
                                    total += sum(1 for f in os.scandir(html_dir)
                                                if f.is_file() and f.name.endswith('.html'))
                                except PermissionError:
                                    pass
            except Exception:
                pass
            return total
        return cache.get('html_count', HTML_COUNT_CACHE_TTL, loader) or 0

    def _get_log_tail(self, lines=50):
        """Get last N lines of the log file (cached)"""
        cache_key = f'log_tail_{lines}'

        def loader():
            try:
                if not LOG_FILE.exists():
                    return "No log file found"

                # Read file directly instead of subprocess for small files
                # Fall back to tail for large files
                file_size = LOG_FILE.stat().st_size
                if file_size < 100000:  # < 100KB, read directly
                    content = LOG_FILE.read_text(errors='replace')
                    log_lines = content.splitlines()[-lines:]
                    return '\n'.join(log_lines)
                else:
                    result = subprocess.run(
                        ['tail', '-n', str(lines), str(LOG_FILE)],
                        capture_output=True,
                        text=True,
                        timeout=5,
                        errors='replace'
                    )
                    return result.stdout
            except Exception as e:
                return f"Error reading log: {str(e)}"

        return cache.get(cache_key, CACHE_TTL, loader) or "No log available"


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """Threaded TCP server for handling concurrent requests"""
    allow_reuse_address = True
    daemon_threads = True


def main():
    """Start the dashboard server"""
    print(f"""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║   Ralph Dashboard Server (Optimized)                      ║
║                                                           ║
║   Dashboard: http://localhost:{PORT}/                       ║
║   API:       http://localhost:{PORT}/status                 ║
║                                                           ║
║   Cache TTL: {CACHE_TTL}s (sources/status), {HTML_COUNT_CACHE_TTL}s (html count)       ║
║   Press Ctrl+C to stop                                    ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
""")

    # Open browser automatically
    try:
        import webbrowser
        webbrowser.open(f'http://localhost:{PORT}/')
    except Exception:
        pass

    with ThreadedTCPServer(("", PORT), DashboardHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n✓ Dashboard server stopped")
        finally:
            executor.shutdown(wait=False)


if __name__ == "__main__":
    main()
