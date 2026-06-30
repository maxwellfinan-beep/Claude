import discord
from discord.ext import commands, tasks
import asyncio
import random
import sqlite3
import os
import time
from datetime import datetime

# ── Configuration ────────────────────────────────────────────────────────────
DUCK_CHANNEL_NAME = os.getenv("DUCK_CHANNEL", "duck-hunt")   # channel where ducks spawn
BOT_TOKEN = os.getenv("DISCORD_TOKEN", "")
DUCK_SPAWN_MIN = int(os.getenv("DUCK_SPAWN_MIN", "30"))      # seconds
DUCK_SPAWN_MAX = int(os.getenv("DUCK_SPAWN_MAX", "180"))     # seconds
DB_PATH = os.getenv("DB_PATH", "scores.db")

# ── Duck varieties ────────────────────────────────────────────────────────────
DUCKS = [
    {"emoji": "🦆", "name": "Common Duck",   "points": 1,  "weight": 60},
    {"emoji": "🐥", "name": "Baby Duck",      "points": 2,  "weight": 25},
    {"emoji": "🦅", "name": "Golden Eagle",   "points": 5,  "weight": 10},
    {"emoji": "👑", "name": "Royal Duck",     "points": 10, "weight": 5},
]

DUCK_WEIGHTS = [d["weight"] for d in DUCKS]

QUACK_MESSAGES = [
    "QUACK QUACK! A {name} {emoji} has landed! Type `!bang` to shoot it!",
    "Watch out! A wild {name} {emoji} appeared! Type `!bang` to hunt it!",
    "🎯 A {name} {emoji} is waddling around! Type `!bang` to bag it!",
    "Shhh... a {name} {emoji} is nearby! Type `!bang` to shoot it!",
]

MISS_MESSAGES = [
    "💨 The duck flew away before you could shoot!",
    "🌊 The duck dove into a pond and escaped!",
    "💨 Too slow! The {name} {emoji} got away!",
]

BANG_MESSAGES = [
    "💥 **BANG!** {user} shot the {name} {emoji} and earned **{points}** point(s)!",
    "🎯 **BANG!** {user} blasted the {name} {emoji} for **{points}** point(s)!",
    "🔫 **BOOM!** {user} took down the {name} {emoji} — +**{points}** point(s)!",
]

# ── Database ──────────────────────────────────────────────────────────────────
def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            guild_id   TEXT NOT NULL,
            user_id    TEXT NOT NULL,
            username   TEXT NOT NULL,
            score      INTEGER DEFAULT 0,
            kills      INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS hunt_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id   TEXT NOT NULL,
            user_id    TEXT NOT NULL,
            duck_name  TEXT NOT NULL,
            points     INTEGER NOT NULL,
            ts         INTEGER NOT NULL
        )
    """)
    con.commit()
    con.close()


def add_score(guild_id: str, user_id: str, username: str, points: int, duck_name: str):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        INSERT INTO scores (guild_id, user_id, username, score, kills)
        VALUES (?, ?, ?, ?, 1)
        ON CONFLICT(guild_id, user_id) DO UPDATE SET
            score    = score + excluded.score,
            kills    = kills + 1,
            username = excluded.username
    """, (guild_id, user_id, username, points))
    cur.execute("""
        INSERT INTO hunt_log (guild_id, user_id, duck_name, points, ts)
        VALUES (?, ?, ?, ?, ?)
    """, (guild_id, user_id, duck_name, points, int(time.time())))
    con.commit()
    con.close()


def get_leaderboard(guild_id: str, limit: int = 10):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    rows = cur.execute("""
        SELECT username, score, kills
        FROM scores
        WHERE guild_id = ?
        ORDER BY score DESC
        LIMIT ?
    """, (guild_id, limit)).fetchall()
    con.close()
    return rows


