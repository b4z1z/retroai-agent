import os
import json
import shutil

OUTIL = {
    "name": "file_ops",
    "description": "Opérations fichiers : lire, écrire, lister, copier, déplacer, supprimer, chercher",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["read", "write", "list", "copy", "move", "delete", "search", "mkdir"], "description": "Action"},
            "path": {"type": "string", "description": "Chemin fichier/dossier"},
            "content": {"type": "string", "description": "Contenu (pour write)"},
            "dest": {"type": "string", "description": "Destination (copy/move)"},
            "pattern": {"type": "string", "description": "Motif recherche (search)"},
            "recursive": {"type": "boolean", "description": "Récursif (list/search)", "default": False}
        },
        "required": ["action", "path"]
    }
}

DANGEREUX = True

def executer(args, config):
    action = args.get("action")
    path = args.get("path")
    content = args.get("content", "")
    dest = args.get("dest", "")
    pattern = args.get("pattern", "")
    recursive = args.get("recursive", False)
    
    try:
        if action == "read":
            if not os.path.isfile(path):
                return f"Erreur: {path} n'est pas un fichier"
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        
        elif action == "write":
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Écrit: {path} ({len(content)} chars)"
        
        elif action == "list":
            if not os.path.isdir(path):
                return f"Erreur: {path} n'est pas un dossier"
            items = []
            if recursive:
                for root, dirs, files in os.walk(path):
                    for f in files:
                        items.append(os.path.join(root, f))
            else:
                items = os.listdir(path)
            return "\n".join(sorted(items)) or "(vide)"
        
        elif action == "mkdir":
            os.makedirs(path, exist_ok=True)
            return f"Dossier créé: {path}"
        
        elif action == "copy":
            if not dest:
                return "Erreur: dest requis"
            if os.path.isdir(path):
                shutil.copytree(path, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(path, dest)
            return f"Copié: {path} -> {dest}"
        
        elif action == "move":
            if not dest:
                return "Erreur: dest requis"
            shutil.move(path, dest)
            return f"Déplacé: {path} -> {dest}"
        
        elif action == "delete":
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            return f"Supprimé: {path}"
        
        elif action == "search":
            if not pattern:
                return "Erreur: pattern requis"
            results = []
            if recursive:
                for root, dirs, files in os.walk(path):
                    for f in files:
                        if pattern.lower() in f.lower():
                            results.append(os.path.join(root, f))
            else:
                for f in os.listdir(path):
                    if pattern.lower() in f.lower():
                        results.append(os.path.join(path, f))
            return "\n".join(results) or "Aucun résultat"
        
        return f"Action inconnue: {action}"
    
    except Exception as e:
        return f"Erreur: {e}"