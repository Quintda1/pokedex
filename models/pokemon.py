"""Modellen (de 'M' in MVC) voor de Pokédex-applicatie.

De PokeAPI geeft grote JSON-objecten terug met veel meer gegevens dan de
website nodig heeft. Deze modellen zetten die ruwe JSON om naar kleine,
overzichtelijke Python-objecten. Zo hoeven de templates (views) niets te
weten over de structuur van de API.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Basis-URL van de officiële afbeeldingen. Deze staan op GitHub en zijn op
# Pokédexnummer te vinden, zodat we voor het overzicht niet elke Pokémon
# apart hoeven op te vragen.
ARTWORK_URL = (
    "https://raw.githubusercontent.com/PokeAPI/sprites/master/"
    "sprites/pokemon/other/official-artwork/{id}.png"
)

# Hoogste mogelijke waarde van een basisstatistiek; gebruikt om de balkjes
# op de detailpagina naar een percentage om te rekenen.
MAX_BASE_STAT = 255

# Nederlandse namen voor de statistieken uit de API.
STAT_LABELS = {
    "hp": "HP",
    "attack": "Aanval",
    "defense": "Verdediging",
    "special-attack": "Sp. aanval",
    "special-defense": "Sp. verdediging",
    "speed": "Snelheid",
}

# Nederlandse namen voor de Pokémon-types.
TYPE_LABELS = {
    "normal": "Normaal", "fire": "Vuur", "water": "Water", "grass": "Gras",
    "electric": "Elektrisch", "ice": "IJs", "fighting": "Vecht",
    "poison": "Gif", "ground": "Grond", "flying": "Vliegend",
    "psychic": "Psychisch", "bug": "Insect", "rock": "Steen",
    "ghost": "Geest", "dragon": "Draak", "dark": "Duister",
    "steel": "Staal", "fairy": "Fee",
}


def format_name(api_name: str) -> str:
    """Maakt van een API-naam ('mr-mime') een leesbare naam ('Mr Mime')."""
    return " ".join(part.capitalize() for part in api_name.split("-"))


def id_from_url(url: str) -> int | None:
    """Haalt het nummer uit een API-URL zoals '.../pokemon/25/'."""
    last_part = url.rstrip("/").rsplit("/", 1)[-1]
    return int(last_part) if last_part.isdigit() else None


@dataclass(frozen=True)
class PokemonType:
    """Eén type van een Pokémon, bijvoorbeeld 'electric' (Elektrisch)."""

    name: str

    @property
    def label(self) -> str:
        return TYPE_LABELS.get(self.name, format_name(self.name))


@dataclass(frozen=True)
class Ability:
    """Een vaardigheid. 'hidden' geeft aan of het een verborgen vaardigheid is."""

    name: str
    hidden: bool = False

    @property
    def label(self) -> str:
        return format_name(self.name)


@dataclass(frozen=True)
class Stat:
    """Eén basisstatistiek, zoals HP of Snelheid."""

    name: str
    value: int

    @property
    def label(self) -> str:
        return STAT_LABELS.get(self.name, format_name(self.name))

    @property
    def percentage(self) -> int:
        """Waarde als percentage van het maximum, voor het balkje (0-100)."""
        return min(100, round(self.value / MAX_BASE_STAT * 100))


@dataclass(frozen=True)
class PokemonSummary:
    """Korte versie van een Pokémon, gebruikt in het overzicht en bij zoeken."""

    id: int
    name: str

    @property
    def display_name(self) -> str:
        return format_name(self.name)

    @property
    def image_url(self) -> str:
        return ARTWORK_URL.format(id=self.id)

    @classmethod
    def from_api(cls, entry: dict) -> PokemonSummary | None:
        """Maakt een samenvatting van één regel uit de lijst-endpoint.

        Geeft None terug als het nummer niet uit de URL te halen is.
        """
        pokemon_id = id_from_url(entry.get("url", ""))
        if pokemon_id is None or not entry.get("name"):
            return None
        return cls(id=pokemon_id, name=entry["name"])


@dataclass
class Pokemon:
    """Alle gegevens van één Pokémon die op de detailpagina getoond worden."""

    id: int
    name: str
    height_m: float
    weight_kg: float
    base_experience: int | None
    image_url: str | None
    types: list[PokemonType] = field(default_factory=list)
    abilities: list[Ability] = field(default_factory=list)
    stats: list[Stat] = field(default_factory=list)
    genus: str | None = None
    description: str | None = None

    @property
    def display_name(self) -> str:
        return format_name(self.name)

    @property
    def number(self) -> str:
        """Pokédexnummer met voorloopnullen, bijv. '#025'."""
        return f"#{self.id:03d}"

    @property
    def total_stats(self) -> int:
        return sum(stat.value for stat in self.stats)

    @classmethod
    def from_api(cls, data: dict, species: dict | None = None) -> Pokemon:
        """Zet het antwoord van /pokemon/{naam} (en optioneel
        /pokemon-species/{naam}) om naar een Pokemon-object.

        De API geeft lengte in decimeters en gewicht in hectogrammen;
        hier rekenen we dat om naar meters en kilogrammen.
        """
        sprites = data.get("sprites") or {}
        artwork = (sprites.get("other") or {}).get("official-artwork") or {}
        image_url = artwork.get("front_default") or sprites.get("front_default")

        # Types worden in de juiste volgorde (slot 1, slot 2) gezet.
        types = [
            PokemonType(entry["type"]["name"])
            for entry in sorted(data.get("types", []), key=lambda t: t["slot"])
        ]
        abilities = [
            Ability(entry["ability"]["name"], entry.get("is_hidden", False))
            for entry in data.get("abilities", [])
        ]
        stats = [
            Stat(entry["stat"]["name"], entry["base_stat"])
            for entry in data.get("stats", [])
        ]

        genus, description = cls._parse_species(species) if species else (None, None)

        return cls(
            id=data["id"],
            name=data["name"],
            height_m=data.get("height", 0) / 10,
            weight_kg=data.get("weight", 0) / 10,
            base_experience=data.get("base_experience"),
            image_url=image_url,
            types=types,
            abilities=abilities,
            stats=stats,
            genus=genus,
            description=description,
        )

    @staticmethod
    def _parse_species(species: dict) -> tuple[str | None, str | None]:
        """Haalt de soortnaam ('Mouse Pokémon') en een beschrijving uit de
        species-gegevens. Nederlands heeft voorrang; de PokeAPI heeft
        meestal alleen Engelse teksten, dus Engels is de terugvaloptie."""

        def pick(entries: list[dict], key: str) -> str | None:
            for language in ("nl", "en"):
                for entry in entries:
                    if entry.get("language", {}).get("name") == language:
                        return entry.get(key)
            return None

        genus = pick(species.get("genera", []), "genus")
        # Gebruik de nieuwste beschrijving: de laatste in de lijst.
        flavor_entries = list(reversed(species.get("flavor_text_entries", [])))
        description = pick(flavor_entries, "flavor_text")
        if description:
            # Teksten uit de oude spellen bevatten regeleinden en een
            # 'form feed'-teken; die vervangen we door gewone spaties.
            description = " ".join(description.replace("\f", " ").split())
        return genus, description
