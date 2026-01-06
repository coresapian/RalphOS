#!/usr/bin/env python3
import subprocess
import json
import os
import time
import sys
import threading
import http.server
import socketserver
import urllib.request
import urllib.error
import ssl
import re
from urllib.parse import urlparse, parse_qs
from datetime import datetime
from pathlib import Path

# --- Load .env file ---
def load_dotenv():
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip())

load_dotenv()

# --- Configuration ---
PORT = 8000
STOP_TOKEN = "RALPH_DONE"
MAX_ITERATIONS = 100
LOG_FILE = ".ralph_history.json"
QUEUE_FILE = ".ralph_queue.json"

# --- Z AI Configuration ---
ZAI_API_KEY = os.environ.get("ZAI_API_KEY", "")
ZAI_MODEL = "glm-4.7"
ZAI_API_URL = "https://api.z.ai/api/paas/v4/chat/completions"

# --- Z AI MCP Server Endpoints ---
MCP_SERVERS = {
    "web_search": {
        "url": "https://api.z.ai/api/mcp/web_search/mcp",
        "description": "Search the web for real-time information"
    },
    "web_reader": {
        "url": "https://api.z.ai/api/mcp/web_reader/mcp",
        "description": "Read and extract content from web pages"
    },
    "zread": {
        "url": "https://api.z.ai/api/mcp/zread/mcp",
        "description": "Search and read code from GitHub repositories"
    }
}

# --- MCP Tools Definition for GLM Function Calling ---
# These match the actual MCP server tool names
MCP_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "webSearchPro",
            "description": "Search the web for real-time information, news, documentation, or any query. Returns web page titles, URLs, and summaries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search_query": {
                        "type": "string",
                        "description": "The search query (max 70 characters recommended)"
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of results (1-50, default: 10)"
                    },
                    "content_size": {
                        "type": "string",
                        "description": "Summary length: 'medium' (400-600 chars) or 'high' (2500 chars)",
                        "enum": ["medium", "high"]
                    }
                },
                "required": ["search_query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "webReader",
            "description": "Fetch and read the full content from a web page URL. Returns markdown-formatted content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL of the webpage to read"
                    },
                    "return_format": {
                        "type": "string",
                        "description": "Response format: 'markdown' or 'text'",
                        "enum": ["markdown", "text"]
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_doc",
            "description": "Search documentation, issues, and commits of a GitHub repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_name": {
                        "type": "string",
                        "description": "GitHub repository: owner/repo (e.g., 'facebook/react')"
                    },
                    "query": {
                        "type": "string",
                        "description": "Search keywords or question about the repository"
                    },
                    "language": {
                        "type": "string",
                        "description": "Response language: 'en' or 'zh'",
                        "enum": ["en", "zh"]
                    }
                },
                "required": ["repo_name", "query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_repo_structure",
            "description": "Get the directory structure and file list of a GitHub repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_name": {
                        "type": "string",
                        "description": "GitHub repository: owner/repo (e.g., 'facebook/react')"
                    },
                    "dir_path": {
                        "type": "string",
                        "description": "Directory path to inspect (default: root '/')"
                    }
                },
                "required": ["repo_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the full code content of a specific file in a GitHub repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_name": {
                        "type": "string",
                        "description": "GitHub repository: owner/repo (e.g., 'facebook/react')"
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Relative path to the file (e.g., 'src/index.ts')"
                    }
                },
                "required": ["repo_name", "file_path"]
            }
        }
    }
]

