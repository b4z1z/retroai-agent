"""
api_client.py - Couche transport vers l'API NVIDIA NIM.

Responsabilite UNIQUE : envoyer une requete HTTP a l'endpoint
chat/completions et rendre la reponse. Ce module ne connait RIEN
aux outils ni a la logique de conversation (cela appartient a
agent_loop.py). Il reste "bete" : il envoie ce qu'on lui donne.

Robustesse geree ici :
    - retry avec backoff exponentiel sur HTTP 429 (Rate Limit) : 5s, 10s, 20s
    - timeout reseau (evite de geler le client sur un vieux PC)
    - messages d'erreur clairs pour les autres codes HTTP / JSON invalide
"""

from __future__ import annotations

import time

import requests

from .config import Config


# Delais d'attente (secondes) entre chaque nouvelle tentative apres un 429.
# 3 valeurs => 3 reessais maximum, soit 4 tentatives au total.
BACKOFF_DELAIS = [5, 10, 20]

# Temps max (secondes) accorde a UNE requete HTTP avant de l'abandonner.
TIMEOUT_REQUETE = 120


class ApiError(Exception):
    """Erreur levee quand l'appel API echoue de maniere non recuperable."""


class ApiClient:
    """Client minimaliste pour l'endpoint chat/completions de NVIDIA NIM."""

    def __init__(self, config: Config) -> None:
        self.config = config
        # Une session requests reutilise la connexion TCP entre les appels
        # (plus rapide, surtout sur une machine modeste).
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    # ------------------------------------------------------------------ #
    #  Construction du payload                                            #
    # ------------------------------------------------------------------ #
    def _construire_payload(self, messages: list, tools: list | None) -> dict:
        """
        Assemble le corps JSON envoye a l'API a partir de la config et
        des messages/outils fournis par l'appelant.
        """
        payload: dict = {
            "model": self.config.model,
            "messages": messages,
            "temperature": 0.6,
            "max_tokens": 4096,
        }

        # Le mode "thinking" (raisonnement) est pilote par la config.
        if self.config.enable_thinking:
            payload["chat_template_kwargs"] = {"thinking": True}

        # On n'ajoute la cle "tools" que si des outils sont fournis :
        # envoyer "tools": null ou [] peut faire echouer certains endpoints.
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        return payload

    # ------------------------------------------------------------------ #
    #  Appel principal                                                   #
    # ------------------------------------------------------------------ #
    def chat(self, messages: list, tools: list | None = None) -> dict:
        """
        Envoie la conversation a l'API et retourne la reponse JSON brute.

        Gere automatiquement le retry/backoff sur les 429. Leve ApiError
        en cas d'echec definitif (mauvaise cle, serveur HS, JSON invalide...).
        """
        payload = self._construire_payload(messages, tools)
        url = self.config.base_url

        # On tente 1 fois + autant de reessais que de delais de backoff.
        for tentative in range(len(BACKOFF_DELAIS) + 1):
            try:
                reponse = self.session.post(
                    url, json=payload, timeout=TIMEOUT_REQUETE
                )
            except requests.exceptions.Timeout as exc:
                raise ApiError(
                    f"Request timed out ({TIMEOUT_REQUETE}s). "
                    "The NVIDIA server is taking too long to respond."
                ) from exc
            except requests.exceptions.RequestException as exc:
                raise ApiError(f"Network error: {exc}") from exc

            # --- Cas 429 : Rate Limit -> on attend puis on reessaie ------
            if reponse.status_code == 429:
                if tentative < len(BACKOFF_DELAIS):
                    delai = BACKOFF_DELAIS[tentative]
                    print(
                        f"  [API] Rate limit reached (429). "
                        f"Retrying in {delai}s..."
                    )
                    time.sleep(delai)
                    continue  # on retente la boucle
                raise ApiError(
                    "Rate limit (429) still active after "
                    f"{len(BACKOFF_DELAIS)} retries. Giving up."
                )

            # --- Autres erreurs HTTP : pas recuperables ------------------
            if reponse.status_code != 200:
                extrait = reponse.text[:500]
                raise ApiError(
                    f"HTTP error {reponse.status_code} from the NVIDIA API:\n"
                    f"{extrait}"
                )

            # --- Succes : on parse le JSON ------------------------------
            try:
                return reponse.json()
            except ValueError as exc:
                raise ApiError(
                    "Unreadable API response (invalid JSON)."
                ) from exc

        # Ne devrait jamais arriver, mais par securite :
        raise ApiError("Unexpected API call failure.")
