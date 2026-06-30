# 🦆 Duck Hunt — Discord Activity

A **visual multiplayer Duck Hunt game** that runs inside Discord.
Ducks fly across the screen — everyone in the session races to click them first.
Live leaderboard, particle effects, animated clouds and scenery.

Works in **text channels AND voice channels**.

## How to play

1. In a text channel, click **+** → **Use an App** → Duck Hunt
   *(or in a voice channel, click the Activities rocket icon)*
2. The game launches inside Discord — no browser needed
3. Ducks randomly fly across the screen — **click one to shoot it**
4. First click wins the points — faster/rarer ducks are worth more
5. Watch the live leaderboard on the right

## Duck types

| | Name | Points | Speed | Rarity |
|-|------|--------|-------|--------|
| 🦆 | Common Duck  | 1  | Normal    | 60% |
| 🐥 | Baby Duck    | 2  | Fast      | 25% |
| 🦅 | Golden Eagle | 5  | Very fast | 10% |
| 👑 | Royal Duck   | 10 | Blazing   | 5%  |

## Setup

### 1. Developer Portal

1. [discord.com/developers/applications](https://discord.com/developers/applications) → your app (or New Application)
2. Copy the **Application ID** → this is your `DISCORD_CLIENT_ID`
3. **OAuth2** → copy the **Client Secret** → `DISCORD_CLIENT_SECRET`
4. **Activities** (left sidebar) → enable Activities
5. Under **URL Mappings**, add:
   - Prefix: `/`
   - Target: `localhost:3000`

### 2. HTTPS tunnel (required for local dev)

Discord requires HTTPS. Install [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) then:

```bash
cloudflared tunnel --url http://localhost:3000
```

Copy the `https://xxxxx.trycloudflare.com` URL.
Go back to **Activities → URL Mappings** and set that as the target.

### 3. Install & run

```bash
npm install
cp .env.example .env
# fill in DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET in .env
npm start
```

### 4. Launch in Discord

- Join a text channel → click **+** next to the message box → **Use an App**
- Or join a voice channel → click the **🚀 Activities** button
- Select **Duck Hunt**

## Tech stack

| Part | Tech |
|------|------|
| Server | Node.js + Express + Socket.io |
| Client | Vanilla JS + HTML5 Canvas (no build step) |
| Auth | Discord Embedded App SDK |
| Storage | In-memory per session |
