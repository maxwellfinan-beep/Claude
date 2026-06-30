'use strict';

const express  = require('express');
const http     = require('http');
const { Server } = require('socket.io');
const path     = require('path');

const app        = express();
const httpServer = http.createServer(app);
const io         = new Server(httpServer);

const CLIENT_ID     = process.env.DISCORD_CLIENT_ID     || '';
const CLIENT_SECRET = process.env.DISCORD_CLIENT_SECRET || '';
const PORT          = process.env.PORT                  || 3000;

// ── Duck types ────────────────────────────────────────────────────────────────
const DUCK_TYPES = [
  { id: 'common', emoji: '🦆', name: 'Common Duck',  points: 1,  weight: 60 },
  { id: 'baby',   emoji: '🐥', name: 'Baby Duck',    points: 2,  weight: 25 },
  { id: 'eagle',  emoji: '🦅', name: 'Golden Eagle', points: 5,  weight: 10 },
  { id: 'royal',  emoji: '👑', name: 'Royal Duck',   points: 10, weight: 5  },
];

function pickDuck() {
  const total = DUCK_TYPES.reduce((s, d) => s + d.weight, 0);
  let r = Math.random() * total;
  for (const d of DUCK_TYPES) { r -= d.weight; if (r <= 0) return d; }
  return DUCK_TYPES[0];
}

// ── Per-instance state ────────────────────────────────────────────────────────
// instanceId → { scores: Map<userId, {username,score,kills}>, activeDuck, timers }
const rooms = new Map();

function getRoom(instanceId) {
  if (!rooms.has(instanceId)) {
    rooms.set(instanceId, {
      scores:      new Map(),
      activeDuck:  null,
      spawnTimer:  null,
      escapeTimer: null,
    });
  }
  return rooms.get(instanceId);
}

function scores2obj(map) {
  const o = {};
  map.forEach((v, k) => { o[k] = v; });
  return o;
}

function scheduleSpawn(instanceId, minMs = 3000, maxMs = 8000) {
  const room = getRoom(instanceId);
  clearTimeout(room.spawnTimer);
  const delay = minMs + Math.random() * (maxMs - minMs);
  room.spawnTimer = setTimeout(() => spawnDuck(instanceId), delay);
}

function spawnDuck(instanceId) {
  const room = rooms.get(instanceId);
  if (!room || room.activeDuck) return;

  // don't spawn if nobody is in the room
  const socketRoom = io.sockets.adapter.rooms.get(instanceId);
  if (!socketRoom || socketRoom.size === 0) return;

  const type      = pickDuck();
  const fromLeft  = Math.random() < 0.5;
  const duck = {
    id:        Math.random().toString(36).slice(2, 10),
    type,
    fromLeft,
    yFraction: 0.15 + Math.random() * 0.45,   // 0–1 fraction of game area height
    spawnTime: Date.now(),
  };

  room.activeDuck = duck;
  io.to(instanceId).emit('duck:spawn', duck);

  // Duck escapes after 5 s
  room.escapeTimer = setTimeout(() => {
    if (room.activeDuck?.id === duck.id) {
      room.activeDuck = null;
      io.to(instanceId).emit('duck:escaped', { duckId: duck.id });
      scheduleSpawn(instanceId);
    }
  }, 5000);
}

// ── HTTP routes ───────────────────────────────────────────────────────────────
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// Config endpoint — lets the client know the Discord Client ID
app.get('/api/config', (_req, res) => {
  res.json({ clientId: CLIENT_ID });
});

// Discord OAuth2 code → access_token exchange (runs server-side to keep secret safe)
app.post('/api/token', async (req, res) => {
  try {
    const { code } = req.body;
    const resp = await fetch('https://discord.com/api/oauth2/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        client_id:     CLIENT_ID,
        client_secret: CLIENT_SECRET,
        grant_type:    'authorization_code',
        code,
      }),
    });
    const data = await resp.json();
    if (!data.access_token) {
      console.error('Token exchange failed:', data);
      return res.status(400).json({ error: 'Token exchange failed' });
    }
    res.json({ access_token: data.access_token });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Server error' });
  }
});

// ── Socket.io ─────────────────────────────────────────────────────────────────
io.on('connection', (socket) => {
  let myInstance = null;
  let myUserId   = null;

  socket.on('join', ({ instanceId, userId, username }) => {
    myInstance = instanceId;
    myUserId   = userId;

    socket.join(instanceId);
    const room = getRoom(instanceId);

    if (!room.scores.has(userId)) {
      room.scores.set(userId, { username, score: 0, kills: 0 });
    } else {
      room.scores.get(userId).username = username;
    }

    // Send current state to the new player
    socket.emit('state:sync', {
      scores:     scores2obj(room.scores),
      activeDuck: room.activeDuck,
    });

    // Tell everyone about the updated roster
    io.to(instanceId).emit('scores:update', scores2obj(room.scores));

    // Start spawning when first player joins
    if (room.scores.size === 1 && !room.activeDuck && !room.spawnTimer) {
      scheduleSpawn(instanceId, 1500, 4000);
    }
  });

  socket.on('duck:shoot', ({ duckId }) => {
    if (!myInstance || !myUserId) return;
    const room = rooms.get(myInstance);
    if (!room || !room.activeDuck || room.activeDuck.id !== duckId) return;

    const duck = room.activeDuck;
    clearTimeout(room.escapeTimer);
    room.activeDuck = null;

    const player = room.scores.get(myUserId);
    if (player) {
      player.score += duck.type.points;
      player.kills += 1;
    }

    io.to(myInstance).emit('duck:killed', {
      duckId,
      shooterId:   myUserId,
      shooterName: player?.username || 'Unknown',
      points:      duck.type.points,
      duckType:    duck.type,
      scores:      scores2obj(room.scores),
    });

    scheduleSpawn(myInstance);
  });

  socket.on('disconnect', () => {
    if (!myInstance) return;
    const socketRoom = io.sockets.adapter.rooms.get(myInstance);
    if (!socketRoom || socketRoom.size === 0) {
      const room = rooms.get(myInstance);
      if (room) {
        clearTimeout(room.spawnTimer);
        clearTimeout(room.escapeTimer);
        rooms.delete(myInstance);
      }
    }
  });
});

httpServer.listen(PORT, () => {
  console.log(`🦆 Duck Hunt Activity → http://localhost:${PORT}`);
  console.log(`   DISCORD_CLIENT_ID: ${CLIENT_ID || '(not set — add to .env)'}`);
});
