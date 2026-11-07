import os, json, base64, requests, sys, subprocess, time, datetime, threading
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.markdown import Markdown
from rich.text import Text
from rich.table import Table
from rich.syntax import Syntax
from rich.live import Live
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse

# ─── ⚙️ CONFIG ───
CONFIG_FILE = os.path.expanduser("~/.lauda_config.json")
SESSION_FILE = os.path.expanduser("~/.lauda_session.json")
console = Console()
DRY_RUN = "--dry-run" in sys.argv
AUTOPILOT = False
WEB_SERVER_RUNNING = False
ACTIVE_PROVIDER = ""
ACTIVE_MODEL = ""
SESSION_TOKENS = 0

PROVIDERS = {
    "openrouter": {"base_url": "https://openrouter.ai/api/v1", "api_key": "", "models": []},
    "groq": {"base_url": "https://api.groq.com/openai/v1", "api_key": "", "models": []},
    "cerebras": {"base_url": "https://api.cerebras.ai/v1", "api_key": "", "models": []},
    "mistral": {"base_url": "https://api.mistral.ai/v1", "api_key": "", "models": []},
    "gemini": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "api_key": "", "models": []},
}

# ─── 🔍 FETCH MODELS ───
def fetch_models(pname):
    pdata = PROVIDERS.get(pname)
    if not pdata or not pdata["api_key"]: return []
    headers = {"Authorization": f"Bearer {pdata['api_key']}"}
    base = pdata["base_url"].rstrip("/")
    try:
        if pname == "openrouter":
            r = requests.get(f"{base}/models", headers=headers, timeout=15)
            r.raise_for_status()
            free = [m["id"] for m in r.json().get("data", []) 
                    if m.get("pricing", {}).get("prompt") == "0" 
                    and "tools" in m.get("supported_parameters", [])]
            if free: pdata["models"] = free

        elif pname == "groq":
            known = ["llama-3.3-70b-versatile", "openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen-qwq-32b"]
            r = requests.get(f"{base}/models", headers=headers, timeout=15)
            live = [m["id"] for m in r.json().get("data", [])]
            pdata["models"] = [m for m in known if m in live]

        elif pname == "cerebras":
            r = requests.get(f"{base}/models", headers=headers, timeout=15)
            live = [m["id"] for m in r.json().get("data", [])]
            pdata["models"] = [m for m in ["qwen-3.8-27b", "gpt-oss-120b"] if m in live]

        elif pname == "mistral":
            r = requests.get(f"{base}/models", headers=headers, timeout=15)
            live = [m["id"] for m in r.json().get("data", [])]
            pdata["models"] = [m for m in ["codestral", "mistral-medium-3-5-128b"] if m in live]

        elif pname == "gemini":
            pdata["models"] = ["gemini-3.8-flash"]
        return pdata["models"]
    except Exception:
        return []

# ─── 🔐 CONFIG ───
def load_config():
    global ACTIVE_PROVIDER, ACTIVE_MODEL, AUTOPILOT
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                cfg = json.load(f)
                for p, d in cfg.get("providers", {}).items():
                    if p in PROVIDERS:
                        PROVIDERS[p]["api_key"] = d.get("api_key", "")
                        PROVIDERS[p]["models"] = d.get("models", [])
                ACTIVE_PROVIDER = cfg.get("active_provider", "")
                ACTIVE_MODEL = cfg.get("active_model", "")
                AUTOPILOT = cfg.get("autopilot", False)
                return True
        except: pass
    return False

def save_config():
    cfg = {
        "providers": {p: {"api_key": d["api_key"], "models": d["models"]} for p, d in PROVIDERS.items()},
        "active_provider": ACTIVE_PROVIDER,
        "active_model": ACTIVE_MODEL,
        "autopilot": AUTOPILOT
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

# ─── 🛠️ TOOLS ───
TOOLS = [
    {"type": "function", "function": {"name": "create_folder", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "write_file", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "read_file", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "list_directory", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {"name": "execute_command", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "test_and_debug", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "stdin": {"type": "string"}}, "required": ["path"]}}},
]

