# RetroAI Agent

Client CLI **léger** transformant un terminal (Windows, Linux ou macOS) en
**agent autonome** propulsé par l'API **NVIDIA NIM**. Pensé pour rester léger
et tourner même sur une machine modeste.

> 🧩 **N'importe quel modèle du catalogue NVIDIA NIM** — pas seulement Moonshot
> AI. Vous choisissez librement via `NVIDIA_MODEL` dans `.env` : DeepSeek, Llama
> (Meta), Qwen, Mistral, Moonshot… La seule condition est que le modèle supporte
> le **tool-calling** (function calling), dont l'agent a besoin pour agir. La
> liste complète est sur <https://build.nvidia.com/models>. Défaut :
> `nvidia/nemotron-3-ultra-550b-a55b` (raisonnement + tool-calling, rapide).

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

## Prérequis (outils à avoir)

Avant d'installer, il te faut quelques outils de base. **Vérifie** chacun avec
`--version` ; **installe** seulement ceux qui manquent.

### Linux / macOS

| Outil | Vérifier | Installer s'il manque |
|---|---|---|
| **curl** (pour le one-liner) | `curl --version` | `sudo apt install curl` |
| **git** | `git --version` | `sudo apt install git` |
| **Python 3.8+** | `python3 --version` | `sudo apt install python3` |

> 💡 `git` et `python3` sont aussi installés **automatiquement** par le script
> d'installation rapide. En pratique, sur Linux Mint, seul **`curl`** doit être
> présent au départ. Si une commande répond *« command not found »*, installe
> l'outil correspondant avec la commande de droite.

### Windows

