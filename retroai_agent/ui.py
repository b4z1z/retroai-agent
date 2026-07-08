"""
ui.py - Couche d'affichage du terminal (interface inspiree de Claude Code).

Centralise TOUT le rendu visuel du projet. Utilise la bibliotheque 'rich'
si elle est installee (panneaux, markdown, couleurs, spinner) ; sinon, bascule
automatiquement sur un affichage texte simple. Le projet reste donc 100%
fonctionnel meme sans 'rich' (dependance optionnelle, cible = vieux PC).

Aucun autre module ne fait de print() decoratif : ils appellent ui.*.
"""

from __future__ import annotations

import contextlib
import os
import sys
import threading
import time

from . import modes

# Force la sortie console en UTF-8 (sinon, sous Windows en cp1252, les
# caracteres comme ✻ ⏺ › ou les accents font planter l'affichage).
# Sans effet sur Linux/macOS, deja en UTF-8.
for _flux in (sys.stdout, sys.stderr):
    try:
        _flux.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.markdown import Markdown
    from rich.text import Text

    RICH_DISPO = True
    _console = Console()
except ImportError:  # pragma: no cover - depend de l'environnement
    RICH_DISPO = False
    _console = None


def _largeur_visible() -> int:
    """
    Largeur VISIBLE du terminal (colonnes de la fenetre, pas du buffer).
    os.get_terminal_size() renvoie la fenetre visible sous Windows ; on s'en
    sert pour eviter que rich rende des lignes plus larges que la fenetre (ce
    qui fait couper les mots en deux par le terminal en mode fenetre).
    """
    try:
        return max(20, os.get_terminal_size().columns)
    except OSError:
        try:
            import shutil
            return max(20, shutil.get_terminal_size((80, 24)).columns)
        except Exception:
            return 80


def _rafraichir_console() -> None:
    """
    Recree la console en fixant sa largeur sur la largeur VISIBLE courante.
    Appelee a chaque tour (dans lire_saisie) -> suit le redimensionnement de
    la fenetre et garantit un retour a la ligne aux bons endroits (mots
    entiers), au lieu d'une coupure au milieu par le terminal.
    """
    global _console
    if RICH_DISPO:
        try:
            _console = Console(width=_largeur_visible())
        except Exception:
            pass

# prompt_toolkit : auto-completion EN DIRECT des commandes (Windows + Linux).
# Optionnel : si absent, on retombe sur une saisie classique.
try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.application import run_in_terminal
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.key_binding import KeyBindings

    PTK_DISPO = True
except ImportError:  # pragma: no cover
    PTK_DISPO = False


# Palette : accent rouge.
ACCENT = "#E03131"
DIM = "grey50"
# Danger en rouge plus sombre (+ titre "ACTION DANGEREUSE") pour rester
# distinct de l'accent rouge des elements normaux.
DANGER = "#9B1C1C"
SUCCES = "#3DD68C"

# Logo ASCII (genere avec un alignement fixe par glyphe).
LOGO = r"""████    ███   █████  ███  █████       ███   ███
█   █  █   █     █    █      █         █   █   █
████   █████    █     █     █          █   █████
█   █  █   █   █      █    █           █   █   █
████   █   █  █████  ███  █████   █   ███  █   █"""


# --------------------------------------------------------------------------- #
#  Auto-completion des commandes (prompt_toolkit)                             #
# --------------------------------------------------------------------------- #
if PTK_DISPO:

    class _CommandeCompleter(Completer):
        """Propose en direct les commandes des que la saisie commence par '/'."""

        def get_completions(self, document, complete_event):
            texte = document.text_before_cursor.lstrip()
            if not texte.startswith("/"):
                return
            # NOMS_COMMANDES est defini plus bas ; resolu au moment de l'appel.
            for nom in NOMS_COMMANDES:
                if nom.startswith(texte):
                    yield Completion(
                        nom,
                        start_position=-len(texte),
                        display=nom,
                    )

    # La session est creee PARESSEUSEMENT (au 1er usage, dans un vrai
    # terminal). La creer a l'import planterait hors console reelle.
    _session = None

    def _obtenir_session():
        """Retourne la PromptSession (creee a la demande), ou None si echec."""
        global _session
        if _session is None:
            try:
                # Saisie simple et FIABLE : Entree = envoyer (comportement par
                # defaut). On ajoute seulement Shift+Tab pour cycler les modes.
                # (Le multi-ligne via Alt+Entree sera repris plus tard ; un
                # override de la touche Entree cassait l'envoi des commandes.)
                kb = KeyBindings()

                @kb.add("s-tab")
                def _(event):
                    modes.cycler()
                    run_in_terminal(mode_actuel)  # texte simple au-dessus du prompt

                _session = PromptSession(
                    completer=_CommandeCompleter(),
                    complete_while_typing=True,
                    key_bindings=kb,
                )
            except Exception:
                return None
        return _session


