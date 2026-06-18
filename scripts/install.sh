#!/bin/sh
# ============================================================
#  Installateur BAZIZ.IA pour Linux / macOS  (methode : pipx)
#  Usage :
#    curl -fsSL https://raw.githubusercontent.com/b4z1z/retroai-agent/main/scripts/install.sh | sh
#
#  pipx installe la commande "baziz.ia" de facon GLOBALE et ISOLEE :
#    - disponible dans tous les terminaux (pas de venv a activer)
#    - les dependances (requests, rich, prompt_toolkit) sont lues depuis
#      pyproject.toml et installees automatiquement.
# ============================================================
set -e

DEPOT="https://github.com/b4z1z/retroai-agent.git"
DOSSIER="retroai-agent"

echo "==> Installation de BAZIZ.IA (via pipx)..."

# ------------------------------------------------------------------ #
# 1. Prerequis : git, python3, pipx.                                 #
#    Sur Debian/Ubuntu/Mint (apt), on installe ce qui manque.        #
# ------------------------------------------------------------------ #
if command -v apt-get >/dev/null 2>&1; then
    BESOINS=""
    command -v git     >/dev/null 2>&1 || BESOINS="$BESOINS git"
    command -v python3 >/dev/null 2>&1 || BESOINS="$BESOINS python3"
    command -v pipx    >/dev/null 2>&1 || BESOINS="$BESOINS pipx"
    if [ -n "$BESOINS" ]; then
        echo "==> Installation des prerequis :$BESOINS"
        sudo apt-get update
        sudo apt-get install -y $BESOINS
    fi
else
    # Hors apt (ex. macOS avec Homebrew) : on verifie seulement.
    command -v git  >/dev/null 2>&1 || { echo "Erreur : git manquant."; exit 1; }
    command -v pipx >/dev/null 2>&1 || { echo "Erreur : pipx manquant (ex: brew install pipx)."; exit 1; }
fi

# S'assurer que le dossier des commandes pipx (~/.local/bin) est sur le PATH.
pipx ensurepath >/dev/null 2>&1 || true

# ------------------------------------------------------------------ #
# 2. Recuperer le code (cloner, ou mettre a jour si deja present).   #
# ------------------------------------------------------------------ #
if [ -d "$DOSSIER/.git" ]; then
    echo "==> Depot deja present, mise a jour..."
    git -C "$DOSSIER" pull --ff-only
else
    echo "==> Clonage du depot..."
    git clone "$DEPOT" "$DOSSIER"
fi
cd "$DOSSIER"

# ------------------------------------------------------------------ #
# 3. Installer via pipx.                                             #
#    pipx lit pyproject.toml -> installe requests, rich,             #
#    prompt_toolkit automatiquement. --force = reinstalle proprement.#
# ------------------------------------------------------------------ #
echo "==> Installation de la commande 'baziz.ia' via pipx..."
pipx install --force .

# ------------------------------------------------------------------ #
# 4. Configuration (.env).                                           #
# ------------------------------------------------------------------ #
if [ ! -f .env ]; then
    cp .env.example .env
fi

echo ""
echo "==> Termine !"
echo "    1) Mettez votre cle dans :  $(pwd)/.env   (nano .env)"
echo "    2) Ouvrez un NOUVEAU terminal (pour recharger le PATH de pipx)"
echo "    3) Lancez depuis ce dossier :  cd $(pwd) && baziz.ia"
