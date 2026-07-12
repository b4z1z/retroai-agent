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

# 4. S'assurer que la commande "baziz.ia" est TROUVABLE.
#    pip depose baziz.ia.exe dans un dossier "Scripts" qui, sous Windows,
#    n'est souvent PAS dans le PATH (surtout hors venv) -> "baziz.ia n'est
#    pas reconnu". On detecte ce cas et on ajoute le dossier au PATH
#    utilisateur (persistant), effectif dans les NOUVEAUX terminaux.
if (-not (Get-Command "baziz.ia" -ErrorAction SilentlyContinue)) {
    $candidats = @(
        (python -c "import sysconfig; print(sysconfig.get_path('scripts'))"),
        (python -c "import sysconfig; print(sysconfig.get_path('scripts', 'nt_user'))")
    )
    foreach ($dossierScripts in $candidats) {
        if ($dossierScripts -and (Test-Path (Join-Path $dossierScripts "baziz.ia.exe"))) {
            # a) PATH PERSISTANT (profil utilisateur) -> tous les FUTURS terminaux.
            $pathUtilisateur = [Environment]::GetEnvironmentVariable("Path", "User")
            if ($pathUtilisateur -notlike "*$dossierScripts*") {
                [Environment]::SetEnvironmentVariable(
                    "Path", "$pathUtilisateur;$dossierScripts", "User")
            }
            # b) PATH de la SESSION EN COURS -> 'baziz.ia' marche TOUT DE SUITE,
            #    sans rouvrir de terminal (c'etait le piege : le PATH persistant
            #    n'affecte pas la fenetre deja ouverte).
            $env:Path = "$env:Path;$dossierScripts"
            Write-Host "==> Dossier des commandes ajoute au PATH : $dossierScripts"
            break
        }
    }
}

# Verification FINALE, sans ambiguite.
if (Get-Command "baziz.ia" -ErrorAction SilentlyContinue) {
    Write-Host "==> Verification : la commande 'baziz.ia' est PRETE." -ForegroundColor Green
} else {
    Write-Host "==> La commande 'baziz.ia' n'est pas trouvable sur ce systeme." -ForegroundColor Yellow
    Write-Host "    Utilisez a la place :  python -m retroai_agent.main"
    Write-Host "    (depuis le dossier $(Get-Location))"
}

# 5. PAS de copie de .env : au premier lancement sans cle, l'ASSISTANT integre
#    guide l'utilisateur (etapes NVIDIA, navigateur, saisie de la cle dans le
#    terminal, ecriture automatique dans .env).

Write-Host ""
Write-Host "==> Termine !  Lancez :  baziz.ia"
Write-Host "    Pas de cle API ? L'assistant integre vous guide au 1er lancement."
