"""Tests du client API : parsing du flux SSE (streaming) et helpers."""

import pytest

from retroai_agent.api_client import (
    ApiClient,
    ApiError,
    _est_saturation,
    _extraire_image_base64,
)


class _FluxFactice:
    """Simule une reponse requests en mode stream (iter_lines)."""

    status_code = 200

    def __init__(self, lignes):
        self._lignes = lignes

    def iter_lines(self, decode_unicode=True):
        yield from self._lignes


def test_lire_flux_texte_raisonnement_et_outils():
    lignes = [
        # raisonnement (thinking) streame
        'data: {"choices":[{"delta":{"reasoning_content":"je "}}]}',
        'data: {"choices":[{"delta":{"reasoning_content":"reflechis"}}]}',
        # reponse en 2 fragments
        'data: {"choices":[{"delta":{"content":"Bon"}}]}',
        'data: {"choices":[{"delta":{"content":"jour"},"finish_reason":null}]}',
        "",  # ligne vide (separateur SSE) -> ignoree
        "event: ping",  # ligne non-data non-JSON -> ignoree
        # tool_call fragmente sur 2 lignes
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"a",'
        '"function":{"name":"read_file","arguments":"{\\"pa"}}]}}]}',
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,'
        '"function":{"arguments":"th\\":\\"x\\"}"}}]},"finish_reason":"tool_calls"}]}',
        "data: [DONE]",
        'data: {"choices":[{"delta":{"content":"APRES-DONE"}}]}',  # jamais lu
    ]
    recu = []
    res = ApiClient._lire_flux(
        _FluxFactice(lignes), lambda frag, pense=False: recu.append((frag, pense))
    )
    message = res["choices"][0]["message"]

    # Le contenu ne contient QUE la reponse (pas le raisonnement).
    assert message["content"] == "Bonjour"
    # Le raisonnement a bien ete streame avec le drapeau True.
    assert ("je ", True) in recu and ("reflechis", True) in recu
    assert ("Bon", False) in recu
    # tool_calls reconstruit depuis les fragments.
    (outil,) = message["tool_calls"]
    assert outil["function"]["name"] == "read_file"
    assert outil["function"]["arguments"] == '{"path":"x"}'
    assert res["choices"][0]["finish_reason"] == "tool_calls"
    # [DONE] stoppe la lecture.
    assert "APRES-DONE" not in message["content"]


def test_lire_flux_sans_callback():
    lignes = ['data: {"choices":[{"delta":{"content":"ok"}}]}', "data: [DONE]"]
    res = ApiClient._lire_flux(_FluxFactice(lignes), None)
    assert res["choices"][0]["message"]["content"] == "ok"


def test_est_saturation():
    vrai = (
        '{"message":"ResourceExhausted: Worker local total request limit '
        'reached (33/32)","type":"internal_server_error","code":500}'
    )
    assert _est_saturation(vrai)
    assert not _est_saturation('{"message":"internal error"}')
    assert not _est_saturation("")


def test_extraire_image_base64_formats():
    assert _extraire_image_base64({"artifacts": [{"base64": "AAA"}]}) == "AAA"
    assert _extraire_image_base64({"data": [{"b64_json": "BBB"}]}) == "BBB"
    assert _extraire_image_base64({"image": "CCC"}) == "CCC"
    with pytest.raises(ApiError):
        _extraire_image_base64({"foo": 1})
