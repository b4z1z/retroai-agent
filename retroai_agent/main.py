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

import os
import signal
import subprocess
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
from . import thinking
from . import sessions
from . import tuto
from . import plugins


def boucle_cli(agent: AgentLoop, modele: str, pseudo: str = "") -> None:
    """Boucle principale : lit les saisies et y repond jusqu'a /exit."""
    ui.banniere(modele)
    ui.saluer(pseudo)
    tuto.jouer()  # ne joue que si jamais vu ; instantane sinon (aucun appel API)

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
            ui.info("History cleared — the previous conversation is safely "
                    "saved (/sessions to see it).")
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
        if saisie == "/think" or saisie.startswith("/think "):
            # /think <niveau> -> fixe directement ; /think -> menu a fleches.
            arg = saisie[len("/think"):].strip().lower()
            if arg:
                if arg in thinking.NIVEAUX:
                    agent.config.thinking_level = arg
                else:
                    ui.erreur("Unknown level. Use: " + " / ".join(thinking.NIVEAUX))
                    continue
            else:
                courant = thinking.normaliser(agent.config.thinking_level)
                # Chaque niveau montre sa JAUGE (barre qui se remplit d'un
                # cran par niveau) : l'effort se voit d'un coup d'oeil.
                options = [
                    (n, f"{ui.barre_thinking(n)}  {n:7} — {thinking.DESCRIPTIONS[n]}")
                    for n in thinking.NIVEAUX
                ]
                choix = ui.selecteur(
                    "Thinking level",
                    "Reasoning effort (↑/↓ then Enter, Esc to cancel):",
                    options,
                    defaut=courant,
                )
                if not choix:  # annule ou pas de selecteur -> on ne change rien
                    ui.niveau_thinking(agent.config.thinking_level)
                    continue
                agent.config.thinking_level = choix
            set_env_value("THINKING_LEVEL", agent.config.thinking_level)
            ui.niveau_thinking(agent.config.thinking_level)
            continue
        if saisie == "/continue":
            _gerer_continue(agent)
            continue
        if saisie == "/sessions" or saisie.startswith("/sessions "):
            _gerer_sessions(agent)
            continue
        if saisie == "/new":
            agent.reset()
            ui.info("Started a new session — the previous one is safely saved "
                    "(/sessions to see it).")
            continue
        if saisie == "/tuto":
            tuto.jouer(force=True)
            continue
        if saisie == "/restart":
            _redemarrer()  # ne revient jamais (quitte apres la relance)
        if saisie == "/btw":
            ui.afficher_jetons(agent.jetons_tour, agent.jetons_session)
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
        if saisie == "/compose" or saisie.startswith("/compose "):
            # /compose <texte> -> ouvre l'editeur pre-rempli avec ce texte.
            _composer(agent, saisie[len("/compose"):].strip())
            continue
        if saisie == "/write":
            _ecrire_multiligne(agent)
            continue
        if saisie == "/image":
            _menu_image(agent)
            continue
        if saisie == "/model":
            _menu_modele(agent)
            continue
        if saisie == "/plugins":
            _menu_plugins()
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
        #    dans agent_loop). Pour un message multi-ligne, utiliser Alt+Entree
        #    (retour a la ligne) puis Entree pour envoyer, ou /write, ou /compose.
        _traiter_reponse(agent, saisie=saisie)


def _redemarrer() -> None:
    """
    Commande /restart : relance BAZIZ.IA dans un interpreteur Python NEUF
    (le code source ET le fichier .env sont donc recharges - pratique apres
    une mise a jour du code, sans fermer/rouvrir le terminal a la main).

    Implementation : on lance la nouvelle instance en PROCESSUS FILS et on
    l'ATTEND, puis on quitte avec son code de sortie. On n'utilise PAS
    os.exec* : sous Windows il ne remplace pas vraiment le processus (le
    shell parent croit la commande finie et affiche son invite pendant que
    la nouvelle instance tourne encore -> les deux se battent pour la
    console). Le parent ignore Ctrl+C pendant l'attente pour que le "stop"
    reste gere par la nouvelle instance seule.

    La conversation courante est deja sauvegardee automatiquement apres
    chaque tour -> /continue dans la nouvelle instance la reprend.
    """
    ui.info("Restarting BAZIZ.IA… (your conversation is saved — use "
            "/continue in the new instance to pick it up)")
    try:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    except (ValueError, OSError):
        pass  # environnement sans gestion de signaux -> tant pis, on relance
    code = subprocess.call([sys.executable, "-m", "retroai_agent.main"])
    raise SystemExit(code)


