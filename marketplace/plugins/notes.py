import json
import os
from datetime import datetime

NOTES_FILE = os.path.join(os.path.expanduser("~"), ".notes.json")

OUTIL = {
    "name": "notes",
    "description": "Gestionnaire de notes : ajouter, lister, chercher, supprimer",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["add", "list", "search", "delete", "show"], "description": "Action"},
            "title": {"type": "string", "description": "Titre de la note"},
            "content": {"type": "string", "description": "Contenu (pour add)"},
            "query": {"type": "string", "description": "Terme de recherche"},
            "id": {"type": "string", "description": "ID note (show/delete)"}
        },
        "required": ["action"]
    }
}

DANGEREUX = False

def load_notes():
    if os.path.exists(NOTES_FILE):
        with open(NOTES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_notes(notes):
    with open(NOTES_FILE, "w", encoding="utf-8") as f:
        json.dump(notes, f, ensure_ascii=False, indent=2)

def executer(args, config):
    action = args.get("action")
    notes = load_notes()
    
    if action == "add":
        title = args.get("title", "Sans titre")
        content = args.get("content", "")
        note = {
            "id": str(int(datetime.now().timestamp() * 1000)),
            "title": title,
            "content": content,
            "created": datetime.now().isoformat(),
            "updated": datetime.now().isoformat()
        }
        notes.append(note)
        save_notes(notes)
        return f"Note ajoutée (ID: {note['id']}): {title}"
    
    elif action == "list":
        if not notes:
            return "Aucune note"
        out = []
        for n in sorted(notes, key=lambda x: x["updated"], reverse=True):
            preview = n["content"][:60].replace("\n", " ") + ("..." if len(n["content"]) > 60 else "")
            out.append(f"[{n['id']}] {n['title']} - {n['updated'][:16]}\n    {preview}")
        return "\n\n".join(out)
    
    elif action == "search":
        query = args.get("query", "").lower()
        if not query:
            return "Erreur: query requis"
        results = [n for n in notes if query in n["title"].lower() or query in n["content"].lower()]
        if not results:
            return "Aucun résultat"
        out = []
        for n in results:
            preview = n["content"][:80].replace("\n", " ") + ("..." if len(n["content"]) > 80 else "")
            out.append(f"[{n['id']}] {n['title']}\n    {preview}")
        return "\n\n".join(out)
    
    elif action == "show":
        note_id = args.get("id")
        if not note_id:
            return "Erreur: id requis"
        note = next((n for n in notes if n["id"] == note_id), None)
        if not note:
            return "Note introuvable"
        return f"[{note['id']}] {note['title']}\n{note['created'][:16]} -> {note['updated'][:16]}\n\n{note['content']}"
    
    elif action == "delete":
        note_id = args.get("id")
        if not note_id:
            return "Erreur: id requis"
        notes = [n for n in notes if n["id"] != note_id]
        save_notes(notes)
        return f"Note {note_id} supprimée"
    
    return f"Action inconnue: {action}"