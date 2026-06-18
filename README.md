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

> **Prérequis** : `git` et Python 3.8+ installés.

### ⚡ Installation rapide (une ligne)

**Linux / macOS** (dans un terminal) :

```bash
curl -fsSL https://raw.githubusercontent.com/b4z1z/retroai-agent/main/scripts/install.sh | sh
```

**Windows** (dans PowerShell) :

```powershell
irm https://raw.githubusercontent.com/b4z1z/retroai-agent/main/scripts/install.ps1 | iex
```

Le script clone le dépôt, installe les dépendances, crée la commande `baziz.ia`
et prépare le fichier `.env`. Il ne reste qu'à y mettre votre clé API.

---

### 🛠️ Installation manuelle

<details>
<summary><b>Linux / macOS</b></summary>

```bash
# 1. Cloner le dépôt
git clone https://github.com/b4z1z/retroai-agent.git
cd retroai-agent

# 2. (Recommandé) environnement virtuel
python3 -m venv .venv
source .venv/bin/activate

# 3. Installer (crée la commande "baziz.ia")
pip install -e .

# 4. Configurer la clé API
cp .env.example .env
nano .env            # renseigner NVIDIA_API_KEY
```
</details>

<details>
<summary><b>Windows (PowerShell / cmd)</b></summary>

```powershell
# 1. Cloner le dépôt
git clone https://github.com/b4z1z/retroai-agent.git
cd retroai-agent

# 2. (Recommandé) environnement virtuel
python -m venv .venv
.venv\Scripts\activate

# 3. Installer (crée la commande "baziz.ia")
pip install -e .

# 4. Configurer la clé API
copy .env.example .env
notepad .env         # renseigner NVIDIA_API_KEY
```
</details>

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

### Raccourci : la commande `baziz.ia`

Pour lancer l'agent en tapant simplement **`baziz.ia`** (au lieu de la
commande complète), installez le projet en mode éditable **une seule fois** :

```bash
cd retroai-agent
pip install -e .
```

Ensuite, depuis le dossier du projet :

```bash
baziz.ia
```

> ⚠️ **À savoir** : l'agent lit `.env`, `user_profile.json`,
> `session_history.json` et `COMMANDES.txt` dans le **dossier courant**.
> Lancez donc `baziz.ia` **depuis le dossier du projet** (ou définissez
> `NVIDIA_API_KEY` comme variable d'environnement système). Si la commande
> n'est pas reconnue, ouvrez un **nouveau terminal** (le PATH doit être
> rechargé après l'installation).

Commandes de l'interface :

| Commande         | Effet                                                        |
|------------------|--------------------------------------------------------------|
| `/help`          | Affiche l'aide (liste des commandes).                        |
| `/continue`      | Reprend une tâche interrompue ou la session précédente.      |
| `/reset`         | Vide l'historique de conversation.                           |
| `/exit`, `/quit` | Quitte proprement.                                           |

Astuces :
- Tapez **`/`** (ou `/?`) pour afficher la liste des commandes à tout moment.
- Une commande partielle propose des **suggestions** (ex. `/c` → `/continue`).
- Un fichier **`COMMANDES.txt`** est généré à la racine à chaque lancement
  (mémo de toutes les commandes, façon `help`).

Tapez n'importe quel autre texte pour dialoguer avec l'agent. Lorsqu'il propose
une écriture de fichier ou une commande shell, il demande **`Confirmer ? (y/n)`** :
seul `y` (ou `o`) valide ; tout le reste annule.

### Profil utilisateur (optionnel)

Au **tout premier lancement**, l'agent propose de renseigner un **pseudo** et
quelques infos pour personnaliser l'expérience (avec votre accord). Ce choix
est mémorisé dans `user_profile.json` (local, ignoré par git) et **n'est plus
redemandé** ensuite. Pour que la question soit reposée, supprimez ce fichier :

```bash
rm user_profile.json        # Windows (cmd) : del user_profile.json
```

### Reprise après une erreur / un timeout

Si l'API échoue (timeout, coupure réseau…), l'agent **réessaie une fois**
automatiquement. Si l'échec persiste **en pleine tâche**, la progression
n'est **pas perdue** : tapez **`/continue`** pour reprendre là où ça s'est
arrêté (la conversation est sauvegardée dans `session_history.json`).

---

## Architecture

```
retroai-agent/
 ├── README.md
 ├── requirements.txt
 ├── pyproject.toml       # packaging + commande "baziz.ia"
 ├── .env.example         # modèle de configuration
 ├── .gitignore
 ├── JOURNAL.txt          # journal de bord (étapes, bugs, décisions)
 ├── COMMANDES.txt        # (généré) mémo des commandes, façon "help"
 ├── user_profile.json    # (généré, local) pseudo + préférences
 ├── session_history.json # (généré, local) conversation pour /continue
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
  shell sans confirmation explicite (`Confirmer ? (y/n)`, défaut = non).
- Détection de commandes dangereuses (`rm -rf`, `mkfs`, `dd`, fork bomb…) avec
  avertissement renforcé.
- En cas d'entrée coupée, la réponse par défaut est **le refus**.

---

## Auteur

**Made by B4Z1Z** 🖋️
Conçu et développé par **B4Z1Z** — [github.com/b4z1z](https://github.com/b4z1z)

Si vous réutilisez ou partagez ce projet, merci de conserver cette mention.
