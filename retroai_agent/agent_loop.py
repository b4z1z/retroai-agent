"""
agent_loop.py - Orchestration du Tool Calling et de l'historique.

C'est le "cerveau" qui relie tout :
    - garde l'historique de la conversation,
    - envoie les messages a l'API (via ApiClient),
    - quand le modele demande un outil, l'execute (via tools.executer_outil),
    - REINJECTE le resultat dans l'historique.

PIEGE NVIDIA NIM (critique) :
    L'endpoint REJETTE le role "tool". Apres l'execution d'un outil, on ne
    renvoie PAS {"role": "tool", ...}. On reinjecte le resultat sous le role
    "user", formate ainsi :
        {"role": "user", "content": "[Resultat de l'outil <nom>]\\n<resultat>"}

PIEGE des arguments :
    Les arguments d'un tool call arrivent en CHAINE JSON brute. On fait donc
    toujours json.loads() sous try/except (le modele peut produire un JSON
    malforme ; dans ce cas on renvoie une erreur exploitable au modele).
"""

from __future__ import annotations

import json
import sys
import threading

from .api_client import ApiClient, ApiError, TimeoutApiError
from .config import Config
from . import tools
from . import ui
from . import images
from . import modes
from . import thinking
from . import sessions


def _description_plateforme() -> str:
    """
    Decrit la VRAIE plateforme/shell d'execution (detectee via sys.platform),
    avec des exemples de commandes NATIVES a utiliser.

    BUG REEL CORRIGE : le prompt disait auparavant "Linux terminal" en dur,
    meme sur une machine Windows. L'agent tentait alors des commandes Unix
    (ex. "find -name") qui echouent sous cmd.exe, produisant des messages
    d'erreur confus (aggrave par un bug d'encodage separe, deja corrige dans
    tools.py) -> plusieurs tours perdus, et l'agent a fini par abandonner
    avec une reponse vide au lieu de continuer la tache.
    """
    if sys.platform.startswith("win"):
        return (
            "a Windows machine. Shell commands run through cmd.exe (native "
            "Windows console), NOT bash/Unix — Unix commands/flags (find -name, "
            "grep, ls -la...) do NOT work here. Use Windows-native commands "
            "instead: 'dir' (not 'ls'), 'dir /s /b <name>' to find a file by "
            "name anywhere below the current folder (not 'find -name'), "
            "'findstr' (not 'grep'), 'del'/'copy'/'move' (not 'rm'/'cp'/'mv'), "
            "'type' (not 'cat'). Paths use backslashes."
        )
    if sys.platform == "darwin":
        return "a macOS machine. Shell commands run through a Unix shell (bash/zsh)."
    return "a Linux machine. Shell commands run through a Unix shell (bash)."