def _gerer_continue(agent: AgentLoop) -> None:
    """
    Commande /continue :
      - Cas 1 : un tour de la session COURANTE a ete interrompu (echec API)
        -> on reprend exactement la ou ca s'est arrete.
      - Cas 2 : pas d'interruption en memoire -> reprend la session
        sauvegardee la PLUS RECENTE (multi-conversations).
    """
    if agent.tour_incomplet:
        ui.info("Resuming interrupted task…")
        _traiter_reponse(agent, reprise=True)
        return

    recentes = sessions.lister()
    if not recentes:
        ui.sessions_vides()
        return
    agent.charger_session_id(recentes[0]["id"])
    ui.session_restauree(agent.session_titre, len(agent.historique))
    _reprendre_si_incomplete(agent)


def _reprendre_si_incomplete(agent: AgentLoop) -> None:
    """
    Apres avoir charge une session (/continue ou /sessions), si son dernier
    message est un message UTILISATEUR sans reponse (tache interrompue avant
    d'etre sauvegardee en plein tour), on la reprend automatiquement.
    """
    if agent.historique and agent.historique[-1].get("role") == "user":
        ui.info("Incomplete task detected — resuming…")
        _traiter_reponse(agent, reprise=True)


def _gerer_sessions(agent: AgentLoop) -> None:
    """
    Commande /sessions : liste les conversations sauvegardees (menu a
    fleches) et charge celle choisie. La session courante n'est jamais
    perdue : elle est deja sauvegardee en continu (autosave apres chaque
    tour), donc changer de session est toujours sans risque.
    """
    disponibles = sessions.lister()
    if not disponibles:
        ui.sessions_vides()
        return

    options = [
        (s["id"], ui.libelle_session(s, id_courant=agent.session_id))
        for s in disponibles
    ]
    choix = ui.selecteur(
        "Sessions",
        "Pick a session to resume (↑/↓ then Enter, Esc to cancel):",
        options,
        defaut=agent.session_id or disponibles[0]["id"],
    )
    if not choix:
        return  # annule (Esc) ou selecteur indisponible -> rien ne change
    if choix == agent.session_id:
        ui.info("Already on this session.")
        return

    agent.charger_session_id(choix)
    ui.session_restauree(agent.session_titre, len(agent.historique))
    _reprendre_si_incomplete(agent)


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
        # Repli : pas de dialogue (annule, cache, ou tkinter indispo) ->
        # on demande le chemin directement pour que /add-file marche quand meme.
        ui.info("No file picker. Type the file path "
                "(tip: you can also use /add-file <path>).")
        try:
            chemin = ui.demander_texte("File path (Enter to cancel):")
        except (EOFError, KeyboardInterrupt):
            chemin = ""
    if not chemin:
        ui.info("Cancelled (no file).")
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


def _composer(agent: AgentLoop, initial: str = "") -> None:
    """
    Commande /compose : ouvre un editeur (notepad/nano/$EDITOR) sur un fichier
    temporaire DEDIE pour ecrire/coller un long message ou bloc de code, puis
    l'envoie a l'agent. '/compose <texte>' pre-remplit l'editeur.
    """
    ui.info("Opening the editor… write below the marker line, then save "
            "and close (just that window/tab). Empty = cancel.")
    texte = files.composer_dans_editeur(initial)
    if texte is None:
        ui.erreur(
            "Could not open an editor. Set EDITOR (e.g. notepad, nano, "
            "\"code -w\"), or use /write to type inline."
        )
        return
    texte = texte.strip()
    if not texte:
        ui.info("Cancelled (nothing written).")
        return
    _traiter_reponse(agent, saisie=texte)


def _ecrire_multiligne(agent: AgentLoop) -> None:
    """
    Commande /write : saisie multi-ligne DIRECTE dans le terminal (aucun
    editeur a ouvrir/fermer). Terminer par une ligne contenant seulement '.'
    (ou Ctrl-D) ; Ctrl-C annule.
    """
    ui.info("Multi-line input — type your lines. End with a single '.' on "
            "its own line (or Ctrl-D). Ctrl-C cancels.")
    try:
        texte = ui.lire_multiligne(".")
    except KeyboardInterrupt:
        ui.info("\nCancelled.")
        return
    texte = texte.strip()
    if not texte:
        ui.info("Cancelled (empty).")
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


