import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import random
import sqlite3
import os
import time

DUCK_CHANNEL_NAME = os.getenv("DUCK_CHANNEL", "duck-hunt")
BOT_TOKEN         = os.getenv("DISCORD_TOKEN", "")
DB_PATH           = os.getenv("DB_PATH", "scores.db")
DUCK_SPAWN_MIN    = int(os.getenv("DUCK_SPAWN_MIN", "20"))   # seconds
DUCK_SPAWN_MAX    = int(os.getenv("DUCK_SPAWN_MAX", "120"))  # seconds

DUCK_TYPES = [
    {"id": "common", "emoji": "🦆", "name": "Common Duck",  "points": 1,  "timeout": 15, "weight": 60, "color": 0x3498DB},
    {"id": "baby",   "emoji": "🐥", "name": "Baby Duck",    "points": 2,  "timeout": 12, "weight": 25, "color": 0xF39C12},
    {"id": "eagle",  "emoji": "🦅", "name": "Golden Eagle", "points": 5,  "timeout": 8,  "weight": 10, "color": 0xE67E22},
    {"id": "royal",  "emoji": "👑", "name": "Royal Duck",   "points": 10, "timeout": 5,  "weight": 5,  "color": 0x9B59B6},
]
DUCK_WEIGHTS = [d["weight"] for d in DUCK_TYPES]

QUACK_LINES = [
    "Quick! A {emoji} **{name}** just landed!",
    "A wild {emoji} **{name}** appeared — don't let it escape!",
    "🎯 Incoming! A {emoji} **{name}** is here!",
    "Shhh… a {emoji} **{name}** is waddling around!",
]


# ── Database ──────────────────────────────────────────────────────────────────
def init_db():
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            guild_id TEXT NOT NULL,
            user_id  TEXT NOT NULL,
            username TEXT NOT NULL,
            score    INTEGER DEFAULT 0,
            kills    INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        )
    """)
    con.commit()
    con.close()


def add_score(guild_id: str, user_id: str, username: str, points: int):
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        INSERT INTO scores (guild_id, user_id, username, score, kills)
        VALUES (?, ?, ?, ?, 1)
        ON CONFLICT(guild_id, user_id) DO UPDATE SET
            score    = score + excluded.score,
            kills    = kills + 1,
            username = excluded.username
    """, (guild_id, user_id, username, points))
    con.commit()
    con.close()


def get_leaderboard(guild_id: str, limit: int = 10):
    con = sqlite3.connect(DB_PATH)
    rows = con.execute("""
        SELECT username, score, kills FROM scores
        WHERE guild_id = ? ORDER BY score DESC LIMIT ?
    """, (guild_id, limit)).fetchall()
    con.close()
    return rows


def get_stats(guild_id: str, user_id: str):
    con = sqlite3.connect(DB_PATH)
    row = con.execute("""
        SELECT username, score, kills FROM scores
        WHERE guild_id = ? AND user_id = ?
    """, (guild_id, user_id)).fetchone()
    con.close()
    return row


def get_rank(guild_id: str, user_id: str) -> int | None:
    con = sqlite3.connect(DB_PATH)
    rows = con.execute("""
        SELECT user_id FROM scores WHERE guild_id = ? ORDER BY score DESC
    """, (guild_id,)).fetchall()
    con.close()
    for i, (uid,) in enumerate(rows, 1):
        if uid == user_id:
            return i
    return None


