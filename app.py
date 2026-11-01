import asyncio
import logging
import math
import os
import random
import re
import sys
from typing import Optional

import aiohttp
import discord

import settings

# Ensure math.random is available if referenced
math.random = random.random

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pokemon-roller")

# Cache for ability English names to minimize API calls
_ABILITY_NAME_CACHE: dict[str, str] = {}

# Matrix of Pokémon natures based on:
# 1st roll (1-5): Lowered Stat
# 2nd roll (1-5): Raised Stat
# Stat indices: 1: Attack, 2: Defense, 3: SpAtk, 4: SpDef, 5: Speed
NATURE_MATRIX: dict[tuple[int, int], str] = {
    (1, 1): "Hardy",
    (1, 2): "Bold",
    (1, 3): "Modest",
    (1, 4): "Calm",
    (1, 5): "Timid",
    (2, 1): "Lonely",
    (2, 2): "Docile",
    (2, 3): "Mild",
    (2, 4): "Gentle",
    (2, 5): "Hasty",
    (3, 1): "Adamant",
    (3, 2): "Impish",
    (3, 3): "Bashful",
    (3, 4): "Careful",
    (3, 5): "Jolly",
    (4, 1): "Naughty",
    (4, 2): "Lax",
    (4, 3): "Rash",
    (4, 4): "Quirky",
    (4, 5): "Naive",
    (5, 1): "Brave",
    (5, 2): "Relaxed",
    (5, 3): "Quiet",
    (5, 4): "Sassy",
    (5, 5): "Serious",
}


class PokemonNotFoundError(Exception):
    """Raised when a Pokémon cannot be found on PokéAPI."""
    pass


def roll_dice(sides: int) -> int:
    """Roll a 1d{sides} die, returning a value from 1 to sides inclusive."""
    return random.randint(1, sides)


def roll_gender(gender_rate: int) -> Optional[str]:
    """
    Step 1: If the Pokémon supports gender, determine the appropriate dice to
    represent the percentile split (e.g. 75/25 -> d4) with the higher range
    rolls being female.

    PokéAPI gender_rate:
      -1: Genderless -> None
       0: 100% Male -> 'M'
       8: 100% Female -> 'F'
       1..7: Female chance is gender_rate/8.
    """
    if gender_rate == -1:
        return None
    if gender_rate == 0:
        return "M"
    if gender_rate == 8:
        return "F"

    g = math.gcd(gender_rate, 8)
    die_sides = 8 // g
    female_count = gender_rate // g
    threshold = die_sides - female_count + 1

    roll = roll_dice(die_sides)
    return "F" if roll >= threshold else "M"


def roll_ivs() -> dict[str, int]:
    """
    Step 2: Roll 6d31 to determine the Pokémon's IVs; these are always sorted
    in order rolled: HP, Attack, Defense, SpAtk, SpDef, and Speed.
    """
    return {
        "HP": roll_dice(31),
        "Atk": roll_dice(31),
        "Def": roll_dice(31),
        "SpA": roll_dice(31),
        "SpD": roll_dice(31),
        "Spe": roll_dice(31),
    }


def roll_nature() -> str:
    """
    Step 3: Roll 2d5 to determine the Pokémon's Nature.
    First roll determines lowered stat, second roll determines raised stat.
    Values mapped skipping HP (1: Attack, 2: Defense, 3: SpAtk, 4: SpDef, 5: Speed).
    """
    lowered = roll_dice(5)
    raised = roll_dice(5)
    return NATURE_MATRIX[(lowered, raised)]


def roll_ability(abilities: list[dict]) -> dict:
    """
    Step 4: If the Pokémon has multiple abilities, roll 1d10.
    On 1-5, the Pokémon gets its first ability option, on 6-10 it gets its second ability.
    Additionally, if they have a hidden ability, this replaces a 10
    (making the second ability slightly rarer than the first).
    """
    normal = [a for a in sorted(abilities, key=lambda x: x.get("slot", 1)) if not a.get("is_hidden", False)]
    hidden = [a for a in sorted(abilities, key=lambda x: x.get("slot", 1)) if a.get("is_hidden", False)]

    total = len(normal) + len(hidden)
    if total <= 1:
        return normal[0] if normal else hidden[0]

    roll = roll_dice(10)
    has_hidden = len(hidden) > 0

    if roll == 10 and has_hidden:
        return hidden[0]
    elif 1 <= roll <= 5:
        return normal[0]
    else:  # roll in 6..10 (or 6..9 if hidden)
        return normal[1] if len(normal) >= 2 else normal[0]