# --- Global State ---
task_state = {
    "active": False,
    "prompt": "",
    "iteration": 0,
    "status": "idle",
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
        task_state["logs"].insert(0, entry)
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
        subprocess.run(['git', 'commit', '-m', f"[Ralph] {message}"], check=False, capture_output=True)
    except Exception as e:
        log(f"Git error: {e}", "error")

# --- MCP Client Functions ---

def parse_sse_response(response_text):
    """Parse Server-Sent Events response format."""
    # SSE format: event:message\ndata:{json}\n\n
    lines = response_text.strip().split('\n')
    data_line = None
    for line in lines:
        if line.startswith('data:'):
            data_line = line[5:]  # Remove 'data:' prefix
            break
    
    if data_line:
        try:
            return json.loads(data_line)
        except json.JSONDecodeError:
            return {"error": f"Failed to parse SSE data: {data_line}"}
    return {"error": f"No data in SSE response: {response_text}"}

def mcp_request(server_name, method, params=None):
    """Make a JSON-RPC request to an MCP server with SSE support."""
    if server_name not in MCP_SERVERS:
        return {"error": f"Unknown MCP server: {server_name}"}
    
    server_url = MCP_SERVERS[server_name]["url"]
    
    payload = {
        "jsonrpc": "2.0",
        "id": int(time.time() * 1000),
        "method": method,
        "params": params or {}
    }
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",  # Required for MCP SSE
        "Authorization": f"Bearer {ZAI_API_KEY}"
    }
    
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(server_url, data=data, headers=headers, method='POST')
        ctx = ssl.create_default_context()
        
        with urllib.request.urlopen(req, timeout=60, context=ctx) as response:
            response_text = response.read().decode('utf-8')
            # Parse SSE response
            result = parse_sse_response(response_text)
            
            if "error" in result:
                return result
            if "result" in result:
                return result["result"]
            return result
    
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else str(e)
        # Try to parse error as JSON
        try:
            error_json = json.loads(error_body)
            if "message" in error_json:
                return {"error": error_json["message"]}
        except:
            pass
        return {"error": f"HTTP {e.code}: {error_body[:200]}"}
    except Exception as e:
        return {"error": str(e)}

def execute_tool(tool_name, arguments):
    """Execute a tool call and return the result."""
    log(f"🔧 Executing tool: {tool_name}")
    
    try:
        # Map tool to MCP server and actual tool name
        if tool_name in ["webSearchPro", "webSearchStd", "webSearchSogou", "webSearchQuark"]:
            result = mcp_request("web_search", "tools/call", {
                "name": tool_name,
                "arguments": arguments
            })
        
        elif tool_name == "webReader":
            result = mcp_request("web_reader", "tools/call", {
                "name": "webReader",
                "arguments": arguments
            })
        
        elif tool_name in ["search_doc", "read_file", "get_repo_structure"]:
            result = mcp_request("zread", "tools/call", {
                "name": tool_name,
                "arguments": arguments
            })
        
        else:
            result = {"error": f"Unknown tool: {tool_name}"}
        
        # Extract content from MCP result
        if isinstance(result, dict):
            if "content" in result:
                # MCP tools return content array
                content_items = result["content"]
                if isinstance(content_items, list):
                    texts = [item.get("text", "") for item in content_items if item.get("type") == "text"]
                    result_text = "\n".join(texts)
                    if result.get("isError"):
                        log(f"❌ Tool error: {result_text[:100]}...")
                        return json.dumps({"error": result_text})
                    log(f"✅ Tool completed successfully")
                    return result_text if result_text else json.dumps(result)
            elif "error" in result:
                log(f"❌ Tool error: {str(result['error'])[:100]}...")
                return json.dumps(result)
        
        log(f"✅ Tool completed")
        return json.dumps(result) if isinstance(result, (dict, list)) else str(result)
    
    except Exception as e:
        log(f"❌ Tool exception: {str(e)}")
        return json.dumps({"error": str(e)})

# --- AI Iteration with Tool Calling ---

def run_ai_iteration(prompt_text):
    """Runs Z AI GLM-4.7 with MCP tools and returns the output."""
    full_prompt = f"""{prompt_text}

---
CRITICAL INSTRUCTION:
You are running in an automated loop with access to powerful tools.
1. Use the available tools (webSearchPro, webReader, search_doc, get_repo_structure, read_file) when you need external information.
2. Perform the task completely.
3. If you COMPLETE the task successfully, you MUST output the exact word: {STOP_TOKEN}
4. If you FAIL or are NOT DONE, do not output {STOP_TOKEN}. Just output the code/fixes.
5. Do not ask questions. Just do.
"""
    
    messages = [
        {"role": "system", "content": "You are an expert coding assistant with access to web search, web reading, and GitHub code analysis tools. Use these tools proactively to gather information needed for your tasks. Execute tasks precisely and completely."},
        {"role": "user", "content": full_prompt}
    ]
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ZAI_API_KEY}"
    }
    ctx = ssl.create_default_context()
    
    # Tool calling loop
    max_tool_rounds = 10
    for round_num in range(max_tool_rounds):
        payload = {
            "model": ZAI_MODEL,
            "messages": messages,
            "tools": MCP_TOOLS,
            "tool_choice": "auto",
            "max_tokens": 4096,
            "temperature": 0.7
        }
        
        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(ZAI_API_URL, data=data, headers=headers, method='POST')
            
            with urllib.request.urlopen(req, timeout=120, context=ctx) as response:
                result = json.loads(response.read().decode('utf-8'))
                choice = result['choices'][0]
                message = choice['message']
                
                # Check if the model wants to call tools
                if message.get('tool_calls'):
                    log(f"🔄 Tool round {round_num + 1}: {len(message['tool_calls'])} tool(s) called")
                    
                    # Add assistant message with tool calls
                    messages.append(message)
                    
                    # Execute each tool call
                    for tool_call in message['tool_calls']:
                        tool_name = tool_call['function']['name']
                        tool_args = json.loads(tool_call['function']['arguments'])
                        tool_result = execute_tool(tool_name, tool_args)
                        
                        # Add tool result to messages
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call['id'],
                            "content": tool_result
                        })
                    
                    # Continue the loop for another round
                    continue
                
                # No more tool calls - return the final content
                return message.get('content', '')
        
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else str(e)
            return f"Error: HTTP {e.code} - {error_body}"
        except urllib.error.URLError as e:
            return f"Error: Connection failed - {str(e.reason)}"
        except Exception as e:
            return f"Error running Z AI: {str(e)}"
    
    return "Error: Maximum tool calling rounds exceeded"

