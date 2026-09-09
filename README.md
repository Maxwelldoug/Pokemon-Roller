# Pokemon-Roller

A Discord bot built with Pycord to roll Pokémon for campaigns and export them directly in Pokémon Showdown importable format.

## Features

- **Automated Roll Mechanics:** Replaces manual Avrae dice rolls with instant generation:
  1. **Gender:** Evaluates PokéAPI's gender ratio. If the Pokémon supports gender, determines the smallest die representing the percentile split (e.g. 75% F / 25% M &rarr; d4, 50/50 &rarr; d2, 12.5% F &rarr; d8), with higher rolls resulting in female. Genderless and single-gender Pokémon are accurately assigned.
  2. **IVs:** Rolls `6d31` (1–31) mapped in order: HP, Attack, Defense, Special Attack, Special Defense, Speed.
  3. **Nature:** Rolls `2d5` where the first roll determines the lowered stat and the second determines the raised stat (mapped to Attack, Defense, SpAtk, SpDef, Speed). Neutral natures occur when both rolls match.
  4. **Ability:** For Pokémon with multiple abilities, rolls `1d10`. Rolls 1–5 award the first regular ability; 6–10 award the second. If the Pokémon has a hidden ability, it replaces roll 10 (making the second ability slightly rarer: 40% vs 50%).
  5. **Shiny Status:** Rolls `1d8192`. On a roll of 1, the Pokémon is shiny (`Shiny: Yes`).
- **Showdown Export:** Formats the resulting Pokémon in a code block ready to copy and paste into Pokémon Showdown (moves and EVs omitted so players can configure them).
- **Single Slash Command:** Registers exactly one guild-scoped slash command (`/roll`) for immediate availability on your Discord server.
- **Docker-Ready:** Runs directly from the standard `python:3.11-slim` image with `requirements.txt`, `app.py`, and `settings.py` statically mounted (no custom image build required).

---

## Configuration

Ensure `settings.py` is configured with your Discord guild ID and bot token (refer to `settings.py.template`):

```python
SERVERID = 123456789012345678  # Discord Server (Guild) ID as an integer
BOTTOKEN = 'your-bot-token-here'
```

---

## Running with Docker

The bot is designed to run in a standard container with `requirements.txt`, `app.py`, and `settings.py` statically mounted.

### Option A: Using Docker Compose (Recommended)

Start the bot in the background:
```bash
docker compose up -d
```

View logs:
```bash
docker compose logs -f
```

Stop the bot:
```bash
docker compose down
```

### Option B: Using `docker run`

```bash
docker run -d \
  --name pokemon-roller \
  --restart unless-stopped \
  -w /app \
  -v "$(pwd)/requirements.txt:/app/requirements.txt:ro" \
  -v "$(pwd)/app.py:/app/app.py:ro" \
  -v "$(pwd)/settings.py:/app/settings.py:ro" \
  python:3.11-slim \
  sh -c "pip install --no-cache-dir -r requirements.txt && python -u app.py"
```

---

## Slash Command Usage

In any channel on the configured server:

```text
/roll pokemon: pikachu
```

Output example:
```text
Pikachu (M)
Ability: Static
IVs: 24 HP / 18 Atk / 31 Def / 9 SpA / 20 SpD / 29 Spe
Jolly Nature
```

Special Pokémon names (e.g. `Tapu Koko`, `Mr. Mime`, `Farfetch'd`, `Rotom-Wash`, `Nidoran-M`) are automatically handled and normalized.

---

## Running Tests

You can run the unit test suite inside Docker:

```bash
docker run --rm \
  -v "$(pwd)/requirements.txt:/app/requirements.txt:ro" \
  -v "$(pwd)/app.py:/app/app.py:ro" \
  -v "$(pwd)/settings.py:/app/settings.py:ro" \
  -v "$(pwd)/test_roller.py:/app/test_roller.py:ro" \
  -w /app \
  python:3.11-slim \
  sh -c "pip install -q -r requirements.txt && python test_roller.py -v"
```
