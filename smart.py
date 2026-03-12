import os
import sys
import subprocess
import glob
import json
import shutil
import difflib
import time
from datetime import datetime
from pathlib import Path
import warnings

# --- Suppress Deprecation Warnings ---
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning) 
# -------------------------------------

# Dependency Check & Auto-Fix for Pydantic
try:
    import pydantic
    # Google GenAI requires Pydantic v2+. If v1 is found, we must upgrade.
    if int(pydantic.__version__.split('.')[0]) < 2:
        print(f"Detected Pydantic v{pydantic.__version__}. Upgrading to v2+ for Google GenAI compatibility...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pydantic"])
        print("\n\n[SUCCESS] Pydantic upgraded. Please RESTART this script now.")
        sys.exit(0)
except ImportError:
    pass # Will be handled below
except Exception:
    pass # Verify version check logic doesn't crash script

try:
    import google.generativeai as genai
    # FIX: Import protos to access Part and FunctionResponse reliably
    from google.generativeai import protos
    from collections.abc import Iterable
    import requests
    from bs4 import BeautifulSoup
    from duckduckgo_search import DDGS
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.syntax import Syntax
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table
    from rich import print as rprint
    from PIL import Image
except ImportError as e:
    print(f"Missing dependency: {e.name}")
    print("Run: pip install --upgrade google-generativeai requests beautifulsoup4 duckduckgo-search rich pillow pydantic")
    sys.exit(1)

# --- Config & Constants ---
# -------------------------------------------------------------------------
# 🔑 PASTE YOUR API KEY BELOW TO SKIP MANUAL ENTRY
# Example: HARDCODED_API_KEY = "AIzaSy..."
HARDCODED_API_KEY = "AIzaSyAHRV_DuAd60VeOugeis43z3An1k1saYRY" 
# -------------------------------------------------------------------------

API_KEY_ENV_VAR = "GEMINI_API_KEY"
HISTORY_FILE = ".agent_history.json"
IGNORE_DIRS = {'.git', 'node_modules', '__pycache__', 'venv', 'env', '.idea', '.vscode', 'dist', 'build'}
IGNORE_EXTS = {'.pyc', '.bak', '.swp', '.lock', '.png', '.jpg', '.jpeg', '.gif', '.ico'}

console = Console()

# --- Tools ---

