# 🦆 Duck Hunt — Discord Activity

A real-time multiplayer duck hunting game that runs **inside Discord** as an
embedded Activity. Players launch it from a voice channel and race to click
ducks for points. Scores are tracked live on a leaderboard visible to everyone.

## How to play

1. Join a voice channel in the server
2. Click the **Activities** rocket icon → choose **Duck Hunt**
3. When a duck flies across the screen — **click it first!**
4. Rarer ducks are worth more points (and move faster)
5. First to the most points wins

## Duck types

| Duck | Points | Rarity | Difficulty |
|------|--------|--------|------------|
| 🦆 Common Duck  | 1 pt  | 60 % | Easy    |
| 🐥 Baby Duck    | 2 pts | 25 % | Moderate |
| 🦅 Golden Eagle | 5 pts | 10 % | Hard     |
| 👑 Royal Duck   | 10 pts | 5 % | Very hard |

## Setup

### 1. Create a Discord Application + Activity

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
2. Click **New Application**
3. Copy the **Application ID** (= `DISCORD_CLIENT_ID`)
4. Go to **OAuth2** → copy the **Client Secret** (= `DISCORD_CLIENT_SECRET`)
5. Go to **Activities** (left sidebar) → **Enable Activities**
6. Under **URL Mappings**, add a mapping:
   - **Prefix**: `/` (root)
   - **Target**: `localhost:3000` (for local dev) or your hosted URL

### 2. Tunnel for local development

Discord requires HTTPS for Activities. Use [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/):

```bash
# Install cloudflared, then:
cloudflared tunnel --url http://localhost:3000
```

Copy the `https://xxxxx.trycloudflare.com` URL and add it as a URL mapping in
the Discord Developer Portal under **Activities → URL Mappings**.

### 3. Install and run

```bash
npm install
cp .env.example .env
# Edit .env with your DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET
npm start
```

### 4. Invite the bot and test

- In **OAuth2 → URL Generator**, select scope `applications.commands` + `bot`
- Add **Send Messages** permission
- Open the generated invite URL to add the app to your server
- Join a voice channel → Activities icon → launch Duck Hunt

## Project structure

```
server.js           — Node.js backend (Express + Socket.io game server)
public/
  index.html        — Game shell / loading screen
  game.js           — Client game logic + Discord SDK integration
  style.css         — Visual styling
package.json
.env.example
```

## Tech stack

- **Runtime**: Node.js 18+
- **Server**: Express + Socket.io (real-time multiplayer)
- **Client**: Vanilla JS ES modules + HTML5 Canvas for effects
- **Discord**: `@discord/embedded-app-sdk` (loaded via esm.sh CDN)
- **Database**: In-memory per activity session (resets when all players leave)

> Scores live only for the duration of an activity session. For persistent
> cross-session leaderboards, swap the in-memory `rooms` Map in `server.js`
> for a SQLite or Postgres store.