def get_user_stats(guild_id: str, user_id: str):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    row = cur.execute("""
        SELECT username, score, kills,
               RANK() OVER (ORDER BY score DESC) AS rank
        FROM scores
        WHERE guild_id = ?
    """, (guild_id,)).fetchall()
    con.close()
    for r in row:
        if r[0] == user_id:
            return r
    # fallback – query directly
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    r = cur.execute("""
        SELECT username, score, kills
        FROM scores WHERE guild_id = ? AND user_id = ?
    """, (guild_id, user_id)).fetchone()
    con.close()
    return r


def get_rank(guild_id: str, user_id: str):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    rows = cur.execute("""
        SELECT user_id FROM scores
        WHERE guild_id = ?
        ORDER BY score DESC
    """, (guild_id,)).fetchall()
    con.close()
    for i, (uid,) in enumerate(rows, 1):
        if uid == user_id:
            return i
    return None


# ── Bot setup ─────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Per-guild state: active duck info
active_ducks: dict[int, dict] = {}   # guild_id -> {duck, message, ts}


# ── Spawn loop ────────────────────────────────────────────────────────────────
@tasks.loop(seconds=10)
async def duck_spawner():
    for guild in bot.guilds:
        # Skip if a duck is already active in this guild
        if guild.id in active_ducks:
            continue

        channel = discord.utils.get(guild.text_channels, name=DUCK_CHANNEL_NAME)
        if channel is None:
            continue

        # Random delay: only spawn ~1/N of the time each tick to spread spawns
        tick_probability = 10 / random.randint(DUCK_SPAWN_MIN, DUCK_SPAWN_MAX)
        if random.random() > tick_probability:
            continue

        await spawn_duck(guild, channel)


async def spawn_duck(guild: discord.Guild, channel: discord.TextChannel):
    duck = random.choices(DUCKS, weights=DUCK_WEIGHTS, k=1)[0]
    text = random.choice(QUACK_MESSAGES).format(name=duck["name"], emoji=duck["emoji"])

    embed = discord.Embed(
        description=text,
        color=0x2ECC71,
    )
    embed.set_footer(text=f"Worth {duck['points']} point(s)  •  React fast!")

    msg = await channel.send(embed=embed)
    active_ducks[guild.id] = {
        "duck": duck,
        "message": msg,
        "channel_id": channel.id,
        "ts": time.time(),
    }

    # Duck flies away after 30 s if nobody shoots
    await asyncio.sleep(30)
    if guild.id in active_ducks and active_ducks[guild.id]["message"].id == msg.id:
        del active_ducks[guild.id]
        miss = random.choice(MISS_MESSAGES).format(
            name=duck["name"], emoji=duck["emoji"]
        )
        await channel.send(f"🦆💨 {miss}")


# ── Commands ──────────────────────────────────────────────────────────────────
@bot.command(name="bang", aliases=["shoot", "fire"])
async def bang(ctx: commands.Context):
    guild_id = ctx.guild.id
    state = active_ducks.get(guild_id)

    if state is None:
        await ctx.send("🚫 There's no duck to shoot right now! Wait for one to appear.")
        return

    duck = state["duck"]
    del active_ducks[guild_id]

    username = ctx.author.display_name
    add_score(str(guild_id), str(ctx.author.id), username, duck["points"], duck["name"])

    text = random.choice(BANG_MESSAGES).format(
        user=ctx.author.mention,
        name=duck["name"],
        emoji=duck["emoji"],
        points=duck["points"],
    )
    rank = get_rank(str(guild_id), str(ctx.author.id))
    rank_str = f"  •  Rank #{rank}" if rank else ""

    embed = discord.Embed(description=text, color=0xE74C3C)
    embed.set_footer(text=f"React time: {time.time() - state['ts']:.2f}s{rank_str}")
    await ctx.send(embed=embed)


