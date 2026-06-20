import os
import sys
import subprocess
import threading
import signal
import time

def log_stream(stream, prefix, color_code):
    """Reads a stream line by line and prints it with a colored prefix."""
    # Color reset code
    reset = "\033[0m"
    try:
        for line in iter(stream.readline, ''):
            if not line:
                break
            print(f"{color_code}{prefix}{reset} {line.strip()}")
    except Exception:
        pass

def kill_process_tree(proc):
    """Cleanly terminates a process and all of its children."""
    if not proc or proc.poll() is not None:
        return
    
    try:
        if sys.platform == 'win32':
            # On Windows, taskkill /F /T kills the process and all child processes it spawned (e.g. node spawned by npm.cmd)
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        else:
            # On Unix-like systems, send SIGTERM, wait, then SIGKILL if still alive
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
    except Exception as e:
        # Fallback to direct kill if anything fails
        try:
            proc.kill()
        except Exception:
            pass

def main():
    # Force ANSI escape sequences on Windows Command Prompt if needed
    if sys.platform == 'win32':
        os.system('color')

    # Color codes for clean output formatting
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    RESET = "\033[0m"

    root_dir = os.path.dirname(os.path.abspath(__file__))
    frontend_dir = os.path.join(root_dir, "frontend")

    # Safety checks
    if not os.path.exists(frontend_dir):
        print(f"{RED}Error: 'frontend' folder not found at {frontend_dir}.{RESET}")
        sys.exit(1)

    node_modules_dir = os.path.join(frontend_dir, "node_modules")
    if not os.path.exists(node_modules_dir):
        print(f"{YELLOW}Warning: 'node_modules' not found in frontend folder. Running 'npm install' first...{RESET}")
        try:
            subprocess.run("npm install", shell=True, cwd=frontend_dir, check=True)
        except subprocess.CalledProcessError as e:
            print(f"{RED}Error: 'npm install' failed with exit code {e.returncode}.{RESET}")
            sys.exit(1)

    print(f"{CYAN}🚀 Starting Contextualizing Lectures Dev Servers...{RESET}")
    print(f"Press {YELLOW}Ctrl+C{RESET} to stop both servers safely.\n")

    # Start FastAPI Backend Server
    # Using sys.executable guarantees we use the same virtualenv/python environment
    backend_proc = subprocess.Popen(
        [sys.executable, "server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        cwd=root_dir
    )

    # Start Frontend React Dev Server
    # Using shell=True allows npm to be resolved natively on Windows/Unix alike
    frontend_proc = subprocess.Popen(
        "npm run dev",
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        cwd=frontend_dir
    )

    # Start non-blocking logging threads
    t1 = threading.Thread(target=log_stream, args=(backend_proc.stdout, "[Backend]", CYAN), daemon=True)
    t2 = threading.Thread(target=log_stream, args=(backend_proc.stderr, "[Backend-Err]", RED), daemon=True)
    t3 = threading.Thread(target=log_stream, args=(frontend_proc.stdout, "[Frontend]", GREEN), daemon=True)
    t4 = threading.Thread(target=log_stream, args=(frontend_proc.stderr, "[Frontend-Err]", RED), daemon=True)

    for t in [t1, t2, t3, t4]:
        t.start()

    # Automatically open web browser once servers are initialized
    def open_browser():
        time.sleep(1.5)
        if backend_proc.poll() is None and frontend_proc.poll() is None:
            print(f"\n{GREEN}🌍 Opening browser at http://localhost:5173 ...{RESET}\n")
            import webbrowser
            webbrowser.open("http://localhost:5173")

    threading.Thread(target=open_browser, daemon=True).start()

    shutdown_called = False

    def shutdown():
        nonlocal shutdown_called
        if shutdown_called:
            return
        shutdown_called = True
        print(f"\n{YELLOW}🛑 Stopping development servers gracefully...{RESET}")
        kill_process_tree(backend_proc)
        kill_process_tree(frontend_proc)
        print(f"{GREEN}✓ Both dev servers stopped cleanly.{RESET}")

    # Register OS signals for clean termination
    def signal_handler(sig, frame):
        shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Keep main thread alive and monitor execution
        while True:
            # Check if either process died unexpectedly
            backend_code = backend_proc.poll()
            frontend_code = frontend_proc.poll()

            if backend_code is not None:
                print(f"{RED}Backend server exited unexpectedly with code {backend_code}.{RESET}")
                break
            if frontend_code is not None:
                print(f"{RED}Frontend server exited unexpectedly with code {frontend_code}.{RESET}")
                break

            time.sleep(1)

    except KeyboardInterrupt:
        pass
    finally:
        shutdown()

if __name__ == "__main__":
    main()
