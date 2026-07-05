"""
thinking.py - Niveaux d'effort de reflexion (raisonnement).

Le modele kimi via NIM n'expose qu'un raisonnement ON/OFF
(chat_template_kwargs thinking). Pour offrir des NIVEAUX plus fins, on combine :
  - thinking ON/OFF,
  - une consigne ajoutee au message demandant plus ou moins d'effort.

Niveaux, du plus rapide au plus pousse : low, medium, high, highx, ultra.
Reglable via la commande /think ou la variable d'env THINKING_LEVEL.
"""

from __future__ import annotations


NIVEAUX = ["low", "medium", "high", "highx", "ultra"]
DEFAUT = "medium"

# Descriptions courtes (affichees dans le selecteur /think a fleches).
DESCRIPTIONS = {
    "low": "fast, direct, minimal reasoning",
    "medium": "balanced (default)",
    "high": "thinks step by step",
    "highx": "very thorough (edge cases)",
    "ultra": "exhaustive - best for code",
}

# niveau -> (raisonnement actif ?, consigne ajoutee au message utilisateur)
_TABLE = {
    "low": (False, "Answer directly and concisely; keep reasoning minimal."),
    "medium": (True, ""),
    "high": (True, "Think step by step and carefully before you answer."),
    "highx": (
        True,
        "Think very thoroughly: weigh edge cases and alternatives, and "
        "double-check your reasoning before answering.",
    ),
    "ultra": (
        True,
        "Reason exhaustively and rigorously, and optimize for CODE QUALITY. "
        "When writing code: produce a COMPLETE, correct, runnable solution with "
        "no placeholders, stubs, or TODOs; handle edge cases and errors; follow "
        "the language's idioms and best practices; mentally compile/trace the "
        "code and fix any issue before answering; keep it efficient and "
        "readable. Explore alternative approaches, verify each step, and "
        "double-check the final answer before responding.",
    ),
}


def normaliser(niveau: str) -> str:
    """Ramene a un niveau connu (DEFAUT si inconnu)."""
    n = (niveau or "").strip().lower()
    return n if n in _TABLE else DEFAUT


def est_actif(niveau: str) -> bool:
    """Le raisonnement (thinking) doit-il etre active pour ce niveau ?"""
    return _TABLE[normaliser(niveau)][0]


def consigne(niveau: str) -> str:
    """Consigne a injecter dans le message pour ce niveau (peut etre vide)."""
    return _TABLE[normaliser(niveau)][1]
