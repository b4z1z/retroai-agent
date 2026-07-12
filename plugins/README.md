# 🔌 Plugins BAZIZ.IA

Chaque fichier `.py` de ce dossier ajoute **un outil** à l'agent — sans
toucher au cœur du logiciel. Déposez un fichier, `/restart`, c'est installé.
`/plugins` liste ce qui est chargé.

## Le contrat (~30 lignes)

```python
OUTIL = {                      # ce que le modèle voit (JSON Schema)
    "name": "mon_outil",
    "description": "Ce que fait l'outil et QUAND l'utiliser.",
    "parameters": {
        "type": "object",
        "properties": {"ville": {"type": "string"}},
        "required": ["ville"],
    },
}

DANGEREUX = False              # optionnel. True = confirmation y/n avant
                               # chaque exécution (comme les commandes shell).

def executer(args: dict, config) -> str:
    # args = les arguments choisis par le modèle (dict déjà parsé).
    # config = la configuration de l'app (clé API NVIDIA incluse).
    # Retournez TOUJOURS une chaîne : c'est ce que le modèle lira.
    return "résultat"
```

## Règles d'or

- **Toujours retourner une `str`** — y compris pour les erreurs
  (`return f"Error: ..."`) : ne laissez jamais une exception nue (elle sera
  attrapée, mais un message clair aide le modèle à réagir).
- **`DANGEREUX = True`** dès que l'outil écrit, supprime, envoie ou paye
  quelque chose. Il passera alors par la confirmation y/n et respectera les
  modes d'approbation (`/mode`).
- Un plugin **cassé est ignoré** au démarrage (message d'erreur, l'app
  démarre quand même). Les fichiers commençant par `_` sont ignorés.
- Un plugin ne peut pas **remplacer un outil du cœur** (`read_file`,
  `write_file`, `list_directory`, `run_shell_command`).
- Préférez les **API gratuites sans clé** (ex. `wttr.in` pour la météo).

## Exemples fournis

| Fichier | Outil | Montre comment... |
|---|---|---|
| `meteo.py` | `get_weather` | appeler une API réseau (requests, timeout, erreurs) |
| `calculatrice.py` | `calculate` | faire de la logique pure, sûre (AST, pas d'eval) |

## 🪄 L'astuce ultime

Vous n'avez même pas besoin d'écrire le plugin vous-même — **demandez-le à
BAZIZ.IA** :

> « Crée-toi un plugin qui donne l'heure actuelle »

Il écrit le fichier dans ce dossier, vous faites `/restart`, et il possède ce
pouvoir pour toujours. L'agent s'améliore lui-même.
