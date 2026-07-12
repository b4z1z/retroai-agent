"""
Plugin communautaire : DATE ET HEURE actuelles.

Pourquoi ? Un modele de langage ne connait JAMAIS l'heure qu'il est.
"""

OUTIL = {
    "name": "current_datetime",
    "description": (
        "Get the CURRENT local date and time. Use it whenever the user asks "
        "the time, the date, or when computing anything relative to now."
    ),
    "parameters": {"type": "object", "properties": {}},
}

DANGEREUX = False


def executer(args: dict, config) -> str:
    import datetime

    maintenant = datetime.datetime.now()
    return maintenant.strftime("%A %d %B %Y, %H:%M:%S (local time)")
