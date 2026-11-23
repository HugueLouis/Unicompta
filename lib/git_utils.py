import shutil
import subprocess
import os


terminal_dir = None  # default; main.py will override this
GIT_AVAILABLE = shutil.which("git") is not None

def git_set_terminal_dir(path):
    global terminal_dir
    terminal_dir = path

def run_command(*command_str):
    if command_str[0] == "git" and not GIT_AVAILABLE:
        return "git is not installed on this computer"
    try:
        result = result = subprocess.run(
            command_str, cwd=terminal_dir, capture_output=True,
            text=True, encoding="utf-8", errors="replace",
            stdin=subprocess.DEVNULL,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except FileNotFoundError:
        return f"command not found: {command_str[0]}"
    parts = [result.stdout.strip(), result.stderr.strip()]
    return "\n".join(p for p in parts if p)

def check_git_up_to_date(output):
    return (("up-to-date" in output) or ("up to date" in output))

def check_git_clean(output):
    return ("working tree clean" in output)

def git_pull():
    return run_command("git", "pull")
def git_add():
    return run_command("git", "add", ".")
def git_commit(str):
    return run_command("git", "commit", "-m", str)
def git_push():
    return run_command("git", "push")
def git_fetch():
    return run_command("git", "fetch", "origin")
def git_status():
    return run_command("git", "status")

def _run_bytes(args):
    try:
        r = subprocess.run(
            args, cwd=terminal_dir, capture_output=True,
            stdin=subprocess.DEVNULL,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except FileNotFoundError:
        return None
    return r.stdout if r.returncode == 0 else None

def git_show_file(rev, relpath):
    """Content of a file at a given revision (bytes), or None if it doesn't exist there."""
    if not GIT_AVAILABLE:
        return None
    return _run_bytes(["git", "show", f"{rev}:{relpath}"])

def git_log(limit=300):
    """[(hash, date, author, subject)] most recent first."""
    if not GIT_AVAILABLE:
        return []
    out = _run_bytes(["git", "log", f"-n{limit}", "--date=short",
                      "--format=%h%x1f%ad%x1f%an%x1f%s"])
    if not out:
        return []
    rows = []
    for line in out.decode("utf-8", errors="replace").splitlines():
        parts = line.split("\x1f")
        if len(parts) == 4:
            rows.append(tuple(parts))
    return rows