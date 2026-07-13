import requests

OUTIL = {
    "name": "translate",
    "description": "Traducteur via LibreTranslate (gratuit, sans clé API)",
    "parameters": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Texte à traduire"},
            "source": {"type": "string", "description": "Langue source (auto = auto-détection)", "default": "auto"},
            "target": {"type": "string", "description": "Langue cible (ex: fr, en, es, de, it, pt, zh, ja, ko, ar, ru)", "default": "fr"}
        },
        "required": ["text"]
    }
}

DANGEREUX = False

LANGUES = {
    "auto": "Auto", "fr": "Français", "en": "Anglais", "es": "Espagnol", "de": "Allemand",
    "it": "Italien", "pt": "Portugais", "nl": "Néerlandais", "pl": "Polonais", "ru": "Russe",
    "zh": "Chinois", "ja": "Japonais", "ko": "Coréen", "ar": "Arabe", "hi": "Hindi",
    "tr": "Turc", "sv": "Suédois", "da": "Danois", "no": "Norvégien", "fi": "Finnois"
}

def executer(args, config):
    text = args.get("text", "").strip()
    source = args.get("source", "auto")
    target = args.get("target", "fr")
    
    if not text:
        return "Erreur: texte vide"
    
    if len(text) > 5000:
        return "Erreur: texte trop long (max 5000 caractères)"
    
    # Instance LibreTranslate publique (gratuite, sans clé)
    url = "https://libretranslate.de/translate"
    data = {"q": text, "source": source, "target": target, "format": "text"}
    
    try:
        resp = requests.post(url, data=data, timeout=15)
        resp.raise_for_status()
        result = resp.json()
        translated = result.get("translatedText", "")
        
        src_name = LANGUES.get(source, source)
        tgt_name = LANGUES.get(target, target)
        return f"[{src_name} → {tgt_name}]\n{translated}"
    
    except requests.exceptions.Timeout:
        return "Erreur: timeout (LibreTranslate peut être lent)"
    except requests.exceptions.RequestException as e:
        return f"Erreur réseau: {e}"
    except Exception as e:
        return f"Erreur: {e}"