def _choisir(titre: str, texte: str, options: list) -> str | None:
    """
    Choix a fleches (ui.selecteur) avec REPLI numerote automatique quand le
    selecteur est indisponible. options = [(valeur, libelle)]. None = annule.
    """
    choix = ui.selecteur(titre, texte, options)
    if choix is not None:
        return choix
    ui.info(texte)
    for i, (_, libelle) in enumerate(options, start=1):
        ui.info(f"  {i}. {libelle}")
    try:
        reponse = ui.demander_texte(
            f"Choice? (1-{len(options)}, Enter to cancel):"
        ).strip()
    except (EOFError, KeyboardInterrupt):
        return None
    if reponse.isdigit() and 1 <= int(reponse) <= len(options):
        return options[int(reponse) - 1][0]
    return None


def _menu_plugins() -> None:
    """
    Commande /plugins : hub de gestion des plugins. Voir / installer depuis
    le marketplace communautaire / desactiver / reactiver / supprimer.
    TOUT est applique A CHAUD (plugins.activer() re-fusionne le schema) :
    aucun /restart necessaire.
    """
    plugins.activer()  # rescan : un fichier ajoute a la main est vu direct
    actifs = plugins.liste()
    inactifs = plugins.lister_desactives()

    action = _choisir(
        "Plugins",
        f"{len(actifs)} active, {len(inactifs)} disabled — community "
        f"marketplace: {plugins.URL_SITE}",
        [
            ("voir", f"📋 See installed plugins ({len(actifs)})"),
            ("creer", "➕ Add / create a new plugin"),
            ("installer", "🛒 Install from the community marketplace"),
            ("publier", "📤 Publish a plugin to the marketplace (auto-deploy)"),
            ("desactiver", f"⏸  Disable a plugin ({len(actifs)} active)"),
            ("reactiver", f"▶  Enable a disabled plugin ({len(inactifs)} off)"),
            ("supprimer", "🗑  Delete a plugin file"),
        ],
    )
    if action is None:
        return

    if action == "voir":
        ui.afficher_plugins(plugins.liste(), plugins.erreurs())
        return

    if action == "creer":
        ui.info(
            "Two ways to add a plugin:\n"
            "  1. The magic one — just ASK me in the chat, e.g.:\n"
            "     \"crée-toi un plugin qui donne les horaires de prière\"\n"
            "     I write plugins/<name>.py myself; reopen /plugins and it's "
            "active.\n"
            "  2. Manual — drop a .py file in the plugins/ folder "
            "(contract: plugins/README.md), then reopen /plugins."
        )
        return

    if action == "publier":
        if not actifs:
            ui.info("No active plugin to publish.")
            return
        fichier_ou_nom = _choisir(
            "Publish", "Pick a plugin to publish to the community "
            "marketplace:", [(p["nom"], f"{p['nom']} — {p['description'][:52]}")
                             for p in actifs])
        if fichier_ou_nom is None:
            return
        try:
            auteur = ui.demander_texte(
                "Author name shown on the site (Enter = B4Z1Z):"
            ).strip() or "B4Z1Z"
        except (EOFError, KeyboardInterrupt):
            return
        probleme = plugins.publier(fichier_ou_nom, auteur)
        if probleme:
            ui.erreur(probleme)
            return
        ui.succes(
            f"'{fichier_ou_nom}' added to the local marketplace files "
            "(registry + site synced)."
        )
        # Le deploiement = un simple push : Vercel rebuild automatiquement.
        try:
            ok = ui.demander_texte(
                "Commit & push now? Vercel will auto-deploy the site (y/n):"
            ).strip().lower()
        except (EOFError, KeyboardInterrupt):
            return
        if ok not in ("y", "yes", "o", "oui"):
            ui.info("Not pushed — the plugin will go online with your next "
                    "git push.")
            return
        commande = (
            'git add marketplace && git commit -m "marketplace: publish '
            + fichier_ou_nom + '" && git push'
        )
        code = subprocess.call(commande, shell=True)
        if code == 0:
            ui.succes("Pushed! Vercel is redeploying — the plugin will be "
                      f"online at {plugins.URL_SITE} in ~30 seconds.")
        else:
            ui.erreur("git push failed — check your git setup and retry.")
        return

    if action == "installer":
        ui.info("Fetching the community catalog…")
        entrees, probleme = plugins.catalogue()
        if probleme:
            ui.erreur(probleme)
            return
        if not entrees:
            ui.info("The marketplace is empty for now.")
            return
        deja = {p["nom"] for p in plugins.liste()}
        options = [
            (i, f"{e['nom']:<16} — {e.get('description', '')[:48]}"
                f"{'  🔐' if e.get('dangereux') else ''}"
                f"{'  (installed)' if e['nom'] in deja else ''}")
            for i, e in enumerate(entrees)
        ]
        idx = _choisir("Marketplace",
                       "Pick a plugin to install (Esc to cancel):", options)
        if idx is None:
            return
        entree = entrees[idx]
        # ACCES ETENDU (fichiers, systeme, donnees sensibles...) : on previent
        # AVANT le telechargement pour que l'utilisateur prenne ses
        # precautions — c'est la qu'un avertissement est utile, pas un badge
        # anxiogene sur chaque carte.
        if entree.get("dangereux"):
            ui.info(
                "🔐 Heads-up: this plugin has BROAD ACCESS (files, system or "
                "sensitive data). Review its code first (marketplace → 'Voir "
                "le code'). Once installed, it will still ask a y/n "
                "confirmation before EACH run."
            )
        # Telecharger du CODE que l'agent pourra executer merite une
        # confirmation explicite, avec la source affichee.
        try:
            ok = ui.demander_texte(
                f"Install '{entree['nom']}' from {entree['url']} ? (y/n):"
            ).strip().lower()
        except (EOFError, KeyboardInterrupt):
            return
        if ok not in ("y", "yes", "o", "oui"):
            ui.info("Cancelled.")
            return
        probleme = plugins.installer(entree)
        if probleme:
            ui.erreur(probleme)
            return
        plugins.activer()
        ui.succes(f"Plugin '{entree['nom']}' installed and ACTIVE right now "
                  "(no restart needed).")
        return

    if action == "desactiver":
        if not actifs:
            ui.info("No active plugin.")
            return
        fichier = _choisir("Disable", "Pick a plugin to disable:",
                           [(p["fichier"], f"{p['nom']} — {p['fichier']}")
                            for p in actifs])
        if fichier is None:
            return
        probleme = plugins.desactiver_fichier(fichier)
        if probleme:
            ui.erreur(probleme)
            return
        plugins.activer()
        ui.succes("Disabled (kept on disk — re-enable anytime via /plugins).")
        return

    if action == "reactiver":
        if not inactifs:
            ui.info("No disabled plugin.")
            return
        fichier = _choisir("Enable", "Pick a plugin to re-enable:",
                           [(f, os.path.basename(f)) for f in inactifs])
        if fichier is None:
            return
        probleme = plugins.reactiver_fichier(fichier)
        if probleme:
            ui.erreur(probleme)
            return
        plugins.activer()
        ui.succes("Enabled and ACTIVE right now (no restart needed).")
        return

    if action == "supprimer":
        tout = [(p["fichier"], f"{p['nom']} — {p['fichier']}") for p in actifs]
        tout += [(f, f"(disabled) {os.path.basename(f)}") for f in inactifs]
        if not tout:
            ui.info("Nothing to delete.")
            return
        fichier = _choisir("Delete", "Pick a plugin file to DELETE forever:",
                           tout)
        if fichier is None:
            return
        try:
            ok = ui.demander_texte(
                f"Really delete {fichier}? This cannot be undone (y/n):"
            ).strip().lower()
        except (EOFError, KeyboardInterrupt):
            return
        if ok not in ("y", "yes", "o", "oui"):
            ui.info("Cancelled.")
            return
        probleme = plugins.supprimer_fichier(fichier)
        if probleme:
            ui.erreur(probleme)
            return
        plugins.activer()
        ui.succes("Deleted.")
        return


