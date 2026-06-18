#!/bin/sh
# ============================================================
#  Installateur BAZIZ.IA pour Linux / macOS
#  Usage :
#    curl -fsSL https://raw.githubusercontent.com/b4z1z/retroai-agent/main/scripts/install.sh | sh
# ============================================================
set -e

DEPOT="https://github.com/b4z1z/retroai-agent.git"
DOSSIER="retroai-agent"

echo "==> Installation de BAZIZ.IA..."

# 1. Verifier les prerequis (git + python3).
if ! command -v git >/dev/null 2>&1; then
    echo "Erreur : git n'est pas installe. Installez-le puis reessayez."
    exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
    echo "Erreur : python3 n'est pas installe. Installez-le puis reessayez."
    exit 1
fi

# 2. Recuperer le code (cloner, ou mettre a jour si deja present).
if [ -d "$DOSSIER/.git" ]; then
    echo "==> Depot deja present, mise a jour..."
    git -C "$DOSSIER" pull --ff-only
else
    echo "==> Clonage du depot..."
    git clone "$DEPOT" "$DOSSIER"
fi

cd "$DOSSIER"

# 3. Installer le paquet (cree la commande "baziz.ia").
echo "==> Installation des dependances..."
python3 -m pip install --user -e .

# 4. Preparer la configuration.
if [ ! -f .env ]; then
    cp .env.example .env
    echo "==> Fichier .env cree. Editez-le pour y mettre votre NVIDIA_API_KEY :"
    echo "      nano $(pwd)/.env"
fi

echo ""
echo "==> Termine !"
echo "    1) Renseignez votre cle dans .env"
echo "    2) Lancez :  baziz.ia"
echo "       (ou :     python3 -m retroai_agent.main)"
