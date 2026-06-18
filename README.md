# RetroAI Agent

Client CLI **léger** transformant un vieux PC (cible : Core 2 Duo, 4 Go RAM,
Linux Mint XFCE) en terminal pour un **agent autonome** propulsé par l'API
**NVIDIA NIM** (modèle `moonshotai/kimi-k2.6`).

100 % ligne de commande, sans framework lourd. Dépendance principale :
`requests`. L'agent peut lire/écrire des fichiers, lister des répertoires et
exécuter des commandes shell — chaque action sensible étant **confirmée par
l'utilisateur**.

---

## Fonctionnalités

- 🔌 Appels à l'API NVIDIA NIM avec **retry + backoff exponentiel** sur les 429.
- 🧠 Mode *thinking* (raisonnement) activable/désactivable via la config.
- 🛠️ **4 outils** : `read_file`, `write_file`, `list_directory`, `run_shell_command`.
- 🔒 **Sécurisé par défaut** : confirmation interactive obligatoire pour toute
  écriture de fichier ou commande shell ; avertissement renforcé sur les
  commandes dangereuses ; aucun mode « toujours accepter ».
- 👁️ Toutes les actions de l'agent sont visibles dans le terminal.
- ⏱️ Timeout sur les commandes shell (30 s par défaut) pour ne pas geler le PC.

---

## Installation

```bash
# 1. Cloner / copier le projet, puis se placer dedans
cd retroai-agent

# 2. (Recommandé) créer un environnement virtuel
python3 -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Configurer la clé API
cp .env.example .env             # Windows (cmd) : copy .env.example .env
# puis éditer .env et renseigner NVIDIA_API_KEY
```

### Obtenir une clé API

Créez une clé sur [build.nvidia.com](https://build.nvidia.com/) (elle commence
par `nvapi-`). **Ne la mettez jamais en dur dans le code** : elle vit uniquement
dans `.env` (ignoré par git) ou dans une variable d'environnement.

---

## Configuration (`.env`)

| Variable           | Obligatoire | Défaut                                                       | Description                                  |
|--------------------|:-----------:|-------------------------------------------------------------|----------------------------------------------|
| `NVIDIA_API_KEY`   | ✅          | —                                                           | Votre clé API NVIDIA NIM.                    |
| `NVIDIA_BASE_URL`  | ❌          | `https://integrate.api.nvidia.com/v1/chat/completions`      | Endpoint chat/completions.                   |
| `NVIDIA_MODEL`     | ❌          | `moonshotai/kimi-k2.6`                                       | Modèle interrogé.                            |
| `ENABLE_THINKING`  | ❌          | `true`                                                      | Active le mode raisonnement.                 |
| `SHELL_TIMEOUT`    | ❌          | `30`                                                        | Délai max (s) d'une commande shell.          |

---

## Utilisation

```bash
python -m retroai_agent.main
```

Commandes de l'interface :

| Commande         | Effet                                  |
|------------------|----------------------------------------|
| `/help`          | Affiche l'aide.                        |
| `/reset`         | Vide l'historique de conversation.     |
| `/exit`, `/quit` | Quitte proprement.                     |

Tapez n'importe quel autre texte pour dialoguer avec l'agent. Lorsqu'il propose
une écriture de fichier ou une commande shell, il vous demande **`[y/N]`** :
seul `y` (ou `o`) valide ; tout le reste annule.

---

## Architecture

```
retroai-agent/
 ├── README.md
 ├── requirements.txt
 ├── .env.example         # modèle de configuration
 ├── .gitignore
 ├── JOURNAL.txt          # journal de bord (étapes, bugs, décisions)
 └── retroai_agent/
     ├── __init__.py
     ├── main.py          # point d'entrée + boucle CLI
     ├── api_client.py    # transport HTTP NVIDIA NIM (retry/backoff)
     ├── tools.py         # schémas JSON + implémentation des 4 outils
     ├── agent_loop.py    # orchestration tool calling + historique
     ├── config.py        # configuration (variables d'environnement)
     ├── safety.py        # garde-fous et confirmations
     ├── profile.py       # profil utilisateur optionnel (pseudo, perso)
     └── ui.py            # affichage terminal (rich, style Claude Code)
```

> L'interface utilise **`rich`** si disponible (panneaux, Markdown, couleurs,
> spinner). Si `rich` n'est pas installé, l'affichage bascule automatiquement
> en texte simple — le projet reste 100 % fonctionnel.

Chaque module a une **responsabilité unique**. Le flux d'un échange :

```
main.py  ──saisie──>  agent_loop.py  ──requête──>  api_client.py  ──>  NVIDIA NIM
                           │                                              │
                           │  <────────────── réponse (+ tool_calls) ─────┘
                           │
                           ├─ exécute l'outil via tools.py (+ safety.py)
                           └─ réinjecte le résultat en role "user"  (piège NIM)
```

> ⚠️ **Particularité NVIDIA NIM** : l'endpoint rejette le rôle `tool`. Les
> résultats d'outils sont donc réinjectés sous le rôle `user`, au format
> `[Resultat de l'outil <nom>]\n<resultat>` (voir `agent_loop.py`).

---

## Sécurité

- La clé API n'est **jamais** écrite en dur ; lue via `config.py`.
- Comportement **ultra-sécurisé par défaut** : aucune écriture ni commande
  shell sans confirmation explicite (`y/N`, défaut = non).
- Détection de commandes dangereuses (`rm -rf`, `mkfs`, `dd`, fork bomb…) avec
  avertissement renforcé.
- En cas d'entrée coupée, la réponse par défaut est **le refus**.
