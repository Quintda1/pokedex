"""Automatische tests. De nummers (TC-xx) verwijzen naar het testplan in het verslag.

Uitvoeren:  python -m pytest -v
"""

import pytest

from models.pokemon import Pokemon, Stat
from services.pokeapi_client import (
    InvalidQueryError,
    PokeApiUnavailableError,
    PokemonNotFoundError,
    normalize_query,
)
from tests.conftest import load


# ---------------------------------------------------------------------------
# US1 - Zoeken op naam of nummer
# ---------------------------------------------------------------------------

def test_tc01_zoeken_op_exacte_naam_gaat_naar_detailpagina(client):
    response = client.get("/zoeken?q=pikachu")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/pokemon/pikachu")


def test_tc02_zoeken_op_nummer_met_voorloopnullen(client):
    response = client.get("/zoeken?q=%23025")  # '#025'
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/pokemon/pikachu")


def test_tc03_zoeken_met_hoofdletters_en_spaties(client):
    response = client.get("/zoeken?q=%20PiKaChU%20")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/pokemon/pikachu")


def test_tc04_zoeken_op_deel_van_naam_toont_resultatenlijst(client):
    response = client.get("/zoeken?q=char")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    for name in ("Charmander", "Charmeleon", "Charizard"):
        assert name in html


def test_tc05_zoeken_zonder_resultaat_geeft_melding(client):
    response = client.get("/zoeken?q=digimon")
    assert response.status_code == 200
    assert "Geen Pokémon gevonden" in response.get_data(as_text=True)


@pytest.mark.parametrize("invoer", ["", "   ", "<script>", "pika chu!", "a" * 51, "0"])
def test_tc06_ongeldige_invoer_geeft_waarschuwing(client, invoer):
    response = client.get("/zoeken", query_string={"q": invoer}, follow_redirects=True)
    assert response.status_code == 200
    assert "Vul een geldige naam" in response.get_data(as_text=True)


# ---------------------------------------------------------------------------
# US2 - Alle gegevens van een Pokémon bekijken
# ---------------------------------------------------------------------------

def test_tc07_detailpagina_toont_alle_gegevens(client):
    html = client.get("/pokemon/pikachu").get_data(as_text=True)
    assert "Pikachu" in html and "#025" in html
    assert "Elektrisch" in html                      # type
    assert "0.4 m" in html and "6.0 kg" in html      # omgerekende lengte/gewicht
    assert "Static" in html and "Lightning Rod" in html
    assert "verborgen" in html                       # verborgen vaardigheid
    assert "Snelheid" in html and "Totaal" in html   # statistieken
    assert "Mouse Pokémon" in html                   # soort
    assert "official-artwork/25.png" in html         # afbeelding


def test_tc08_onbekende_pokemon_geeft_404(client):
    response = client.get("/pokemon/agumon")
    assert response.status_code == 404
    assert "bestaat niet" in response.get_data(as_text=True)


def test_tc09_ongeldige_url_invoer_geeft_404_zonder_api_aanroep(client, session):
    response = client.get("/pokemon/<b>test</b>")
    assert response.status_code == 404
    assert session.calls == []  # er is niets naar de API gestuurd


def test_tc10_vorige_en_volgende_knoppen(client):
    html = client.get("/pokemon/charizard").get_data(as_text=True)
    assert "/pokemon/charmeleon" in html   # #005
    assert "/pokemon/squirtle" in html     # #007


# ---------------------------------------------------------------------------
# US3 - Overzicht en bladeren
# ---------------------------------------------------------------------------

def test_tc11_overzicht_eerste_pagina(client):
    html = client.get("/").get_data(as_text=True)
    assert "Bulbasaur" in html and "Pagina 1 van 7" in html


def test_tc12_bladeren_en_pagina_buiten_bereik(client):
    assert "Mew" in client.get("/?page=7").get_data(as_text=True)
    assert "Pagina 7 van 7" in client.get("/?page=999").get_data(as_text=True)
    assert "Pagina 1 van 7" in client.get("/?page=-3").get_data(as_text=True)


# ---------------------------------------------------------------------------
# US4 - Duidelijke foutmeldingen
# ---------------------------------------------------------------------------

def test_tc13_api_onbereikbaar_geeft_503_melding(offline_client):
    response = offline_client.get("/pokemon/pikachu")
    assert response.status_code == 503
    assert "niet bereikbaar" in response.get_data(as_text=True)


def test_tc14_api_onbereikbaar_op_startpagina(offline_client):
    assert offline_client.get("/").status_code == 503


# ---------------------------------------------------------------------------
# Unit tests: service, model en beveiliging
# ---------------------------------------------------------------------------

def test_normalize_query():
    assert normalize_query(" Mr Mime ") == "mr-mime"
    assert normalize_query("#001") == "1"
    with pytest.raises(InvalidQueryError):
        normalize_query("drop table;")


def test_cache_voorkomt_dubbele_api_aanroepen(api, session):
    api.get_pokemon("pikachu")
    api.get_pokemon("pikachu")
    assert len(session.calls) == 2  # 1x pokemon + 1x species, daarna uit cache


def test_service_foutklassen(api):
    with pytest.raises(PokemonNotFoundError):
        api.get_pokemon("agumon")
    from tests.conftest import FakeSession
    api.session = FakeSession(mode="error")
    with pytest.raises(PokeApiUnavailableError):
        api.get_pokemon("mew")


def test_model_omrekening_en_beschrijving():
    pokemon = Pokemon.from_api(load("pokemon_charizard"), load("species_charizard"))
    assert pokemon.height_m == 1.7 and pokemon.weight_kg == 90.5
    assert [t.label for t in pokemon.types] == ["Vuur", "Vliegend"]
    assert "\n" not in pokemon.description and "\f" not in pokemon.description
    assert pokemon.total_stats == 534


def test_stat_percentage():
    assert Stat("hp", 255).percentage == 100
    assert Stat("hp", 0).percentage == 0


def test_beveiligingsheaders(client):
    response = client.get("/")
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]
    assert response.headers["X-Frame-Options"] == "DENY"
