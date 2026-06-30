# 🦆 Discord Duck Hunter

A competitive Discord bot game where ducks randomly appear in a channel and server members race to shoot them first. Scores are tracked on a persistent leaderboard.

## How It Works

1. Ducks randomly appear in the `#duck-hunt` channel (configurable)
2. First person to type `!bang` shoots the duck and earns points
3. If nobody shoots within 30 seconds, the duck flies away
4. Different duck types are worth different points

## Duck Types

| Duck | Points | Rarity |
|------|--------|--------|
| 🦆 Common Duck | 1 pt | Common |
| 🐥 Baby Duck | 2 pts | Uncommon |
| 🦅 Golden Eagle | 5 pts | Rare |
| 👑 Royal Duck | 10 pts | Very Rare |

## Commands

| Command | Description |
|---------|-------------|
| `!bang` / `!shoot` | Shoot the active duck |
| `!leaderboard` / `!lb` | Show the server leaderboard |
| `!stats` / `!me` | Show your personal stats |
| `!duckhelp` | Show help |

## Setup

### 1. Create a Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **New Application** → give it a name
3. Go to **Bot** → click **Add Bot**
4. Under **Privileged Gateway Intents**, enable:
   - **Message Content Intent**
5. Copy the **Token** (you'll need it below)
6. Go to **OAuth2 → URL Generator**:
   - Scopes: `bot`
   - Bot Permissions: `Send Messages`, `Embed Links`, `Read Message History`, `View Channels`
7. Open the generated URL to invite the bot to your server

### 2. Create the Channel

Create a text channel named `duck-hunt` in your server (or set `DUCK_CHANNEL` env var to a different name).

### 3. Run the Bot

```bash
# Install dependencies
pip install -r requirements.txt

# Set your bot token
export DISCORD_TOKEN=your-token-here

# Run
python bot.py
```

Or copy `.env.example` to `.env`, fill it in, and use a tool like `python-dotenv` or `dotenv` CLI to load it:

```bash
cp .env.example .env
# edit .env with your token
dotenv run python bot.py
```

## Configuration

| Environment Variable | Default | Description |
|----------------------|---------|-------------|
| `DISCORD_TOKEN` | *(required)* | Your bot token |
| `DUCK_CHANNEL` | `duck-hunt` | Channel name where ducks spawn |
| `DUCK_SPAWN_MIN` | `30` | Minimum seconds between spawns |
| `DUCK_SPAWN_MAX` | `180` | Maximum seconds between spawns |
| `DB_PATH` | `scores.db` | Path to SQLite database |

## Scores

Scores are stored in a local SQLite database (`scores.db`). Each guild has its own independent leaderboard.
