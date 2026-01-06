#!/usr/bin/env python3
import subprocess
import json
import os
import time
import sys
import threading
import http.server
import socketserver
from urllib.parse import urlparse, parse_qs
from datetime import datetime

# --- Configuration ---
PORT = 8000
STOP_TOKEN = "RALPH_DONE"
MAX_ITERATIONS = 100
# Files
LOG_FILE = ".ralph_history.json"
QUEUE_FILE = ".ralph_queue.json"

# --- Global State ---
# This shared state holds the current task
task_state = {
    "active": False,
    "prompt": "",
    "iteration": 0,
    "status": "idle", # idle, running, success, error
    "message": "Waiting for task...",
    "logs": []
}
state_lock = threading.Lock()

# --- Helper Functions ---

def log(message, level="info"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = f"[{timestamp}] {message}"
    print(entry)
    with state_lock:
        task_state["logs"].insert(0, entry) # Prepend
        if len(task_state["logs"]) > 50: task_state["logs"].pop()

def update_status(status, message, iteration=None):
    with state_lock:
        task_state["status"] = status
        task_state["message"] = message
        if iteration is not None:
            task_state["iteration"] = iteration

def git_commit(message):
    try:
        subprocess.run(['git', 'add', '.'], check=False, capture_output=True)
        # --allow-empty allows us to mark time/iterations even if no code changed yet
        subprocess.run(['git', 'commit', '-m', f"[Ralph] {message}"], check=False, capture_output=True)
    except Exception as e:
        log(f"Git error: {e}", "error")

def run_claude_iteration(prompt_text):
    """Runs Claude once and returns the output."""
    # Write prompt to temp file
    temp_prompt = ".ralph_current_prompt.md"
    with open(temp_prompt, "w") as f:
        # Add Ralph specific context to the user prompt
        full_prompt = f"""
{prompt_text}

---
CRITICAL INSTRUCTION:
You are running in an automated loop.
1. Perform the task.
2. If you COMPLETE the task successfully, you MUST output the exact word: {STOP_TOKEN}
3. If you FAIL or are NOT DONE, do not output {STOP_TOKEN}. Just output the code/fixes.
4. Do not ask questions. Just do.
"""
        f.write(full_prompt)

    try:
        result = subprocess.run(
            ['claude', '-p', temp_prompt],
            capture_output=True,
            text=True,
            timeout=120 # 2 minute timeout per iteration
        )
        return result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return "Error: Claude timed out."
    except Exception as e:
        return f"Error running Claude: {str(e)}"
    finally:
        if os.path.exists(temp_prompt):
            os.remove(temp_prompt)

# --- The Ralph Loop Thread ---

def ralph_worker():
    while True:
        time.sleep(1) # Check frequency
        
        with state_lock:
            active = task_state["active"]
            current_prompt = task_state["prompt"]
            iter_count = task_state["iteration"]
        
        if active and iter_count < MAX_ITERATIONS:
            if iter_count == 0:
                log("Starting new task...")
                update_status("running", "Initializing Ralph Loop...", 0)
                time.sleep(1)
            
            # Run Iteration
            iter_count += 1
            update_status("running", f"Iteration {iter_count}/{MAX_ITERATIONS}", iter_count)
            
            log(f"Running Iteration {iter_count}...")
            output = run_claude_iteration(current_prompt)
            
            # Check Stop Token
            if STOP_TOKEN in output:
                log(f"SUCCESS: {STOP_TOKEN} detected.")
                git_commit(f"Task Completed at Iteration {iter_count}")
                update_status("success", "Task Completed!", iter_count)
                with state_lock:
                    task_state["active"] = False
                continue
            
            # Auto-commit progress
            git_commit(f"Iteration {iter_count} progress")
            
            # Simple logic: if we hit max iterations, stop
            if iter_count >= MAX_ITERATIONS:
                log("Max iterations reached. Stopping.")
                update_status("error", "Max iterations reached without success.", iter_count)
                with state_lock:
                    task_state["active"] = False

# --- The Web Server ---

class RalphHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            with open('dashboard.html', 'rb') as f:
                self.wfile.write(f.read())
        
        elif self.path == '/status':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            with state_lock:
                # Return a copy of the state
                self.wfile.write(json.dumps(dict(task_state)).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == '/submit_prompt':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            new_prompt = data.get('prompt', '')
            
            if not new_prompt:
                self.send_response(400)
                self.end_headers()
                return

            log("New task received via Dashboard.")
            
            with state_lock:
                # 1. Stop current task if any
                if task_state["active"]:
                    log("Interrupting previous task.")
                
                # 2. Reset State
                task_state["active"] = True
                task_state["prompt"] = new_prompt
                task_state["iteration"] = 0
                task_state["status"] = "queued"
                task_state["logs"] = [] # Clear logs for new task
            
            # 3. Create a Checkpoint Git commit so we can rollback if needed
            git_commit("CHECKPOINT: Before new Ralph task")
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "started"}).encode())

    def log_message(self, format, *args):
        # Suppress standard server logging to keep console clean
        pass

# --- Main Entry Point ---

def start_server():
    with socketserver.TCPServer(("", PORT), RalphHandler) as httpd:
        print(f"\n🚀 Ralph-OS Server running at http://localhost:{PORT}")
        print("💡 Open the URL above in your browser to control Ralph.\n")
        httpd.serve_forever()

if __name__ == "__main__":
    # Check for git
    try:
        subprocess.run(["git", "status"], capture_output=True, check=True)
    except:
        print("Warning: Not in a git repo. Ralph cannot save checkpoints.")
        print("Please run 'git init' first.")

    # Start the worker thread
    worker_thread = threading.Thread(target=ralph_worker, daemon=True)
    worker_thread.start()

    # Start the web server (blocking)
    try:
        start_server()
    except KeyboardInterrupt:
        print("\nShutting down Ralph-OS...")
        sys.exit(0)