# --------------------------------------------------------------------------- #
#  Banniere et accueil                                                        #
# --------------------------------------------------------------------------- #
def banniere(modele: str) -> None:
    """Affiche le grand panneau d'accueil de l'application (pleine largeur)."""
    if RICH_DISPO:
        contenu = Text(justify="center")
        contenu.append(LOGO + "\n\n", style=f"bold {ACCENT}")
        contenu.append("Autonomous CLI agent  ·  NVIDIA NIM\n", style="default")
        contenu.append(f"Model: {modele}\n", style=DIM)
        contenu.append("made by B4Z1Z · github.com/b4z1z\n\n", style=DIM)
        contenu.append("/help", style=f"bold {ACCENT}")
        contenu.append(" help     ", style=DIM)
        contenu.append("/continue", style=f"bold {ACCENT}")
        contenu.append(" resume     ", style=DIM)
        contenu.append("/reset", style=f"bold {ACCENT}")
        contenu.append(" clear     ", style=DIM)
        contenu.append("/exit", style=f"bold {ACCENT}")
        contenu.append(" quit", style=DIM)
        _console.print()
        _console.print(
            Panel(contenu, border_style=ACCENT, padding=(2, 4), expand=True)
        )
        _console.print()
    else:
        print("=" * 70)
        print("   BAZIZ.IA  -  lightweight CLI client for an autonomous agent (NIM)")
        print("   made by B4Z1Z · github.com/b4z1z")
        print(f"   Model: {modele}")
        print("   Commands: /help  /continue  /reset  /exit")
        print("=" * 70)


# Police pixel maison pour le message d'adieu (meme esprit que LOGO).
# Chaque glyphe = 5 lignes de 5 colonnes, pour un rendu "gros caracteres".
_FONT_ADIEU = {
    "A": [" ███ ", "█   █", "█████", "█   █", "█   █"],
    "B": ["████ ", "█   █", "████ ", "█   █", "████ "],
    "D": ["████ ", "█   █", "█   █", "█   █", "████ "],
    "E": ["█████", "█    ", "████ ", "█    ", "█████"],
    "G": [" ███ ", "█    ", "█  ██", "█   █", " ███ "],
    "O": [" ███ ", "█   █", "█   █", "█   █", " ███ "],
    "Y": ["█   █", " █ █ ", "  █  ", "  █  ", "  █  "],
    " ": ["     ", "     ", "     ", "     ", "     "],
}


def _texte_pixel(texte: str) -> str:
    """Assemble un texte en gros caracteres pixelises (5 lignes)."""
    lignes = ["", "", "", "", ""]
    for caractere in texte.upper():
        glyphe = _FONT_ADIEU.get(caractere, _FONT_ADIEU[" "])
        for i in range(5):
            lignes[i] += glyphe[i] + " "
    return "\n".join(lignes)