@bot.command(name="leaderboard", aliases=["lb", "top", "scores"])
async def leaderboard(ctx: commands.Context):
    rows = get_leaderboard(str(ctx.guild.id))

    if not rows:
        await ctx.send("📋 No scores yet — wait for a duck to appear and shoot it with `!bang`!")
        return

    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, (username, score, kills) in enumerate(rows, 1):
        medal = medals[i - 1] if i <= 3 else f"`#{i}`"
        lines.append(f"{medal} **{username}** — {score} pts  ({kills} kills)")

    embed = discord.Embed(
        title="🦆 Duck Hunt Leaderboard",
        description="\n".join(lines),
        color=0xF39C12,
        timestamp=datetime.utcnow(),
    )
    embed.set_footer(text="Use !bang when a duck appears to score points!")
    await ctx.send(embed=embed)


@bot.command(name="stats", aliases=["myscore", "me"])
async def stats(ctx: commands.Context):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    row = cur.execute("""
        SELECT username, score, kills
        FROM scores WHERE guild_id = ? AND user_id = ?
    """, (str(ctx.guild.id), str(ctx.author.id))).fetchone()
    con.close()

    if row is None:
        await ctx.send(f"🦆 {ctx.author.mention}, you haven't shot any ducks yet! Wait for one with `!bang`.")
        return

    username, score, kills = row
    rank = get_rank(str(ctx.guild.id), str(ctx.author.id))
    avg = round(score / kills, 2) if kills else 0

    embed = discord.Embed(
        title=f"🎯 {username}'s Duck Hunt Stats",
        color=0x3498DB,
        timestamp=datetime.utcnow(),
    )
    embed.add_field(name="Score",      value=f"**{score}** pts",   inline=True)
    embed.add_field(name="Kills",      value=f"**{kills}** ducks", inline=True)
    embed.add_field(name="Avg pts",    value=f"**{avg}**",         inline=True)
    embed.add_field(name="Server Rank",value=f"**#{rank}**",       inline=True)
    await ctx.send(embed=embed)


@bot.command(name="duckscore", aliases=["ds"])
async def duckscore(ctx: commands.Context):
    """Alias for !stats"""
    await stats(ctx)


@bot.command(name="duckhelp", aliases=["hunthelp"])
async def duckhelp(ctx: commands.Context):
    embed = discord.Embed(
        title="🦆 Duck Hunt — How to Play",
        color=0x9B59B6,
    )
    embed.add_field(
        name="How it works",
        value=(
            "Ducks randomly appear in this channel. "
            "When you see one, type **`!bang`** as fast as possible to shoot it before anyone else!"
        ),
        inline=False,
    )
    embed.add_field(
        name="Duck Types",
        value="\n".join(
            f"{d['emoji']} **{d['name']}** — {d['points']} pt(s)" for d in DUCKS
        ),
        inline=False,
    )
    embed.add_field(
        name="Commands",
        value=(
            "`!bang` / `!shoot` — Shoot the duck\n"
            "`!leaderboard` / `!lb` — Server leaderboard\n"
            "`!stats` / `!me` — Your personal stats\n"
            "`!duckhelp` — This help message"
        ),
        inline=False,
    )
    await ctx.send(embed=embed)


# ── Events ────────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    init_db()
    duck_spawner.start()
    print(f"✅  Logged in as {bot.user} ({bot.user.id})")
    print(f"    Watching channel: #{DUCK_CHANNEL_NAME}")
    print(f"    Spawn interval: {DUCK_SPAWN_MIN}–{DUCK_SPAWN_MAX}s")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="for ducks 🦆 | !duckhelp"
        )
    )


@bot.event
async def on_guild_join(guild: discord.Guild):
    channel = discord.utils.get(guild.text_channels, name=DUCK_CHANNEL_NAME)
    if channel:
        await channel.send(
            "🦆 **Duck Hunt Bot has arrived!** Ducks will randomly appear here.\n"
            "Type `!bang` when you see one — first to shoot wins points!\n"
            "Use `!duckhelp` for more info."
        )


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not BOT_TOKEN:
        raise ValueError("Set the DISCORD_TOKEN environment variable to your bot token.")
    bot.run(BOT_TOKEN)
