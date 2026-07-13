import secrets
import string

OUTIL = {
    "name": "password",
    "description": "Générateur de mots de passe sécurisés",
    "parameters": {
        "type": "object",
        "properties": {
            "length": {"type": "integer", "description": "Longueur du mot de passe", "default": 16},
            "count": {"type": "integer", "description": "Nombre de mots de passe à générer", "default": 1},
            "symbols": {"type": "boolean", "description": "Inclure symboles", "default": True},
            "numbers": {"type": "boolean", "description": "Inclure chiffres", "default": True},
            "uppercase": {"type": "boolean", "description": "Inclure majuscules", "default": True},
            "lowercase": {"type": "boolean", "description": "Inclure minuscules", "default": True},
            "passphrase": {"type": "boolean", "description": "Mode phrase de passe (mots aléatoires)", "default": False},
            "words": {"type": "integer", "description": "Nombre de mots (mode passphrase)", "default": 4}
        }
    }
}

DANGEREUX = False

WORDLIST = [
    "correct", "horse", "battery", "staple", "apple", "banana", "orange", "grape",
    "mountain", "river", "forest", "ocean", "sunset", "sunrise", "cloud", "storm",
    "python", "pythonic", "script", "code", "debug", "compile", "deploy", "server",
    "coffee", "pizza", "burger", "taco", "sushi", "pasta", "salad", "soup",
    "guitar", "piano", "drums", "violin", "flute", "trumpet", "saxophone", "bass",
    "rocket", "planet", "galaxy", "star", "comet", "asteroid", "nebula", "orbit",
    "diamond", "emerald", "ruby", "sapphire", "pearl", "crystal", "amber", "jade"
]

def executer(args, config):
    length = args.get("length", 16)
    count = args.get("count", 1)
    symbols = args.get("symbols", True)
    numbers = args.get("numbers", True)
    uppercase = args.get("uppercase", True)
    lowercase = args.get("lowercase", True)
    passphrase = args.get("passphrase", False)
    words = args.get("words", 4)
    
    if passphrase:
        results = []
        for _ in range(count):
            selected = secrets.SystemRandom().sample(WORDLIST, words)
            pwd = "-".join(selected)
            results.append(pwd)
        return "\n".join(results)
    
    chars = ""
    if lowercase: chars += string.ascii_lowercase
    if uppercase: chars += string.ascii_uppercase
    if numbers: chars += string.digits
    if symbols: chars += "!@#$%^&*()_+-=[]{}|;:,.<>?"
    
    if not chars:
        return "Erreur: au moins un type de caractère requis"
    
    results = []
    for _ in range(count):
        pwd = "".join(secrets.choice(chars) for _ in range(length))
        # S'assurer qu'on a au moins un de chaque type demandé
        if lowercase and not any(c.islower() for c in pwd):
            pwd = secrets.choice(string.ascii_lowercase) + pwd[1:]
        if uppercase and not any(c.isupper() for c in pwd):
            pwd = secrets.choice(string.ascii_uppercase) + pwd[1:]
        if numbers and not any(c.isdigit() for c in pwd):
            pwd = secrets.choice(string.digits) + pwd[1:]
        if symbols and not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in pwd):
            pwd = secrets.choice("!@#$%^&*()_+-=[]{}|;:,.<>?") + pwd[1:]
        results.append(pwd)
    
    return "\n".join(results)