# ── Interactive duck button ───────────────────────────────────────────────────
class DuckView(discord.ui.View):
    def __init__(self, duck: dict, guild_id: int):
        super().__init__(timeout=duck["timeout"])
        self.duck       = duck
        self.guild_id   = guild_id
        self.shot       = False
        self.spawn_time = time.time()
        self.message: discord.Message | None = None

    @discord.ui.button(label="🔫  BANG!", style=discord.ButtonStyle.danger)
    async def bang(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.shot:
            await interaction.response.send_message(
                "💨 Too slow — someone already got it!", ephemeral=True
            )
            return

        self.shot = True
        self.stop()

        user     = interaction.user
        duck     = self.duck
        react_ms = (time.time() - self.spawn_time) * 1000

        add_score(str(self.guild_id), str(user.id), user.display_name, duck["points"])
        rank = get_rank(str(self.guild_id), str(user.id))

        button.disabled = True
        button.label    = f"🎯 Shot by {user.display_name}!"
        button.style    = discord.ButtonStyle.success

        rank_str = f"  •  🏆 Rank #{rank}" if rank else ""
        embed = discord.Embed(
            description=(
                f"💥 **BANG!** {user.mention} shot the **{duck['name']} {duck['emoji']}**!\n"
                f"**+{duck['points']} pts**  •  ⏱️ {react_ms:.0f} ms{rank_str}"
            ),
            color=0x2ECC71,
        )
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        if self.shot or self.message is None:
            return
        for child in self.children:
            child.disabled = True
            child.label    = "🌊 Flew away…"
            child.style    = discord.ButtonStyle.secondary  # type: ignore[attr-defined]
        embed = discord.Embed(
            description=f"🌊 The **{self.duck['name']} {self.duck['emoji']}** got away!",
            color=0x95A5A6,
        )
        try:
            await self.message.edit(embed=embed, view=self)
        except discord.HTTPException:
            pass


# ── Bot ───────────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
bot     = commands.Bot(command_prefix="!", intents=intents)

# guild_id → True while a duck is active
_active: dict[int, bool] = {}


async def spawn_duck(guild: discord.Guild, channel: discord.TextChannel):
    duck  = random.choices(DUCK_TYPES, weights=DUCK_WEIGHTS, k=1)[0]
    text  = random.choice(QUACK_LINES).format(emoji=duck["emoji"], name=duck["name"])
    view  = DuckView(duck, guild.id)

    embed = discord.Embed(description=text, color=duck["color"])
    embed.set_footer(text=f"Worth {duck['points']} pt(s)  •  {duck['timeout']}s to shoot!")

    _active[guild.id] = True
    msg = await channel.send(embed=embed, view=view)
    view.message = msg
    await view.wait()
    _active[guild.id] = False


@tasks.loop(seconds=10)
async def spawn_loop():
    for guild in bot.guilds:
        if _active.get(guild.id):
            continue
        channel = discord.utils.get(guild.text_channels, name=DUCK_CHANNEL_NAME)
        if channel is None:
            continue
        # Probabilistic spawn — fires roughly every SPAWN_MIN–SPAWN_MAX seconds
        if random.random() > 10 / random.randint(DUCK_SPAWN_MIN, DUCK_SPAWN_MAX):
            continue
        asyncio.create_task(spawn_duck(guild, channel))


# ── Slash commands ────────────────────────────────────────────────────────────
@bot.tree.command(name="leaderboard", description="Show the Duck Hunt leaderboard")
async def cmd_leaderboard(interaction: discord.Interaction):
    rows = get_leaderboard(str(interaction.guild_id))
    if not rows:
        await interaction.response.send_message(
            "No scores yet — wait for a duck to appear!", ephemeral=True
        )
        return
    medals = ["🥇", "🥈", "🥉"]
    lines  = [
        f"{medals[i] if i < 3 else f'`#{i+1}`'} **{u}** — {s} pts ({k} kills)"
        for i, (u, s, k) in enumerate(rows)
    ]
    embed = discord.Embed(
        title="🦆 Duck Hunt Leaderboard",
        description="\n".join(lines),
        color=0xF39C12,
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="stats", description="Show your personal Duck Hunt stats")
async def cmd_stats(interaction: discord.Interaction):
    row = get_stats(str(interaction.guild_id), str(interaction.user.id))
    if not row:
        await interaction.response.send_message(
            "You haven't shot any ducks yet! Watch for one to appear.", ephemeral=True
        )
        return
    username, score, kills = row
    rank = get_rank(str(interaction.guild_id), str(interaction.user.id))
    avg  = round(score / kills, 2) if kills else 0
    embed = discord.Embed(title=f"🎯 {username}'s Stats", color=0x3498DB)
    embed.add_field(name="Score",  value=f"**{score}** pts",    inline=True)
    embed.add_field(name="Kills",  value=f"**{kills}** ducks",  inline=True)
    embed.add_field(name="Avg",    value=f"**{avg}** pts/kill", inline=True)
    embed.add_field(name="Rank",   value=f"**#{rank}**",        inline=True)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="duckhelp", description="How to play Duck Hunt")
async def cmd_duckhelp(interaction: discord.Interaction):
    channel = discord.utils.get(interaction.guild.text_channels, name=DUCK_CHANNEL_NAME)
    ch_mention = channel.mention if channel else f"#{DUCK_CHANNEL_NAME}"
    embed = discord.Embed(title="🦆 How to Play Duck Hunt", color=0x9B59B6)
    embed.add_field(
        name="How it works",
        value=(
            f"Ducks randomly appear in {ch_mention}.\n"
            "Click **🔫 BANG!** the moment you see one.\n"
            "**First click wins** — rarer ducks are worth more but vanish faster!"
        ),
        inline=False,
    )
    embed.add_field(
        name="Duck types",
        value="\n".join(
            f"{d['emoji']} **{d['name']}** — {d['points']} pt(s), {d['timeout']}s window"
            for d in DUCK_TYPES
        ),
        inline=False,
    )
    embed.add_field(
        name="Commands",
        value="`/leaderboard`  `/stats`  `/duckhelp`",
        inline=False,
    )
    await interaction.response.send_message(embed=embed)


# ── Events ────────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    init_db()
    await bot.tree.sync()
    spawn_loop.start()
    print(f"✅  Logged in as {bot.user} ({bot.user.id})")
    print(f"    Channel : #{DUCK_CHANNEL_NAME}")
    print(f"    Spawn   : every {DUCK_SPAWN_MIN}–{DUCK_SPAWN_MAX}s")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching, name="for ducks 🦆"
        )
    )


@bot.event
async def on_guild_join(guild: discord.Guild):
    channel = discord.utils.get(guild.text_channels, name=DUCK_CHANNEL_NAME)
    if channel:
        await channel.send(
            "🦆 **Duck Hunt is here!** Ducks will randomly appear — "
            "click **🔫 BANG!** first to score points!\n"
            "Use `/duckhelp` for more info."
        )


if __name__ == "__main__":
    if not BOT_TOKEN:
        raise ValueError("Set the DISCORD_TOKEN environment variable.")
    bot.run(BOT_TOKEN)
