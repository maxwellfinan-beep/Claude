'use strict';

const express    = require('express');
const http       = require('http');
const { Server } = require('socket.io');
const path       = require('path');

const app        = express();
const httpServer = http.createServer(app);
const io         = new Server(httpServer);

const CLIENT_ID     = process.env.DISCORD_CLIENT_ID     || '';
const CLIENT_SECRET = process.env.DISCORD_CLIENT_SECRET || '';
const PORT          = process.env.PORT || 3000;

// ── Duck types ────────────────────────────────────────────────────────────────
const DUCK_TYPES = [
  { id: 'common', emoji: '🦆', name: 'Common Duck',  points: 1,  speed: 1.0, weight: 60 },
  { id: 'baby',   emoji: '🐥', name: 'Baby Duck',    points: 2,  speed: 1.4, weight: 25 },
  { id: 'eagle',  emoji: '🦅', name: 'Golden Eagle', points: 5,  speed: 1.9, weight: 10 },
  { id: 'royal',  emoji: '👑', name: 'Royal Duck',   points: 10, speed: 2.5, weight: 5  },
];

function pickDuck() {
  const total = DUCK_TYPES.reduce((s, d) => s + d.weight, 0);
  let r = Math.random() * total;
  for (const d of DUCK_TYPES) { r -= d.weight; if (r <= 0) return d; }
  return DUCK_TYPES[0];
}

// ── Per-instance state ────────────────────────────────────────────────────────
const rooms = new Map(); // instanceId → { scores, activeDuck, timers }

function getRoom(id) {
  if (!rooms.has(id)) rooms.set(id, { scores: new Map(), activeDuck: null, spawnTimer: null, escapeTimer: null });
  return rooms.get(id);
}

function scoreObj(map) {
  const o = {};
  map.forEach((v, k) => { o[k] = v; });
  return o;
}

function scheduleSpawn(instanceId) {
  const room = getRoom(instanceId);
  clearTimeout(room.spawnTimer);
  const delay = 3000 + Math.random() * 7000;
  room.spawnTimer = setTimeout(() => spawnDuck(instanceId), delay);
}

function spawnDuck(instanceId) {
  const room = rooms.get(instanceId);
  if (!room || room.activeDuck) return;
  const ioRoom = io.sockets.adapter.rooms.get(instanceId);
  if (!ioRoom || ioRoom.size === 0) return;

  const type = pickDuck();
  const duck = {
    id:        Math.random().toString(36).slice(2, 10),
    type,
    fromLeft:  Math.random() < 0.5,
    yFraction: 0.12 + Math.random() * 0.50,
    spawnTime: Date.now(),
  };
  room.activeDuck = duck;
  io.to(instanceId).emit('duck:spawn', duck);

  // Escape timer: faster ducks get less time
  const escapeMs = Math.round(5000 / type.speed);
  room.escapeTimer = setTimeout(() => {
    if (room.activeDuck?.id === duck.id) {
      room.activeDuck = null;
      io.to(instanceId).emit('duck:escaped', { duckId: duck.id });
      scheduleSpawn(instanceId);
    }
  }, escapeMs);
}

// ── HTTP ──────────────────────────────────────────────────────────────────────
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

app.get('/api/config', (_req, res) => res.json({ clientId: CLIENT_ID }));

app.post('/api/token', async (req, res) => {
  try {
    const resp = await fetch('https://discord.com/api/oauth2/token', {
      method:  'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body:    new URLSearchParams({
        client_id:     CLIENT_ID,
        client_secret: CLIENT_SECRET,
        grant_type:    'authorization_code',
        code:          req.body.code,
      }),
    });
    const data = await resp.json();
    if (!data.access_token) return res.status(400).json({ error: 'Auth failed' });
    res.json({ access_token: data.access_token });
  } catch (e) {
    res.status(500).json({ error: 'Server error' });
  }
});

// ── Socket.io ─────────────────────────────────────────────────────────────────
io.on('connection', socket => {
  let myInstance = null;
  let myUserId   = null;

  socket.on('join', ({ instanceId, userId, username }) => {
    myInstance = instanceId;
    myUserId   = userId;
    socket.join(instanceId);
    const room = getRoom(instanceId);
    if (!room.scores.has(userId)) room.scores.set(userId, { username, score: 0, kills: 0 });
    else room.scores.get(userId).username = username;

    socket.emit('state:sync', { scores: scoreObj(room.scores), activeDuck: room.activeDuck });
    io.to(instanceId).emit('scores:update', scoreObj(room.scores));

    if (room.scores.size === 1 && !room.activeDuck) scheduleSpawn(instanceId);
  });

  socket.on('duck:shoot', ({ duckId }) => {
    const room = myInstance && rooms.get(myInstance);
    if (!room || !room.activeDuck || room.activeDuck.id !== duckId) return;

    const duck = room.activeDuck;
    clearTimeout(room.escapeTimer);
    room.activeDuck = null;

    const player = room.scores.get(myUserId);
    if (player) { player.score += duck.type.points; player.kills++; }

    io.to(myInstance).emit('duck:killed', {
      duckId,
      shooterId:   myUserId,
      shooterName: player?.username || 'Unknown',
      points:      duck.type.points,
      duckType:    duck.type,
      scores:      scoreObj(room.scores),
    });
    scheduleSpawn(myInstance);
  });

  socket.on('disconnect', () => {
    if (!myInstance) return;
    const ioRoom = io.sockets.adapter.rooms.get(myInstance);
    if (!ioRoom || ioRoom.size === 0) {
      const room = rooms.get(myInstance);
      if (room) { clearTimeout(room.spawnTimer); clearTimeout(room.escapeTimer); }
      rooms.delete(myInstance);
    }
  });
});

httpServer.listen(PORT, () => {
  console.log(`🦆 Duck Hunt → http://localhost:${PORT}`);
  console.log(`   DISCORD_CLIENT_ID: ${CLIENT_ID || '(not set)'}`);
});
