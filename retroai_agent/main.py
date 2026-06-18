"""
main.py - Point d'entree et boucle CLI utilisateur.

Role :
    - charger la configuration,
    - construire le client API et la boucle d'agent,
    - afficher une invite, lire les saisies de l'utilisateur,
    - gerer les commandes speciales (/exit, /quit, /reset, /help),
    - afficher un indicateur "reflexion" pendant l'attente de l'API.

Lancement :
    python -m retroai_agent.main
"""

from __future__ import annotations

import sys

from .config import load_config
from .api_client import ApiClient, ApiError
from .agent_loop import AgentLoop
from . import profile
from . import ui


def boucle_cli(agent: AgentLoop, modele: str, pseudo: str = "") -> None:
    """Boucle principale : lit les saisies et y repond jusqu'a /exit."""
    ui.banniere(modele)
    ui.saluer(pseudo)

    while True:
        # 1. Lire la saisie utilisateur (gerer Ctrl+C / Ctrl+D proprement).
        try:
            saisie = ui.lire_saisie()
        except (EOFError, KeyboardInterrupt):
            ui.au_revoir()
            return

        if not saisie:
            continue

        # 2. Commandes speciales (commencent par "/").
        if saisie in ("/exit", "/quit"):
            ui.info("Au revoir.")
            return
        if saisie == "/help":
            ui.aide()
            continue
        if saisie == "/reset":
            agent.reset()
            ui.info("Historique vide.")
            continue
        if saisie.startswith("/"):
            ui.erreur(f"Commande inconnue : {saisie}. Tapez /help.")
            continue

        # 3. Saisie normale -> on interroge l'agent (le spinner est gere
        #    dans agent_loop, autour de chaque appel API).
        try:
            reponse = agent.envoyer(saisie)
        except ApiError as exc:
            ui.erreur(str(exc))
            continue
        except KeyboardInterrupt:
            ui.info("\n[Interrompu.]")
            continue

        ui.reponse_agent(reponse)


def main() -> None:
    """Point d'entree : prepare tout puis lance la boucle."""
    try:
        config = load_config()
    except SystemExit as exc:
        # load_config leve SystemExit avec un message clair si la cle manque.
        print(exc)
        sys.exit(1)

    client = ApiClient(config)

    # Premier lancement : proposer (avec consentement) de renseigner un profil
    # pour personnaliser l'experience. Memorise pour ne plus redemander ensuite.
    profil = profile.initialiser_profil()
    infos = profile.profil_en_texte(profil)

    agent = AgentLoop(client, config, infos_utilisateur=infos)
    boucle_cli(agent, config.model, pseudo=profil.get("pseudo", ""))


if __name__ == "__main__":
    main()
