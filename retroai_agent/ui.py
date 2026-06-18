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
#  Banniere et accueil                                                        #
# --------------------------------------------------------------------------- #
def banniere(modele: str) -> None:
    """Affiche le grand panneau d'accueil de l'application (pleine largeur)."""
    if RICH_DISPO:
        contenu = Text(justify="center")
        contenu.append(LOGO + "\n\n", style=f"bold {ACCENT}")
        contenu.append("Agent autonome CLI  ·  NVIDIA NIM\n", style="default")
        contenu.append(f"Modele : {modele}\n\n", style=DIM)
        contenu.append("/help", style=f"bold {ACCENT}")
        contenu.append(" aide       ", style=DIM)
        contenu.append("/reset", style=f"bold {ACCENT}")
        contenu.append(" effacer       ", style=DIM)
        contenu.append("/exit", style=f"bold {ACCENT}")
        contenu.append(" quitter", style=DIM)
        _console.print()
        _console.print(
            Panel(contenu, border_style=ACCENT, padding=(2, 4), expand=True)
        )
        _console.print()
    else:
        print("=" * 70)
        print("   BAZIZ.IA  -  client CLI pour agent autonome (NIM)")
        print(f"   Modele : {modele}")
        print("   /help aide  ·  /reset effacer  ·  /exit quitter")
        print("=" * 70)


# Police pixel maison pour le message d'adieu (meme esprit que LOGO).
# Chaque glyphe = 5 lignes de 5 colonnes, pour un rendu "gros caracteres".
_FONT_ADIEU = {
    "A": [" ███ ", "█   █", "█████", "█   █", "█   █"],
    "U": ["█   █", "█   █", "█   █", "█   █", " ███ "],
    "R": ["████ ", "█   █", "████ ", "█  █ ", "█   █"],
    "E": ["█████", "█    ", "████ ", "█    ", "█████"],
    "V": ["█   █", "█   █", "█   █", " █ █ ", "  █  "],
    "O": [" ███ ", "█   █", "█   █", "█   █", " ███ "],
    "I": ["█████", "  █  ", "  █  ", "  █  ", "█████"],
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
    """Affiche un grand 'AU REVOIR' facon logo, centre, pour dire au revoir."""
    art = _texte_pixel("AU REVOIR")
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
        _console.print(f"[{DIM}]Ravi de te retrouver,[/] [bold {ACCENT}]{pseudo}[/] !")
    else:
        print(f"  Ravi de te retrouver, {pseudo} !")


# --------------------------------------------------------------------------- #
#  Entrees / sorties de conversation                                          #
# --------------------------------------------------------------------------- #
def lire_saisie() -> str:
    """
    Affiche une zone de saisie encadree (facon Claude Code) et lit la
    reponse de l'utilisateur. Peut lever EOFError / KeyboardInterrupt.
    """
    if RICH_DISPO:
        largeur = max(20, _console.size.width)
        haut = "╭─ Vous " + "─" * max(0, largeur - 8)
        _console.print()
        _console.print(haut, style=ACCENT)
        # Le coin bas-gauche "╰─›" sert d'invite de saisie : le cadre parait
        # ferme et soigne SANS devoir dessiner une ligne sous le curseur, ce
        # qui est impossible avec input() (on ne peut rien afficher en dessous
        # tant que l'utilisateur tape). Evite l'aspect "boite ouverte".
        return _console.input(f"[{ACCENT}]╰─›[/] ").strip()
    return input("\n› ").strip()


def reponse_agent(texte: str) -> None:
    """Affiche la reponse de l'agent (rendue en Markdown si rich dispo)."""
    if not texte:
        texte = "_(reponse vide)_"
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
        print(f"\n  [OUTIL] {nom}{suffixe}")


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
            _console.print(Text(f"    … (+{reste} lignes)", style=DIM))
    else:
        for i, ligne in enumerate(apercu):
            prefixe = "  |_ " if i == 0 else "     "
            print(f"{prefixe}{ligne}")
        if reste > 0:
            print(f"     ... (+{reste} lignes)")


@contextlib.contextmanager
def reflexion(message: str = "Reflexion en cours…"):
    """
    Indicateur d'attente pendant un appel API. Spinner anime si rich dispo,
    sinon simple ligne de texte. A utiliser autour de l'appel reseau SEUL
    (jamais autour d'une saisie input()).
    """
    if RICH_DISPO:
        with _console.status(f"[{ACCENT}]{message}[/]", spinner="dots"):
            yield
    else:
        print("  L'agent reflechit...", flush=True)
        yield


# --------------------------------------------------------------------------- #
#  Aide                                                                       #
# --------------------------------------------------------------------------- #
def aide() -> None:
    """Affiche l'aide des commandes."""
    lignes = [
        ("/help", "Affiche cette aide"),
        ("/reset", "Vide l'historique de la conversation"),
        ("/exit, /quit", "Quitte le programme"),
    ]
    if RICH_DISPO:
        contenu = Text()
        contenu.append("Commandes disponibles\n\n", style=f"bold {ACCENT}")
        for cmd, desc in lignes:
            contenu.append(f"  {cmd:14}", style=f"bold {ACCENT}")
            contenu.append(f"{desc}\n", style=DIM)
        contenu.append(
            "\nSinon, tapez votre demande et appuyez sur Entree.", style=DIM
        )
        _console.print(Panel(contenu, border_style=DIM, padding=(1, 4), expand=True))
    else:
        print("\nCommandes disponibles :")
        for cmd, desc in lignes:
            print(f"  {cmd:14} {desc}")
        print("Sinon, tapez votre demande et appuyez sur Entree.")


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
        titre_panneau = "⚠  ACTION DANGEREUSE" if dangereux else "Confirmation requise"
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
        marque = "ACTION DANGEREUSE" if dangereux else "CONFIRMATION REQUISE"
        print(f"  |  {marque}")
        print("  +-----------------------------------------------------------+")
        print(f"  Action : {titre}")
        for ligne in details.splitlines():
            print(f"    {ligne}")
        print()


def lire_oui_non(invite: str = "Confirmer ?") -> str:
    """Lit une reponse y/n (retourne la chaine brute, en minuscules)."""
    if RICH_DISPO:
        return _console.input(f"[bold]{invite}[/] [{DIM}][y/N][/] ").strip().lower()
    return input(f"  {invite} [y/N] ").strip().lower()