class AgentTools:
    @staticmethod
    def scan_project(path: str = ".") -> str:
        """
        Scans the project structure, ignoring common junk folders.
        Returns a tree-like string of the project layout.
        """
        start_path = Path(path)
        tree_str = f"Project Root: {start_path.resolve()}\n"
        
        for root, dirs, files in os.walk(start_path):
            # Modify dirs in-place to skip ignored directories
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            
            level = root.replace(str(start_path), '').count(os.sep)
            indent = ' ' * 4 * (level)
            subindent = ' ' * 4 * (level + 1)
            
            if root != str(start_path):
                tree_str += f"{indent}{os.path.basename(root)}/\n"
            
            for f in files:
                if not any(f.endswith(ext) for ext in IGNORE_EXTS):
                    tree_str += f"{subindent}{f}\n"
                    
        return tree_str

    @staticmethod
    def detect_test_runner(path: str = ".") -> str:
        """
        Analyzes the project to identify how to run tests/code.
        Returns suggested commands based on file evidence.
        """
        p = Path(path)
        if not p.exists():
            return "Path not found."

        recommendations = []
        files = {f.name for f in p.iterdir() if f.is_file()}
        dirs = {d.name for d in p.iterdir() if d.is_dir()}

        # 1. Node.js / JS
        if "package.json" in files:
            try:
                content = json.loads((p / "package.json").read_text(encoding='utf-8'))
                scripts = content.get("scripts", {})
                if "test" in scripts:
                    recommendations.append(f"Node.js (test script): `npm test` (runs: {scripts['test']})")
                if "start" in scripts:
                    recommendations.append(f"Node.js (start script): `npm start` (runs: {scripts['start']})")
            except:
                recommendations.append("Node.js: `npm test` or `node index.js`")

        # 2. Python
        if "pytest.ini" in files or "tests" in dirs:
            recommendations.append("Python (pytest): `pytest`")
        elif "manage.py" in files:
            recommendations.append("Django: `python manage.py test`")
        elif "requirements.txt" in files:
            recommendations.append("Python: Check requirements.txt. Try `pytest` or `python -m unittest`")
        
        # 3. Rust
        if "Cargo.toml" in files:
            recommendations.append("Rust: `cargo test`")

        # 4. Go
        if "go.mod" in files:
            recommendations.append("Go: `go test ./...`")
            
        # 5. Generic / Manual
        main_files = [f for f in files if f.lower() in ['main.py', 'app.py', 'index.js', 'server.js']]
        if main_files:
            recommendations.append(f"Entry Points: Try running `{main_files[0]}` directly.")

        if not recommendations:
            return "No specific test runner detected. Please check documentation or ask user for the command."
        
        return "Detected Test/Run Commands:\n" + "\n".join(recommendations)

    @staticmethod
    def read_file(filepath: str) -> str:
        """Reads a file. Returns content or error message."""
        try:
            p = Path(filepath)
            if not p.exists():
                return f"Error: File '{filepath}' does not exist."
            
            # Basic binary check
            try:
                content = p.read_text(encoding='utf-8')
                return f"--- FILE: {filepath} ---\n{content}\n--- END FILE ---"
            except UnicodeDecodeError:
                return f"Error: '{filepath}' appears to be a binary file. Cannot read."
        except Exception as e:
            return f"Error reading '{filepath}': {e}"

    @staticmethod
    def write_file(filepath: str, content: str) -> str:
        """
        Writes a file with SAFETY features:
        1. Creates a backup (.bak) of the old file.
        2. Returns a diff summary of what changed.
        """
        p = Path(filepath)
        status_msg = ""
        
        # 1. Create Backup if exists
        if p.exists():
            timestamp = datetime.now().strftime("%H%M%S")
            backup_path = p.with_suffix(f".{timestamp}.bak")
            try:
                shutil.copy2(p, backup_path)
                status_msg += f"Backup created: {backup_path.name}\n"
            except Exception as e:
                return f"Error creating backup: {e}. Operation aborted."

        # 2. Write File
        try:
            # Check directory exists
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding='utf-8')
            status_msg += f"Successfully wrote to '{filepath}'."
            return status_msg
        except Exception as e:
            return f"Error writing file: {e}"

    @staticmethod
    def run_shell(command: str) -> str:
        """Runs a shell command. Use caution. Timeout: 10 mins."""
        try:
            # Increased timeout to 10 minutes (600s) as requested
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=600 
            )
            output = f"Exit Code: {result.returncode}\n"
            if result.stdout:
                output += f"STDOUT:\n{result.stdout}\n"
            if result.stderr:
                output += f"STDERR:\n{result.stderr}\n"
            return output
        except subprocess.TimeoutExpired:
            return "Error: Command timed out after 600 seconds (10 minutes)."
        except Exception as e:
            return f"Error running command: {e}"
    
    @staticmethod
    def install_package(package_name: str) -> str:
        """Installs a Python package using pip. Use this for ModuleNotFoundError."""
        try:
            # Increased timeout to 15 minutes (900s) for large installs
            command = f"pip install {package_name}"
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=900
            )
            output = f"Exit Code: {result.returncode}\n"
            if result.stdout:
                output += f"STDOUT:\n{result.stdout}\n"
            if result.stderr:
                output += f"STDERR:\n{result.stderr}\n"
            return output
        except subprocess.TimeoutExpired:
            return "Error: Installation timed out after 900 seconds."
        except Exception as e:
            return f"Error installing package: {e}"

    @staticmethod
    def web_search(query: str) -> str:
        """Searches DuckDuckGo."""
        try:
            results = DDGS().text(query, max_results=4)
            return "\n\n".join([f"**{r['title']}**\n{r['href']}\n{r['body']}" for r in results]) if results else "No results."
        except Exception as e:
            return f"Search failed: {e}"

    @staticmethod
    def read_web_page(url: str) -> str:
        """Scrapes text from a URL."""
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Cleanup
            for tag in soup(["script", "style", "nav", "footer", "iframe"]):
                tag.decompose()
                
            text = soup.get_text(separator='\n')
            clean_text = "\n".join([line.strip() for line in text.splitlines() if line.strip()])
            return clean_text[:10000] # Limit context
        except Exception as e:
            return f"Error reading URL: {e}"