# Message systeme : definit le role et le comportement de l'agent.
SYSTEME = (
    "You are BAZIZ.IA, an autonomous agent that helps the user from a "
    f"terminal on {_description_plateforme()} You have tools to read/write "
    "files, list directories and run shell commands. Use them when useful. "
    "Reply concisely, in the same language as the user. If the user "
    "references an image file, that image is ALREADY attached to the "
    "message: look at it directly, do not try to open or inspect it with "
    "shell tools.\n"
    "FILES - when asked to CREATE, MODIFY, IMPROVE, FIX or REFACTOR code: do "
    "NOT just print the whole new code in the chat. ACTUALLY save it with the "
    "write_file tool, to the file's exact path when it is known (overwrite "
    "the original), or to a clearly-named new file otherwise. Write each "
    "file ONCE - do NOT re-read or re-write a file repeatedly to double-check "
    "and do NOT run extra verification commands unless the user asks. At the "
    "end, give a short text summary of what changed.\n"
    "OUTPUTS - every NEW project/app/game/site you create for the user goes "
    "in the outputs/ folder: outputs/<project-name>/... (write_file creates "
    "missing folders automatically). Never create new projects at the "
    "repository root. Exceptions: the user gives an explicit path, you "
    "are modifying an EXISTING project (then work where it already lives - "
    "e.g. a project already under outputs/ stays under outputs/), and "
    "PLUGINS: a plugin you create for yourself ALWAYS goes in the plugins/ "
    "folder, NEVER in outputs/ (only plugins/ is scanned and loaded).\n"
    "METHOD - for a LONG or complex task (a whole project, several files, or "
    "a big rewrite), work like a careful engineer, step by step: FIRST state "
    "a short numbered plan (one line per step). THEN execute the steps ONE at "
    "a time: announce the current step in one line ('Step 2/4 - game logic'), "
    "do that step's tool calls (ONE file or one coherent part per step), then "
    "move to the next step. Never dump the whole project in a single giant "
    "response: small incremental steps keep the progress safe (it is saved "
    "after every step and can be resumed with /continue).\n"
    "PLUGINS - you are EXTENSIBLE. Each .py file in the plugins/ folder adds "
    "a tool to you: it defines OUTIL = {name, description, parameters} (JSON "
    "schema), optionally DANGEREUX = True (asks user confirmation), and "
    "executer(args, config) -> str. After creating one, tell the user to "
    "type /plugins (reloads instantly) or /restart so you gain the ability. "
    "IMPORTANT: when "
    "the user asks for something you CANNOT do because you lack a capability "
    "(live data like weather or news, web access, a specific service...), do "
    "NOT just decline or point to websites. Answer what you can, then END "
    "your message with a short one-sentence offer to create that plugin "
    "yourself, e.g.: 'Je peux me creer un plugin meteo pour repondre a ca "
    "directement - dis oui et je l'ecris (puis /restart).' If the user "
    "accepts: write ONE small file in plugins/ following the contract "
    "(~30 lines, use the requests library, prefer FREE keyless APIs such as "
    "wttr.in for weather), then remind them to type /plugins or /restart.\n"
    "CRITICAL - KEEP GOING until the whole plan is DONE. After finishing a "
    "step, do NOT stop and do NOT hand control back to the user: immediately "
    "start the NEXT step's tool calls in the SAME turn. Announcing a step is "
    "not doing it - a step is only done once its write_file/other tool calls "
    "have run. Do not end your turn with a message like 'let's continue' or "
    "'next I will...' and then stop; actually continue. Only produce your "
    "final text summary AFTER the LAST step's tools have run. The single "
    "exception is plan mode (read-only): there you present the plan and stop, "
    "because you are not allowed to make changes."
)

# Identite du CREATEUR de l'agent (connaissance permanente, grave dans le
# prompt). A NE PAS confondre avec le profil optionnel de l'utilisateur
# courant (profile.py). Si on demande "qui est BAZIZ / B4Z1Z ?", l'agent
# repond avec ces infos. -> Edite librement ce texte pour completer ta bio.
A_PROPOS = (
    "About your creator: BAZIZ.IA was created by BAZIZ (online handle B4Z1Z, "
    "email bazizdev07@gmail.com), a developer. He designed and built you as a "
    "lightweight autonomous-agent terminal running on the NVIDIA NIM API. The "
    "source code lives at https://github.com/b4z1z/retroai-agent . "
    "If anyone asks 'who is BAZIZ', 'who is B4Z1Z', 'who made/created you' or "
    "similar, answer using this information. BAZIZ, B4Z1Z and 'your creator' "
    "all refer to the same person."
)