def roll_shiny() -> bool:
    """
    Step 5: Roll 1d(shiny odds) to determine if the Pokémon is shiny.
    """
    return roll_dice(settings.SHINYODDS) == 1


def format_showdown(
    name: str,
    gender: Optional[str],
    ability_name: str,
    is_shiny: bool,
    ivs: dict[str, int],
    nature: str,
) -> str:
    """
    Formats the complete Pokémon into a Pokémon Showdown text export.
    No moves or EVs are included.
    """
    header = f"{name} ({gender})" if gender else name
    lines = [
        header,
        f"Ability: {ability_name}",
    ]
    if is_shiny:
        lines.append("Shiny: Yes")

    iv_str = " / ".join(f"{val} {stat}" for stat, val in ivs.items())
    lines.append(f"IVs: {iv_str}")
    lines.append(f"{nature} Nature")

    return "\n".join(lines)


def normalize_pokemon_name(raw: str) -> str:
    """Normalizes user input for PokéAPI lookup."""
    name = raw.strip().lower()
    special = {
        "nidoran m": "nidoran-m",
        "nidoran-m": "nidoran-m",
        "nidoran male": "nidoran-m",
        "nidoran(m)": "nidoran-m",
        "nidoran (m)": "nidoran-m",
        "nidoran f": "nidoran-f",
        "nidoran-f": "nidoran-f",
        "nidoran female": "nidoran-f",
        "nidoran(f)": "nidoran-f",
        "nidoran (f)": "nidoran-f",
        "type: null": "type-null",
        "type:null": "type-null",
        "type null": "type-null",
        "flabébé": "flabebe",
        "mr. mime": "mr-mime",
        "mr mime": "mr-mime",
        "mr. rime": "mr-rime",
        "mr rime": "mr-rime",
        "mime jr.": "mime-jr",
        "mime jr": "mime-jr",
        "farfetch'd": "farfetchd",
        "sirfetch'd": "sirfetchd",
    }
    if name in special:
        return special[name]

    name = re.sub(r"[\s_]+", "-", name)
    name = re.sub(r"[^a-z0-9\-]", "", name)
    name = re.sub(r"-+", "-", name).strip("-")
    return name


def format_display_name(pokemon_data: dict, species_data: dict) -> str:
    """Determines the appropriate Showdown species/form name."""
    clean = pokemon_data.get("name", "")
    spec_name = species_data.get("name", "")

    if clean == "nidoran-m":
        return "Nidoran-M"
    if clean == "nidoran-f":
        return "Nidoran-F"

    # If it's the base species, use official English name from species
    if clean == spec_name:
        for entry in species_data.get("names", []):
            if entry.get("language", {}).get("name") == "en":
                name = entry.get("name", "")
                # Clean up typographic quotes for Showdown compatibility
                return name.replace("’", "'")

    # For forms or fallbacks, titlecase hyphen-separated parts
    parts = clean.split("-")
    return "-".join(p.capitalize() for p in parts)


def format_slug_fallback(slug: str) -> str:
    """Converts a slug like 'lightning-rod' to 'Lightning Rod'."""
    return " ".join(word.capitalize() for word in slug.split("-"))


