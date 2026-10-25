# Pokédex – Flask + PokeAPI

Een eenvoudige website waarmee je Pokémon kunt doorzoeken en alle gegevens
van een Pokémon kunt bekijken. De gegevens komen live uit de
[PokeAPI](https://pokeapi.co/) (v2).

## Functionaliteit

- Zoeken op naam (ook een deel van de naam, bijv. `char`) of nummer (`25`, `#025`)
- Detailpagina: afbeelding, nummer, soort, types, beschrijving, lengte, gewicht,
  basiservaring, vaardigheden (incl. verborgen) en basisstatistieken
- Overzicht van alle Pokémon met paginering (24 per pagina)
- Vorige/volgende Pokémon-knoppen
- Duidelijke meldingen bij ongeldige invoer, onbekende Pokémon (404) of
  als de API niet bereikbaar is (503)

## Installeren en starten

Vereist: Python 3.10 of hoger.

```bash
python -m venv venv
# Windows:  venv\Scripts\activate
# macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
flask --app app run
```

Open daarna <http://127.0.0.1:5000> in de browser.

## Tests uitvoeren

```bash
python -m pytest -v
```

De tests gebruiken opgeslagen (echte) PokeAPI-antwoorden in `tests/fixtures/`,
zodat ze ook zonder internet werken.

## Projectstructuur (MVC)

```
app.py                     Controller: routes, foutpagina's, beveiligingsheaders
config.py                  Instellingen (via omgevingsvariabelen aan te passen)
models/pokemon.py          Model: Pokemon, PokemonSummary, Stat, Ability, PokemonType
services/pokeapi_client.py Service: praat met de PokeAPI, cache, validatie, fouten
templates/                 Views (Jinja2): base, index, search, pokemon, error
static/css/style.css       Opmaak
tests/                     Automatische tests (pytest)
```

## Instellingen

| Variabele          | Standaard                     | Betekenis                        |
|--------------------|-------------------------------|----------------------------------|
| `POKEAPI_BASE_URL` | `https://pokeapi.co/api/v2`   | Adres van de API                 |
| `POKEAPI_TIMEOUT`  | `5`                           | Max. wachttijd in seconden       |
| `CACHE_TTL`        | `86400`                       | Hoe lang antwoorden gecachet worden |
| `SECRET_KEY`       | willekeurig per start         | Sleutel voor meldingen (flash)   |
| `FLASK_DEBUG`      | uit                           | `1` = debugmodus (alleen lokaal) |
