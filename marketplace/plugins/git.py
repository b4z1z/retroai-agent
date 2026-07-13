import subprocess
import os

OUTIL = {
    "name": "git",
    "description": "Helper Git (status, diff, log, commit, push, branch, etc.)",
    "parameters": {
        "type": "object",
        "properties": {
            "cmd": {"type": "string", "description": "Commande: status, diff, log, commit, push, pull, branch, add, diff-staged, stash"},
            "args": {"type": "string", "description": "Arguments additionnels", "default": ""},
            "path": {"type": "string", "description": "Chemin du repo (défaut: dossier courant)", "default": "."}
        },
        "required": ["cmd"]
    }
}

DANGEREUX = True

def run_git(cmd, path):
    try:
        result = subprocess.run(cmd, cwd=path, capture_output=True, text=True, shell=True, timeout=30)
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", "Timeout", 1
    except Exception as e:
        return "", str(e), 1

def executer(args, config):
    cmd = args.get("cmd", "")
    args_str = args.get("args", "")
    path = args.get("path", ".")
    
    if not os.path.isdir(os.path.join(path, ".git")):
        return f"Erreur: pas un repo Git: {path}"
    
    git_cmd = f"git {cmd} {args_str}".strip()
    stdout, stderr, code = run_git(git_cmd, path)
    
    if code != 0 and stderr:
        return f"Erreur (code {code}): {stderr}"
    
    if cmd == "status":
        return stdout or "Propre (working tree clean)"
    elif cmd == "log":
        return stdout or "Aucun commit"
    elif cmd == "diff":
        return stdout or "Pas de changements"
    elif cmd == "diff-staged":
        return run_git("git diff --staged", path)[0] or "Pas de changements indexés"
    elif cmd == "branch":
        return stdout or "Aucune branche"
    elif cmd == "stash":
        return stdout or "Aucun stash"
    elif cmd in ("commit", "push", "pull", "add"):
        return stdout + ("\n" + stderr if stderr else "") or "OK"
    
    return stdout or stderr or "OK"