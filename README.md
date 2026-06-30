# 🦆 Duck Hunt — Discord Text Channel Game

A competitive Duck Hunt game that runs in a Discord **text channel**.
Ducks appear as interactive message embeds with a **🔫 BANG!** button.
The whole server races to click first — fastest finger wins points.

## How it works

1. A duck randomly appears in `#duck-hunt` as a message with a button
2. Everyone sees it — **first to click 🔫 BANG! wins the points**
3. The button locks after the first click (others see "Too slow!")
4. If nobody clicks in time, the duck flies away
5. Scores are saved permanently in a local database

## Duck types

| Duck | Points | Time window | Rarity |
|------|--------|-------------|--------|
| 🦆 Common Duck  | 1 pt   | 15 s | 60 % |
| 🐥 Baby Duck    | 2 pts  | 12 s | 25 % |
| 🦅 Golden Eagle | 5 pts  | 8 s  | 10 % |
| 👑 Royal Duck   | 10 pts | 5 s  | 5 %  |

Rarer ducks are worth more but vanish faster — reaction time matters!

## Commands

| Command | Description |
|---------|-------------|
| `/leaderboard` | Server-wide leaderboard (top 10) |
| `/stats` | Your personal score, kills, avg, and rank |
| `/duckhelp` | Rules and duck type guide |

## Setup

### 1. Create a Discord bot

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
2. **New Application** → give it a name
3. Go to **Bot** → **Add Bot** → copy the **Token**
4. Under **Privileged Gateway Intents** → no special intents needed
5. Go to **OAuth2 → URL Generator**:
   - Scopes: `bot` + `applications.commands`
   - Bot Permissions: `Send Messages`, `Embed Links`, `Read Message History`, `View Channels`
6. Open the generated URL to invite the bot to your server

### 2. Create the channel

Make a text channel named exactly `duck-hunt` (or set `DUCK_CHANNEL` env var).

### 3. Run

```bash
pip install -r requirements.txt
export DISCORD_TOKEN=your-token-here
python bot.py
```

Or copy `.env.example` → `.env`, fill in your token, then:

```bash
pip install python-dotenv
# add: from dotenv import load_dotenv; load_dotenv()  at top of bot.py
python bot.py
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DISCORD_TOKEN` | *(required)* | Your bot token |
| `DUCK_CHANNEL` | `duck-hunt` | Channel name for duck spawns |
| `DUCK_SPAWN_MIN` | `20` | Min seconds between spawns |
| `DUCK_SPAWN_MAX` | `120` | Max seconds between spawns |
| `DB_PATH` | `scores.db` | SQLite database path |

Scores are stored per-server and persist across restarts.