# Modeles de CHAT proposes dans le menu /model : (id NVIDIA, description).
# Le 1er est le MODELE DE BASE (defaut de l'app). Tous verifies en reel avec
# tool-calling. "custom" permet d'entrer n'importe quel id du catalogue.
MODELES_CHAT = [
    ("nvidia/nemotron-3-ultra-550b-a55b",
     "default — reasoning + tools, fast (NVIDIA's own, best served)"),
    ("deepseek-ai/deepseek-v4-flash",
     "reasoning, strong at code (can be busy at peak times)"),
    ("meta/llama-3.3-70b-instruct",
     "no reasoning — steady, quick, simple tasks"),
]


def _menu_modele(agent: AgentLoop) -> None:
    """
    Commande /model : gestion du modele de CHAT. Affiche le modele courant,
    propose les modeles verifies (+ saisie libre), applique A CHAUD (le
    prochain message part deja sur le nouveau modele — config.model est relu
    a chaque appel API) et PERSISTE dans .env : le choix reste jusqu'a ce que
    l'utilisateur le rechange. Annuler ne change rien.
    """
    config = agent.config
    options = [(mid, f"{mid} — {desc}") for mid, desc in MODELES_CHAT]
    options.append(("__custom__", "Custom… (any model id from build.nvidia.com/models)"))

    choix = ui.selecteur(
        "Chat model",
        f"Current model: {config.model}\n"
        "The choice is applied immediately and kept until you change it.",
        options,
        defaut=config.model if any(config.model == m for m, _ in options) else None,
    )
    if choix is None:
        # Selecteur indisponible (pas de prompt_toolkit / pas de TTY) ou Esc :
        # repli en saisie numerotee, comme /image.
        ui.info(f"Current model: {config.model}")
        for i, (mid, desc) in enumerate(MODELES_CHAT, start=1):
            ui.info(f"  {i}. {mid} — {desc}")
        ui.info(f"  {len(MODELES_CHAT) + 1}. Custom (type a model id)")
        try:
            reponse = ui.demander_texte(
                f"Change model? (1-{len(MODELES_CHAT) + 1}, Enter to keep):"
            ).strip()
        except (EOFError, KeyboardInterrupt):
            ui.info("\nCancelled.")
            return
        if not reponse:
            return
        if reponse.isdigit() and 1 <= int(reponse) <= len(MODELES_CHAT):
            choix = MODELES_CHAT[int(reponse) - 1][0]
        elif reponse == str(len(MODELES_CHAT) + 1):
            choix = "__custom__"
        else:
            ui.erreur(f"Unknown choice: {reponse}")
            return

    if choix == "__custom__":
        try:
            choix = ui.demander_texte(
                "Model id (e.g. qwen/… — see build.nvidia.com/models):"
            ).strip()
        except (EOFError, KeyboardInterrupt):
            ui.info("\nCancelled.")
            return
        if not choix:
            ui.info("Cancelled (empty).")
            return

    if choix == config.model:
        ui.info(f"Already using {config.model} — nothing changed.")
        return

    # Application A CHAUD + persistance : le choix survit aux relances et
    # reste le modele courant jusqu'au prochain /model.
    config.model = choix
    set_env_value("NVIDIA_MODEL", choix)
    ui.succes(
        f"Chat model switched to {choix} — applies from your NEXT message "
        "(saved to .env, no restart needed)."
    )


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
    # En streaming, la reponse a deja ete affichee en direct -> pas de re-rendu.
    if getattr(agent, "_stream_affiche", False):
        return
    ui.reponse_agent(reponse)