async def fetch_ability_display_name(session: aiohttp.ClientSession, ability_entry: dict) -> str:
    """Fetches the official English ability name, with caching and fallback."""
    slug = ability_entry.get("ability", {}).get("name", "")
    if not slug:
        return "Unknown"

    if slug in _ABILITY_NAME_CACHE:
        return _ABILITY_NAME_CACHE[slug]

    url = ability_entry.get("ability", {}).get("url")
    if url:
        try:
            async with session.get(url, headers={"User-Agent": "Pokemon-Roller/1.0"}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for entry in data.get("names", []):
                        if entry.get("language", {}).get("name") == "en":
                            official_name = entry.get("name", "")
                            _ABILITY_NAME_CACHE[slug] = official_name
                            return official_name
        except Exception as e:
            logger.warning(f"Could not fetch official ability name for {slug}: {e}")

    fallback = format_slug_fallback(slug)
    _ABILITY_NAME_CACHE[slug] = fallback
    return fallback


async def roll_pokemon(name_query: str) -> str:
    """
    Fetches data from PokéAPI for the given Pokémon, applies all dice rolls,
    and returns a Pokémon Showdown formatted export string.
    """
    clean_name = normalize_pokemon_name(name_query)
    if not clean_name:
        raise PokemonNotFoundError(f"Invalid Pokémon name '{name_query}'.")

    url = f"https://pokeapi.co/api/v2/pokemon/{clean_name}"
    headers = {"User-Agent": "Pokemon-Roller/1.0"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status == 404:
                raise PokemonNotFoundError(f"Pokémon '{name_query}' not found.")
            if resp.status != 200:
                raise RuntimeError(f"PokéAPI error (status {resp.status}) fetching Pokémon '{name_query}'.")
            pokemon_data = await resp.json()

        species_url = pokemon_data.get("species", {}).get("url")
        if not species_url:
            raise RuntimeError(f"No species URL found for '{name_query}'.")

        async with session.get(species_url, headers=headers) as resp:
            if resp.status != 200:
                raise RuntimeError(f"PokéAPI error (status {resp.status}) fetching species data.")
            species_data = await resp.json()

        gender_rate = species_data.get("gender_rate", -1)
        gender = roll_gender(gender_rate)
        ivs = roll_ivs()
        nature = roll_nature()

        abilities = pokemon_data.get("abilities", [])
        chosen_ability = roll_ability(abilities)
        ability_name = await fetch_ability_display_name(session, chosen_ability)

        is_shiny = roll_shiny()
        display_name = format_display_name(pokemon_data, species_data)

        return format_showdown(
            name=display_name,
            gender=gender,
            ability_name=ability_name,
            is_shiny=is_shiny,
            ivs=ivs,
            nature=nature,
        )


def create_bot() -> discord.Bot:
    server_id = int(settings.SERVERID)

    intents = discord.Intents.default()
    bot = discord.Bot(
        intents=intents,
        debug_guilds=[server_id],
    )

    @bot.event
    async def on_ready():
        logger.info(f"Bot connected as {bot.user} (ID: {bot.user.id})")
        logger.info(f"Registered on server ID: {server_id}")

    @bot.slash_command(
        name="roll",
        description="Roll a Pokémon and export in Pokémon Showdown format",
        guild_ids=[server_id],
    )
    async def roll(
        ctx: discord.ApplicationContext,
        pokemon: discord.Option(
            str,
            name="pokemon",
            description="The name of the Pokémon to roll",
            required=True,
        ),
    ):
        await ctx.defer()
        try:
            export_text = await roll_pokemon(pokemon)
            await ctx.respond(f"```\n{export_text}\n```")
        except PokemonNotFoundError:
            await ctx.respond(f"Could not find Pokémon '{pokemon}'. Please check spelling and try again.")
        except Exception as e:
            logger.error(f"Error rolling '{pokemon}': {e}", exc_info=True)
            await ctx.respond(f"An error occurred while rolling '{pokemon}': {e}")

    return bot


def main():
    if not hasattr(settings, "BOTTOKEN") or not settings.BOTTOKEN or settings.BOTTOKEN == "placeholder":
        logger.error("BOTTOKEN is not configured or still set to placeholder in settings.py.")
        sys.exit(1)

    if not hasattr(settings, "SERVERID") or not settings.SERVERID:
        logger.error("SERVERID is not configured in settings.py.")
        sys.exit(1)

    bot = create_bot()
    bot.run(settings.BOTTOKEN)


if __name__ == "__main__":
    main()