# --- Helper Functions ---

def show_diff(filepath: str, new_content: str):
    """Displays a pretty diff between file on disk and new content."""
    p = Path(filepath)
    if not p.exists():
        console.print(f"[green]New File: {filepath}[/green]")
        return

    old_lines = p.read_text(encoding='utf-8').splitlines()
    new_lines = new_content.splitlines()
    
    diff = difflib.unified_diff(
        old_lines, new_lines, 
        fromfile=f"Original: {filepath}", 
        tofile=f"New: {filepath}", 
        lineterm=""
    )
    
    diff_text = "\n".join(list(diff))
    if diff_text:
        console.print(Panel(Syntax(diff_text, "diff", theme="monokai"), title=f"Proposed Changes for {filepath}"))
    else:
        console.print("[yellow]No content changes detected.[/yellow]")

def extract_image_path(user_input: str):
    """Checks if user input contains image paths (pasted or typed) and loads them."""
    # Handle the case where the entire input is a path (e.g. Drag & Drop with spaces)
    possible_full_path = user_input.strip().strip('"').strip("'")
    if os.path.exists(possible_full_path) and os.path.isfile(possible_full_path):
        try:
            # Check basic extension first to avoid opening random files
            lower_path = possible_full_path.lower()
            if any(lower_path.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp']):
                img = Image.open(possible_full_path)
                console.print(f"[cyan]Image detected (direct path): {possible_full_path}[/cyan]")
                return "", img
        except:
            pass # Not an image, proceed to word splitting

    words = user_input.split()
    cleaned_words = []
    img_obj = None
    
    for word in words:
        # Strip quotes that terminals might add
        clean_word = word.strip('"').strip("'")
        path_to_check = None

        if word.startswith("img:"):
            path_to_check = word[4:].strip('"').strip("'")
        elif os.path.exists(clean_word) and os.path.isfile(clean_word):
            # Check for image extensions
            if any(clean_word.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp']):
                path_to_check = clean_word

        if path_to_check:
            try:
                # Load image
                if not img_obj: # Prioritize first image found
                    img_obj = Image.open(path_to_check)
                    console.print(f"[cyan]Image detected: {path_to_check}[/cyan]")
                    continue # Skip adding this word to text context
            except Exception as e:
                console.print(f"[red]Failed to load image {path_to_check}: {e}[/red]")
                # If fail, treat as text
                cleaned_words.append(word)
        else:
            cleaned_words.append(word)
            
    return " ".join(cleaned_words), img_obj

# --- Main Setup ---

SYSTEM_PROMPT = """
You are a Senior AI DevOps & Coding Agent.
You operate in a terminal. You have access to files, the web, and shell commands.

BEHAVIORAL RULES:
1.  **Discovery First**: If asked to "fix the bug", first use `scan_project` or `read_file` to understand the code.
2.  **Safety**: You cannot run commands or write files without approval. Explain your plan clearly before asking to execute.
3.  **Backups**: When you use `write_file`, the system automatically backs up the old file. You don't need to manually copy it.
4.  **Conciseness**: Give short, actionable responses. Use Markdown.
5.  **Vision**: If the user provides an image, analyze it for UI bugs, error messages, or layout issues.
6.  **Testing Protocol**: 
    - If asked to "test" or "verify", do NOT complain about unknown output. 
    - Use `detect_test_runner` to find standard test commands (pytest, npm test, etc.).
    - If no test suite is found, propose running the main entry point (e.g. `python main.py`) to check for crashes.
    - Your job is to run the command and report the *Actual Output* (exit code, errors).
7.  **Dependency Management**: If the user needs a library (e.g., 'ModuleNotFoundError'), use 'install_package' to install it. Always ask first.
8.  **Anti-Repetition & Memory**:
    - Do NOT read the same file twice in a row unless the content has changed.
    - Do NOT try the same failing command twice. If something fails, analyze the error and try a different approach.
    - Remember what you have already scanned or read in the conversation history.
9.  **Quality & References**:
    - When fixing code, provide the BEST industry-standard solution, not just a quick patch.
    - Explain WHY a fix works.
    - If possible, reference standard libraries or official documentation (e.g., "According to the Python docs...") in your explanation.
10. **Self-Correction**:
    - If a tool fails, do NOT repeat the exact same call. Change parameters, ask for clarification, or try a different tool.

When writing code, provide the COMPLETE file content, not just snippets, unless explicitly asked for a patch.
"""

def select_best_model():
    """Dynamically finds the best available model for the API key."""
    console.print("[dim]Scanning available models...[/dim]")
    try:
        # Get all models that support generating content
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    except Exception as e:
        console.print(f"[yellow]Warning: Could not list models. Defaulting to 'gemini-1.5-flash'. ({e})[/yellow]")
        return 'gemini-1.5-flash'

    # Preference list - Prioritizing 3.0 Pro and 2.5 Flash as requested
    priorities = [
        'models/gemini-3.0-pro',
        'models/gemini-3.0-pro-latest',
        'models/gemini-2.5-flash',
        'models/gemini-2.5-flash-latest',
        'models/gemini-2.0-flash-exp',    # Experimental
        'models/gemini-1.5-pro',
        'models/gemini-1.5-pro-latest',
        'models/gemini-1.5-flash',
        'models/gemini-1.5-flash-latest',
    ]
    
    for pref in priorities:
        if pref in available_models:
            return pref.replace('models/', '') # Clean the name
            
    # Fallback to whatever is found if none of the above exist
    if available_models:
        fallback = available_models[0].replace('models/', '')
        console.print(f"[dim]Preferred models not found. Fallback to: {fallback}[/dim]")
        return fallback

    return 'gemini-1.5-flash' # Absolute fallback

def main():
    api_key = os.environ.get(API_KEY_ENV_VAR)
    
    # 1. Try Hardcoded Key First
    if HARDCODED_API_KEY and HARDCODED_API_KEY.strip() != "":
        api_key = HARDCODED_API_KEY
    
    # --- Manual Key Entry Fallback ---
    if not api_key:
        console.print(Panel("[bold yellow]Environment Variable 'GEMINI_API_KEY' not found.[/bold yellow]\nDon't worry, you can paste it below.", title="Configuration Check"))
        api_key = Prompt.ask("🔑 Paste your Gemini API Key here (hidden)", password=True)
        if not api_key:
            console.print("[red]No key provided. Exiting.[/red]")
            return
        os.environ[API_KEY_ENV_VAR] = api_key
    # ---------------------------------

    genai.configure(api_key=api_key)
    
    # Auto-select best model
    model_name = select_best_model()
    console.print(f"[dim]Using Model: {model_name}[/dim]")
    
    tools = [
        AgentTools.scan_project,
        AgentTools.read_file,
        AgentTools.write_file,
        AgentTools.run_shell,
        AgentTools.web_search,
        AgentTools.read_web_page,
        AgentTools.detect_test_runner,
        AgentTools.install_package # New Tool
    ]
    
    tools_map = {func.__name__: func for func in tools}
    
    try:
        model = genai.GenerativeModel(
            model_name=model_name,
            tools=tools,
            system_instruction=SYSTEM_PROMPT
        )
        
        chat = model.start_chat(enable_automatic_function_calling=False)
    except Exception as e:
        console.print(f"[bold red]Initialization Error:[/bold red] {e}")
        console.print("[yellow]Tip: This usually means a Pydantic version conflict. The script should have auto-fixed this. Please RESTART the script.[/yellow]")
        return
    
    console.print(Panel(f"[bold green]Smart AI Agent v3.0 Online[/bold green]\nModel: {model_name}\n[dim]Timeouts: Shell=10m, Install=15m[/dim]\n[bold yellow]NEW:[/bold yellow] Type 'paste' to enter multi-line text.", title="System Ready"))

    while True:
        try:
            # Updated Prompt
            user_input = Prompt.ask("\n[bold blue]User[/bold blue] (type 'paste' for multiline)")
            
            # --- Multiline Paste Logic ---
            if user_input.lower().strip() == 'paste':
                console.print(Panel("[bold yellow]Multi-line Mode[/bold yellow]\nPaste your text below.\nType [bold red]EOF[/bold red] on a new line to finish.", border_style="yellow"))
                lines = []
                while True:
                    try:
                        line = input()
                    except EOFError:
                        break
                    if line.strip().upper() == 'EOF':
                        break
                    lines.append(line)
                user_input = "\n".join(lines)
                console.print(f"[dim]Received {len(lines)} lines of input.[/dim]")
            # -----------------------------
            
            if user_input.lower() in ['exit', 'quit']:
                break
            if user_input.lower() == 'clear':
                chat = model.start_chat(enable_automatic_function_calling=False)
                console.clear()
                console.print("[yellow]Memory wiped.[/yellow]")
                continue

            # Check for image syntax "img:./screenshot.png"
            text_prompt, image_obj = extract_image_path(user_input)
            
            if not text_prompt.strip() and not image_obj:
                continue

            # Build message payload
            message_parts = [text_prompt]
            if image_obj:
                message_parts.append(image_obj)

            with Progress(SpinnerColumn(), TextColumn("[cyan]{task.description}"), transient=True) as progress:
                progress.add_task("Thinking...", total=None)
                response = chat.send_message(message_parts)

                # TOOL LOOP
                # Robustly check if any part of the response is a function call
                while response.parts and any(part.function_call for part in response.parts):
                    
                    # 1. Handle mixed content: Print any text that came before/with the tool use
                    for part in response.parts:
                        # Safely check for text vs function call
                        try:
                             # Check if it is a function call first to avoid error
                            if part.function_call:
                                continue
                            if part.text:
                                console.print(Markdown(part.text))
                        except:
                            # If accessing part.text fails, it's likely a complex object; skip it
                            pass
                    
                    # 2. Extract the function call
                    # We grab the first function call found (Gemini usually executes sequentially)
                    fc_part = next(part for part in response.parts if part.function_call)
                    fc = fc_part.function_call
                    fn_name = fc.name
                    fn_args = dict(fc.args)
                    
                    progress.stop()
                    
                    # INTERCEPT: Show Diffs for write_file
                    if fn_name == 'write_file':
                        console.print(f"[bold yellow]⚠️  AI Request: Write File '{fn_args.get('filepath')}'[/bold yellow]")
                        show_diff(fn_args.get('filepath'), fn_args.get('content'))
                        confirm = Confirm.ask("Apply these changes?")
                    elif fn_name == 'run_shell':
                        console.print(f"[bold red]⚠️  AI Request: Run Command[/bold red]")
                        console.print(Panel(fn_args.get('command'), title="Shell Command"))
                        confirm = Confirm.ask("Execute this?")
                    elif fn_name == 'install_package':
                        console.print(f"[bold red]⚠️  AI Request: Install Package[/bold red]")
                        console.print(Panel(f"pip install {fn_args.get('package_name')}", title="Installation Command"))
                        confirm = Confirm.ask("Execute this?")
                    else:
                        console.print(f"[dim]Auto-running: {fn_name}[/dim]")
                        confirm = True
                    
                    if confirm:
                        try:
                            result = tools_map[fn_name](**fn_args)
                        except Exception as e:
                            result = f"Tool Error: {e}"
                    else:
                        result = "User denied action."
                        console.print("[red]Action cancelled.[/red]")

                    progress.start()
                    
                    # Feed result back - FIX: Use protos to access Part and FunctionResponse
                    response = chat.send_message(
                        protos.Part(
                            function_response=protos.FunctionResponse(
                                name=fn_name,
                                response={'result': result}
                            )
                        )
                    )

            # Display final text
            # Use try/except to avoid "Could not convert part.function_call to text" crashes
            try:
                if response.text:
                    console.print(Markdown(response.text))
            except Exception:
                # Fallback: Manually print only the text parts
                for part in response.parts:
                    if part.text:
                        console.print(Markdown(part.text))
                
        except KeyboardInterrupt:
            console.print("\n[yellow]Session interrupted. Type 'exit' to quit.[/yellow]")
        except Exception as e:
            console.print(f"[red]System Error: {e}[/red]")

if __name__ == "__main__":
    main()