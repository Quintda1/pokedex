"""Gedeelde test-opzet.

In plaats van echt met internet te praten, krijgt de PokeApiClient een
'FakeSession'. Die geeft echte (ingekorte) PokeAPI-antwoorden terug uit de
map fixtures/. Zo zijn de tests snel en altijd herhaalbaar.
"""

import json
from pathlib import Path

import pytest
import requests

from app import create_app
from config import TestConfig
from services.pokeapi_client import PokeApiClient

FIXTURES = Path(__file__).parent / "fixtures"
BASE_URL = "https://pokeapi.co/api/v2"


def load(name):
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


class FakeResponse:
    def __init__(self, status_code, data=None):
        self.status_code = status_code
        self._data = data

    def json(self):
        if self._data is None:
            raise ValueError("geen JSON")
        return self._data


class FakeSession:
    """Doet alsof het requests.Session is. mode: 'ok', 'down' of 'error'."""

    def __init__(self, mode="ok"):
        self.mode = mode
        self.calls = []  # houdt bij welke URL's zijn opgevraagd (voor de cache-test)
        self.pokemon = {"pikachu": load("pokemon_pikachu"), "charizard": load("pokemon_charizard")}
        self.species = {"pikachu": load("species_pikachu"), "charizard": load("species_charizard")}
        self.ids = {"25": "pikachu", "6": "charizard"}

    def get(self, url, timeout=None):
        self.calls.append(url)
        if self.mode == "down":
            raise requests.ConnectionError("netwerk onbereikbaar")
        if self.mode == "error":
            return FakeResponse(500)

        path = url.replace(BASE_URL, "")
        if path.startswith("/pokemon?"):
            return FakeResponse(200, load("pokemon_list"))
        if path.startswith("/pokemon-species/"):
            name = path.split("/")[2]
            return FakeResponse(200, self.species[name]) if name in self.species else FakeResponse(404)
        if path.startswith("/pokemon/"):
            key = path.split("/")[2]
            name = self.ids.get(key, key)
            return FakeResponse(200, self.pokemon[name]) if name in self.pokemon else FakeResponse(404)
        return FakeResponse(404)


@pytest.fixture
def session():
    return FakeSession()


@pytest.fixture
def api(session):
    return PokeApiClient(BASE_URL, session=session)


@pytest.fixture
def client(api):
    app = create_app(TestConfig, client=api)
    return app.test_client()


@pytest.fixture
def offline_client():
    api = PokeApiClient(BASE_URL, session=FakeSession(mode="down"))
    return create_app(TestConfig, client=api).test_client()
