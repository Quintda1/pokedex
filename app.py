"""Controller (de 'C' in MVC) van de Pokédex-website.

Hier staan alle routes. Een route haalt gegevens op via de PokeApiClient
(service + modellen) en geeft die door aan een Jinja-template (view).

Starten:  flask --app app run   (of: python app.py)
"""

from __future__ import annotations

import logging
import os

from flask import Flask, abort, flash, redirect, render_template, request, url_for

from config import Config
from services.pokeapi_client import (
    InvalidQueryError,
    PokeApiClient,
    PokeApiUnavailableError,
    PokemonNotFoundError,
)


def create_app(config_class: type[Config] = Config,
               client: PokeApiClient | None = None) -> Flask:
    """Maakt de Flask-applicatie aan (application factory).

    In de tests geven we een nep-client mee, zodat de tests niet van
    internet afhankelijk zijn.
    """
    app = Flask(__name__)
    app.config.from_object(config_class)
    logging.basicConfig(level=logging.INFO)

    api = client or PokeApiClient(
        base_url=app.config["POKEAPI_BASE_URL"],
        timeout=app.config["POKEAPI_TIMEOUT"],
        cache_ttl=app.config["CACHE_TTL"],
    )

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------

    @app.route("/")
    def index():
        """Startpagina: zoekbalk en een overzicht van alle Pokémon per pagina."""
        page = request.args.get("page", 1, type=int)
        per_page = app.config["PER_PAGE"]

        try:
            all_pokemon = api.get_all_summaries()
        except PokeApiUnavailableError:
            return render_template("error.html", code=503,
                                   message="De PokeAPI is op dit moment niet bereikbaar. "
                                           "Probeer het later opnieuw."), 503

        total_pages = max(1, -(-len(all_pokemon) // per_page))  # naar boven afronden
        page = min(max(page, 1), total_pages)                    # pagina binnen bereik houden
        start = (page - 1) * per_page

        return render_template(
            "index.html",
            pokemon_list=all_pokemon[start:start + per_page],
            page=page,
            total_pages=total_pages,
            total=len(all_pokemon),
        )

    @app.route("/zoeken")
    def search():
        """Verwerkt de zoekbalk.

        - Exacte naam of nummer  -> direct naar de detailpagina.
        - Deel van een naam       -> lijst met resultaten.
        - Ongeldige/lege invoer   -> terug naar start met een melding.
        """
        query = request.args.get("q", "")

        try:
            results = api.search(query)
        except InvalidQueryError:
            flash("Vul een geldige naam of een nummer in "
                  "(alleen letters, cijfers en streepjes).", "warning")
            return redirect(url_for("index"))
        except PokeApiUnavailableError:
            return render_template("error.html", code=503,
                                   message="De PokeAPI is op dit moment niet bereikbaar. "
                                           "Probeer het later opnieuw."), 503

        # Precies één treffer, of een exacte naam: meteen naar de details.
        exact = [p for p in results if p.name == query.strip().lower()]
        if len(results) == 1 or exact:
            target = exact[0] if exact else results[0]
            return redirect(url_for("pokemon_detail", identifier=target.name))

        return render_template("search.html", query=query, results=results)

    @app.route("/pokemon/<identifier>")
    def pokemon_detail(identifier: str):
        """Detailpagina met alle gegevens van één Pokémon."""
        try:
            pokemon = api.get_pokemon(identifier)
        except (InvalidQueryError, PokemonNotFoundError):
            abort(404)
        except PokeApiUnavailableError:
            return render_template("error.html", code=503,
                                   message="De gegevens konden niet worden opgehaald, "
                                           "omdat de PokeAPI niet bereikbaar is."), 503

        previous_pokemon, next_pokemon = _neighbours(pokemon.id)
        return render_template("pokemon.html", pokemon=pokemon,
                               previous_pokemon=previous_pokemon,
                               next_pokemon=next_pokemon)

    def _neighbours(pokemon_id: int):
        """Zoekt de vorige en volgende Pokémon voor de navigatieknoppen."""
        try:
            by_id = {p.id: p for p in api.get_all_summaries()}
        except PokeApiUnavailableError:
            return None, None
        return by_id.get(pokemon_id - 1), by_id.get(pokemon_id + 1)

    # ------------------------------------------------------------------
    # Foutpagina's en beveiligingsheaders
    # ------------------------------------------------------------------

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("error.html", code=404,
                               message="Deze Pokémon of pagina bestaat niet. "
                                       "Controleer de spelling of zoek opnieuw."), 404

    @app.errorhandler(500)
    def server_error(_error):
        return render_template("error.html", code=500,
                               message="Er ging iets mis aan onze kant."), 500

    @app.after_request
    def security_headers(response):
        """Extra beveiliging: alleen eigen scripts/stijlen en afbeeldingen van
        GitHub (waar de PokeAPI zijn plaatjes host) mogen worden geladen."""
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' https://raw.githubusercontent.com; "
            "style-src 'self'; script-src 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        return response

    return app


app = create_app()

if __name__ == "__main__":
    # Debugmodus alleen aan als FLASK_DEBUG=1 is gezet, nooit standaard.
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