# --- The Ralph Loop Thread ---

def ralph_worker():
    while True:
        time.sleep(1)
        
        with state_lock:
            active = task_state["active"]
            current_prompt = task_state["prompt"]
            iter_count = task_state["iteration"]
        
        if active and iter_count < MAX_ITERATIONS:
            if iter_count == 0:
                log("Starting new task...")
                log("🛠️ MCP Tools: webSearchPro, webReader, zread tools")
                update_status("running", "Initializing Ralph Loop...", 0)
                time.sleep(1)
            
            iter_count += 1
            update_status("running", f"Iteration {iter_count}/{MAX_ITERATIONS}", iter_count)
            
            log(f"Running Iteration {iter_count}...")
            output = run_ai_iteration(current_prompt)
            
            if STOP_TOKEN in output:
                log(f"SUCCESS: {STOP_TOKEN} detected.")
                git_commit(f"Task Completed at Iteration {iter_count}")
                update_status("success", "Task Completed!", iter_count)
                with state_lock:
                    task_state["active"] = False
                continue
            
            git_commit(f"Iteration {iter_count} progress")
            
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
                self.wfile.write(json.dumps(dict(task_state)).encode())
        
        elif self.path == '/tools':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            tools_info = {
                "mcp_servers": list(MCP_SERVERS.keys()),
                "tools": [t["function"]["name"] for t in MCP_TOOLS]
            }
            self.wfile.write(json.dumps(tools_info).encode())
        
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
                if task_state["active"]:
                    log("Interrupting previous task.")
                
                task_state["active"] = True
                task_state["prompt"] = new_prompt
                task_state["iteration"] = 0
                task_state["status"] = "queued"
                task_state["logs"] = []
            
            git_commit("CHECKPOINT: Before new Ralph task")
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "started"}).encode())

    def log_message(self, format, *args):
        pass

# --- Main Entry Point ---

def start_server():
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), RalphHandler) as httpd:
        print(f"\n🚀 Ralph-OS Server running at http://localhost:{PORT}")
        print("💡 Open the URL above in your browser to control Ralph.")
        print("\n🛠️  MCP Tools Enabled:")
        print("   • webSearchPro   - Search the web for real-time info")
        print("   • webReader      - Read full webpage content")
        print("   • search_doc     - Search GitHub repo documentation")
        print("   • get_repo_structure - Get GitHub repo file tree")
        print("   • read_file      - Read file from GitHub repo\n")
        httpd.serve_forever()

if __name__ == "__main__":
    # Check for API key
    if not ZAI_API_KEY:
        print("❌ Error: ZAI_API_KEY not found!")
        print("   Create a .env file with: ZAI_API_KEY=your_api_key")
        sys.exit(1)
    
    # Check for git
    try:
        subprocess.run(["git", "status"], capture_output=True, check=True)
    except:
        print("Warning: Not in a git repo. Ralph cannot save checkpoints.")
        print("Please run 'git init' first.")

    worker_thread = threading.Thread(target=ralph_worker, daemon=True)
    worker_thread.start()

    try:
        start_server()
    except KeyboardInterrupt:
        print("\nShutting down Ralph-OS...")
        sys.exit(0)
