"""
Plugin exemple 2 : CALCULATRICE exacte (montre la logique PURE, sans reseau).

Pourquoi ? Les modeles de langage se trompent en arithmetique (verifie en
reel). Cet outil evalue l'expression de facon EXACTE et SANS DANGER :
parsing AST strict, seuls les operateurs mathematiques sont autorises —
aucun eval() sauvage, aucun acces au systeme possible.
"""

import ast
import operator

OUTIL = {
    "name": "calculate",
    "description": (
        "Evaluate a math expression EXACTLY (+ - * / // % ** and "
        "parentheses). Use it for any non-trivial arithmetic instead of "
        "computing in your head."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "Math expression, e.g. '17*23 - 19*21'",
            }
        },
        "required": ["expression"],
    },
}

DANGEREUX = False  # calcul pur : rien a confirmer

_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos,
}


def _evaluer(noeud):
    if isinstance(noeud, ast.Expression):
        return _evaluer(noeud.body)
    if isinstance(noeud, ast.Constant) and isinstance(noeud.value, (int, float)):
        return noeud.value
    if isinstance(noeud, ast.BinOp) and type(noeud.op) in _OPS:
        return _OPS[type(noeud.op)](_evaluer(noeud.left), _evaluer(noeud.right))
    if isinstance(noeud, ast.UnaryOp) and type(noeud.op) in _OPS:
        return _OPS[type(noeud.op)](_evaluer(noeud.operand))
    raise ValueError(f"forbidden element: {type(noeud).__name__}")


def executer(args: dict, config) -> str:
    expression = str(args.get("expression", "")).strip()
    if not expression:
        return "Error: no expression given."
    try:
        resultat = _evaluer(ast.parse(expression, mode="eval"))
    except ZeroDivisionError:
        return "Error: division by zero."
    except Exception as exc:
        return f"Error: invalid expression ({exc})."
    # 14.0 -> 14 pour rester lisible.
    if isinstance(resultat, float) and resultat.is_integer():
        resultat = int(resultat)
    return f"{expression} = {resultat}"