# Connaissance du LOGICIEL lui-meme : permet a l'agent d'aider l'utilisateur a
# se servir de BAZIZ.IA (questions du type "comment ajouter une image ?",
# "quelles commandes ?", "comment generer une image ?"). L'agent EST le manuel.
AIDE_LOGICIEL = (
    "You also act as the built-in help for the BAZIZ.IA software itself: if "
    "the user asks how to use you, how to do something in this app, or what is "
    "possible, explain it clearly and ACCURATELY using the exact facts below. "
    "Do not invent commands, options or syntax that are not listed here.\n"
    "IMPORTANT about syntax: every slash command is typed on its own line. The "
    "ONLY command that accepts text on the same line is /create-image. All the "
    "others are typed alone — they then open a dialog/panel or ask you a "
    "follow-up question. Never tell the user to append arguments to a command "
    "other than /create-image (e.g. '/add-image photo.png' does NOT work).\n"
    "Slash commands:\n"
    "- /help (or just '/') : show the list of commands. Typing '/' also shows "
    "live suggestions.\n"
    "- /create-image : generate a NEW image (saved as a PNG and opened "
    "automatically). Either write the description on the same line, e.g. "
    "'/create-image a red fox astronaut, watercolor', OR type '/create-image' "
    "alone and it will then ask you for the description.\n"
    "- /plugins : the plugin HUB (arrow menu). Options: see installed "
    "plugins ; ADD/CREATE (drop a .py in plugins/ or ask YOU to write one) ; "
    "INSTALL from the community marketplace (a shared online catalog — "
    "downloads and activates INSTANTLY, no restart) ; PUBLISH a local plugin "
    "TO the marketplace (PASSWORD-protected — only the owner can publish ; "
    "copies it into the repo, updates the registry and the site, then "
    "commit+push — the Vercel site auto-deploys in ~30s) ; "
    "disable / re-enable ; delete. All changes apply immediately. The "
    "marketplace site is at https://retroai-agent.vercel.app\n"
    "- /model : pick the CHAT model (arrow menu). Shows the current model, "
    "offers verified NVIDIA models plus a custom entry (any id from "
    "build.nvidia.com/models, tool-calling required). The change applies "
    "IMMEDIATELY (next message) and is saved to .env, so it stays until the "
    "user changes it again. The base/default model is "
    "nvidia/nemotron-3-ultra-550b-a55b.\n"
    "- /image : open the image panel. It shows the CURRENT generation model and "
    "lets you switch it: 1) FLUX (NVIDIA, free, default), 2) Nano Banana Pro "
    "(Google), 3) Nano Banana Flash (Google). Choosing a Google model asks for "
    "a GEMINI_API_KEY once (entered in the app, saved locally in .env). This "
    "command only configures the model; it does not generate anything.\n"
    "- /add-image : type it alone; a file-picker dialog opens, you choose an "
    "image, then it asks for an optional message; the image is sent FOR YOU TO "
    "ANALYZE. (Needs a graphical dialog; on Linux that means python3-tk.)\n"
    "- /paste : type it alone; it sends the image currently in the system "
    "clipboard FOR YOU TO ANALYZE. (Needs the Pillow library.)\n"
    "- /add-file : attach the content of a TEXT/code file (any kind) for you "
    "to analyze. Type '/add-file' alone to open a file picker, or '/add-file "
    "<path>' to give the path directly; it then asks for an optional message. "
    "(For images use /add-image instead, not /add-file.)\n"
    "- /compose : opens a text editor (notepad on Windows, nano on Linux, or "
    "$EDITOR e.g. \"code -w\") on a DEDICATED temporary file, to write or paste "
    "a long message / code block comfortably. The user writes below the marker "
    "line, saves and closes that window/tab, and the text is sent. "
    "'/compose <text>' pre-fills the editor. Empty file = cancel.\n"
    "- /write : multi-line input directly in the terminal (no editor). The "
    "user types lines and finishes with a single '.' on its own line (or "
    "Ctrl-D); Ctrl-C cancels. Suggest /compose or /write when the user wants "
    "to paste many lines of code (the normal input line is single-line: Enter "
    "sends).\n"
    "- /mode (or pressing Shift+Tab) : cycle the approval mode — normal (every "
    "action is confirmed, the default), auto-accept edits (file writes are "
    "auto-approved, shell still confirmed), plan mode (read-only: the agent "
    "investigates and proposes a plan without changing anything), auto-accept "
    "all (everything runs without confirmation). During any confirmation "
    "prompt, typing 'm' (or '/mode') also cycles the mode right there.\n"
    "- /think : set the reasoning effort level — low, medium, high, highx, "
    "ultra ('/think high' to set, '/think' to cycle). Higher = the agent "
    "thinks more thoroughly (slower); low = fast and direct.\n"
    "- /continue : resume an interrupted task, or (if nothing was "
    "interrupted) reload the most recently saved session.\n"
    "- /sessions : list all saved conversations (title, date, message count) "
    "and switch to any of them — nothing is ever lost when switching, every "
    "session is saved automatically after each turn.\n"
    "- /new : start a brand-new empty session. The previous conversation "
    "is NOT deleted — it stays saved and reachable via /sessions.\n"
    "- /reset : clear the current conversation. Same effect as /new (the "
    "old conversation is kept, safely, as a separate session).\n"
    "- /tuto : replay the short interactive getting-started tour (also shown "
    "automatically once, the very first time the app is used).\n"
    "- /restart : restart the whole app in a fresh process — reloads the "
    "code and the .env configuration (useful right after the software was "
    "updated). The conversation is saved automatically; after restarting, "
    "/continue picks it up again.\n"
    "- /btw : a fun token meter — shows how many tokens the LAST turn and "
    "the whole session used (input/output, plus an estimated count for the "
    "hidden reasoning). Values marked ~ are client-side estimates. The live "
    "'Thinking…' spinner shows the SAME counters in real time while the "
    "model thinks (current reasoning tokens + running session total), so "
    "there is no need to wait for the turn to end to check consumption.\n"
    "- /exit or /quit : quit the program.\n"
    "To send an image FOR YOU TO ANALYZE: use /add-image, or /paste, or simply "
    "mention an existing image file path (or an http(s) image URL) inside your "
    "message — it is attached automatically. You cannot paste raw image pixels "
    "into the text line (terminal limitation); use /paste for that. To CREATE a "
    "new image instead, use /create-image. "
    "When the user struggles, point them to the exact right command."
)