| Outil | Vérifier (PowerShell) | Installer s'il manque |
|---|---|---|
| **Git** | `git --version` | [git-scm.com/download/win](https://git-scm.com/download/win) |
| **Python 3.8+** | `python --version` | [python.org/downloads](https://www.python.org/downloads/) — ⚠️ cocher **« Add Python to PATH »** à l'installation |
| **curl / irm** | `irm --help` | déjà inclus dans Windows 10/11 |

> ⚠️ Si `python` ou `git` répond *« n'est pas reconnu… »* après installation,
> **ferme et rouvre** ton terminal (le PATH doit être rechargé). Si ça persiste,
> c'est que l'option *« Add to PATH »* n'a pas été cochée → réinstalle en la
> cochant.

---

## Installation

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

> ⚠️ **`.env` vs `.env.example` — à ne pas confondre :**
>
> | Fichier | Rôle | Suivi par git ? | Votre vraie clé ? |
> |---|---|:---:|:---:|
> | `.env.example` | Modèle public (montre les variables) | ✅ oui | ❌ **jamais** (garder `nvapi-xxxx`) |
> | `.env` | Votre configuration locale réelle | ❌ non (ignoré) | ✅ **oui**, ici |
>
> Concrètement : `cp .env.example .env`, puis éditez **uniquement `.env`**.
> Mettre la clé dans `.env.example` la **publierait sur GitHub** → fuite de
> secret. Ne touchez donc jamais à `.env.example`.

---

## Configuration (`.env`)

| Variable           | Obligatoire | Défaut                                                       | Description                                  |
|--------------------|:-----------:|-------------------------------------------------------------|----------------------------------------------|
| `NVIDIA_API_KEY`   | ✅          | —                                                           | Votre clé API NVIDIA NIM.                    |
| `NVIDIA_BASE_URL`  | ❌          | `https://integrate.api.nvidia.com/v1/chat/completions`      | Endpoint chat/completions.                   |
| `NVIDIA_MODEL`     | ❌          | `nvidia/nemotron-3-ultra-550b-a55b`                         | **N'importe quel** modèle NVIDIA NIM (tool-calling requis). Voir build.nvidia.com/models. |
| `ENABLE_THINKING`  | ❌          | `true`                                                      | Active le mode raisonnement.                 |
| `SHELL_TIMEOUT`    | ❌          | `30`                                                        | Délai max (s) d'une commande shell.          |
| `AUTO_SAFE_COMMANDS` | ❌        | `false`                                                     | Auto-exécute les commandes shell **lecture seule** sûres (`ls`, `cat`, `echo`, `find`, `grep`…) sans confirmation. |

> 🔒 **`AUTO_SAFE_COMMANDS`** : par défaut `false` (toute commande shell est
> confirmée). Si activé, seules les commandes d'une **liste blanche** lecture
> seule s'exécutent sans demander — et **uniquement** si elles ne contiennent
> aucun caractère dangereux (`>`, `|`, `;`, `&`, `$(...)`, `` ` ``) ni flag
> destructeur (`find -exec`, `-delete`…). Au moindre doute, confirmation requise.

---

## Utilisation

```bash
python -m retroai_agent.main
```

### Raccourci : la commande `baziz.ia`

Pour lancer l'agent en tapant simplement **`baziz.ia`** (au lieu de la
commande complète), installez-le **une seule fois**.

**Linux / macOS — méthode recommandée : `pipx`** (commande globale, isolée,
disponible dans tous les terminaux sans activer de venv) :

```bash
sudo apt install pipx     # si pipx n'est pas déjà installé
pipx ensurepath           # ajoute ~/.local/bin au PATH (une fois)
cd retroai-agent
pipx install .            # crée la commande "baziz.ia"
```
Ouvrez ensuite un **nouveau terminal**, puis depuis le dossier du projet :
```bash
baziz.ia
```
> Mise à jour plus tard : `git pull` puis `pipx install --force .`

**Windows — `pip` (dans un venv) :**

```powershell
cd retroai-agent
pip install -e .
baziz.ia
```

> ⚠️ **À savoir** : l'agent lit `.env`, `user_profile.json`,
> `sessions/` et `COMMANDES.txt` dans le **dossier courant**.
> Lancez donc `baziz.ia` **depuis le dossier du projet** (ou définissez
> `NVIDIA_API_KEY` comme variable d'environnement système). Si la commande
> n'est pas reconnue, ouvrez un **nouveau terminal** (le PATH doit être
> rechargé après l'installation).

Commandes de l'interface :

| Commande         | Effet                                                        |
|------------------|--------------------------------------------------------------|
| `/help`          | Affiche l'aide (liste des commandes).                        |
| `/tuto`          | Rejoue le tour guidé de prise en main.                       |
| `/continue`      | Reprend une tâche interrompue, ou la session la plus récente.|
| `/sessions`      | Liste les conversations sauvegardées et permet d'en changer. |
| `/new`           | Démarre une nouvelle session (l'ancienne reste sauvegardée). |
| `/reset`         | Vide la conversation courante (équivalent à `/new`).         |
| `/restart`       | Redémarre l'app (recharge le code et la config `.env`).      |
| `/exit`, `/quit` | Quitte proprement.                                           |

Astuces :
- Tapez **`/`** (ou `/?`) pour afficher la liste des commandes à tout moment.
- Une commande partielle propose des **suggestions** (ex. `/c` → `/continue`).
- Un fichier **`COMMANDES.txt`** est généré à la racine à chaque lancement
  (mémo de toutes les commandes, façon `help`).
- Au **tout premier lancement**, un court **tutoriel interactif** (~1 minute,
  aucun appel API) présente les commandes essentielles. Rejouable à tout
  moment avec `/tuto`.

### Sessions multiples (façon Claude Code)

Chaque conversation est sauvegardée **automatiquement** après chaque tour
dans son propre fichier (`sessions/<id>.json`) : rien n'est jamais perdu en
changeant de conversation.

- **`/sessions`** ouvre un menu à flèches (↑/↓, Entrée pour choisir, Échap
  pour annuler) listant toutes vos conversations : titre (déduit du premier
  message), date de dernière activité, nombre de messages.
- **`/new`** démarre une conversation vierge ; l'ancienne reste intacte et
  reste accessible via `/sessions`.
- **`/continue`** reprend une tâche interrompue en cours, sinon recharge la
  session la plus récente — pratique pour reprendre exactement là où vous
  vous étiez arrêté après avoir fermé le terminal.

Tapez n'importe quel autre texte pour dialoguer avec l'agent. Lorsqu'il propose
une écriture de fichier ou une commande shell, il demande **`Confirmer ? (y/n)`** :
seul `y` (ou `o`) valide ; tout le reste annule.

**⏹ Stopper l'agent** : pendant qu'il réfléchit ou utilise des outils, appuyez
sur **`Ctrl+C`** pour **interrompre sans quitter** l'application. La progression
déjà faite est conservée : tapez **`/continue`** pour reprendre là où ça s'est
arrêté. (À l'invite vide, `Ctrl+C` quitte l'application.)

**🖼 Envoyer une image** : le modèle sait analyser des images. Trois façons :

1. **Mentionner le chemin** dans votre message (l'agent la joint automatiquement) :
   ```
   What is in photo.png ?
   Describe @captures/screenshot.jpg in detail
   ```
2. **`/add-image`** → ouvre une **fenêtre de sélection de fichier** pour choisir
   l'image, puis demande votre message.
3. **`/paste`** → envoie l'**image du presse-papiers** (ex. une capture d'écran),
   puis demande votre message.

Formats : png, jpg, jpeg, gif, webp, bmp. Taille max 8 Mo. Vous verrez
`🖼 image attached: <nom>` quand une image est jointe.

> Dépendances pour ces commandes : `/paste` nécessite **Pillow**
> (`pip install pillow`, déjà inclus) ; `/add-image` nécessite **tkinter**
> (Linux : `sudo apt install python3-tk`).

### Profil utilisateur (optionnel)

Au **tout premier lancement**, l'agent propose de renseigner un **pseudo** et
quelques infos pour personnaliser l'expérience (avec votre accord). Ce choix
est mémorisé dans `user_profile.json` (local, ignoré par git) et **n'est plus
redemandé** ensuite.

### Réinitialiser ses données / paramètres

Toutes les données personnelles sont dans des fichiers locaux que vous pouvez
supprimer à tout moment. L'agent les recréera proprement au prochain lancement.

| Pour réinitialiser… | Supprimez | Effet |
|---|---|---|
| Le **pseudo** et les infos perso | `user_profile.json` | la question du profil est **reposée** au prochain lancement |
| **Toutes les conversations** sauvegardées | le dossier `sessions/` | `/sessions` repart à vide |
| Le **tutoriel** (le revoir au prochain lancement) | `tuto_complete.json` | le tour guidé est **rejoué automatiquement** |
| **Tout** d'un coup | les trois | remise à zéro complète |

```bash
# Linux / macOS
rm -r user_profile.json sessions/ tuto_complete.json

# Windows (cmd / PowerShell)
rmdir /s /q sessions & del user_profile.json tuto_complete.json
```

> 💡 Pour démarrer une conversation vierge **sans quitter** (l'ancienne reste
> sauvegardée), tapez `/new` ou `/reset` directement dans l'agent.

### Reprise après une erreur / un timeout

Si l'API échoue (timeout, coupure réseau…), l'agent **réessaie une fois**
automatiquement (sauf en streaming, où la réponse est déjà en partie affichée).
Si l'échec persiste **en pleine tâche**, la progression n'est **pas perdue** :
tapez **`/continue`** pour reprendre là où ça s'est arrêté (chaque conversation
est sauvegardée automatiquement dans `sessions/<id>.json`).

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
 ├── tuto_complete.json   # (généré, local) marqueur : tutoriel déjà vu
 ├── sessions/            # (généré, local) une conversation par fichier
 └── retroai_agent/
     ├── __init__.py
     ├── main.py          # point d'entrée + boucle CLI
     ├── api_client.py    # transport HTTP NVIDIA NIM (retry/backoff, streaming)
     ├── tools.py         # schémas JSON + implémentation des 4 outils
     ├── agent_loop.py    # orchestration tool calling + historique
     ├── config.py        # configuration (variables d'environnement)
     ├── safety.py        # garde-fous et confirmations
     ├── modes.py         # modes d'approbation (normal/auto-edit/plan/auto-all)
     ├── thinking.py      # niveaux d'effort de réflexion (/think)
     ├── sessions.py      # multi-conversations (/continue, /sessions, /new)
     ├── tuto.py          # tutoriel interactif (/tuto)
     ├── profile.py       # profil utilisateur optionnel (pseudo, perso)
     ├── images.py        # support des images en entrée (vision/multimodal)
     ├── image_gen.py     # génération d'images (/create-image, /image)
     ├── files.py         # /add-file, /compose, /write
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

## Tests

Des tests automatisés couvrent les parties **critiques et stables** (sécurité
des commandes shell, configuration, détection d'images). Pour les lancer :

```bash
pip install -e ".[dev]"   # installe pytest
pytest
```

```
tests/
 ├── test_safety.py   # liste blanche + détection de commandes dangereuses
 ├── test_config.py   # validation de la clé, valeurs par défaut, conversions
 └── test_images.py   # détection des chemins d'images, contenu multimodal
```

---

## Auteur

**Made by B4Z1Z** 🖋️
Conçu et développé par **B4Z1Z** — [github.com/b4z1z](https://github.com/b4z1z)

Si vous réutilisez ou partagez ce projet, merci de conserver cette mention.
