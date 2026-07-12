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
    # python3-tk : fenetre de selection de fichier pour la commande /add-image.
    python3 -c "import tkinter" >/dev/null 2>&1 || BESOINS="$BESOINS python3-tk"
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
# 4. PAS de copie de .env : au premier lancement sans cle, l'ASSISTANT #
#    integre guide l'utilisateur (etapes NVIDIA, navigateur, saisie de #
#    la cle dans le terminal, ecriture automatique dans .env).         #
# ------------------------------------------------------------------ #

echo ""
echo "==> Termine !"
echo ""
echo "    Pour lancer MAINTENANT, dans CETTE fenetre :"
echo "        export PATH=\"\$PATH:\$HOME/.local/bin\" && cd $(pwd) && baziz.ia"
echo ""
echo "    (Ou plus simple : ouvrez un NOUVEAU terminal, puis :"
echo "        cd $(pwd) && baziz.ia )"
echo ""
echo "    Pas de cle API ? L'assistant integre vous guide au 1er lancement."
