#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import subprocess
import threading
import os
import signal
import re
import queue
from datetime import datetime

class RalphLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("RalphOS Launcher")
        self.root.geometry("1000x700")
        self.root.configure(bg="#1e1e1e")

        self.process = None
        self.log_queue = queue.Queue()
        self.is_running = False

        self.setup_styles()
        self.create_widgets()
        self.find_ralphs()
        
        # Start queue processing
        self.root.after(100, self.process_log_queue)
        self.root.after(1000, self.refresh_stats)

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        
        # Dark theme colors
        bg_color = "#1e1e1e"
        fg_color = "#d4d4d4"
        accent_color = "#007acc"
        
        style.configure("TFrame", background=bg_color)
        style.configure("TLabel", background=bg_color, foreground=fg_color, font=("Segoe UI", 10))
        style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"))
        style.configure("TButton", font=("Segoe UI", 10))
        style.configure("Action.TButton", foreground="white", background=accent_color)
        style.configure("Stop.TButton", foreground="white", background="#cc3333")
        
        style.configure("TCombobox", fieldbackground="#333333", background="#333333", foreground="white")
        style.configure("TEntry", fieldbackground="#333333", foreground="white")

    def create_widgets(self):
        # Main container
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Label(header_frame, text="🤖 RalphOS Launcher", style="Header.TLabel").pack(side=tk.LEFT)
        self.status_label = ttk.Label(header_frame, text="Status: Ready", foreground="#4ec9b0")
        self.status_label.pack(side=tk.RIGHT)

        # Top Section: Config and Stats side by side
        top_container = ttk.Frame(main_frame)
        top_container.pack(fill=tk.X, pady=(0, 20))

        # Configuration Area
        config_frame = ttk.LabelFrame(top_container, text=" Configuration ", padding="15")
        config_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # Ralph Selection
        ttk.Label(config_frame, text="Select Ralph:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.ralph_var = tk.StringVar()
        self.ralph_combo = ttk.Combobox(config_frame, textvariable=self.ralph_var, width=30, state="readonly")
        self.ralph_combo.grid(row=0, column=1, sticky=tk.W)

        # Iterations
        ttk.Label(config_frame, text="Iterations:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=10)
        self.iter_var = tk.StringVar(value="25")
        self.iter_entry = ttk.Entry(config_frame, textvariable=self.iter_var, width=10)
        self.iter_entry.grid(row=1, column=1, sticky=tk.W, pady=10)

        # Flags
        self.scrape_only_var = tk.BooleanVar(value=False)
        self.scrape_only_check = tk.Checkbutton(config_frame, text="Scrape Only", variable=self.scrape_only_var, 
                                               bg="#1e1e1e", fg="#d4d4d4", selectcolor="#333333", 
                                               activebackground="#1e1e1e", activeforeground="white")
        self.scrape_only_check.grid(row=2, column=0, columnspan=2, sticky=tk.W)

        # Stats Area
        stats_frame = ttk.LabelFrame(top_container, text=" Pipeline Statistics ", padding="15")
        stats_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.stat_vars = {
            "Total Sources": tk.StringVar(value="0"),
            "Completed": tk.StringVar(value="0"),
            "In Progress": tk.StringVar(value="0"),
            "Pending": tk.StringVar(value="0"),
            "Blocked": tk.StringVar(value="0"),
            "URLs Found": tk.StringVar(value="0"),
            "HTML Scraped": tk.StringVar(value="0"),
            "Builds": tk.StringVar(value="0"),
            "Mods": tk.StringVar(value="0")
        }

        # Grid for stats
        r, c = 0, 0
        for label, var in self.stat_vars.items():
            ttk.Label(stats_frame, text=f"{label}:", font=("Segoe UI", 9, "bold")).grid(row=r, column=c, sticky=tk.W, padx=(0, 5))
            ttk.Label(stats_frame, textvariable=var, foreground="#4ec9b0").grid(row=r, column=c+1, sticky=tk.W, padx=(0, 20))
            c += 2
            if c >= 6:
                c = 0
                r += 1

        # Control Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        self.start_btn = ttk.Button(btn_frame, text="▶ Start Ralph", command=self.start_ralph, style="Action.TButton")
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.stop_btn = ttk.Button(btn_frame, text="🛑 Stop", command=self.stop_ralph, state=tk.DISABLED, style="Stop.TButton")
        self.stop_btn.pack(side=tk.LEFT)

        self.clear_btn = ttk.Button(btn_frame, text="Clear Logs", command=self.clear_logs)
        self.clear_btn.pack(side=tk.RIGHT)

        # Log Monitor
        log_label_frame = ttk.Frame(main_frame)
        log_label_frame.pack(fill=tk.X, pady=(10, 5))
        ttk.Label(log_label_frame, text="Real-time Console Output:").pack(side=tk.LEFT)

        self.log_area = scrolledtext.ScrolledText(main_frame, bg="#000000", fg="#d4d4d4", 
                                                 font=("Consolas", 10), insertbackground="white")
        self.log_area.pack(fill=tk.BOTH, expand=True)
        
        # Color tags
        self.log_area.tag_config("red", foreground="#f44747")
        self.log_area.tag_config("green", foreground="#6a9955")
        self.log_area.tag_config("yellow", foreground="#d7ba7d")
        self.log_area.tag_config("blue", foreground="#569cd6")
        self.log_area.tag_config("cyan", foreground="#4ec9b0")
        self.log_area.tag_config("magenta", foreground="#c586c0")
        self.log_area.tag_config("dim", foreground="#808080")

    def refresh_stats(self):
        try:
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
            sources_path = os.path.join(project_root, "scripts/ralph/sources.json")
            
            if os.path.exists(sources_path):
                import json
                with open(sources_path, 'r') as f:
                    data = json.load(f)
                
                sources = data.get("sources", [])
                
                counts = {
                    "Total Sources": len(sources),
                    "Completed": 0,
                    "In Progress": 0,
                    "Pending": 0,
                    "Blocked": 0,
                    "URLs Found": 0,
                    "HTML Scraped": 0,
                    "Builds": 0,
                    "Mods": 0
                }
                
                for s in sources:
                    status = s.get("status", "pending")
                    if status == "completed": counts["Completed"] += 1
                    elif status == "in_progress": counts["In Progress"] += 1
                    elif status == "blocked": counts["Blocked"] += 1
                    else: counts["Pending"] += 1
                    
                    p = s.get("pipeline", {})
                    counts["URLs Found"] += p.get("urlsFound", 0) or 0
                    counts["HTML Scraped"] += p.get("htmlScraped", 0) or 0
                    counts["Builds"] += p.get("builds", 0) or 0
                    counts["Mods"] += p.get("mods", 0) or 0
                
                for label, var in self.stat_vars.items():
                    var.set(str(counts[label]))
        except Exception as e:
            print(f"Error refreshing stats: {e}")
            
        self.root.after(2000, self.refresh_stats) # Refresh every 2 seconds

    def find_ralphs(self):
        self.ralphs = []
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        
        # Main Ralph
        main_ralph = os.path.join(project_root, "scripts/ralph/ralph.sh")
        if os.path.exists(main_ralph):
            self.ralphs.append({"name": "Main Ralph (Full Pipeline)", "path": main_ralph, "cwd": os.path.dirname(main_ralph)})

        self.ralph_combo["values"] = [r["name"] for r in self.ralphs]
        if self.ralphs:
            self.ralph_combo.current(0)

    def process_log_queue(self):
        try:
            while True:
                line = self.log_queue.get_nowait()
                self.append_log(line)
        except queue.Empty:
            pass
        self.root.after(50, self.process_log_queue)

    def strip_ansi(self, text):
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)

    def append_log(self, text):
        # ANSI sequence parsing for colors
        # This is a basic implementation
        segments = re.split(r'(\x1B\[[0-9;]*m)', text)
        
        current_tags = []
        for seg in segments:
            if not seg: continue
            
            if seg.startswith('\x1B['):
                # Map ANSI codes to tags
                if '31' in seg: current_tags = ["red"]
                elif '32' in seg: current_tags = ["green"]
                elif '33' in seg: current_tags = ["yellow"]
                elif '34' in seg: current_tags = ["blue"]
                elif '35' in seg: current_tags = ["magenta"]
                elif '36' in seg: current_tags = ["cyan"]
                elif '2' in seg: current_tags = ["dim"]
                elif '0' in seg: current_tags = []
            else:
                self.log_area.insert(tk.END, seg, tuple(current_tags))
        
        self.log_area.see(tk.END)

    def start_ralph(self):
        if self.is_running: return

        selected_name = self.ralph_var.get()
        if not selected_name:
            messagebox.showwarning("Warning", "Please select a Ralph to launch")
            return

        selected_ralph = next((r for r in self.ralphs if r["name"] == selected_name), None)
        if not selected_ralph: return

        iters = self.iter_var.get()
        if not iters.isdigit():
            messagebox.showerror("Error", "Iterations must be a number")
            return

        self.is_running = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_label.config(text=f"Status: Running {selected_name}", foreground="#ce9178")
        
        self.log_area.insert(tk.END, f"\n--- Starting {selected_name} at {datetime.now().strftime('%H:%M:%S')} ---\n", "cyan")

        # Build command
        cmd = ["bash", selected_ralph["path"], iters]
        if self.scrape_only_var.get() and "Main Ralph" in selected_name:
            cmd.append("--scrape-only")

        # Run in thread
        threading.Thread(target=self.run_subprocess, args=(cmd, selected_ralph["cwd"]), daemon=True).start()

    def run_subprocess(self, cmd, cwd):
        try:
            # Use pseudo-terminal to force flush output
            import pty
            master, slave = pty.openpty()
            
            # Set environment variable to avoid buffering
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            
            self.process = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdout=slave,
                stderr=slave,
                text=True,
                bufsize=1,
                preexec_fn=os.setsid, # Allow killing process group
                env=env,
                close_fds=True
            )
            
            # We must close the slave in the parent
            os.close(slave)
            
            # Read from master
            with os.fdopen(master, 'r') as f:
                for line in iter(f.readline, ''):
                    self.log_queue.put(line)
            
            return_code = self.process.wait()
            
            self.root.after(0, lambda: self.on_process_complete(return_code))
        except Exception as e:
            self.log_queue.put(f"Error launching process: {str(e)}\n")
            self.root.after(0, lambda: self.on_process_complete(-1))

    def on_process_complete(self, return_code):
        self.is_running = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        
        status_text = "Status: Completed" if return_code == 0 else f"Status: Stopped (Code {return_code})"
        color = "#4ec9b0" if return_code == 0 else "#f44747"
        self.status_label.config(text=status_text, foreground=color)
        
        self.log_area.insert(tk.END, f"\n--- Process finished with code {return_code} ---\n", "dim")
        self.log_area.see(tk.END)

    def stop_ralph(self):
        if self.process and self.is_running:
            if messagebox.askyesno("Confirm Stop", "Are you sure you want to stop the running Ralph?"):
                try:
                    # Kill the whole process group
                    os.killpg(os.getpgid(self.process.pid), signal.SIGINT)
                    self.append_log("\n[GUI] Stopping Ralph... (SIGINT sent)\n")
                except Exception as e:
                    self.append_log(f"\n[GUI] Error stopping process: {str(e)}\n")

    def clear_logs(self):
        self.log_area.delete(1.0, tk.END)

if __name__ == "__main__":
    root = tk.Tk()
    app = RalphLauncher(root)
    root.mainloop()

