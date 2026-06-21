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
import sys

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

# prompt_toolkit : auto-completion EN DIRECT des commandes (Windows + Linux).
# Optionnel : si absent, on retombe sur une saisie classique.
try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.formatted_text import HTML

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
                _session = PromptSession(
                    completer=_CommandeCompleter(),
                    complete_while_typing=True,
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
        largeur = max(20, _console.size.width)
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
    # Haut du cadre (commun a tous les modes).
    largeur = max(20, _console.size.width) if RICH_DISPO else 80
    haut = "╭─ You " + "─" * max(0, largeur - 7)
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


def demander_texte(invite: str) -> str:
    """Pose une question texte simple (sans cadre ni auto-completion)."""
    if RICH_DISPO:
        return _console.input(f"[bold {ACCENT}]{invite}[/] ").strip()
    return input(f"  {invite} ").strip()


def image_jointe(nom: str) -> None:
    """Confirme visuellement qu'une image a ete jointe au message."""
    if RICH_DISPO:
        _console.print(f"[{ACCENT}]🖼[/]  [{DIM}]image attached: {nom}[/]")
    else:
        print(f"  [image attached: {nom}]")


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
    ("/image", "Image panel: choose the generation model (FLUX / Nano Banana)"),
    ("/add-image", "Pick an image via a file dialog and send it"),
    ("/paste", "Send the image from your clipboard"),
    ("/create-image", "Generate an image from a text description"),
    ("/continue", "Resume an interrupted task / previous session"),
    ("/reset", "Clear the conversation history"),
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


def lire_oui_non(invite: str = "Confirm?") -> str:
    """Lit une reponse de confirmation (retourne la chaine brute, minuscules)."""
    if RICH_DISPO:
        return _console.input(
            f"[bold {ACCENT}]{invite}[/] [{DIM}](y/n)[/] "
        ).strip().lower()
    return input(f"  {invite} (y/n) ").strip().lower()
