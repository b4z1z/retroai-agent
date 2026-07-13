import subprocess
import os

OUTIL = {
    "name": "git_helper",
    "description": "Commandes Git rapides : status, diff, log, commit, push, branch",
    "parameters": {
        "type": "object",
        "properties": {
            "command": {"type": "string", "enum": ["status", "diff", "log", "commit", "push", "pull", "branch", "add"], "description": "Commande git"},
            "message": {"type": "string", "description": "Message de commit (pour commit)"},
            "path": {"type": "string", "description": "Chemin du repo (défaut: dossier courant)"}
        },
        "required": ["command"]
    }
}

DANGEREUX = True

def executer(args, config):
    cmd = args.get("command")
    msg = args.get("message", "")
    path = args.get("path", ".")
    
    if not os.path.isdir(os.path.join(path, ".git")):
        return f"Erreur: {path} n'est pas un repo Git"
    
    def run(git_args):
        try:
            result = subprocess.run(["git"] + git_args, cwd=path, capture_output=True, text=True, timeout=30)
            return result.stdout.strip(), result.stderr.strip(), result.returncode
        except Exception as e:
            return "", str(e), 1
    
    if cmd == "status":
        out, err, _ = run(["status", "--short"])
        return out or "Working tree clean"
    
    elif cmd == "diff":
        out, err, _ = run(["diff"])
        return out or "Aucun changement"
    
    elif cmd == "log":
        out, err, _ = run(["log", "--oneline", "-15"])
        return out or "Historique vide"
    
    elif cmd == "branch":
        out, err, _ = run(["branch", "-v"])
        return out or "Aucune branche"
    
    elif cmd == "add":
        out, err, code = run(["add", "-A"])
        return "Tous les fichiers ajoutés (staged)" if code == 0 else f"Erreur: {err}"
    
    elif cmd == "commit":
        if not msg:
            return "Erreur: message requis pour commit"
        out, err, code = run(["commit", "-m", msg])
        return out if code == 0 else f"Erreur: {err}"
    
    elif cmd == "push":
        out, err, code = run(["push"])
        return out if code == 0 else f"Erreur: {err}"
    
    elif cmd == "pull":
        out, err, code = run(["pull"])
        return out if code == 0 else f"Erreur: {err}"
    
    return f"Commande inconnue: {cmd}"