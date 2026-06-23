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

from .config import load_config, set_env_value
from .api_client import ApiClient, ApiError, QuotaError
from .agent_loop import AgentLoop
from . import profile
from . import ui
from . import images
from . import image_gen
from . import files
from . import modes


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
            ui.info("History cleared.")
            continue
        if saisie == "/mode" or saisie.startswith("/mode "):
            # /mode -> passe au mode suivant ; /mode <nom> -> fixe directement.
            arg = saisie[len("/mode"):].strip().lower()
            if arg:
                if not modes.definir(arg):
                    ui.erreur(
                        "Unknown mode. Use: normal / auto-edit / plan / auto-all "
                        "(or just /mode to cycle, or Shift+Tab)."
                    )
            else:
                modes.cycler()
            ui.mode_actuel()
            continue
        if saisie == "/continue":
            # Cas 1 : un tour de la session COURANTE a ete interrompu (echec
            # API) -> on reprend exactement la ou ca s'est arrete.
            if agent.tour_incomplet:
                ui.info("Resuming interrupted task…")
                _traiter_reponse(agent, reprise=True)
            # Cas 2 : pas d'interruption en memoire -> on recharge le disque.
            elif agent.charger_session():
                ui.info(
                    f"Previous session restored "
                    f"({len(agent.historique)} messages)."
                )
                # Si la session rechargee est incomplete (dernier message =
                # utilisateur sans reponse), on reprend la tache.
                if agent.historique and agent.historique[-1].get("role") == "user":
                    ui.info("Incomplete task detected — resuming…")
                    _traiter_reponse(agent, reprise=True)
            else:
                ui.info("No previous session to restore.")
            continue
        if saisie == "/add-image":
            _envoyer_avec_image(agent, images.choisir_image_dialogue(),
                                source="file dialog")
            continue
        if saisie == "/paste":
            _envoyer_avec_image(agent, images.image_depuis_presse_papiers(),
                                source="clipboard")
            continue
        if saisie == "/add-file" or saisie.startswith("/add-file "):
            # /add-file <chemin>  -> direct ; /add-file  -> selecteur de fichier.
            _ajouter_fichier(agent, saisie[len("/add-file"):].strip())
            continue
        if saisie == "/compose":
            _composer(agent)
            continue
        if saisie == "/image":
            _menu_image(agent)
            continue
        if saisie == "/create-image" or saisie.startswith("/create-image "):
            # Description optionnelle sur la meme ligne :
            #   /create-image un chat astronaute   -> genere directement
            #   /create-image                       -> demande la description
            description = saisie[len("/create-image"):].strip()
            _creer_image(agent, description)
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
                ui.erreur(f"Unknown command: {saisie}")
                ui.aide()
            continue

        # 3. Saisie normale -> on interroge l'agent (le spinner est gere
        #    dans agent_loop, autour de chaque appel API).
        _traiter_reponse(agent, saisie=saisie)


def _envoyer_avec_image(agent: AgentLoop, chemin, *, source: str) -> None:
    """
    Joint une image (choisie via dialogue ou presse-papiers) au prochain
    message et l'envoie a l'agent.
    """
    if not chemin:
        if source == "clipboard":
            ui.erreur("No image found in the clipboard "
                      "(or Pillow not installed: pip install pillow).")
        else:
            ui.erreur("No image selected "
                      "(or file dialog unavailable: install python3-tk).")
        return
    try:
        texte = ui.demander_texte("Message about this image (Enter to just describe):")
    except (EOFError, KeyboardInterrupt):
        ui.info("\nCancelled.")
        return
    if not texte:
        texte = "Describe this image."
    _traiter_reponse(agent, saisie=texte, chemins_images=[chemin])


def _ajouter_fichier(agent: AgentLoop, chemin: str) -> None:
    """
    Commande /add-file : lit un fichier texte/code (selecteur ou chemin donne)
    et l'envoie a l'agent pour analyse, avec un message optionnel.
    """
    if not chemin:
        chemin = files.choisir_fichier_dialogue()
    if not chemin:
        ui.erreur("No file selected "
                  "(or file dialog unavailable: install python3-tk).")
        return
    contenu, erreur = files.lire_fichier_texte(chemin)
    if erreur:
        ui.erreur(erreur)
        return
    try:
        message = ui.demander_texte(
            "Message about this file (Enter to just analyze it):"
        )
    except (EOFError, KeyboardInterrupt):
        ui.info("\nCancelled.")
        return
    ui.fichier_joint(chemin, len(contenu))
    texte = files.construire_message_fichier(chemin, contenu, message)
    _traiter_reponse(agent, saisie=texte)


def _composer(agent: AgentLoop) -> None:
    """
    Commande /compose : ouvre un editeur temporaire (nano/notepad/$EDITOR)
    pour ecrire/coller un long message ou bloc de code sans encombrer la ligne
    de saisie, puis l'envoie a l'agent.
    """
    ui.info("Opening an editor… write your message, then save and close.")
    texte = files.composer_dans_editeur()
    if texte is None:
        ui.erreur(
            "Could not open an editor. Set $EDITOR (e.g. 'export EDITOR=nano'), "
            "or just type/paste directly at the prompt."
        )
        return
    texte = texte.strip()
    if not texte:
        ui.info("Cancelled (nothing written).")
        return
    _traiter_reponse(agent, saisie=texte)


