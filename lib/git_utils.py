import subprocess

terminal_dir = None  # default; main.py will override this


def git_set_terminal_dir(path):
    global terminal_dir
    terminal_dir = path

def run_command(*command_str):
    result = subprocess.run(
        command_str,
        cwd=terminal_dir,
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"bash error: {result.stderr}")
    return result.stdout.strip()

def check_git_up_to_date(output):
    return (("Your branch is up-to-date" in output) or ("Already up-to-date" in output))
        
def check_git_clean(output):
    return ("working tree clean"in output)

def git_pull():
    return run_command("git", "pull")
def git_add():
    return run_command("git", "add", ".")
def git_commit(str):
    return run_command("git", "commit", "-m", str)
def git_push():
    return run_command("git", "push")
def git_fetch():
    return run_command("git", "fetch","origin")
def git_status():
    return run_command("git", "status")