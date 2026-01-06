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
from urllib.parse import urlparse, parse_qs
from datetime import datetime

# --- Configuration ---
PORT = 8000
STOP_TOKEN = "RALPH_DONE"
MAX_ITERATIONS = 100
LOG_FILE = ".ralph_history.json"
QUEUE_FILE = ".ralph_queue.json"

# --- Z AI Configuration ---
ZAI_API_KEY = "60d06b15165945f388f66800a973eb01.rXT0FqpZniBHzQJj"
ZAI_MODEL = "glm-4.7"
ZAI_API_URL = "https://api.z.ai/api/paas/v4/chat/completions"

# --- Z AI MCP Server Endpoints ---
MCP_SERVERS = {
    "web_search": {
        "url": "https://api.z.ai/api/mcp/web_search_prime/mcp",
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
MCP_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for real-time information, news, documentation, or any query. Use this when you need current information from the internet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to look up on the web"
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of results to return (default: 10)",
                        "default": 10
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_reader",
            "description": "Read and extract the full content from a web page URL. Use this to get detailed information from a specific webpage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL of the webpage to read"
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "zread_search_doc",
            "description": "Search documentation, code, and comments within a GitHub repository. Use this to understand how a project works.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repository": {
                        "type": "string",
                        "description": "GitHub repository in format 'owner/repo' (e.g., 'facebook/react')"
                    },
                    "query": {
                        "type": "string",
                        "description": "Search query for documentation or code"
                    }
                },
                "required": ["repository", "query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "zread_get_structure",
            "description": "Get the directory structure and file list of a GitHub repository. Use this to understand a project's layout.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repository": {
                        "type": "string",
                        "description": "GitHub repository in format 'owner/repo' (e.g., 'facebook/react')"
                    },
                    "path": {
                        "type": "string",
                        "description": "Optional path within the repository to list (default: root)",
                        "default": ""
                    }
                },
                "required": ["repository"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "zread_read_file",
            "description": "Read the complete content of a specific file from a GitHub repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repository": {
                        "type": "string",
                        "description": "GitHub repository in format 'owner/repo' (e.g., 'facebook/react')"
                    },
                    "path": {
                        "type": "string",
                        "description": "Path to the file within the repository"
                    }
                },
                "required": ["repository", "path"]
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

def mcp_request(server_name, method, params=None):
    """Make a JSON-RPC request to an MCP server."""
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
        "Authorization": f"Bearer {ZAI_API_KEY}"
    }
    
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(server_url, data=data, headers=headers, method='POST')
        ctx = ssl.create_default_context()
        
        with urllib.request.urlopen(req, timeout=60, context=ctx) as response:
            result = json.loads(response.read().decode('utf-8'))
            if "error" in result:
                return {"error": result["error"]}
            return result.get("result", result)
    
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else str(e)
        return {"error": f"HTTP {e.code}: {error_body}"}
    except Exception as e:
        return {"error": str(e)}

def execute_tool(tool_name, arguments):
    """Execute a tool call and return the result."""
    log(f"🔧 Executing tool: {tool_name}")
    
    try:
        if tool_name == "web_search":
            result = mcp_request("web_search", "tools/call", {
                "name": "web_search",
                "arguments": {
                    "query": arguments.get("query", ""),
                    "count": arguments.get("count", 10)
                }
            })
        
        elif tool_name == "web_reader":
            result = mcp_request("web_reader", "tools/call", {
                "name": "read_url",
                "arguments": {
                    "url": arguments.get("url", "")
                }
            })
        
        elif tool_name == "zread_search_doc":
            result = mcp_request("zread", "tools/call", {
                "name": "search_doc",
                "arguments": {
                    "repository": arguments.get("repository", ""),
                    "query": arguments.get("query", "")
                }
            })
        
        elif tool_name == "zread_get_structure":
            result = mcp_request("zread", "tools/call", {
                "name": "get_structure",
                "arguments": {
                    "repository": arguments.get("repository", ""),
                    "path": arguments.get("path", "")
                }
            })
        
        elif tool_name == "zread_read_file":
            result = mcp_request("zread", "tools/call", {
                "name": "read_file",
                "arguments": {
                    "repository": arguments.get("repository", ""),
                    "path": arguments.get("path", "")
                }
            })
        
        else:
            result = {"error": f"Unknown tool: {tool_name}"}
        
        # Format result for logging
        if isinstance(result, dict) and "error" in result:
            log(f"❌ Tool error: {result['error'][:100]}...")
        else:
            log(f"✅ Tool completed successfully")
        
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
1. Use the available tools (web_search, web_reader, zread_*) when you need external information.
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
                log("🛠️ MCP Tools: web_search, web_reader, zread")
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
            # Endpoint to list available MCP tools
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
        print("   • web_search    - Search the web for real-time info")
        print("   • web_reader    - Read full webpage content")
        print("   • zread_*       - Search/read GitHub repositories\n")
        httpd.serve_forever()

if __name__ == "__main__":
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
