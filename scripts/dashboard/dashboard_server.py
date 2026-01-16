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
import threading
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse, parse_qs

# Configuration
PORT = 8765
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
SOURCES_FILE = PROJECT_ROOT / "scripts" / "ralph" / "sources.json"
LOG_FILE = PROJECT_ROOT / "logs" / "ralph_output.log"
SCRAPER_LOG_FILE = PROJECT_ROOT / "logs" / "scraper_output.log"
PRD_FILE = PROJECT_ROOT / "scripts" / "ralph" / "prd.json"
DATA_DIR = PROJECT_ROOT / "data"
STEALTH_SCRAPER = PROJECT_ROOT / "scripts" / "tools" / "aggressive_stealth_scraper.py"
RALPH_SCRIPT = PROJECT_ROOT / "scripts" / "ralph" / "ralph.sh"

# Track running processes
scraper_process = None
scraper_lock = threading.Lock()
ralph_process = None
ralph_lock = threading.Lock()

class DashboardHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress default logging
        pass
    
    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_POST(self):
        path = urlparse(self.path).path
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else '{}'
        
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            data = {}
        
        if path == '/scraper/start':
            self.handle_start_scraper(data)
        elif path == '/scraper/stop':
            self.handle_stop_scraper()
        elif path == '/ralph/start':
            self.handle_start_ralph(data)
        elif path == '/ralph/stop':
            self.handle_stop_ralph()
        elif path == '/prd/generate':
            self.handle_generate_prd(data)
        else:
            self.send_json({'error': 'Not found'}, 404)
    
    def do_GET(self):
        path = urlparse(self.path).path
        
        if path == '/status':
            self.handle_status()
        elif path == '/log':
            self.handle_log()
        elif path == '/log/fresh':
            self.handle_log_fresh()
        elif path == '/sources':
            self.handle_sources()
        elif path == '/scraper/status':
            self.handle_scraper_status()
        elif path == '/scraper/log':
            self.handle_scraper_log()
        elif path == '/ralph/status':
            self.handle_ralph_status()
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
    
    def handle_start_scraper(self, data):
        """Start the aggressive stealth scraper"""
        global scraper_process
        
        with scraper_lock:
            if scraper_process and scraper_process.poll() is None:
                self.send_json({'error': 'Scraper already running', 'running': True}, 400)
                return
            
            source = data.get('source')
            if not source:
                self.send_json({'error': 'Source is required'}, 400)
                return
            
            # Build command
            cmd = ['python3', str(STEALTH_SCRAPER), '--source', source]
            
            # Add optional parameters
            if data.get('minDelay'):
                cmd.extend(['--min-delay', str(data['minDelay'])])
            if data.get('maxDelay'):
                cmd.extend(['--max-delay', str(data['maxDelay'])])
            if data.get('dailyLimit'):
                cmd.extend(['--daily-limit', str(data['dailyLimit'])])
            if data.get('rotateEvery'):
                cmd.extend(['--rotate-every', str(data['rotateEvery'])])
            if data.get('limit'):
                cmd.extend(['--limit', str(data['limit'])])
            if data.get('initialBackoff'):
                cmd.extend(['--initial-backoff', str(data['initialBackoff'])])
            if data.get('noHeadless'):
                cmd.append('--no-headless')
            
            # Start scraper process
            SCRAPER_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            log_file = open(SCRAPER_LOG_FILE, 'w')
            
            try:
                scraper_process = subprocess.Popen(
                    cmd,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    cwd=str(PROJECT_ROOT)
                )
                
                self.send_json({
                    'success': True,
                    'pid': scraper_process.pid,
                    'command': ' '.join(cmd),
                    'message': f'Scraper started for {source}'
                })
            except Exception as e:
                self.send_json({'error': str(e)}, 500)
    
    def handle_stop_scraper(self):
        """Stop the running scraper"""
        global scraper_process
        
        with scraper_lock:
            if scraper_process and scraper_process.poll() is None:
                scraper_process.terminate()
                try:
                    scraper_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    scraper_process.kill()
                self.send_json({'success': True, 'message': 'Scraper stopped'})
            else:
                self.send_json({'success': True, 'message': 'No scraper running'})
    
    def handle_scraper_status(self):
        """Get scraper status"""
        global scraper_process
        
        with scraper_lock:
            running = scraper_process and scraper_process.poll() is None
            pid = scraper_process.pid if running else None
            
            # Get checkpoint data if exists
            checkpoint_data = {}
            if running or True:  # Always try to get checkpoint
                # Find checkpoint from most recent source
                sources = self.load_sources()
                for source in sources:
                    checkpoint_path = PROJECT_ROOT / source.get('outputDir', '') / 'aggressive_checkpoint.json'
                    if checkpoint_path.exists():
                        try:
                            with open(checkpoint_path) as f:
                                checkpoint_data = json.load(f)
                                checkpoint_data['source'] = source.get('id')
                                break
                        except:
                            pass
            
            self.send_json({
                'running': running,
                'pid': pid,
                'checkpoint': checkpoint_data
            })
    
    def handle_scraper_log(self):
        """Get scraper log tail"""
        lines = 100
        try:
            if SCRAPER_LOG_FILE.exists():
                result = subprocess.run(
                    ['tail', '-n', str(lines), str(SCRAPER_LOG_FILE)],
                    capture_output=True,
                    text=True
                )
                self.send_json({'log': result.stdout})
            else:
                self.send_json({'log': 'No scraper log available'})
        except Exception as e:
            self.send_json({'log': f'Error reading log: {e}'})
    
    def handle_log_fresh(self):
        """Get fresh log tail - forces re-read from disk"""
        lines = int(self.path.split('?lines=')[-1]) if '?lines=' in self.path else 150
        try:
            if LOG_FILE.exists():
                # Force fresh read by not caching
                with open(LOG_FILE, 'r') as f:
                    all_lines = f.readlines()
                    tail_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
                    log_content = ''.join(tail_lines)
                self.send_json({
                    'log': log_content,
                    'timestamp': datetime.now().isoformat(),
                    'total_lines': len(all_lines)
                })
            else:
                self.send_json({'log': 'No log file found', 'timestamp': datetime.now().isoformat()})
        except Exception as e:
            self.send_json({'log': f'Error reading log: {e}', 'timestamp': datetime.now().isoformat()})
    
    def handle_start_ralph(self, data):
        """Start the Ralph loop"""
        global ralph_process
        
        with ralph_lock:
            if ralph_process and ralph_process.poll() is None:
                self.send_json({'error': 'Ralph already running', 'running': True}, 400)
                return
            
            iterations = data.get('iterations', 25)
            selected_sources = data.get('sources', [])
            
            # If sources are selected, update sources.json to prioritize them
            if selected_sources:
                try:
                    self._set_source_priority(selected_sources)
                except Exception as e:
                    print(f"Warning: Failed to set source priority: {e}")
            
            # Build command
            cmd = ['bash', str(RALPH_SCRIPT), str(iterations)]
            
            try:
                # Create/clear log file
                LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
                log_file = open(LOG_FILE, 'a')
                
                # Set environment with selected sources
                env = {**os.environ, 'TERM': 'xterm-256color'}
                if selected_sources:
                    env['RALPH_TARGET_SOURCES'] = ','.join(selected_sources)
                
                ralph_process = subprocess.Popen(
                    cmd,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    cwd=str(PROJECT_ROOT),
                    env=env
                )
                
                self.send_json({
                    'success': True,
                    'pid': ralph_process.pid,
                    'iterations': iterations,
                    'sources': selected_sources,
                    'message': f'Ralph started with {iterations} iterations' + 
                              (f' targeting {len(selected_sources)} source(s)' if selected_sources else '')
                })
            except Exception as e:
                self.send_json({'error': str(e)}, 500)
    
    def _set_source_priority(self, source_ids):
        """Set selected sources to high priority and create PRD for first one"""
        try:
            with open(SOURCES_FILE, 'r') as f:
                data = json.load(f)
            
            selected_source = None
            for source in data.get('sources', []):
                if source.get('id') in source_ids:
                    # Set to in_progress and high priority
                    source['status'] = 'in_progress'
                    source['priority'] = 1
                    if not selected_source:
                        selected_source = source
                else:
                    # Lower priority for non-selected sources
                    if source.get('priority', 5) < 5:
                        source['priority'] = 5
            
            with open(SOURCES_FILE, 'w') as f:
                json.dump(data, f, indent=2)
            
            # Create a new PRD for the selected source
            if selected_source:
                self._create_prd_for_source(selected_source)
                
        except Exception as e:
            raise Exception(f"Failed to update sources.json: {e}")
    
    def _create_prd_for_source(self, source):
        """Create a new PRD file for the selected source"""
        pipeline = source.get('pipeline', {})
        urls_found = pipeline.get('urlsFound', 0)
        html_scraped = pipeline.get('htmlScraped', 0)
        builds = pipeline.get('builds', 0)
        
        # Determine which stage to start from
        stories = []
        
        # Stage 1: URL Discovery
        if urls_found == 0:
            stories.append({
                "id": "URL-001",
                "title": "Discover all build/vehicle URLs on the site",
                "acceptanceCriteria": [
                    "urls.json contains all discoverable URLs",
                    "URLs are deduplicated and normalized"
                ],
                "priority": 1,
                "passes": False
            })
        
        # Stage 2: HTML Scraping
        if urls_found > 0 and html_scraped < urls_found:
            stories.append({
                "id": "HTML-001",
                "title": "Scrape HTML for all discovered URLs",
                "acceptanceCriteria": [
                    "HTML files saved for each URL",
                    "Use stealth scraper for protected sites"
                ],
                "priority": 1,
                "passes": False,
                "notes": "Use aggressive_stealth_scraper.py for anti-bot protection"
            })
        
        # Stage 3: Build Extraction
        if html_scraped > 0 and (builds is None or builds == 0):
            stories.append({
                "id": "BUILD-001",
                "title": "Extract build data from HTML files",
                "acceptanceCriteria": [
                    "builds.json contains structured vehicle data",
                    "Follow schema/build_extraction_schema.json"
                ],
                "priority": 1,
                "passes": False
            })
        
        # Stage 4: Mod Extraction
        if builds and builds > 0:
            stories.append({
                "id": "MOD-001",
                "title": "Extract modifications from builds",
                "acceptanceCriteria": [
                    "mods.json contains part/modification data",
                    "Follow schema/Vehicle_Componets.json"
                ],
                "priority": 1,
                "passes": False
            })
        
        # Default story if nothing else
        if not stories:
            stories.append({
                "id": "VERIFY-001",
                "title": "Verify source data completeness",
                "acceptanceCriteria": [
                    "All pipeline stages verified",
                    "Data quality checked"
                ],
                "priority": 1,
                "passes": False
            })
        
        prd = {
            "projectName": f"{source.get('name', source.get('id'))} Scraping",
            "sourceId": source.get('id'),
            "branchName": "main",
            "targetUrl": source.get('url', ''),
            "outputDir": source.get('outputDir', f"data/{source.get('id')}"),
            "userStories": stories,
            "createdAt": datetime.now().isoformat(),
            "createdBy": "dashboard"
        }
        
        # Write the PRD
        with open(PRD_FILE, 'w') as f:
            json.dump(prd, f, indent=2)
        
        print(f"Created PRD for {source.get('id')} with {len(stories)} stories")
    
    def handle_generate_prd(self, data):
        """Generate PRD using browser analysis"""
        source_id = data.get('sourceId')
        url = data.get('url')
        name = data.get('name')
        use_browser = data.get('useBrowser', True)
        
        if not source_id or not url:
            self.send_json({'error': 'sourceId and url are required'}, 400)
            return
        
        try:
            # Find source in sources.json
            sources = self.load_sources()
            source = next((s for s in sources if s.get('id') == source_id), None)
            
            if not source:
                self.send_json({'error': f'Source {source_id} not found'}, 404)
                return
            
            if use_browser:
                # Create a prompt file for Claude to analyze the site
                self._generate_prd_with_browser(source)
            else:
                # Use basic PRD generation
                self._create_prd_for_source(source)
            
            self.send_json({
                'success': True,
                'message': f'PRD generated for {name}',
                'sourceId': source_id
            })
            
        except Exception as e:
            self.send_json({'error': str(e)}, 500)
    
    def _generate_prd_with_browser(self, source):
        """Generate PRD by running Claude with browser tools to analyze the site"""
        source_id = source.get('id')
        url = source.get('url')
        name = source.get('name', source_id)
        output_dir = source.get('outputDir', f'data/{source_id}')
        
        # Create the analysis prompt
        prompt = f'''You are analyzing a website to create a scraping PRD (Product Requirements Document).

TARGET SITE: {name}
URL: {url}
OUTPUT DIR: {output_dir}

YOUR TASK:
1. Use the browser tools to navigate to {url}
2. Take a snapshot to understand the site structure
3. Identify:
   - What type of content is on this site (vehicle listings, build threads, gallery, etc.)
   - How to find all vehicle/build URLs (pagination, infinite scroll, categories)
   - What data can be extracted (year, make, model, mods, images, etc.)
   - Any anti-bot protections (Cloudflare, rate limiting)

4. Create a PRD file at scripts/ralph/prd.json with appropriate user stories

IMPORTANT: 
- Use browser_navigate to go to the URL
- Use browser_snapshot to see the page structure
- Create realistic, actionable user stories based on what you find
- If the site has anti-bot protection, note to use aggressive_stealth_scraper.py

After analysis, write the PRD to: {PRD_FILE}

The PRD format should be:
{{
  "projectName": "{name} Scraping",
  "sourceId": "{source_id}",
  "branchName": "main", 
  "targetUrl": "{url}",
  "outputDir": "{output_dir}",
  "userStories": [
    {{
      "id": "URL-001",
      "title": "Discover all vehicle/build URLs",
      "acceptanceCriteria": ["..."],
      "priority": 1,
      "passes": false,
      "notes": "Based on site analysis..."
    }}
  ],
  "siteAnalysis": {{
    "contentType": "...",
    "paginationType": "...",
    "antiBot": "...",
    "dataFields": ["..."]
  }}
}}

START by navigating to the URL and taking a snapshot.
'''
        
        # Write prompt to a temp file
        prompt_file = PROJECT_ROOT / "scripts" / "ralph" / "prd_gen_prompt.md"
        prompt_file.write_text(prompt)
        
        # Run Claude CLI with browser tools to generate the PRD
        # This runs in background so the API can return quickly
        cmd = [
            'claude',
            '--print',
            '--dangerously-skip-permissions',
            '-p', str(prompt_file)
        ]
        
        log_file = PROJECT_ROOT / "logs" / "prd_gen.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(log_file, 'w') as f:
            subprocess.Popen(
                cmd,
                stdout=f,
                stderr=subprocess.STDOUT,
                cwd=str(PROJECT_ROOT)
            )
        
        print(f"Started PRD generation for {source_id} - check logs/prd_gen.log")
    
    def handle_stop_ralph(self):
        """Stop the Ralph loop"""
        global ralph_process
        
        with ralph_lock:
            if ralph_process and ralph_process.poll() is None:
                ralph_process.terminate()
                try:
                    ralph_process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    ralph_process.kill()
                self.send_json({'success': True, 'message': 'Ralph stopped'})
            else:
                # Try to kill any running ralph.sh processes
                try:
                    subprocess.run(['pkill', '-f', 'ralph.sh'], capture_output=True)
                    self.send_json({'success': True, 'message': 'Ralph processes terminated'})
                except:
                    self.send_json({'success': True, 'message': 'No Ralph running'})
    
    def handle_ralph_status(self):
        """Get Ralph status"""
        global ralph_process
        
        with ralph_lock:
            # Check our tracked process
            process_running = ralph_process and ralph_process.poll() is None
            
            # Also check for any ralph.sh in process list
            try:
                result = subprocess.run(['pgrep', '-f', 'ralph.sh'], capture_output=True, text=True)
                system_running = result.returncode == 0
            except:
                system_running = False
            
            running = process_running or system_running
            pid = ralph_process.pid if process_running else None
            
            # Get current PRD info
            prd_info = {}
            try:
                if PRD_FILE.exists():
                    prd = json.loads(PRD_FILE.read_text())
                    stories = prd.get('userStories', [])
                    completed = sum(1 for s in stories if s.get('passes'))
                    prd_info = {
                        'project': prd.get('projectName', 'Unknown'),
                        'source': prd.get('sourceId', prd.get('outputDir', '').split('/')[-1]),
                        'stories_total': len(stories),
                        'stories_completed': completed,
                        'current_story': next((s for s in stories if not s.get('passes')), None)
                    }
            except:
                pass
            
            self.send_json({
                'running': running,
                'pid': pid,
                'prd': prd_info
            })
    
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

