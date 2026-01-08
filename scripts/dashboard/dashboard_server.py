#!/usr/bin/env python3
"""
Ralph Dashboard Server
A simple HTTP server that provides real-time status data for the Ralph dashboard.
"""

import json
import os
import subprocess
import http.server
import socketserver
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

# Configuration
PORT = 8765
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
SOURCES_FILE = PROJECT_ROOT / "scripts" / "ralph" / "sources.json"
LOG_FILE = PROJECT_ROOT / "logs" / "ralph_output.log"
PRD_FILE = PROJECT_ROOT / "scripts" / "ralph" / "prd.json"
DATA_DIR = PROJECT_ROOT / "data"

class DashboardHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress default logging
        pass
    
    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
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
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(dashboard_path.read_bytes())
        else:
            self.send_json({'error': 'Dashboard not found'}, 404)
    
    def handle_status(self):
        """Return comprehensive status data"""
        data = {
            'timestamp': datetime.now().isoformat(),
            'running': self.check_ralph_running(),
            'sources': self.get_sources_summary(),
            'current_source': self.get_current_source(),
            'all_sources': self.get_all_sources(),
            'html_files': self.count_html_files(),
            'log_tail': self.get_log_tail(100)
        }
        self.send_json(data)
    
    def handle_log(self):
        """Return log tail"""
        lines = int(self.path.split('?lines=')[-1]) if '?lines=' in self.path else 50
        self.send_json({'log': self.get_log_tail(lines)})
    
    def handle_sources(self):
        """Return all sources"""
        self.send_json({'sources': self.get_all_sources()})
    
    def check_ralph_running(self):
        """Check if ralph.sh is currently running"""
        try:
            result = subprocess.run(
                ['pgrep', '-f', 'ralph.sh'],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except:
            return False
    
    def get_sources_summary(self):
        """Get summary counts of sources by status"""
        sources = self.load_sources()
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
    
    def get_current_source(self):
        """Get the currently active source from PRD"""
        try:
            if PRD_FILE.exists():
                prd = json.loads(PRD_FILE.read_text())
                source_id = prd.get('sourceId') or prd.get('outputDir', '').split('/')[-1]
                
                # Find matching source
                sources = self.load_sources()
                for source in sources:
                    if source.get('id') == source_id or source.get('outputDir', '').endswith(source_id):
                        return {
                            'id': source.get('id'),
                            'name': source.get('name'),
                            'url': source.get('url'),
                            'pipeline': source.get('pipeline', {}),
                            'status': source.get('status')
                        }
                
                # Return PRD info if source not found
                return {
                    'id': source_id,
                    'name': prd.get('projectName', 'Unknown'),
                    'url': prd.get('targetUrl', ''),
                    'pipeline': {},
                    'status': 'in_progress'
                }
        except Exception as e:
            pass
        return None
    
    def get_all_sources(self):
        """Get all sources with their pipeline data"""
        sources = self.load_sources()
        return [{
            'id': s.get('id'),
            'name': s.get('name'),
            'url': s.get('url'),
            'status': s.get('status'),
            'pipeline': s.get('pipeline', {})
        } for s in sources]
    
    def load_sources(self):
        """Load sources from sources.json"""
        try:
            if SOURCES_FILE.exists():
                data = json.loads(SOURCES_FILE.read_text())
                return data.get('sources', [])
        except:
            pass
        return []
    
    def count_html_files(self):
        """Count total HTML files across all data sources"""
        total = 0
        try:
            if DATA_DIR.exists():
                for source_dir in DATA_DIR.iterdir():
                    html_dir = source_dir / 'html'
                    if html_dir.exists():
                        total += len(list(html_dir.glob('*.html')))
        except:
            pass
        return total
    
    def get_log_tail(self, lines=50):
        """Get last N lines of the log file"""
        try:
            if LOG_FILE.exists():
                result = subprocess.run(
                    ['tail', '-n', str(lines), str(LOG_FILE)],
                    capture_output=True,
                    text=True
                )
                return result.stdout
        except:
            pass
        return "No log available"


def main():
    """Start the dashboard server"""
    print(f"""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║   🤖 Ralph Dashboard Server                               ║
║                                                           ║
║   Dashboard: http://localhost:{PORT}/                       ║
║   API:       http://localhost:{PORT}/status                 ║
║                                                           ║
║   Press Ctrl+C to stop                                    ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
""")
    
    # Open browser automatically
    import webbrowser
    webbrowser.open(f'http://localhost:{PORT}/')
    
    with socketserver.TCPServer(("", PORT), DashboardHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n✓ Dashboard server stopped")


if __name__ == "__main__":
    main()