def _menu_image(agent: AgentLoop) -> None:
    """
    Commande /image : affiche le modele de generation courant et permet d'en
    changer (FLUX par defaut, ou Nano Banana via une cle Gemini saisie in-app
    et enregistree dans .env). Ne genere ni n'affiche aucune image.
    """
    config = agent.config
    ui.menu_image(image_gen.label_modele(config), gemini_pret=bool(config.gemini_api_key))

    try:
        choix = ui.demander_texte("Change model? (1/2/3, Enter to keep):").strip()
    except (EOFError, KeyboardInterrupt):
        ui.info("\nCancelled.")
        return
    if not choix:
        return

    if choix == "1":
        config.image_provider = "nvidia"
        set_env_value("IMAGE_PROVIDER", "nvidia")
        ui.succes(f"Model set to {image_gen.label_modele(config)}.")
        return

    if choix in ("2", "3"):
        modele = "gemini-3-pro-image" if choix == "2" else "gemini-2.5-flash-image"
        # Cle Gemini requise : on la demande une seule fois et on l'enregistre.
        if not config.gemini_api_key:
            try:
                cle = ui.demander_texte(
                    "Enter your GEMINI_API_KEY (saved locally in .env):"
                ).strip()
            except (EOFError, KeyboardInterrupt):
                ui.info("\nCancelled.")
                return
            if not cle:
                ui.erreur("No key entered — keeping the current model.")
                return
            config.gemini_api_key = cle
            set_env_value("GEMINI_API_KEY", cle)
        config.image_provider = "gemini"
        config.gemini_model = modele
        set_env_value("IMAGE_PROVIDER", "gemini")
        set_env_value("GEMINI_MODEL", modele)
        ui.succes(f"Model set to {image_gen.label_modele(config)}.")
        return

    ui.erreur(f"Unknown choice: {choix}")


def _creer_image(agent: AgentLoop, description: str = "") -> None:
    """
    Commande /create-image : genere une image et l'enregistre localement.
    La description peut etre passee en ligne (/create-image un chat) ; sinon
    on la demande. Affiche le chemin du PNG et l'ouvre.
    """
    if not description:
        try:
            description = ui.demander_texte("Describe the image to generate:")
        except (EOFError, KeyboardInterrupt):
            ui.info("\nCancelled.")
            return
    if not description:
        ui.info("Cancelled (empty description).")
        return
    chemin = _generer_image(agent, description)
    if not chemin:
        return
    ui.image_creee(chemin)
    # Ouvre l'image dans la visionneuse par defaut pour voir le resultat.
    if not image_gen.ouvrir_image(chemin):
        ui.info("(Could not open the image automatically — open it manually.)")


def _generer_image(agent: AgentLoop, description: str):
    """
    Genere une image et retourne son chemin (ou None en cas d'echec/annulation).
    Si le palier gratuit Gemini est epuise (QuotaError), propose de basculer
    sur FLUX (gratuit) et de reessayer immediatement.
    """
    try:
        with ui.reflexion("Generating image…"):
            return image_gen.creer_image(agent.client, agent.config, description)
    except QuotaError:
        return _gerer_quota(agent, description)
    except ApiError as exc:
        ui.erreur(str(exc))
        return None
    except KeyboardInterrupt:
        ui.info("\nCancelled.")
        return None


def _gerer_quota(agent: AgentLoop, description: str):
    """Palier gratuit Gemini epuise : propose FLUX (gratuit) + reessai direct."""
    ui.quota_atteint()
    try:
        rep = ui.demander_texte(
            "Switch to FLUX (free) and retry now? (y/n):"
        ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        ui.info("\nCancelled.")
        return None

    if rep in ("y", "o", "yes", "oui"):
        agent.config.image_provider = "nvidia"
        set_env_value("IMAGE_PROVIDER", "nvidia")
        ui.info("Switched to FLUX. Retrying…")
        try:
            with ui.reflexion("Generating image…"):
                return image_gen.creer_image(agent.client, agent.config, description)
        except ApiError as exc:
            ui.erreur(str(exc))
            return None
        except KeyboardInterrupt:
            ui.info("\nCancelled.")
            return None

    ui.info(
        "Kept Nano Banana. The free quota resets daily — or use an upgraded "
        "key. Switch model anytime with /image."
    )
    return None


def _traiter_reponse(agent: AgentLoop, *, saisie: str = "", reprise: bool = False,
                     chemins_images=None) -> None:
    """
    Lance un tour de l'agent (nouveau message ou reprise d'un tour interrompu)
    et affiche la reponse. En cas d'echec API, la progression est CONSERVEE
    et on indique a l'utilisateur comment reprendre.
    """
    try:
        if reprise:
            reponse = agent.reprendre()
        else:
            reponse = agent.envoyer(saisie, chemins_images=chemins_images)
    except ApiError as exc:
        ui.erreur(str(exc))
        ui.info(
            "Progress saved. Type /continue to resume where it "
            "stopped (no need to redo)."
        )
        return
    except KeyboardInterrupt:
        # Ctrl+C pendant la reflexion = STOP : on revient au prompt sans
        # quitter l'appli. La progression est conservee (cf. _executer_tour).
        ui.stop_reflexion()
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