def execute_tool(name, args):
    try:
        if name == "create_folder": os.makedirs(args["path"], exist_ok=True); return f"✅ {args['path']}"
        elif name == "write_file":
            d = os.path.dirname(args["path"]); os.makedirs(d, exist_ok=True) if d else None
            if os.path.exists(args["path"]): os.rename(args["path"], args["path"] + ".bak")
            with open(args["path"], "w", encoding="utf-8") as f: f.write(args["content"])
            return f"✅ {args['path']}"
        elif name == "read_file":
            with open(args["path"], "r", encoding="utf-8") as f: return f.read()
        elif name == "list_directory":
            return "\n".join(os.listdir(args.get("path", ".")))
        elif name == "execute_command":
            res = subprocess.run(args["command"], shell=True, capture_output=True, text=True)
            return f"{res.stdout}\n{res.stderr}"
        elif name == "test_and_debug":
            res = subprocess.run(f"python {args['path']}", shell=True, capture_output=True, text=True, input=args.get("stdin", ""))
            if res.returncode != 0: return f"❌ Error:\n{res.stderr}"
            return f"✅ Output:\n{res.stdout}"
    except Exception as e: return f"❌ {str(e)}"

# ─── 🧠 AGENT CORE ───
def run_agent(user_input, messages, is_web=False):
    global AUTOPILOT, ACTIVE_PROVIDER, ACTIVE_MODEL, SESSION_TOKENS
    
    if AUTOPILOT:
        if not hasattr(run_agent, "steps"): run_agent.steps = 0
        run_agent.steps += 1
        if run_agent.steps > 8:
            run_agent.steps = 0; AUTOPILOT = False
            return "🛑 Auto-Pilot limit reached."

    messages.append({"role": "user", "content": user_input})

    chain = [(ACTIVE_PROVIDER, ACTIVE_MODEL)] if ACTIVE_MODEL else []
    for p, d in PROVIDERS.items():
        if d["api_key"]:
            for m in d["models"]:
                if (p, m) not in chain: chain.append((p, m))

    if not chain: return "❌ No models available."

    for pname, model in chain:
        pdata = PROVIDERS[pname]
        headers = {"Authorization": f"Bearer {pdata['api_key']}", "Content-Type": "application/json"}
        payload = {"model": model, "messages": messages, "tools": TOOLS, "tool_choice": "auto"}
        
        try:
            if not is_web:
                with console.status(f"[dim]Thinking with {pname}/{model}...[/]", spinner="dots"):
                    r = requests.post(f"{pdata['base_url']}/chat/completions", headers=headers, json=payload, timeout=45)
            else:
                r = requests.post(f"{pdata['base_url']}/chat/completions", headers=headers, json=payload, timeout=45)

            if r.status_code == 429:
                if not is_web: console.print(f"[yellow]⚠️ {pname} rate limited. Switching...[/]")
                ACTIVE_PROVIDER, ACTIVE_MODEL = "", ""
                continue

            if r.status_code != 200:
                if not is_web: console.print(f"[red]⚠️ {pname} failed ({r.status_code})[/]")
                continue

            data = r.json()
            msg = data["choices"][0]["message"]
            
            # Token Tracking
            if "usage" in data:
                SESSION_TOKENS += data["usage"].get("total_tokens", 0)

            ACTIVE_PROVIDER, ACTIVE_MODEL = pname, model
            save_config()

            if not msg.get("tool_calls"):
                messages.append({"role": "assistant", "content": msg.get("content", "")})
                if is_web: return msg.get("content", "")
                console.print(Panel(Markdown(msg.get("content", "")), title=f"🤖 {pname}/{model}", border_style="cyan"))
                if AUTOPILOT and "TASK COMPLETE" not in msg.get("content", "").upper():
                    return run_agent("Review code. If no bugs, say 'TASK COMPLETE'.", messages, is_web)
                return messages

            messages.append(msg)
            for tc in msg["tool_calls"]:
                fn = tc["function"]["name"]
                args = json.loads(tc["function"]["arguments"])
                
                if not is_web:
                    if fn == "write_file":
                        ext = args["path"].split(".")[-1]
                        console.print(Panel(Syntax(args["content"], ext, theme="monokai"), title=f"📝 {args['path']}", border_style="green"))
                    with console.status(f"[dim]Running {fn}...[/]", spinner="bouncingBar"):
                        res = execute_tool(fn, args)
                    if fn == "test_and_debug":
                        style = "red" if "Error" in res else "green"
                        console.print(Panel(res, title=f"🧪 Test", border_style=style))
                    else:
                        console.print(f"[green]  {res}[/]")
                else:
                    res = execute_tool(fn, args)
                
                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": res})

            return run_agent("Continue. Do NOT summarize.", messages, is_web)

        except Exception as e:
            if not is_web: console.print(f"[red]⚠️ {pname} error: {str(e)[:40]}[/]")
            continue

    return "❌ All providers failed." if is_web else messages