def main() -> None:
    """Point d'entree : prepare tout puis lance la boucle."""
    try:
        config = load_config()
    except SystemExit as exc:
        # Pas de cle API : au lieu d'echouer avec une erreur seche, on lance
        # l'ASSISTANT DE PREMIERE CONFIGURATION (guide + navigateur + saisie
        # de la cle dans le terminal + ecriture .env automatique).
        from . import setup_cle
        if setup_cle.assistant_cle() is None:
            print(exc)  # abandon (ou terminal non interactif) -> aide classique
            sys.exit(1)
        config = load_config()  # la cle est maintenant dans os.environ + .env

    client = ApiClient(config)

    # Genere/actualise le fichier de reference des commandes (facon 'help').
    ui.exporter_commandes()

    # Recupere l'ancien fichier de conversation unique (avant le multi-
    # session) dans le nouveau systeme, une seule fois, sans perte.
    sessions.migrer_ancienne_session()

    # Plugins : charge le dossier plugins/ et ajoute leurs outils au schema
    # envoye au modele. Chargement SILENCIEUX quand tout va bien (/plugins
    # pour voir la liste) ; seuls les plugins CASSES sont signales.
    _, erreurs_plugins = plugins.activer()
    for probleme in erreurs_plugins:
        ui.erreur(f"Plugin ignored: {probleme}")

    # Premier lancement : proposer (avec consentement) de renseigner un profil
    # pour personnaliser l'experience. Memorise pour ne plus redemander ensuite.
    profil = profile.initialiser_profil()
    infos = profile.profil_en_texte(profil)

    agent = AgentLoop(client, config, infos_utilisateur=infos)
    boucle_cli(agent, config.model, pseudo=profil.get("pseudo", ""))


if __name__ == "__main__":
    main()