def au_revoir() -> None:
    """Affiche un grand 'GOODBYE' facon logo, centre, pour dire au revoir."""
    art = _texte_pixel("GOODBYE")
    lignes = art.split("\n")
    if RICH_DISPO:
        largeur = _largeur_visible()
        bloc = max(len(ligne) for ligne in lignes)
        marge = " " * max(0, (largeur - bloc) // 2)
        _console.print()
        for ligne in lignes:
            _console.print(Text(marge + ligne, style=f"bold {ACCENT}"))
        _console.print()
    else:
        print("\n" + art + "\n")


def saluer(pseudo: str) -> None:
    """Message de bienvenue personnalise (si un pseudo est connu)."""
    if not pseudo:
        return
    if RICH_DISPO:
        _console.print(f"[{DIM}]Welcome back,[/] [bold {ACCENT}]{pseudo}[/]!")
    else:
        print(f"  Welcome back, {pseudo}!")


# --------------------------------------------------------------------------- #
#  Entrees / sorties de conversation                                          #
# --------------------------------------------------------------------------- #
def lire_saisie() -> str:
    """
    Affiche une zone de saisie encadree (facon Claude Code) et lit la
    reponse de l'utilisateur. Peut lever EOFError / KeyboardInterrupt.

    Si prompt_toolkit est dispo ET qu'on est dans un vrai terminal, on
    profite de l'auto-completion EN DIRECT des commandes (tape '/').
    Sinon, on retombe sur une saisie classique (rich, puis input()).
    """
    # Aligne la largeur de rendu sur la fenetre visible courante (suit le
    # resize ; evite la coupure des mots en mode fenetre).
    _rafraichir_console()

    # Haut du cadre (commun a tous les modes). On laisse 1 colonne de marge
    # (largeur - 1) pour ne pas declencher un retour a la ligne du terminal.
    largeur = _largeur_visible() if RICH_DISPO else 80
    haut = "╭─ You " + "─" * max(0, largeur - 8)
    if RICH_DISPO:
        _console.print()
        _console.print(haut, style=ACCENT)
    else:
        print("\n" + haut)

    # Mode 1 : prompt_toolkit (auto-completion live) — uniquement en vrai TTY.
    if PTK_DISPO and sys.stdin.isatty():
        session = _obtenir_session()
        if session is not None:
            try:
                return session.prompt(
                    HTML(f'<b><style fg="{ACCENT}">╰─› </style></b>')
                ).strip()
            except (EOFError, KeyboardInterrupt):
                raise
            except Exception:
                pass  # probleme ptk -> on retombe sur les modes suivants

    # Le coin bas-gauche "╰─›" sert d'invite : le cadre parait ferme et soigne
    # sans devoir dessiner une ligne sous le curseur (impossible avec input()).
    # Mode 2 : rich (sans completion live).
    if RICH_DISPO:
        return _console.input(f"[bold {ACCENT}]╰─›[/] ").strip()

    # Mode 3 : input() basique.
    return input("╰─› ").strip()


def _stream_entete() -> None:
    """En-tete affiche une fois, juste avant le 1er fragment streame."""
    if RICH_DISPO:
        _console.print()
        _console.print(f"[bold {ACCENT}]⏺ BAZIZ.IA[/]")
        _console.print()
    else:
        print("\nBAZIZ.IA >")


class _Attente:
    """
    Spinner anime (thread) affiche PENDANT que le modele reflechit, avant le
    1er morceau de reponse streame. Donne un retour visuel (sinon ca parait
    fige, surtout en /think ultra). S'efface des le 1er fragment.
    """

    FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def __init__(self, message: str = "Thinking", extra=None) -> None:
        self._stop = threading.Event()
        self._th: threading.Thread | None = None
        self.message = message
        # Callable optionnel -> texte ajoute en direct dans la ligne du
        # spinner (ex. compteur de tokens de raisonnement consommes).
        self._extra = extra

    def demarrer(self) -> None:
        def run() -> None:
            debut = time.monotonic()
            i = 0
            while not self._stop.is_set():
                secondes = int(time.monotonic() - debut)
                extra = ""
                if self._extra is not None:
                    try:
                        extra = self._extra() or ""
                    except Exception:
                        extra = ""
                sys.stdout.write(
                    f"\r  {self.FRAMES[i % len(self.FRAMES)]} {self.message}… "
                    f"{secondes}s{extra} (Ctrl+C to stop)  "
                )
                sys.stdout.flush()
                i += 1
                self._stop.wait(0.1)
            sys.stdout.write("\r" + " " * 76 + "\r")  # efface la ligne
            sys.stdout.flush()

        self._th = threading.Thread(target=run, daemon=True)
        self._th.start()

    def arreter(self) -> None:
        if self._th is not None:
            self._stop.set()
            self._th.join(timeout=0.5)
            self._th = None


# Estimation grossiere : ~4 caracteres par token (suffisant pour un compteur
# "fun" affiche en direct ; les vrais comptes viennent de l'API quand dispo).
CHARS_PAR_TOKEN = 4


def creer_stream_printer():
    """
    Cree (printer, cloturer, stats) pour afficher une reponse EN DIRECT.

    Le RAISONNEMENT (mode thinking) n'est PAS affiche : pendant que le modele
    reflechit, le spinner "Thinking… Ns · ~T tok" tourne, avec un COMPTEUR DE
    TOKENS estime en direct (caracteres de raisonnement recus / 4). La
    REPONSE, elle, s'affiche au fil de l'eau sous l'en-tete "⏺ BAZIZ.IA".

    printer(fragment, reflexion=False) ; cloturer() -> True si une REPONSE a
    ete affichee ; stats() -> {"pense_chars": N, "reponse_chars": M} (sert au
    compteur de tokens de /btw quand l'API ne renvoie pas de champ usage).
    """
    compteur = {"pense_chars": 0, "reponse_chars": 0}

    def _suffixe_tokens() -> str:
        if compteur["pense_chars"] == 0:
            return ""
        return f" · ~{compteur['pense_chars'] // CHARS_PAR_TOKEN} tok"

    attente = _Attente(extra=_suffixe_tokens)
    attente.demarrer()
    etat = {"ouvert": False}

    def printer(fragment: str, reflexion: bool = False) -> None:
        if reflexion:
            # Raisonnement masque : on le COMPTE (compteur live du spinner
            # + stats pour /btw), sans l'afficher.
            compteur["pense_chars"] += len(fragment)
            return
        compteur["reponse_chars"] += len(fragment)
        if not etat["ouvert"]:
            attente.arreter()
            _stream_entete()
            etat["ouvert"] = True
        sys.stdout.write(fragment)
        sys.stdout.flush()

    def cloturer() -> bool:
        attente.arreter()  # au cas ou aucune reponse n'est arrivee
        if etat["ouvert"]:
            sys.stdout.write("\n")
            sys.stdout.flush()
        return etat["ouvert"]

    def stats() -> dict:
        return dict(compteur)

    return printer, cloturer, stats


def reponse_agent(texte: str) -> None:
    """Affiche la reponse de l'agent (rendue en Markdown si rich dispo)."""
    if not texte:
        texte = "_(empty response)_"
    if RICH_DISPO:
        _console.print()                       # ligne vide avant
        _console.print(f"[bold {ACCENT}]⏺ BAZIZ.IA[/]")
        _console.print()                       # respiration avant le contenu
        _console.print(Markdown(texte))
        _console.print()                       # ligne vide apres (separation du tour)
    else:
        print(f"\nBAZIZ.IA > {texte}\n")


# --------------------------------------------------------------------------- #
#  Messages d'etat                                                            #
# --------------------------------------------------------------------------- #
def info(texte: str) -> None:
    """Message d'information discret (gris)."""
    if RICH_DISPO:
        _console.print(f"[{DIM}]{texte}[/]")
    else:
        print(f"  {texte}")


def en_developpement(nom: str) -> None:
    """Signale qu'une fonctionnalite est en cours de developpement (a venir)."""
    if RICH_DISPO:
        _console.print(
            f"[bold {ACCENT}]🚧 {nom}[/] [{DIM}]is under development — coming soon.[/]"
        )
    else:
        print(f"  [{nom}] under development - coming soon.")


def succes(texte: str) -> None:
    if RICH_DISPO:
        _console.print(f"[{SUCCES}]{texte}[/]")
    else:
        print(f"  {texte}")


def erreur(texte: str) -> None:
    """Message d'erreur (rouge)."""
    if RICH_DISPO:
        _console.print(f"[bold {DANGER}]✗ {texte}[/]")
    else:
        print(f"  [Erreur] {texte}")


def selecteur(titre: str, texte: str, options: list, defaut=None):
    """
    Menu a FLECHES (haut/bas) pour choisir parmi 'options'. Retourne la valeur
    choisie, ou None si annule / indisponible (l'appelant gere alors un repli).

    options : liste de couples (valeur, libelle_affiche).
    Necessite prompt_toolkit + un vrai terminal ; sinon renvoie None.
    """
    if not (PTK_DISPO and sys.stdin.isatty()):
        return None
    try:
        from prompt_toolkit.shortcuts import radiolist_dialog
        from prompt_toolkit.styles import Style

        style = Style.from_dict({
            "dialog frame.label": f"bg:{ACCENT} #ffffff",
            "button.focused": f"bg:{ACCENT} #ffffff",
            "radio-selected": f"{ACCENT}",
        })
        return radiolist_dialog(
            title=titre, text=texte, values=options, default=defaut, style=style
        ).run()
    except Exception:
        return None


def demander_texte(invite: str) -> str:
    """Pose une question texte simple (sans cadre ni auto-completion)."""
    if RICH_DISPO:
        return _console.input(f"[bold {ACCENT}]{invite}[/] ").strip()
    return input(f"  {invite} ").strip()


def lire_multiligne(sentinelle: str = ".") -> str:
    """
    Lit plusieurs lignes au clavier jusqu'a une ligne contenant SEULEMENT la
    sentinelle (ex. '.') ou jusqu'a Ctrl-D (EOF). Retourne le texte assemble.
    Alternative a l'editeur externe : pas d'editeur a ouvrir/fermer.
    KeyboardInterrupt (Ctrl-C) remonte a l'appelant (annulation).
    """
    lignes: list[str] = []
    while True:
        try:
            ligne = input()
        except EOFError:  # Ctrl-D -> fin de saisie
            break
        if ligne.strip() == sentinelle:
            break
        lignes.append(ligne)
    return "\n".join(lignes)


def image_jointe(nom: str) -> None:
    """Confirme visuellement qu'une image a ete jointe au message."""
    if RICH_DISPO:
        _console.print(f"[{ACCENT}]🖼[/]  [{DIM}]image attached: {nom}[/]")
    else:
        print(f"  [image attached: {nom}]")


def fichier_joint(chemin: str, taille: int) -> None:
    """Confirme visuellement qu'un fichier texte/code a ete joint au message."""
    nom = os.path.basename(chemin)
    if RICH_DISPO:
        _console.print(
            f"[{ACCENT}]📄[/]  [{DIM}]file attached: {nom} ({taille} chars)[/]"
        )
    else:
        print(f"  [file attached: {nom} ({taille} chars)]")


def menu_image(courant: str, gemini_pret: bool) -> None:
    """
    Affiche le panneau /image : modele courant, commandes image, et options
    pour changer de modele de generation. 'gemini_pret' indique si une cle
    Gemini est deja enregistree (sinon on signale qu'elle sera demandee).
    """
    note_gemini = "" if gemini_pret else "  (a Google API key will be asked once)"
    if RICH_DISPO:
        t = Text()
        t.append("Image generation\n\n", style=f"bold {ACCENT}")
        t.append("Current model: ", style=DIM)
        t.append(courant + "\n\n", style="bold")
        t.append("Commands:\n", style=DIM)
        t.append("  /create-image", style=f"bold {ACCENT}")
        t.append("  generate from text\n", style=DIM)
        t.append("  /add-image", style=f"bold {ACCENT}")
        t.append("     send an image from a file\n", style=DIM)
        t.append("  /paste", style=f"bold {ACCENT}")
        t.append("         send an image from clipboard\n\n", style=DIM)
        t.append("Change generation model:\n", style=DIM)
        t.append("  1) FLUX.1            ", style=f"bold {ACCENT}")
        t.append("NVIDIA · free · default\n", style=DIM)
        t.append("  2) Nano Banana Pro   ", style=f"bold {ACCENT}")
        t.append(f"Google · best quality{note_gemini}\n", style=DIM)
        t.append("  3) Nano Banana Flash ", style=f"bold {ACCENT}")
        t.append(f"Google · faster{note_gemini}\n", style=DIM)
        _console.print()
        _console.print(Panel(t, border_style=ACCENT, padding=(1, 4), expand=True))
    else:
        print("\nImage generation")
        print(f"  Current model: {courant}")
        print("  Commands: /create-image  /add-image  /paste")
        print("  Change model:")
        print("    1) FLUX.1            NVIDIA · free · default")
        print(f"    2) Nano Banana Pro   Google · best quality{note_gemini}")
        print(f"    3) Nano Banana Flash Google · faster{note_gemini}")


def libelle_session(session: dict, id_courant: str | None = None) -> str:
    """
    Construit le libelle d'une session pour le selecteur /sessions :
    titre tronque + date + nb de messages, avec un marqueur si c'est la
    session actuellement ouverte.
    """
    marque = "→ " if session["id"] == id_courant else "  "
    date = session.get("maj", "")[:16].replace("T", " ")  # "2026-07-06 20:15"
    titre = session.get("titre", "New session")
    return f"{marque}{titre:<40} {date}  · {session.get('nb_messages', 0)} msgs"


def sessions_vides() -> None:
    """Aucune session sauvegardee (ni en cours, ni sur disque)."""
    info("No saved sessions yet. Just start chatting — it's saved automatically.")


def session_restauree(titre: str, nb_messages: int) -> None:
    """Confirme le chargement d'une session (via /continue ou /sessions)."""
    if RICH_DISPO:
        _console.print(
            f"[{SUCCES}]↺ Session restored:[/] [bold]{titre}[/] "
            f"[{DIM}]({nb_messages} messages)[/]"
        )
    else:
        print(f"  [Session restored: {titre} ({nb_messages} messages)]")


def panneau_info(titre: str, lignes: list, etape: str = "") -> None:
    """
    Panneau d'information generique (non lie a une confirmation) : utilise
    par le tutoriel /tuto pour ses ecrans successifs.
    """
    if RICH_DISPO:
        contenu = Text()
        if etape:
            contenu.append(f"{etape}\n\n", style=DIM)
        contenu.append(f"{titre}\n\n", style=f"bold {ACCENT}")
        for ligne in lignes:
            contenu.append(f"{ligne}\n", style="default")
        _console.print()
        _console.print(Panel(contenu, border_style=ACCENT, padding=(1, 4), expand=True))
    else:
        print()
        if etape:
            print(f"[{etape}]")
        print(f"=== {titre} ===")
        for ligne in lignes:
            print(f"  {ligne}")


def pause(invite: str = "Press Enter to continue (type 'skip' to exit the tour):") -> str:
    """
    Attend une saisie (Entree ou texte) ; retourne le texte en minuscules.

    Utilisee par le tutoriel (/tuto), qui doit rester 100% incassable au tout
    premier lancement de l'app : si le flux d'entree n'est pas lisible pour
    QUELQUE raison que ce soit (EOFError classique, mais aussi OSError dans
    certains environnements non-interactifs ou stdin redirige/ferme), on
    n'ecrase pas l'application avec une exception -> on sort proprement du
    tutoriel (comme si l'utilisateur avait tape 'skip').
    """
    try:
        if RICH_DISPO:
            return _console.input(f"[{DIM}]{invite}[/] ").strip().lower()
        return input(f"  {invite} ").strip().lower()
    except (EOFError, OSError):
        return "skip"


def quota_atteint() -> None:
    """Avertit que le palier gratuit Gemini est epuise et liste les options."""
    if RICH_DISPO:
        t = Text()
        t.append("Gemini free-tier limit reached\n\n", style=f"bold {DANGER}")
        t.append("Your daily free quota for Nano Banana is exhausted.\n\n",
                 style="default")
        t.append("Options:\n", style=DIM)
        t.append("  • Switch to FLUX (free) and keep generating\n", style=DIM)
        t.append("  • Wait — the free quota resets daily\n", style=DIM)
        t.append("  • Use an upgraded / paid Google API key\n", style=DIM)
        _console.print()
        _console.print(
            Panel(t, title="⚠  Quota reached", border_style=DANGER,
                  padding=(1, 4), expand=True)
        )
    else:
        print("\n  [Gemini free-tier limit reached]")
        print("  Options: switch to FLUX (free) · wait (resets daily) · upgrade key")


def image_creee(chemin: str) -> None:
    """Confirme qu'une image a ete generee et indique ou elle est enregistree."""
    if RICH_DISPO:
        _console.print()
        _console.print(f"[{SUCCES}]🎨 Image generated[/] [{DIM}]→[/] [bold {ACCENT}]{chemin}[/]")
    else:
        print(f"\n  [Image generated: {chemin}]")


def astuce_modes(categorie: str = "") -> None:
    """
    Petit rappel (texte simple, discret) affiche lors d'une demande de
    confirmation. Le message precise QUEL mode auto sauterait CETTE
    confirmation : 'auto-accept edits' couvre seulement les ecritures de
    fichiers ; les commandes shell ne sont sautees que par 'auto-accept all'.
    """
    if categorie == "edit":
        texte = ("Tip: type 'm' (or Shift+Tab) → 'auto-accept edits' (or "
                 "'all') to stop confirming file writes.")
    elif categorie == "command":
        texte = ("Tip: type 'm' (or Shift+Tab) → 'auto-accept all' to stop "
                 "confirming commands ('auto-accept edits' covers file writes only).")
    else:
        texte = ("Tip: type 'm' (or Shift+Tab) → auto-accept to skip these "
                 "prompts, or plan mode.")
    if RICH_DISPO:
        _console.print(f"[{DIM}]{texte}[/]")
    else:
        print(f"  {texte}")


def _ligne_jetons(compteurs: dict) -> str:
    """Formate une ligne de compteur de tokens ('?' si l'API n'a rien donne)."""
    entree = f"{compteurs['entree']:,}".replace(",", " ") if compteurs["entree"] else "?"
    if compteurs["sortie"]:
        sortie = f"{compteurs['sortie']:,}".replace(",", " ")
    elif compteurs["sortie_est"]:
        sortie = f"~{compteurs['sortie_est']:,}".replace(",", " ")
    else:
        sortie = "?"
    pense = compteurs["raisonnement_est"]
    detail_pense = f"  ·  thinking ~{pense:,}".replace(",", " ") if pense else ""
    return f"in {entree}  ·  out {sortie}{detail_pense}"


def afficher_jetons(tour: dict, session: dict) -> None:
    """
    Commande /btw : petit compteur de tokens "pour le fun".
    'in/out' = comptes reels renvoyes par l'API (usage) quand disponibles ;
    'thinking ~N' et les valeurs prefixees de ~ sont des ESTIMATIONS cote
    client (~4 caracteres/token) depuis le texte streame.
    """
    if RICH_DISPO:
        t = Text()
        t.append("🤔 btw — token meter\n\n", style=f"bold {ACCENT}")
        t.append("Last turn : ", style=DIM)
        t.append(_ligne_jetons(tour) + "\n", style="default")
        t.append("Session   : ", style=DIM)
        t.append(_ligne_jetons(session), style="default")
        t.append(f"   ({session['appels']} API calls)\n\n", style=DIM)
        t.append("~ values are client-side estimates (≈4 chars/token); "
                 "'?' = the API did not report usage.", style=DIM)
        _console.print()
        _console.print(Panel(t, border_style=DIM, padding=(1, 4), expand=True))
    else:
        print("\n[btw - token meter]")
        print(f"  Last turn : {_ligne_jetons(tour)}")
        print(f"  Session   : {_ligne_jetons(session)}  ({session['appels']} API calls)")
        print("  (~ = estimate, ? = usage not reported by the API)")


def niveau_thinking(niveau: str) -> None:
    """Affiche le niveau de reflexion courant (apres un changement)."""
    if RICH_DISPO:
        _console.print(
            f"[bold {ACCENT}]🧠 Thinking level:[/] [bold]{niveau}[/]"
        )
    else:
        print(f"  Thinking level: {niveau}")


def mode_actuel() -> None:
    """Affiche le mode d'approbation courant (apres un changement)."""
    nom = modes.label()
    if RICH_DISPO:
        couleur = DIM if modes.courant() == modes.NORMAL else ACCENT
        _console.print(f"[bold {couleur}]⏵ Approval mode:[/] [bold]{nom}[/]")
    else:
        print(f"  Approval mode: {nom}")


def stop_reflexion() -> None:
    """Message affiche quand l'utilisateur stoppe l'agent avec Ctrl+C."""
    if RICH_DISPO:
        _console.print()
        _console.print(f"[bold {ACCENT}]⏹ Stopped.[/]")
        _console.print(
            f"[{DIM}]Type [/][bold {ACCENT}]/continue[/]"
            f"[{DIM}] to resume where it stopped.[/]"
        )
    else:
        print("\n  [Stopped. Type /continue to resume.]")


def action_outil(nom: str, detail: str = "") -> None:
    """Affiche l'action d'un outil facon Claude Code : ⏺ nom (detail)."""
    if RICH_DISPO:
        _console.print()  # respiration avant le bloc outil
        ligne = Text()
        ligne.append("⏺ ", style=ACCENT)
        ligne.append(nom, style="bold")
        if detail:
            ligne.append(f"  {detail}", style=DIM)
        _console.print(ligne)
    else:
        suffixe = f" : {detail}" if detail else ""
        print(f"\n  [TOOL] {nom}{suffixe}")


def resultat_outil(resultat: str, max_lignes: int = 4) -> None:
    """
    Affiche un apercu du resultat d'un outil sous la ligne d'action,
    avec le connecteur ⎿ facon Claude Code. Tronque a max_lignes.
    Le texte est affiche SANS interpretation de balisage (markup=False)
    pour ne pas casser l'affichage si le resultat contient des crochets.
    """
    lignes = (resultat or "").strip().splitlines() or [""]
    apercu = lignes[:max_lignes]
    reste = len(lignes) - len(apercu)

    if RICH_DISPO:
        for i, ligne in enumerate(apercu):
            prefixe = "  ⎿ " if i == 0 else "    "
            _console.print(
                Text(prefixe + ligne, style=DIM), markup=False, highlight=False
            )
        if reste > 0:
            _console.print(Text(f"    … (+{reste} lines)", style=DIM))
    else:
        for i, ligne in enumerate(apercu):
            prefixe = "  |_ " if i == 0 else "     "
            print(f"{prefixe}{ligne}")
        if reste > 0:
            print(f"     ... (+{reste} lines)")


@contextlib.contextmanager
def reflexion(message: str = "Thinking…"):
    """
    Indicateur d'attente pendant un appel API. Spinner anime si rich dispo,
    sinon simple ligne de texte. Affiche l'astuce "(Ctrl+C to stop)".
    A utiliser autour de l'appel reseau SEUL (jamais autour d'un input()).
    """
    if RICH_DISPO:
        texte = f"[{ACCENT}]{message}[/] [{DIM}](Ctrl+C to stop)[/]"
        with _console.status(texte, spinner="dots"):
            yield
    else:
        print(f"  {message} (Ctrl+C to stop)", flush=True)
        yield


# --------------------------------------------------------------------------- #
#  Aide                                                                       #
# --------------------------------------------------------------------------- #
# Source UNIQUE des commandes : utilisee par aide(), l'export texte et le
# handler "/" de main.py. Modifier ici suffit a tout mettre a jour.
COMMANDES = [
    ("/help", "Show this help"),
    ("/tuto", "Replay the interactive getting-started tour"),
    ("/image", "Image panel: choose the generation model (FLUX / Nano Banana)"),
    ("/add-image", "Pick an image via a file dialog and send it"),
    ("/add-file", "Attach a text/code file's content for analysis"),
    ("/compose", "Open an editor for a long message / code block"),
    ("/write", "Type a multi-line message inline (end with a '.' line)"),
    ("/paste", "Send the image from your clipboard"),
    ("/create-image", "Generate an image from a text description"),
    ("/mode", "Cycle approval mode (or Shift+Tab): normal / edits / plan / all"),
    ("/think", "Pick reasoning effort with arrows (low → ultra)"),
    ("/continue", "Resume an interrupted task, or the last session"),
    ("/sessions", "List saved conversations and switch between them"),
    ("/new", "Start a brand-new session (previous one stays saved)"),
    ("/reset", "Clear the conversation (same as /new)"),
    ("/btw", "Fun token meter — tokens used by the last turn and the session"),
    ("/restart", "Restart the app (reloads code & .env; conversation stays saved)"),
    ("/exit, /quit", "Quit the program"),
]


# Liste plate des noms de commandes (pour les suggestions par prefixe).
# "/exit, /quit" -> ["/exit", "/quit"].
NOMS_COMMANDES = [
    nom.strip()
    for cmd, _ in COMMANDES
    for nom in cmd.split(",")
]


def commandes_correspondantes(prefixe: str) -> list[str]:
    """Retourne les commandes qui commencent par 'prefixe' (suggestions)."""
    prefixe = prefixe.strip().lower()
    return [nom for nom in NOMS_COMMANDES if nom.startswith(prefixe)]


def suggestions(prefixe: str) -> None:
    """Affiche des suggestions de commandes pour un prefixe saisi."""
    correspondances = commandes_correspondantes(prefixe)
    if RICH_DISPO:
        if correspondances:
            ligne = Text()
            ligne.append("Suggestions: ", style=DIM)
            ligne.append("   ".join(correspondances), style=f"bold {ACCENT}")
            _console.print(ligne)
        else:
            _console.print(
                f'[{DANGER}]No command matches "{prefixe}".[/]'
            )
    else:
        if correspondances:
            print("  Suggestions: " + "   ".join(correspondances))
        else:
            print(f'  No command matches "{prefixe}".')


def aide() -> None:
    """Affiche l'aide des commandes (depuis la source unique COMMANDES)."""
    if RICH_DISPO:
        contenu = Text()
        contenu.append("Available commands\n\n", style=f"bold {ACCENT}")
        for cmd, desc in COMMANDES:
            contenu.append(f"  {cmd:14}", style=f"bold {ACCENT}")
            contenu.append(f"{desc}\n", style=DIM)
        contenu.append("\nApproval modes — press ", style=DIM)
        contenu.append("Shift+Tab", style=f"bold {ACCENT}")
        contenu.append(" (or /mode) to cycle:\n", style=DIM)
        contenu.append(
            "  normal (confirm all) · auto-accept edits · plan (read-only) · "
            "auto-accept all\n",
            style=DIM,
        )
        contenu.append(
            "\nOtherwise, type your request and press Enter.\n", style=DIM
        )
        contenu.append("Need help using BAZIZ.IA? ", style=DIM)
        contenu.append("Just ask me", style=f"bold {ACCENT}")
        contenu.append(
            ' — e.g. "how do I send an image?" or "how does /continue work?".',
            style=DIM,
        )
        _console.print(Panel(contenu, border_style=DIM, padding=(1, 4), expand=True))
    else:
        print("\nAvailable commands:")
        for cmd, desc in COMMANDES:
            print(f"  {cmd:14} {desc}")
        print("\nApproval modes — Shift+Tab (or /mode) to cycle:")
        print("  normal (confirm all) · auto-accept edits · plan (read-only) "
              "· auto-accept all")
        print("Otherwise, type your request and press Enter.")
        print('Need help using BAZIZ.IA? Just ask me '
              '(e.g. "how do I send an image?").')


def exporter_commandes(chemin: str = "COMMANDES.txt") -> None:
    """
    Ecrit un fichier texte listant toutes les commandes (facon 'help' cmd).
    Genere depuis COMMANDES -> reste toujours a jour. Echec silencieux.
    """
    lignes = [
        "============================================================",
        "  BAZIZ.IA - Interface commands",
        "============================================================",
        "",
        "Type one of these commands at the prompt, or '/' to show",
        "this list directly in the terminal.",
        "",
    ]
    for cmd, desc in COMMANDES:
        lignes.append(f"  {cmd:14} {desc}")
    lignes += [
        "",
        "Any other text is sent as a message to the agent.",
        "",
        "Need help using BAZIZ.IA? Just ask the agent in plain language,",
        '  e.g. "how do I send an image?" or "how does /create-image work?".',
        "",
    ]
    try:
        with open(chemin, "w", encoding="utf-8") as f:
            f.write("\n".join(lignes))
    except OSError:
        pass


# --------------------------------------------------------------------------- #
#  Confirmation (utilisee par safety.py)                                      #
# --------------------------------------------------------------------------- #
def panneau_confirmation(titre: str, details: str, dangereux: bool = False) -> None:
    """Affiche le panneau decrivant l'action a confirmer."""
    if RICH_DISPO:
        couleur = DANGER if dangereux else ACCENT
        contenu = Text()
        contenu.append(f"{titre}\n\n", style=f"bold {couleur}")
        contenu.append(details, style="default")
        titre_panneau = "⚠  DANGEROUS ACTION" if dangereux else "Confirmation required"
        _console.print()
        _console.print(
            Panel(
                contenu,
                title=titre_panneau,
                border_style=couleur,
                padding=(1, 4),
                expand=True,
            )
        )
    else:
        print()
        print("  +-----------------------------------------------------------+")
        marque = "DANGEROUS ACTION" if dangereux else "CONFIRMATION REQUIRED"
        print(f"  |  {marque}")
        print("  +-----------------------------------------------------------+")
        print(f"  Action: {titre}")
        for ligne in details.splitlines():
            print(f"    {ligne}")
        print()


def _mode_couvre(categorie: str) -> bool:
    """Le mode courant auto-approuve-t-il une action de cette categorie ?"""
    if categorie == "edit":
        return modes.auto_edits()
    return modes.auto_tout()  # "command" ou generique -> seul auto-all couvre


# Reponses qui, tapees a une confirmation, cyclent le mode d'approbation.
# Fiable dans TOUT terminal (contrairement a Shift+Tab, qui depend de ce que
# le terminal transmet et peut ne pas marcher partout) : c'est du texte simple.
_DECLENCHEURS_MODE = ("m", "mode", "/mode")


def _lire_reponse_brute(invite: str) -> str:
    """
    Lit UNE ligne de reponse a la confirmation. Avec prompt_toolkit, Shift+Tab
    est aussi cable : il insere 'm' et valide, pour rejoindre le meme chemin
    que taper 'm' a la main (voir lire_oui_non). Repli rich/input sinon.
    """
    if PTK_DISPO and sys.stdin.isatty():
        try:
            kb = KeyBindings()

            @kb.add("s-tab")
            def _(event):
                buf = event.current_buffer
                buf.text = "m"
                buf.validate_and_handle()

            return PromptSession(key_bindings=kb).prompt(
                HTML(f'<b><style fg="{ACCENT}">{invite}</style></b> '
                     f'<style fg="{DIM}">(y/n · Shift+Tab or type m: change mode)</style> ')
            )
        except (EOFError, KeyboardInterrupt):
            raise
        except Exception:
            pass  # souci ptk -> repli ci-dessous

    if RICH_DISPO:
        return _console.input(
            f"[bold {ACCENT}]{invite}[/] [{DIM}](y/n · type m: change mode)[/] "
        )
    return input(f"  {invite} (y/n · type m: change mode) ")


def lire_oui_non(invite: str = "Confirm?", categorie: str = "") -> str:
    """
    Lit une reponse de confirmation (y/n). Deux facons de changer de mode
    SANS quitter la confirmation :
      - taper 'm' (ou '/mode', ou faire Shift+Tab si dispo) -> CYCLE au mode
        suivant ;
      - taper le NOM d'un mode directement (ex. 'all', 'edits', 'plan',
        'normal' — les memes mots que ceux affiches par l'astuce) -> bascule
        DIRECTEMENT sur ce mode (voir modes.definir/ALIAS).
    Dans les deux cas, si le nouveau mode couvre deja cette confirmation,
    elle est auto-approuvee tout de suite ; sinon la question est reposee.
    """
    while True:
        try:
            brute = _lire_reponse_brute(invite)
        except (EOFError, KeyboardInterrupt):
            raise
        reponse = (brute or "").strip().lower()

        change = False
        if reponse in _DECLENCHEURS_MODE:
            modes.cycler()
            change = True
        elif modes.definir(reponse):
            change = True

        if change:
            mode_actuel()
            if _mode_couvre(categorie):
                return "y"
            continue  # re-pose la question avec le nouveau mode
        return reponse