# Garde-fou anti-boucle infinie : le nombre max d'aller-retours d'outils par
# tour est desormais dans la config (config.max_iterations, defaut 25).


class AgentLoop:
    """Gere l'historique et le cycle complet d'un echange avec l'agent."""

    # Nombre de tours COMPLETEMENT vides (ni contenu, ni outil) tolerés
    # d'affilee avant d'abandonner. Un modele surcharge (ex. deepseek-v4-flash)
    # renvoie parfois du vide ; le tour suivant reussit presque toujours.
    MAX_TOURS_VIDES = 3

    def __init__(
        self,
        client: ApiClient,
        config: Config,
        infos_utilisateur: str = "",
    ) -> None:
        self.client = client
        self.config = config
        # Bloc d'infos sur l'utilisateur (issu de profile.py), ajoute au
        # message systeme pour personnaliser les reponses. Peut etre vide.
        self.infos_utilisateur = infos_utilisateur
        self.historique: list[dict] = []
        # Vrai si le dernier tour a ete interrompu (echec API) et reste a
        # reprendre. Permet a /continue de relancer la ou ca s'est arrete.
        self.tour_incomplet = False
        # Vrai si la derniere reponse a deja ete affichee en direct (streaming)
        # -> main n'a pas a la reafficher.
        self._stream_affiche = False
        # Identite de la session COURANTE (multi-conversations, voir sessions.py).
        # None = session neuve, jamais encore sauvegardee (un id est genere au
        # tout premier sauver_session()). session_titre est fige au 1er
        # message utilisateur pour rester stable au fil des sauvegardes.
        self.session_id: str | None = None
        self.session_titre: str | None = None
        # Compteurs de tokens (commande /btw + spinner). Runtime uniquement
        # (pas persistes). "entree"/"sortie" viennent du champ usage de l'API
        # quand il est present ; "raisonnement_est"/"sortie_est" sont des
        # ESTIMATIONS cote client (~4 chars/token) depuis le texte streame.
        self.jetons_session = self._jetons_zero()
        self.jetons_tour = self._jetons_zero()
        self.reset()

    @staticmethod
    def _jetons_zero() -> dict:
        return {"appels": 0, "entree": 0, "sortie": 0,
                "raisonnement_est": 0, "sortie_est": 0}

    def reset(self) -> None:
        """
        Vide l'historique et reinjecte le message systeme (commande /reset
        ou /new). IMPORTANT : detache aussi la session courante (session_id
        remis a None) -> la PRECEDENTE conversation reste intacte sur disque
        (listable/reprenable via /sessions) au lieu d'etre ecrasee par du vide
        au prochain autosave.
        """
        contenu = SYSTEME + "\n\n" + A_PROPOS + "\n\n" + AIDE_LOGICIEL
        if self.infos_utilisateur:
            contenu = contenu + "\n\n" + self.infos_utilisateur
        self.historique = [{"role": "system", "content": contenu}]
        self.tour_incomplet = False
        self.session_id = None
        self.session_titre = None
        self.jetons_session = self._jetons_zero()
        self.jetons_tour = self._jetons_zero()

    # ------------------------------------------------------------------ #
    #  Parsing robuste des arguments d'un tool call                      #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _parser_arguments(brut: str) -> dict:
        """
        Convertit la chaine JSON des arguments en dict Python.
        Retourne {} si la chaine est vide, et leve ValueError si le JSON
        est invalide (gere par l'appelant).
        """
        if not brut:
            return {}
        donnees = json.loads(brut)  # peut lever json.JSONDecodeError
        if not isinstance(donnees, dict):
            raise ValueError("Les arguments ne sont pas un objet JSON.")
        return donnees

    # ------------------------------------------------------------------ #
    #  Persistance multi-conversations (sessions.py) : /continue,        #
    #  /sessions, /new                                                   #
    # ------------------------------------------------------------------ #
    def sauver_session(self) -> None:
        """
        Enregistre l'historique dans le fichier de LA session courante
        (echec silencieux si impossible). Genere un id + un titre au tout
        premier appel pour une session neuve ; les reutilise ensuite pour
        toujours ecraser le MEME fichier (pas de doublons a chaque tour).

        Les images base64 sont allegees avant ecriture pour ne pas gonfler
        le fichier de session (voir images.alleger_pour_disque).
        """
        if self.session_id is None:
            self.session_id = sessions.generer_id()
        if self.session_titre is None:
            self.session_titre = sessions.deriver_titre(self.historique)
        sessions.sauver(
            self.session_id,
            images.alleger_pour_disque(self.historique),
            self.session_titre,
        )

    def charger_session_id(self, id_session: str) -> bool:
        """
        Remplace l'historique courant par celui d'une session sauvegardee
        (utilise par /continue et /sessions). Retourne True si trouvee et
        valide, False sinon (rien n'est modifie dans ce cas).
        """
        donnees = sessions.charger(id_session)
        if donnees is None:
            return False
        self.historique = donnees["historique"]
        self.session_id = donnees["id"]
        self.session_titre = donnees.get("titre")
        self.tour_incomplet = False
        return True

    # ------------------------------------------------------------------ #
    #  Appel API avec un reessai automatique (timeout / erreur reseau)   #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _executer_interruptible(fn):
        """
        Execute fn() dans un thread et attend par petits paliers (100 ms) afin
        que Ctrl+C reste REACTIF pendant l'appel reseau. Sans ca, l'appel HTTP
        bloquant (requests) ne rend la main au gestionnaire de signal qu'a la
        fin -> Ctrl+C inefficace ou tres en retard (notamment sous Windows).

        En cas de Ctrl+C, KeyboardInterrupt remonte immediatement ; le thread
        (daemon) finit en arriere-plan et son resultat est ignore.
        """
        resultat: dict = {}

        def worker():
            try:
                resultat["ok"] = fn()
            except BaseException as exc:  # on relaie toute erreur a l'appelant
                resultat["err"] = exc

        th = threading.Thread(target=worker, daemon=True)
        th.start()
        while th.is_alive():
            th.join(0.1)  # reveil regulier -> SIGINT (Ctrl+C) traite vite
        if "err" in resultat:
            raise resultat["err"]
        return resultat["ok"]

    def _appel_api(self) -> dict:
        """
        Appelle l'API. En STREAMING : la reponse s'affiche en direct (morceau
        par morceau) -> pas de timeout sur les longues generations, et Ctrl+C
        reste reactif (le flux rend la main tres souvent). Pas de retry en
        streaming (un partiel a deja pu s'afficher). En NON-streaming : spinner
        + appel interruptible + 1 reessai sur erreur reseau.
        """
        if self.config.stream:
            # Le spinner affiche le total de session EN DIRECT (facon Claude
            # Code) : tokens deja comptabilises + ceux du flux en cours.
            printer, cloturer, stats = ui.creer_stream_printer(
                session_tokens=self._total_session_estime
            )
            self._stream_affiche = False
            try:
                reponse = self.client.chat(
                    self.historique, tools=tools.TOOLS_SCHEMA, on_texte=printer
                )
            finally:
                # Vrai si du texte a ete affiche en direct (-> ne pas reafficher).
                self._stream_affiche = cloturer()
            self._comptabiliser(reponse, stats())
            return reponse

        # --- Mode non-streaming (reponse complete d'un coup) -------------
        derniere_erreur: ApiError | None = None
        for tentative in range(2):  # 1 essai + 1 reessai
            try:
                with ui.reflexion():
                    reponse = self._executer_interruptible(
                        lambda: self.client.chat(
                            self.historique, tools=tools.TOOLS_SCHEMA
                        )
                    )
                self._comptabiliser(reponse, None)
                return reponse
            except TimeoutApiError:
                # Un timeout sur une generation deja longue : inutile de
                # reessayer (on re-attendrait aussi longtemps). On remonte direct.
                raise
            except ApiError as exc:
                derniere_erreur = exc
                if tentative == 0:
                    ui.info("Network issue — retrying automatically…")
        # Les deux tentatives ont echoue.
        raise derniere_erreur  # type: ignore[misc]

    def _total_session_estime(self) -> int:
        """
        Total de tokens GENERES sur la session (reels si l'API les a fournis,
        sinon estimes), AVANT l'appel en cours. Sert au compteur live du
        spinner ("session ~N") : ui y ajoute les tokens du flux en cours.
        """
        s = self.jetons_session
        sortie = s["sortie"] or s["sortie_est"]
        return sortie + s["raisonnement_est"]

    def _comptabiliser(self, reponse: dict, flux: dict | None) -> None:
        """
        Met a jour les compteurs de tokens (tour + session) apres un appel.

        - reponse["usage"] : comptes REELS (prompt_tokens/completion_tokens)
          si le serveur les fournit ;
        - flux : compteurs de caracteres streames (pense_chars/reponse_chars),
          convertis en tokens ESTIMES (~4 chars/token) — seule source pour le
          raisonnement, et repli pour la sortie si usage est absent.
        Ne doit JAMAIS faire echouer un tour -> tolerant a tout format.
        """
        try:
            usage = reponse.get("usage") or {}
            entree = int(usage.get("prompt_tokens") or 0)
            sortie = int(usage.get("completion_tokens") or 0)
            pense_est = 0
            sortie_est = 0
            if flux:
                pense_est = flux.get("pense_chars", 0) // ui.CHARS_PAR_TOKEN
                sortie_est = flux.get("reponse_chars", 0) // ui.CHARS_PAR_TOKEN
            for compteurs in (self.jetons_tour, self.jetons_session):
                compteurs["appels"] += 1
                compteurs["entree"] += entree
                compteurs["sortie"] += sortie
                compteurs["raisonnement_est"] += pense_est
                compteurs["sortie_est"] += sortie_est
        except Exception:
            pass  # compteur "fun" : jamais au prix d'un tour casse

    # ------------------------------------------------------------------ #
    #  Traitement d'un tour de parole utilisateur                        #
    # ------------------------------------------------------------------ #
    def envoyer(self, message_utilisateur: str, chemins_images=None) -> str:
        """
        Ajoute le message de l'utilisateur puis traite le tour complet
        (appels API + outils) et retourne la reponse finale de l'agent.

        Les images sont jointes (contenu multimodal) si elles sont
        referencees dans le texte OU fournies via chemins_images (issu de
        /paste ou /add-image).
        """
        # Mode plan : on rappelle au modele de ne rien modifier et de planifier.
        if modes.est_plan():
            message_utilisateur = (
                "[Plan mode is active: do NOT edit files or run commands. "
                "Investigate using read-only tools only, then reply with a "
                "clear step-by-step plan and wait for approval.]\n\n"
                + message_utilisateur
            )

        # Niveau de reflexion : on injecte une consigne d'effort (si non vide).
        consigne_effort = thinking.consigne(self.config.thinking_level)
        if consigne_effort:
            message_utilisateur = f"[{consigne_effort}]\n\n" + message_utilisateur

        contenu, images_jointes = images.construire_contenu(
            message_utilisateur, chemins_images
        )
        for nom in images_jointes:
            ui.image_jointe(nom)
        self.historique.append({"role": "user", "content": contenu})
        return self._executer_tour()

    def reprendre(self) -> str:
        """
        Reprend un tour INTERROMPU sans ajouter de nouveau message.
        Le modele continue a partir des derniers resultats d'outils deja
        obtenus : toute la progression precedente est conservee.
        """
        return self._executer_tour()

    def _executer_tour(self) -> str:
        """
        Execute la boucle de dialogue avec gestion d'echec NON destructive.

        IMPORTANT : en cas d'echec API (apres le reessai auto de _appel_api),
        on NE supprime RIEN de l'historique. Toute la reflexion deja faite
        (resultats d'outils, etapes intermediaires) est conservee ET
        sauvegardee, pour pouvoir reprendre plus tard avec /continue sans
        repartir de zero.
        """
        # Nouveau tour -> remet a zero le compteur de tokens DU TOUR (/btw).
        self.jetons_tour = self._jetons_zero()
        try:
            reponse_finale = self._dialoguer()
        except (ApiError, KeyboardInterrupt):
            # Echec API OU stop utilisateur (Ctrl+C) : on marque le tour
            # comme incomplet et on PRESERVE tout (resultats d'outils, etapes).
            # -> /continue pourra reprendre la ou ca s'est arrete.
            self.tour_incomplet = True
            self.sauver_session()
            raise

        # Succes : tour termine, on sauvegarde l'etat complet. Exception : la
        # PAUSE budget d'outils (garde-fou max_iterations) laisse le tour
        # marque incomplet pour que /continue reprenne la tache en cours.
        self.tour_incomplet = getattr(self, "_pause_limite", False)
        self._pause_limite = False
        self.sauver_session()
        return reponse_finale

    def _dialoguer(self) -> str:
        """Boucle de dialogue : appels API + execution d'outils."""
        # Certains modeles (vecu en reel avec deepseek-v4-flash sous charge)
        # renvoient par intermittence un tour COMPLETEMENT vide : pas de
        # contenu, pas de tool_calls, finish_reason null, rien streame. Le
        # tour d'apres reussit presque toujours. On reessaie donc quelques
        # fois AVANT d'abandonner, au lieu d'afficher un "(empty response)".
        vides_consecutifs = 0
        for _ in range(self.config.max_iterations):
            reponse = self._appel_api()

            try:
                message = reponse["choices"][0]["message"]
            except (KeyError, IndexError) as exc:
                raise ApiError(f"Unexpected API response: {exc}") from exc

            tool_calls = message.get("tool_calls")
            finish = reponse["choices"][0].get("finish_reason")

            # Reponse VALIDE (outil demande OU contenu present) -> compteur
            # de vides remis a ZERO. BUG REEL corrige : sans ce reset, des
            # vides EPARPILLES dans un long tour (vide, 5 outils OK, vide,
            # vide...) finissaient par depasser la limite et faire abandonner
            # un tour qui PROGRESSAIT ("consecutifs" doit le rester).
            if tool_calls or (message.get("content") or "").strip():
                vides_consecutifs = 0

            # --- Cas 1 : pas d'outil demande -> reponse finale -----------
            if not tool_calls:
                contenu = message.get("content") or ""
                # Reponse coupee par la limite de tokens AVANT d'avoir produit
                # du contenu (typiquement : long raisonnement qui epuise le
                # budget). On le dit clairement au lieu d'un "empty response".
                if not contenu.strip() and finish == "length":
                    contenu = (
                        "[The answer was cut off: the model reached its output "
                        "limit (MAX_TOKENS) — often during long reasoning. Try "
                        "again, raise MAX_TOKENS in .env, or set "
                        "ENABLE_THINKING=false for very long code.]"
                    )
                    # Message synthetique : il n'a PAS ete streame a l'ecran,
                    # main doit donc l'afficher.
                    self._stream_affiche = False
                # Tour vide "degenere" (ni contenu, ni outil, coupure != length)
                # -> hoquet serveur/modele. On NE l'enregistre PAS dans
                # l'historique et on retente, jusqu'a MAX_TOURS_VIDES.
                elif not contenu.strip():
                    vides_consecutifs += 1
                    if vides_consecutifs <= self.MAX_TOURS_VIDES:
                        ui.info(
                            f"Empty response from the model — retrying "
                            f"({vides_consecutifs}/{self.MAX_TOURS_VIDES})…"
                        )
                        continue
                    contenu = (
                        "[The model returned an empty response several times "
                        "in a row. This usually means the model is overloaded "
                        "(NVIDIA capacity) — wait a moment and retry, or switch "
                        "NVIDIA_MODEL in .env then /restart.]"
                    )
                    self._stream_affiche = False
                self.historique.append({"role": "assistant", "content": contenu})
                return contenu

            # --- Cas 2 : le modele demande un ou plusieurs outils --------
            # On garde le message "assistant" (avec ses tool_calls) dans
            # l'historique pour la coherence de la conversation.
            self.historique.append(
                {
                    "role": "assistant",
                    "content": message.get("content") or "",
                    "tool_calls": tool_calls,
                }
            )

            for appel in tool_calls:
                nom = appel["function"]["name"]
                brut = appel["function"].get("arguments", "")

                # Parsing robuste des arguments (chaine JSON brute).
                try:
                    args = self._parser_arguments(brut)
                except (json.JSONDecodeError, ValueError) as exc:
                    resultat = (
                        f"Error: invalid JSON arguments for '{nom}' "
                        f"({exc}). Received arguments: {brut}"
                    )
                    # IMPORTANT : le modele peut generer des arguments JSON mal
                    # echappes sur du gros contenu (ex. un enorme fichier de
                    # code) -> json.loads() echoue ici (gere gracieusement),
                    # MAIS 'appel' est le MEME objet deja stocke dans
                    # self.historique (ligne ci-dessus) ; si on le laisse tel
                    # quel, cette chaine cassee est renvoyee a l'API a CHAQUE
                    # futur tour -> l'API la rejette encore et encore (HTTP 400
                    # "Invalid \escape"), empoisonnant la session en PERMANENCE.
                    # On la remplace par un JSON vide valide pour que la suite
                    # de la conversation reste utilisable.
                    appel["function"]["arguments"] = "{}"
                else:
                    resultat = tools.executer_outil(nom, args, self.config)

                # Apercu du resultat sous la ligne d'action (style Claude Code).
                ui.resultat_outil(resultat)

                # *** LE PIEGE NVIDIA NIM ***
                # On NE renvoie PAS role "tool". On reinjecte en role "user".
                self.historique.append(
                    {
                        "role": "user",
                        "content": f"[Tool result: {nom}]\n{resultat}",
                    }
                )
            # On reboucle : le modele voit les resultats et continue.

        # Garde-fou : trop d'iterations d'affilee. Ce n'est PAS un echec —
        # une longue tache legitime (ex. lire 15 fichiers) peut simplement
        # depasser le budget d'un tour. On fait donc une PAUSE reprenable :
        # tour marque incomplet -> /continue repart d'ici (bug reel corrige :
        # avant, le message disait "rephrase your request" et /continue ne
        # pouvait pas reprendre).
        message_limite = (
            f"[Paused: I reached this turn's tool budget "
            f"({self.config.max_iterations} rounds). Nothing is lost - type "
            "/continue and I will keep going right where I stopped. (You can "
            "also raise MAX_ITERATIONS in .env.)]"
        )
        # Message synthetique (pas streame) : main doit l'afficher.
        self._stream_affiche = False
        self._pause_limite = True
        self.historique.append({"role": "assistant", "content": message_limite})
        return message_limite
