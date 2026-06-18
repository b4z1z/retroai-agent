"""
config.py - Source unique de verite pour la configuration du projet.

Role :
    1. Lire (optionnellement) un fichier .env sans dependance externe.
    2. Construire un objet Config typé et valide.
    3. Echouer tot et clairement si une valeur obligatoire manque.

Tous les autres modules importent Config plutot que d'appeler os.environ
directement : la configuration est centralisee, validee et testable.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


# --------------------------------------------------------------------------- #
#  1. La "boite" de configuration                                             #
# --------------------------------------------------------------------------- #
@dataclass
class Config:
    """Regroupe tous les reglages de l'application dans un seul objet."""

    api_key: str          # Cle API NVIDIA (obligatoire)
    base_url: str         # URL de l'endpoint chat/completions
    model: str            # Nom du modele a interroger
    enable_thinking: bool # Mode raisonnement active ou non
    shell_timeout: int    # Delai max (s) pour une commande shell


# --------------------------------------------------------------------------- #
#  2. Lecture du fichier .env (parser maison, zero dependance)                #
# --------------------------------------------------------------------------- #
def _load_dotenv(path: str = ".env") -> None:
    """
    Lit un fichier .env ligne par ligne et injecte les variables dans
    os.environ SANS ecraser celles deja definies au niveau systeme.

    Les variables systeme ont donc la priorite sur le fichier .env.
    Si le fichier n'existe pas, on ne fait rien (ce n'est pas une erreur).
    """
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as fichier:
        for ligne in fichier:
            ligne = ligne.strip()

            # Ignore les lignes vides et les commentaires.
            if not ligne or ligne.startswith("#"):
                continue

            # Ignore les lignes mal formees (pas de "=").
            if "=" not in ligne:
                continue

            cle, valeur = ligne.split("=", 1)
            cle = cle.strip()
            valeur = valeur.strip().strip('"').strip("'")

            # On n'ecrase pas une variable deja presente dans l'environnement.
            if cle and cle not in os.environ:
                os.environ[cle] = valeur


# --------------------------------------------------------------------------- #
#  3. Petites aides de conversion                                             #
# --------------------------------------------------------------------------- #
def _env_bool(nom: str, defaut: bool) -> bool:
    """Lit une variable d'env et la convertit en booleen."""
    valeur = os.environ.get(nom)
    if valeur is None:
        return defaut
    return valeur.strip().lower() in ("1", "true", "yes", "on", "oui")


def _env_int(nom: str, defaut: int) -> int:
    """Lit une variable d'env et la convertit en entier (defaut si invalide)."""
    valeur = os.environ.get(nom)
    if valeur is None:
        return defaut
    try:
        return int(valeur)
    except ValueError:
        return defaut


# --------------------------------------------------------------------------- #
#  4. Construction + validation de la configuration                           #
# --------------------------------------------------------------------------- #
def load_config(dotenv_path: str = ".env") -> Config:
    """
    Charge le .env, lit l'environnement, valide et retourne un objet Config.

    Leve SystemExit avec un message clair si la cle API est absente :
    mieux vaut planter tout de suite que recevoir un 401 incomprehensible
    plus tard pendant un appel API.
    """
    # 1. On peuple os.environ a partir du fichier .env (si present).
    _load_dotenv(dotenv_path)

    # 2. Valeur OBLIGATOIRE : la cle API.
    api_key = os.environ.get("NVIDIA_API_KEY", "").strip()
    if not api_key:
        raise SystemExit(
            "Erreur de configuration : NVIDIA_API_KEY est manquante.\n"
            "  -> Copiez .env.example en .env et renseignez votre cle,\n"
            "     ou exportez la variable : export NVIDIA_API_KEY=nvapi-..."
        )

    # 3. Valeurs OPTIONNELLES avec defauts alignes sur le cahier des charges.
    return Config(
        api_key=api_key,
        base_url=os.environ.get(
            "NVIDIA_BASE_URL",
            "https://integrate.api.nvidia.com/v1/chat/completions",
        ),
        model=os.environ.get("NVIDIA_MODEL", "moonshotai/kimi-k2.6"),
        enable_thinking=_env_bool("ENABLE_THINKING", True),
        shell_timeout=_env_int("SHELL_TIMEOUT", 30),
    )
