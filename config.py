"""Instellingen van de applicatie.

Waarden kunnen via omgevingsvariabelen worden aangepast, zodat er geen
geheimen of omgevingsspecifieke instellingen in de code staan.
"""

import os
import secrets


class Config:
    # Basisadres van de PokeAPI (v2).
    POKEAPI_BASE_URL = os.environ.get("POKEAPI_BASE_URL", "https://pokeapi.co/api/v2")
    # Maximaal aantal seconden wachten op de API.
    POKEAPI_TIMEOUT = float(os.environ.get("POKEAPI_TIMEOUT", "5"))
    # Hoe lang (in seconden) antwoorden in de cache blijven: 24 uur.
    CACHE_TTL = int(os.environ.get("CACHE_TTL", "86400"))
    # Aantal Pokémon per pagina in het overzicht.
    PER_PAGE = 24
    # Nodig voor flash-meldingen. Zonder omgevingsvariabele wordt bij elke
    # start een willekeurige sleutel gemaakt (nooit een vaste sleutel in code).
    SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test"