# ─── 🌐 WEB UI ───
HTML_UI = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Lauda Code</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { background: #0d1117; color: #c9d1d9; font-family: monospace; padding: 20px; }
        .container { max-width: 800px; margin: auto; }
        .log { background: #161b22; border-left: 4px solid #58a6ff; padding: 10px; margin: 10px 0; border-radius: 4px; white-space: pre-wrap; }
        .tool { background: #1f6feb; color: white; padding: 5px 10px; border-radius: 12px; display: inline-block; font-size: 12px; margin: 5px 0; }
        .result { background: #1f6feb; color: white; padding: 5px 10px; border-radius: 4px; margin: 5px 0; }
        .input-area { display: flex; gap: 10px; margin-top: 20px; }
        input[type="text"] { flex: 1; padding: 10px; border-radius: 6px; border: 1px solid #30363d; background: #0d1117; color: white; }
        button { padding: 10px 20px; background: #238636; color: white; border: none; border-radius: 6px; cursor: pointer; }
        .status { color: #8b949e; font-size: 12px; margin-bottom: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 Lauda Code</h1>
        <div class="status" id="status">Connecting...</div>
        <div id="output"></div>
        <div class="input-area">
            <input type="text" id="prompt" placeholder="Type a task..." />
            <button onclick="send()">Send</button>
        </div>
    </div>
    <script>
        async function send() {
            const p = document.getElementById('prompt').value;
            if (!p) return;
            const out = document.getElementById('output');
            const status = document.getElementById('status');
            out.innerHTML += `<div class="log">👤 ${p}</div>`;
            document.getElementById('prompt').value = '';
            status.textContent = '🤖 Thinking...';
            
            const res = await fetch('/api?p=' + encodeURIComponent(p));
            const reader = res.body.getReader();
            const dec = new TextDecoder();
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                for (const line of dec.decode(value).split('\\n\\n')) {
                    if (line.startsWith('data: ')) {
                        try {
                            const d = JSON.parse(line.substring(6));
                            if (d.t === 'tool') out.innerHTML += `<div class="tool">🛠️ ${d.n}</div>`;
                            if (d.t === 'res') out.innerHTML += `<div class="result">${d.v}</div>`;
                            if (d.t === 'txt') { out.innerHTML += `<div class="log">🤖 ${d.v}</div>`; status.textContent = 'Ready'; }
                        } catch(e){}
                    }
                }
            }
        }
    </script>
</body>
</html>
"""

class WebHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/api"):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            prompt = q.get("p", [""])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.end_headers()
            
            global execute_tool
            orig = execute_tool
            def web_exec(n, a):
                self.wfile.write(f"data: {json.dumps({'t': 'tool', 'n': n})}\n\n".encode())
                self.wfile.flush()
                r = orig(n, a)
                self.wfile.write(f"data: {json.dumps({'t': 'res', 'v': r[:500]})}\n\n".encode())
                self.wfile.flush()
                return r
            execute_tool = web_exec
            
            msgs = [{"role": "system", "content": "Be concise."}]
            final = run_agent(prompt, msgs, True)
            execute_tool = orig
            self.wfile.write(f"data: {json.dumps({'t': 'txt', 'v': final})}\n\n".encode())
            self.wfile.flush()
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML_UI.encode())

def start_web():
    global WEB_SERVER_RUNNING
    WEB_SERVER_RUNNING = True
    console.print("[green]🌐 http://localhost:8080[/]")
    HTTPServer(('0.0.0.0', 8080), WebHandler).serve_forever()

# ─── 🚀 STARTUP & MENU ───
def startup_menu():
    global ACTIVE_PROVIDER, ACTIVE_MODEL, AUTOPILOT
    
    avail = [p for p, d in PROVIDERS.items() if d["api_key"]]
    if not avail:
        console.print("[red]❌ No API keys found. Run /reset to configure.[/]")
        sys.exit(1)

    console.print(Panel("[bold cyan]Select Provider[/]", border_style="blue", expand=False))
    for i, p in enumerate(avail):
        console.print(f"  [cyan]{i+1}[/]. {p}")

    idx = Prompt.ask("[bold]Choose[/]", choices=[str(i+1) for i in range(len(avail))], default="1")
    ACTIVE_PROVIDER = avail[int(idx)-1]

    models = PROVIDERS[ACTIVE_PROVIDER]["models"]
    if not models:
        console.print(f"[yellow]Fetching models for {ACTIVE_PROVIDER}...[/]")
        models = fetch_models(ACTIVE_PROVIDER)
        if not models:
            console.print("[red]❌ No models found. Check API key.[/]")
            sys.exit(1)

    console.print(f"\n[bold cyan]Select Model ({ACTIVE_PROVIDER})[/]")
    for i, m in enumerate(models):
        console.print(f"  [cyan]{i+1}[/]. {m}")
    
    midx = Prompt.ask("[bold]Choose[/]", choices=[str(i+1) for i in range(len(models))], default="1")
    ACTIVE_MODEL = models[int(midx)-1]
    
    console.print(f"\n[dim]Active: {ACTIVE_PROVIDER} / {ACTIVE_MODEL}[/]")
    if AUTOPILOT: console.print("[yellow]🤖 Auto-Pilot is ON[/]")
    console.print()

def main():
    global AUTOPILOT, ACTIVE_PROVIDER, ACTIVE_MODEL, SESSION_TOKENS
    
    console.print(Panel(Text.from_markup(
        "[bold cyan]🚀 Lauda Code v10.0[/]\n"
        "[dim]Professional AI Coding Agent[/]\n"
        "[green]✔ Multi-Provider · Smart Fallback · Token Tracking[/]"
    ), border_style="bold blue", expand=False))

    if not load_config():
        console.print("[yellow]First setup. Enter keys (empty to skip):[/]\n")
        for p in PROVIDERS:
            k = Prompt.ask(f"[bold]{p}[/]", default="")
            if k: PROVIDERS[p]["api_key"] = k
        save_config()
    
    startup_menu()
    messages = [{"role": "system", "content": "You are Lauda Code. Be concise."}]

    while True:
        try:
            u = console.input("[bold cyan]❯[/] ")
            if not u.strip(): continue
            if u.lower() in ["exit", "quit"]: break
            
            if u.startswith("!"):
                os.system(u[1:]); continue
            
            if u.startswith("/"):
                cmd = u.split()[0].lower()
                if cmd == "/web" and not WEB_SERVER_RUNNING:
                    threading.Thread(target=start_web, daemon=True).start()
                elif cmd == "/autopilot":
                    AUTOPILOT = not AUTOPILOT; save_config()
                    console.print(f"[yellow]Auto-Pilot: {'ON' if AUTOPILOT else 'OFF'}[/]")
                elif cmd == "/reset":
                    if Prompt.ask("[red]Delete config?[/]", choices=["y","n"]) == "y":
                        os.remove(CONFIG_FILE); sys.exit(0)
                elif cmd == "/provider":
                    startup_menu()
                elif cmd == "/keys":
                    t = Table(title="🔑 API Keys")
                    t.add_column("Provider"); t.add_column("Status")
                    for p, d in PROVIDERS.items():
                        t.add_row(p, "✅ Set" if d["api_key"] else "❌ Missing")
                    console.print(t)
                elif cmd == "/status":
                    console.print(f"[bold]Provider:[/] {ACTIVE_PROVIDER}")
                    console.print(f"[bold]Model:[/] {ACTIVE_MODEL}")
                    console.print(f"[bold]Auto-Pilot:[/] {'ON' if AUTOPILOT else 'OFF'}")
                    console.print(f"[bold]Session Tokens:[/] {SESSION_TOKENS}")
                elif cmd == "/clear":
                    messages = [{"role": "system", "content": "You are Lauda Code. Be concise."}]
                    SESSION_TOKENS = 0
                    console.print("[green]🧹 Context cleared[/]")
                elif cmd == "/session":
                    if "save" in u:
                        with open(SESSION_FILE, "w") as f: json.dump(messages, f)
                        console.print("[green]💾 Session saved[/]")
                    elif "load" in u:
                        if os.path.exists(SESSION_FILE):
                            with open(SESSION_FILE, "r") as f: messages = json.load(f)
                            console.print("[green]📂 Session loaded[/]")
                        else: console.print("[red]No session found[/]")
                elif cmd == "/help":
                    console.print("[dim]/web /provider /autopilot /keys /status /clear /session save|load /reset /exit[/]")
                continue
            
            messages = run_agent(u, messages)
            
        except (KeyboardInterrupt, EOFError):
            break

if __name__ == "__main__":
    main()