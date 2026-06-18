# ============================================================
#  Installateur BAZIZ.IA pour Windows (PowerShell)
#  Usage :
#    irm https://raw.githubusercontent.com/b4z1z/retroai-agent/main/scripts/install.ps1 | iex
# ============================================================
$ErrorActionPreference = "Stop"

$Depot = "https://github.com/b4z1z/retroai-agent.git"
$Dossier = "retroai-agent"

Write-Host "==> Installation de BAZIZ.IA..."

# 1. Verifier les prerequis (git + python).
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "Erreur : git n'est pas installe. Installez-le puis reessayez."
    exit 1
}
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Erreur : python n'est pas installe. Installez-le puis reessayez."
    exit 1
}

# 2. Recuperer le code (cloner, ou mettre a jour si deja present).
if (Test-Path "$Dossier\.git") {
    Write-Host "==> Depot deja present, mise a jour..."
    git -C $Dossier pull --ff-only
} else {
    Write-Host "==> Clonage du depot..."
    git clone $Depot $Dossier
}

Set-Location $Dossier

# 3. Installer le paquet (cree la commande "baziz.ia").
Write-Host "==> Installation des dependances..."
python -m pip install -e .

# 4. Preparer la configuration.
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "==> Fichier .env cree. Editez-le pour y mettre votre NVIDIA_API_KEY :"
    Write-Host "      notepad $(Get-Location)\.env"
}

Write-Host ""
Write-Host "==> Termine !"
Write-Host "    1) Renseignez votre cle dans .env"
Write-Host "    2) Lancez :  baziz.ia"
Write-Host "       (ou :     python -m retroai_agent.main)"
