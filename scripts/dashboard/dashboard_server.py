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
        elif path == '/prd/save':
            self.handle_save_prd(data)
        elif path == '/prd/check-file':
            self.handle_check_prd_file(data)
        elif path == '/prd/analyze-domain':
            self.handle_analyze_domain(data)
        elif path == '/prd/generate-from-analysis':
            self.handle_generate_prd_from_analysis(data)
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
    
    def handle_save_prd(self, data):
        """Save PRD to file"""
        prd = data.get('prd')
        if not prd:
            self.send_json({'error': 'PRD content is required'}, 400)
            return
        
        try:
            # Ensure it's valid JSON
            if isinstance(prd, str):
                prd = json.loads(prd)
            
            # Write to prd.json
            with open(PRD_FILE, 'w') as f:
                json.dump(prd, f, indent=2)
            
            self.send_json({
                'success': True,
                'message': 'PRD saved successfully',
                'path': str(PRD_FILE)
            })
            
            print(f"PRD saved for {prd.get('sourceId', 'unknown')}")
            
        except json.JSONDecodeError as e:
            self.send_json({'error': f'Invalid JSON: {str(e)}'}, 400)
        except Exception as e:
            self.send_json({'error': str(e)}, 500)
    
    def handle_check_prd_file(self, data):
        """Check if a PRD-related file exists and return its content"""
        filename = data.get('filename')
        if not filename:
            self.send_json({'error': 'filename is required'}, 400)
            return
        
        # Security: Only allow specific file patterns
        if not filename.endswith(('_domain_analysis.md', '_prd.md', '_prd.json')):
            self.send_json({'error': 'Invalid filename pattern'}, 400)
            return
        
        # Check in multiple locations
        search_paths = [
            PROJECT_ROOT / "scripts" / "ralph" / filename,
            PROJECT_ROOT / "data" / filename,
            PROJECT_ROOT / filename,
        ]
        
        # Also check in source-specific data directories
        source_id = filename.split('_')[0] if '_' in filename else None
        if source_id:
            search_paths.insert(0, PROJECT_ROOT / "data" / source_id / filename)
        
        for file_path in search_paths:
            if file_path.exists():
                try:
                    content = file_path.read_text()
                    self.send_json({
                        'exists': True,
                        'path': str(file_path),
                        'content': content[:10000]  # Limit content size
                    })
                    return
                except Exception as e:
                    self.send_json({'exists': True, 'path': str(file_path), 'error': str(e)})
                    return
        
        self.send_json({'exists': False})
    
    def handle_analyze_domain(self, data):
        """Run domain analysis for a source using LLM"""
        source_id = data.get('sourceId')
        source_name = data.get('sourceName')
        source_url = data.get('sourceUrl')
        
        if not source_id:
            self.send_json({'error': 'sourceId is required'}, 400)
            return
        
        # Create output directory
        output_dir = PROJECT_ROOT / "data" / source_id
        output_dir.mkdir(parents=True, exist_ok=True)
        analysis_file = output_dir / f"{source_id}_domain_analysis.md"
        
        # Create analysis prompt
        analysis_prompt = f"""# Domain Analysis: {source_name or source_id}

## Target Information
- **Source ID**: {source_id}
- **Source Name**: {source_name or 'Unknown'}
- **URL**: {source_url or 'No URL provided'}

## Analysis Tasks

Please analyze this automotive website and document:

### 1. Site Structure
- What type of content does this site have? (vehicle listings, build threads, gallery, forum, etc.)
- How is the content organized? (categories, makes/models, pagination)
- What is the URL pattern for individual vehicle/build pages?

### 2. Content Discovery
- How can all vehicle/build URLs be discovered?
- Is there pagination? Infinite scroll? Category pages?
- Are there any sitemap files available?
- Estimated number of vehicles/builds on the site

### 3. Data Available
- What vehicle data fields are available? (year, make, model, trim, VIN, etc.)
- Are modifications/parts listed?
- Are there images? How many per build?
- Is there a build story or description?

### 4. Technical Considerations
- Does the site use JavaScript rendering?
- Are there anti-bot protections? (Cloudflare, rate limiting, CAPTCHAs)
- What scraping approach is recommended? (httpx, Camoufox stealth, etc.)
- Recommended rate limiting delays

### 5. Scraping Strategy
Based on the analysis, recommend:
- Best approach for URL discovery
- Best approach for HTML scraping
- Key selectors/patterns for data extraction
- Any special considerations

---

*Analysis generated: {datetime.now().isoformat()}*
"""

        try:
            # Try to use Gemini API for analysis if available
            import os
            gemini_key = os.environ.get('GEMINI_API_KEY')
            
            if gemini_key and source_url:
                # Use Gemini to analyze the site
                analysis_content = self._run_gemini_analysis(source_id, source_name, source_url, gemini_key)
                if analysis_content:
                    # Save analysis
                    full_content = analysis_prompt + "\n\n---\n\n## LLM Analysis Results\n\n" + analysis_content
                    analysis_file.write_text(full_content)
                    self.send_json({
                        'success': True,
                        'analysis': analysis_content,
                        'path': str(analysis_file)
                    })
                    return
            
            # Fallback: Create template analysis
            template_analysis = f"""
## Automated Template Analysis

Since no LLM API is available or URL is missing, here's a template:

### Site Type
- Likely automotive content based on source name

### Recommended Approach
1. **URL Discovery**: Use sitemap or crawl category pages
2. **HTML Scraping**: 
   - If protected: Use `aggressive_stealth_scraper.py`
   - If standard: Use `httpx` with rate limiting
3. **Data Extraction**: Create custom extractor in `src/scrapers/core/extractors/`

### Next Steps
1. Manually visit {source_url or 'the site'} to understand structure
2. Check for sitemap at `/sitemap.xml`
3. Identify URL patterns for builds
4. Test for anti-bot protection

---

*Template generated - manual review recommended*
"""
            full_content = analysis_prompt + template_analysis
            analysis_file.write_text(full_content)
            
            self.send_json({
                'success': True,
                'analysis': template_analysis,
                'path': str(analysis_file),
                'note': 'Template analysis - manual review recommended'
            })
            
        except Exception as e:
            self.send_json({'error': str(e)}, 500)
    
    def _run_gemini_analysis(self, source_id, source_name, source_url, api_key):
        """Run analysis using Gemini API"""
        try:
            import google.generativeai as genai
            
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            prompt = f"""You are an expert web scraping analyst. Analyze this automotive website for a scraping project.

Website: {source_name or source_id}
URL: {source_url}

Please provide a detailed analysis covering:

1. **Site Type**: What kind of automotive content is this? (listings, builds, forum, gallery)

2. **URL Discovery Strategy**: 
   - How to find all vehicle/build URLs
   - Pagination approach (pages, infinite scroll, load more)
   - Category/make/model organization

3. **Data Fields Available**:
   - Vehicle info (year, make, model, trim)
   - Modifications/parts
   - Images
   - Build story/description

4. **Technical Assessment**:
   - JavaScript rendering requirements
   - Anti-bot protection (Cloudflare, rate limits)
   - Recommended scraping tool (httpx for simple, Camoufox for protected)
   - Rate limiting recommendations

5. **Extraction Strategy**:
   - Key HTML selectors or patterns
   - API endpoints if any
   - Special considerations

Be specific and actionable. This analysis will guide automated scraping."""

            response = model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            print(f"Gemini analysis failed: {e}")
            return None
    
    def handle_generate_prd_from_analysis(self, data):
        """Generate PRD from domain analysis using LLM"""
        source_id = data.get('sourceId')
        source_name = data.get('sourceName')
        source_url = data.get('sourceUrl')
        
        if not source_id:
            self.send_json({'error': 'sourceId is required'}, 400)
            return
        
        # Find and read domain analysis
        analysis_file = PROJECT_ROOT / "data" / source_id / f"{source_id}_domain_analysis.md"
        analysis_content = ""
        
        if analysis_file.exists():
            analysis_content = analysis_file.read_text()
        
        # Output files
        output_dir = PROJECT_ROOT / "data" / source_id
        output_dir.mkdir(parents=True, exist_ok=True)
        prd_md_file = output_dir / f"{source_id}_prd.md"
        
        try:
            import os
            gemini_key = os.environ.get('GEMINI_API_KEY')
            
            if gemini_key and analysis_content:
                prd_content = self._generate_prd_with_gemini(
                    source_id, source_name, source_url, 
                    analysis_content, gemini_key
                )
                if prd_content:
                    # Save PRD markdown
                    prd_md_file.write_text(prd_content)
                    
                    # Also create JSON PRD for Ralph
                    prd_json = self._convert_prd_to_json(source_id, source_name, source_url, prd_content)
                    if prd_json:
                        # Save to main PRD file for Ralph
                        with open(PRD_FILE, 'w') as f:
                            json.dump(prd_json, f, indent=2)
                    
                    self.send_json({
                        'success': True,
                        'prd': prd_content,
                        'path': str(prd_md_file),
                        'json_path': str(PRD_FILE)
                    })
                    return
            
            # Fallback: Generate template PRD
            prd_content = self._generate_template_prd(source_id, source_name, source_url, analysis_content)
            prd_md_file.write_text(prd_content)
            
            # Create JSON PRD
            prd_json = self._convert_prd_to_json(source_id, source_name, source_url, prd_content)
            if prd_json:
                with open(PRD_FILE, 'w') as f:
                    json.dump(prd_json, f, indent=2)
            
            self.send_json({
                'success': True,
                'prd': prd_content,
                'path': str(prd_md_file),
                'note': 'Template PRD - customize user stories as needed'
            })
            
        except Exception as e:
            self.send_json({'error': str(e)}, 500)
    
    def _generate_prd_with_gemini(self, source_id, source_name, source_url, analysis, api_key):
        """Generate PRD using Gemini based on domain analysis"""
        try:
            import google.generativeai as genai
            
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            prompt = f"""Based on this domain analysis, create a detailed PRD (Product Requirements Document) for scraping this automotive website.

## Domain Analysis:
{analysis}

## Source Info:
- Source ID: {source_id}
- Source Name: {source_name or source_id}
- URL: {source_url or 'Unknown'}

## Create a PRD with:

### Project Overview
Brief description of what we're scraping and why.

### User Stories

Create 3-5 specific, actionable user stories following this format:

#### US-001: URL Discovery
**Goal**: [What we want to achieve]
**Acceptance Criteria**:
- [ ] Specific, measurable criterion 1
- [ ] Specific, measurable criterion 2

**Implementation Notes**:
- Specific technical guidance based on the analysis
- Tools to use (sitemap crawler, pagination handler, etc.)

#### US-002: HTML Scraping  
**Goal**: [What we want to achieve]
**Acceptance Criteria**:
- [ ] Specific criterion

**Implementation Notes**:
- Whether to use httpx or Camoufox stealth
- Rate limiting requirements
- Session handling needs

#### US-003: Data Extraction
**Goal**: [What we want to achieve]  
**Acceptance Criteria**:
- [ ] Fields to extract
- [ ] Data quality requirements

**Implementation Notes**:
- Key selectors/patterns
- Data normalization needs

### Technical Requirements
- Scraping mode (standard/stealth)
- Rate limits
- Error handling approach

### Success Metrics
- Expected number of builds
- Data completeness targets

Be specific and base recommendations on the domain analysis provided."""

            response = model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            print(f"Gemini PRD generation failed: {e}")
            return None
    
    def _generate_template_prd(self, source_id, source_name, source_url, analysis):
        """Generate template PRD when LLM is not available"""
        has_analysis = bool(analysis and len(analysis) > 100)
        
        return f"""# PRD: {source_name or source_id} Scraping Project

## Project Overview
Scrape vehicle build data from {source_name or source_id} ({source_url or 'URL TBD'}).

## Source Information
- **Source ID**: {source_id}
- **Source Name**: {source_name or source_id}
- **URL**: {source_url or 'Not specified'}
- **Analysis Available**: {'Yes' if has_analysis else 'No - manual review needed'}

---

## User Stories

### US-001: URL Discovery
**Goal**: Discover all vehicle/build URLs on the site

**Acceptance Criteria**:
- [ ] urls.jsonl contains all discoverable URLs
- [ ] URLs are deduplicated and normalized
- [ ] Pagination/infinite scroll handled

**Implementation Notes**:
- Check for sitemap at /sitemap.xml
- Identify category/listing pages
- Handle pagination or infinite scroll

---

### US-002: HTML Scraping
**Goal**: Scrape HTML for all discovered URLs

**Acceptance Criteria**:
- [ ] HTML files saved for each URL
- [ ] Success rate > 95%
- [ ] Respectful rate limiting applied

**Implementation Notes**:
- Use `aggressive_stealth_scraper.py` if anti-bot detected
- Otherwise use standard httpx scraper
- Rate limit: 2-5 second delays minimum

---

### US-003: Build Data Extraction
**Goal**: Extract structured build data from HTML

**Acceptance Criteria**:
- [ ] builds.jsonl contains vehicle data
- [ ] Required fields: build_id, year, make, model, source_url
- [ ] Images extracted to gallery_images array

**Implementation Notes**:
- Create extractor in src/scrapers/core/extractors/{source_id}.py
- Follow BaseExtractor pattern
- Register with @register_extractor decorator

---

### US-004: Modification Extraction
**Goal**: Extract parts/modifications from builds

**Acceptance Criteria**:
- [ ] mods.jsonl contains modification data
- [ ] Categories assigned (Engine, Suspension, etc.)
- [ ] Brand/part names extracted where visible

**Implementation Notes**:
- Use LLM extraction pipeline if build_story available
- Otherwise extract from structured mod lists

---

## Technical Requirements

| Setting | Value |
|---------|-------|
| Scrape Mode | {'Stealth (Camoufox)' if 'protected' in analysis.lower() or 'cloudflare' in analysis.lower() else 'Standard (httpx)'} |
| Min Delay | 2 seconds |
| Max Delay | 5 seconds |
| Concurrency | 1-2 |
| Daily Limit | 500 |

---

## Success Metrics
- URLs discovered: TBD after US-001
- HTML scraped: 95%+ success rate
- Builds extracted: Match HTML count
- Data quality: All required fields populated

---

*PRD generated: {datetime.now().isoformat()}*
*Review and customize user stories based on actual site structure*
"""
    
    def _convert_prd_to_json(self, source_id, source_name, source_url, prd_markdown):
        """Convert markdown PRD to JSON format for Ralph"""
        try:
            # Parse user stories from markdown
            stories = []
            
            # Look for US-XXX patterns
            import re
            story_pattern = r'###\s+US-(\d+):\s*(.+?)(?=\n)'
            matches = re.findall(story_pattern, prd_markdown)
            
            for i, (story_num, title) in enumerate(matches):
                story_id = f"US-{story_num.zfill(3)}"
                
                # Determine acceptance criteria
                criteria = []
                if 'url' in title.lower() or 'discover' in title.lower():
                    criteria = [
                        "urls.jsonl contains all discoverable URLs",
                        "URLs are deduplicated and normalized"
                    ]
                elif 'html' in title.lower() or 'scrap' in title.lower():
                    criteria = [
                        "HTML files saved for each URL",
                        "Success rate > 95%"
                    ]
                elif 'build' in title.lower() or 'extract' in title.lower():
                    criteria = [
                        "builds.jsonl contains vehicle data",
                        "Required fields populated"
                    ]
                elif 'mod' in title.lower():
                    criteria = [
                        "mods.jsonl contains modification data",
                        "Categories assigned correctly"
                    ]
                else:
                    criteria = ["Task completed successfully"]
                
                stories.append({
                    "id": story_id,
                    "title": title.strip(),
                    "acceptanceCriteria": criteria,
                    "priority": i + 1,
                    "passes": False
                })
            
            # Default stories if none found
            if not stories:
                stories = [
                    {
                        "id": "URL-001",
                        "title": "Discover all build/vehicle URLs",
                        "acceptanceCriteria": ["urls.jsonl populated"],
                        "priority": 1,
                        "passes": False
                    },
                    {
                        "id": "HTML-001", 
                        "title": "Scrape HTML for all URLs",
                        "acceptanceCriteria": ["HTML files saved"],
                        "priority": 2,
                        "passes": False
                    },
                    {
                        "id": "BUILD-001",
                        "title": "Extract build data",
                        "acceptanceCriteria": ["builds.jsonl populated"],
                        "priority": 3,
                        "passes": False
                    }
                ]
            
            return {
                "projectName": f"{source_name or source_id} Scraping",
                "sourceId": source_id,
                "branchName": "main",
                "targetUrl": source_url or "",
                "outputDir": f"data/{source_id}",
                "userStories": stories,
                "createdAt": datetime.now().isoformat(),
                "createdBy": "dashboard-prd-generator"
            }
            
        except Exception as e:
            print(f"Error converting PRD to JSON: {e}")
            return None

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
        
        # Get current source from PRD to mark as in_progress
        current_source_id = None
        try:
            if PRD_FILE.exists():
                prd = json.loads(PRD_FILE.read_text())
                current_source_id = prd.get('sourceId') or prd.get('outputDir', '').split('/')[-1]
        except:
            pass
        
        ralph_running = self.check_ralph_running()
        
        for source in sources:
            source_id = source.get('id')
            status = source.get('status', 'pending')
            
            # If Ralph is running and this is the current source, mark as in_progress
            if ralph_running and current_source_id and source_id == current_source_id:
                status = 'in_progress'
            
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
        
        # Get current source from PRD to mark as in_progress
        current_source_id = None
        try:
            if PRD_FILE.exists():
                prd = json.loads(PRD_FILE.read_text())
                current_source_id = prd.get('sourceId') or prd.get('outputDir', '').split('/')[-1]
        except:
            pass
        
        ralph_running = self.check_ralph_running()
        
        result = []
        for s in sources:
            source_id = s.get('id')
            status = s.get('status', 'pending')
            
            # If Ralph is running and this is the current source, mark as in_progress
            if ralph_running and current_source_id and source_id == current_source_id:
                status = 'in_progress'
            
            result.append({
                'id': source_id,
                'name': s.get('name'),
                'url': s.get('url'),
                'status': status,
                'pipeline': s.get('pipeline', {})
            })
        
        return result
    
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

