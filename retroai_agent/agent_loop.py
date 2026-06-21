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
import os

from .api_client import ApiClient, ApiError
from .config import Config
from . import tools
from . import ui
from . import images


# Fichier local de sauvegarde de la conversation (pour /continue).
CHEMIN_SESSION = "session_history.json"


# Message systeme : definit le role et le comportement de l'agent.
SYSTEME = (
    "You are BAZIZ.IA, an autonomous agent that helps the user from a "
    "Linux terminal. You have tools to read/write files, list directories "
    "and run shell commands. Use them when useful. Reply concisely, in the "
    "same language as the user. If the user references an image file, that "
    "image is ALREADY attached to the message: look at it directly, do not "
    "try to open or inspect it with shell tools."
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
        # Vrai si le dernier tour a ete interrompu (echec API) et reste a
        # reprendre. Permet a /continue de relancer la ou ca s'est arrete.
        self.tour_incomplet = False
        self.reset()

    def reset(self) -> None:
        """Vide l'historique et reinjecte le message systeme (commande /reset)."""
        contenu = SYSTEME + "\n\n" + A_PROPOS
        if self.infos_utilisateur:
            contenu = contenu + "\n\n" + self.infos_utilisateur
        self.historique = [{"role": "system", "content": contenu}]
        self.tour_incomplet = False

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
    #  Persistance de la conversation (commande /continue)               #
    # ------------------------------------------------------------------ #
    def sauver_session(self, chemin: str = CHEMIN_SESSION) -> None:
        """Enregistre l'historique sur disque (echec silencieux si impossible).

        Les images base64 sont allegees avant ecriture pour ne pas gonfler
        session_history.json (voir images.alleger_pour_disque).
        """
        try:
            with open(chemin, "w", encoding="utf-8") as f:
                json.dump(
                    images.alleger_pour_disque(self.historique),
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except OSError:
            pass

    def charger_session(self, chemin: str = CHEMIN_SESSION) -> bool:
        """
        Recharge un historique sauvegarde. Retourne True si une session
        valide a ete restauree, False sinon.
        """
        if not os.path.exists(chemin):
            return False
        try:
            with open(chemin, "r", encoding="utf-8") as f:
                donnees = json.load(f)
        except (OSError, ValueError):
            return False
        if isinstance(donnees, list) and donnees:
            self.historique = donnees
            return True
        return False

    # ------------------------------------------------------------------ #
    #  Appel API avec un reessai automatique (timeout / erreur reseau)   #
    # ------------------------------------------------------------------ #
    def _appel_api(self) -> dict:
        """
        Appelle l'API en reessayant UNE fois en cas d'ApiError (timeout,
        coupure reseau...). Si le 2e essai echoue aussi, l'ApiError remonte.
        """
        derniere_erreur: ApiError | None = None
        for tentative in range(2):  # 1 essai + 1 reessai
            try:
                with ui.reflexion():
                    return self.client.chat(
                        self.historique, tools=tools.TOOLS_SCHEMA
                    )
            except ApiError as exc:
                derniere_erreur = exc
                if tentative == 0:
                    ui.info("Failure/timeout — retrying automatically…")
        # Les deux tentatives ont echoue.
        raise derniere_erreur  # type: ignore[misc]

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
        try:
            reponse_finale = self._dialoguer()
        except (ApiError, KeyboardInterrupt):
            # Echec API OU stop utilisateur (Ctrl+C) : on marque le tour
            # comme incomplet et on PRESERVE tout (resultats d'outils, etapes).
            # -> /continue pourra reprendre la ou ca s'est arrete.
            self.tour_incomplet = True
            self.sauver_session()
            raise

        # Succes : tour termine, on sauvegarde l'etat complet.
        self.tour_incomplet = False
        self.sauver_session()
        return reponse_finale

    def _dialoguer(self) -> str:
        """Boucle de dialogue : appels API + execution d'outils."""
        for _ in range(MAX_ITERATIONS):
            reponse = self._appel_api()

            try:
                message = reponse["choices"][0]["message"]
            except (KeyError, IndexError) as exc:
                raise ApiError(f"Unexpected API response: {exc}") from exc

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
                        f"Error: invalid JSON arguments for '{nom}' "
                        f"({exc}). Received arguments: {brut}"
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
                        "content": f"[Tool result: {nom}]\n{resultat}",
                    }
                )
            # On reboucle : le modele voit les resultats et continue.

        # Securite : trop d'iterations d'affilee.
        message_limite = (
            "[Limit reached: the agent used too many tools in a row without "
            "answering. Please rephrase your request.]"
        )
        self.historique.append({"role": "assistant", "content": message_limite})
        return message_limite
