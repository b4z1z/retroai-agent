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

from .api_client import ApiClient, ApiError
from .config import Config
from . import tools
from . import ui


# Message systeme : definit le role et le comportement de l'agent.
SYSTEME = (
    "Tu es BAZIZ.IA, un agent autonome qui aide l'utilisateur depuis un "
    "terminal Linux. Tu disposes d'outils pour lire/ecrire des fichiers, "
    "lister des repertoires et executer des commandes shell. Utilise-les "
    "quand c'est utile. Reponds de maniere concise et en francais."
)

# Garde-fou anti-boucle infinie : nombre max d'aller-retours outils par tour.
MAX_ITERATIONS = 10


class AgentLoop:
    """Gere l'historique et le cycle complet d'un echange avec l'agent."""

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
        self.reset()

    def reset(self) -> None:
        """Vide l'historique et reinjecte le message systeme (commande /reset)."""
        contenu = SYSTEME
        if self.infos_utilisateur:
            contenu = SYSTEME + "\n\n" + self.infos_utilisateur
        self.historique = [{"role": "system", "content": contenu}]

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
    #  Traitement d'un tour de parole utilisateur                        #
    # ------------------------------------------------------------------ #
    def envoyer(self, message_utilisateur: str) -> str:
        """
        Ajoute le message de l'utilisateur, dialogue avec l'API en boucle
        tant que le modele demande des outils, et retourne la reponse
        textuelle finale de l'agent.
        """
        self.historique.append({"role": "user", "content": message_utilisateur})

        for _ in range(MAX_ITERATIONS):
            with ui.reflexion():
                reponse = self.client.chat(self.historique, tools=tools.TOOLS_SCHEMA)

            try:
                message = reponse["choices"][0]["message"]
            except (KeyError, IndexError) as exc:
                raise ApiError(f"Reponse API inattendue : {exc}") from exc

            tool_calls = message.get("tool_calls")

            # --- Cas 1 : pas d'outil demande -> reponse finale -----------
            if not tool_calls:
                contenu = message.get("content") or ""
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
                        f"Erreur : arguments JSON invalides pour '{nom}' "
                        f"({exc}). Arguments recus : {brut}"
                    )
                else:
                    resultat = tools.executer_outil(nom, args, self.config)

                # Apercu du resultat sous la ligne d'action (style Claude Code).
                ui.resultat_outil(resultat)

                # *** LE PIEGE NVIDIA NIM ***
                # On NE renvoie PAS role "tool". On reinjecte en role "user".
                self.historique.append(
                    {
                        "role": "user",
                        "content": f"[Resultat de l'outil {nom}]\n{resultat}",
                    }
                )
            # On reboucle : le modele voit les resultats et continue.

        # Securite : trop d'iterations d'affilee.
        message_limite = (
            "[Limite atteinte : l'agent a utilise trop d'outils d'affilee "
            "sans repondre. Reformulez votre demande.]"
        )
        self.historique.append({"role": "assistant", "content": message_limite})
        return message_limite
