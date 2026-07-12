"""
Plugin exemple 1 : METEO en temps reel (montre un appel RESEAU).

API utilisee : wttr.in — gratuite, SANS cle, sans inscription.
Demande a BAZIZ.IA : "quel temps fait-il a Fes ?" -> il appelle get_weather.
"""

OUTIL = {
    "name": "get_weather",
    "description": (
        "Get the CURRENT weather for a city (temperature, conditions, wind). "
        "Use it whenever the user asks about the weather."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "City name, e.g. 'Fes' or 'Paris'",
            }
        },
        "required": ["city"],
    },
}

DANGEREUX = False  # simple lecture publique : pas de confirmation


def executer(args: dict, config) -> str:
    import requests

    ville = str(args.get("city", "")).strip()
    if not ville:
        return "Error: no city given."
    try:
        # format=3 -> une ligne lisible : "Fes: ☀️ +31°C". j1 dispo si besoin.
        reponse = requests.get(
            f"https://wttr.in/{ville}",
            params={"format": "3", "m": ""},
            headers={"User-Agent": "curl"},  # wttr.in sert du texte a curl
            timeout=10,
        )
        if reponse.status_code != 200:
            return f"Error: weather service replied HTTP {reponse.status_code}."
        return reponse.text.strip()
    except Exception as exc:
        return f"Error: could not reach the weather service ({exc})."
