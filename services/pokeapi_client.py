"""Service die alle communicatie met de PokeAPI (https://pokeapi.co) regelt.

Alleen deze klasse praat met de externe API. De rest van de applicatie
gebruikt de methodes van PokeApiClient en krijgt modelobjecten terug.
Daardoor staan foutafhandeling, time-outs en caching op één plek.
"""

from __future__ import annotations

import logging
import re
import time

import requests

from models.pokemon import Pokemon, PokemonSummary

logger = logging.getLogger(__name__)

# Toegestane invoer: kleine letters, cijfers en streepjes (zoals 'mr-mime'),
# maximaal 50 tekens. Alles wat hier niet aan voldoet, wordt nooit naar de
# API gestuurd.
VALID_QUERY = re.compile(r"^[a-z0-9][a-z0-9-]{0,49}$")


class PokeApiError(Exception):
    """Basisklasse voor fouten bij het ophalen van gegevens."""


class PokemonNotFoundError(PokeApiError):
    """De gevraagde Pokémon bestaat niet (HTTP 404 van de API)."""


class PokeApiUnavailableError(PokeApiError):
    """De API is niet bereikbaar, reageert te traag of geeft een serverfout."""


class InvalidQueryError(PokeApiError):
    """De invoer van de gebruiker is geen geldige naam of nummer."""


def normalize_query(raw: str | None) -> str:
    """Maakt gebruikersinvoer schoon en controleert of deze geldig is.

    Voorbeelden: ' Pikachu ' -> 'pikachu', '#025' -> '25', 'Mr Mime' -> 'mr-mime'.
    Gooit InvalidQueryError als de invoer leeg of ongeldig is.
    """
    query = (raw or "").strip().lower().lstrip("#")
    query = re.sub(r"\s+", "-", query)
    if query.isdigit():
        query = str(int(query))  # voorloopnullen weghalen: '025' -> '25'
    if not query or not VALID_QUERY.match(query) or query == "0":
        raise InvalidQueryError(raw)
    return query


class PokeApiClient:
    """Haalt Pokémon-gegevens op bij de PokeAPI, met een eenvoudige cache.

    De PokeAPI vraagt gebruikers om antwoorden lokaal op te slaan, omdat de
    gegevens vrijwel nooit veranderen. Daarom bewaart deze client elk
    antwoord een tijd (standaard 24 uur) in het geheugen.
    """

    def __init__(self, base_url: str, timeout: float = 5.0,
                 cache_ttl: int = 86400, session: requests.Session | None = None):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.cache_ttl = cache_ttl
        self.session = session or requests.Session()
        self._cache: dict[str, tuple[float, dict]] = {}

    # ------------------------------------------------------------------
    # Publieke methodes (worden door de controller gebruikt)
    # ------------------------------------------------------------------

    def get_pokemon(self, query: str) -> Pokemon:
        """Haalt één Pokémon op via naam of nummer, inclusief beschrijving."""
        identifier = normalize_query(query)
        data = self._get_json(f"/pokemon/{identifier}")

        # De beschrijving staat in een apart endpoint. Als dat mislukt,
        # tonen we de Pokémon gewoon zonder beschrijving.
        species = None
        species_name = (data.get("species") or {}).get("name")
        if species_name:
            try:
                species = self._get_json(f"/pokemon-species/{species_name}")
            except PokeApiError:
                logger.warning("Geen species-gegevens voor %s", species_name)

        return Pokemon.from_api(data, species)

    def get_all_summaries(self) -> list[PokemonSummary]:
        """Geeft de lijst van alle Pokémon (naam + nummer) terug.

        Eén verzoek met een hoge limit is efficiënter dan door alle pagina's
        van 20 resultaten te bladeren. De lijst wordt gecachet.
        """
        data = self._get_json("/pokemon?limit=100000&offset=0")
        summaries = (PokemonSummary.from_api(e) for e in data.get("results", []))
        return [s for s in summaries if s is not None]

    def search(self, query: str, max_results: int = 30) -> list[PokemonSummary]:
        """Zoekt Pokémon waarvan de naam de zoekterm bevat.

        Namen die met de zoekterm beginnen komen eerst. Een nummer zoekt
        op het exacte Pokédexnummer.
        """
        term = normalize_query(query)
        all_pokemon = self.get_all_summaries()

        if term.isdigit():
            return [p for p in all_pokemon if p.id == int(term)]

        starts = [p for p in all_pokemon if p.name.startswith(term)]
        contains = [p for p in all_pokemon
                    if term in p.name and not p.name.startswith(term)]
        return (starts + contains)[:max_results]

    # ------------------------------------------------------------------
    # Interne hulpmethodes
    # ------------------------------------------------------------------

    def _get_json(self, path: str) -> dict:
        """Doet een GET-verzoek en geeft de JSON terug (uit cache indien mogelijk).

        Vertaalt technische fouten naar de eigen foutklassen hierboven,
        zodat de controller een duidelijke melding kan tonen.
        """
        cached = self._cache.get(path)
        if cached and time.monotonic() - cached[0] < self.cache_ttl:
            return cached[1]

        url = f"{self.base_url}{path}"
        try:
            response = self.session.get(url, timeout=self.timeout)
        except requests.RequestException as error:
            logger.error("PokeAPI niet bereikbaar: %s", error)
            raise PokeApiUnavailableError(str(error)) from error

        if response.status_code == 404:
            raise PokemonNotFoundError(path)
        if response.status_code != 200:
            logger.error("PokeAPI gaf status %s voor %s", response.status_code, url)
            raise PokeApiUnavailableError(f"HTTP {response.status_code}")

        try:
            data = response.json()
        except ValueError as error:
            raise PokeApiUnavailableError("Ongeldig antwoord van de API") from error

        self._cache[path] = (time.monotonic(), data)
        return data
