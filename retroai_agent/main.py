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
            ui.au_revoir()
            return
        if saisie == "/help":
            ui.aide()
            continue
        if saisie == "/reset":
            agent.reset()
            ui.info("Historique vide.")
            continue
        if saisie == "/continue":
            # Cas 1 : un tour de la session COURANTE a ete interrompu (echec
            # API) -> on reprend exactement la ou ca s'est arrete.
            if agent.tour_incomplet:
                ui.info("Reprise de la tache interrompue…")
                _traiter_reponse(agent, reprise=True)
            # Cas 2 : pas d'interruption en memoire -> on recharge le disque.
            elif agent.charger_session():
                ui.info(
                    f"Session precedente restauree "
                    f"({len(agent.historique)} messages)."
                )
                # Si la session rechargee est incomplete (dernier message =
                # utilisateur sans reponse), on reprend la tache.
                if agent.historique and agent.historique[-1].get("role") == "user":
                    ui.info("Tache incomplete detectee — reprise…")
                    _traiter_reponse(agent, reprise=True)
            else:
                ui.info("Aucune session precedente a restaurer.")
            continue
        # Taper juste "/" (ou "/?") affiche la liste complete des commandes.
        if saisie in ("/", "/?"):
            ui.aide()
            continue
        if saisie.startswith("/"):
            # Commande non reconnue : on propose les commandes qui
            # commencent par ce que l'utilisateur a tape (suggestions).
            if ui.commandes_correspondantes(saisie):
                ui.suggestions(saisie)
            else:
                ui.erreur(f"Commande inconnue : {saisie}")
                ui.aide()
            continue

        # 3. Saisie normale -> on interroge l'agent (le spinner est gere
        #    dans agent_loop, autour de chaque appel API).
        _traiter_reponse(agent, saisie=saisie)


def _traiter_reponse(agent: AgentLoop, *, saisie: str = "", reprise: bool = False) -> None:
    """
    Lance un tour de l'agent (nouveau message ou reprise d'un tour interrompu)
    et affiche la reponse. En cas d'echec API, la progression est CONSERVEE
    et on indique a l'utilisateur comment reprendre.
    """
    try:
        if reprise:
            reponse = agent.reprendre()
        else:
            reponse = agent.envoyer(saisie)
    except ApiError as exc:
        ui.erreur(str(exc))
        ui.info(
            "Progression conservee. Tape /continue pour reprendre "
            "la ou ca s'est arrete (sans tout refaire)."
        )
        return
    except KeyboardInterrupt:
        ui.info("\n[Interrompu.]")
        return
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

    # Genere/actualise le fichier de reference des commandes (facon 'help').
    ui.exporter_commandes()

    # Premier lancement : proposer (avec consentement) de renseigner un profil
    # pour personnaliser l'experience. Memorise pour ne plus redemander ensuite.
    profil = profile.initialiser_profil()
    infos = profile.profil_en_texte(profil)

    agent = AgentLoop(client, config, infos_utilisateur=infos)
    boucle_cli(agent, config.model, pseudo=profil.get("pseudo", ""))


if __name__ == "__main__":
    main()
