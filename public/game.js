// Duck Hunt — Discord Activity
// Visual game: ducks fly across the screen, click to shoot, live leaderboard
import { DiscordSDK } from 'https://esm.sh/@discord/embedded-app-sdk@1';

// ── Bob params per duck type (higher = harder to click) ───────────────────────
const BOB = {
  common: { freq: 1.0, amp: 16 },
  baby:   { freq: 2.0, amp: 26 },
  eagle:  { freq: 3.2, amp: 40 },
  royal:  { freq: 5.0, amp: 55 },
};

// ── DOM ───────────────────────────────────────────────────────────────────────
const $  = id => document.getElementById(id);
const world    = $('world');
const duckLayer= $('ducks');
const fxCanvas = $('fx');
const fxCtx    = fxCanvas.getContext('2d');

function W() { return world.clientWidth;  }
function H() { return world.clientHeight; }
function resizeFx() { fxCanvas.width = W(); fxCanvas.height = H(); }
window.addEventListener('resize', resizeFx);

// ── Discord SDK ───────────────────────────────────────────────────────────────
let sdk = null, me = null, instanceId = 'dev';

async function discordInit(clientId) {
  sdk = new DiscordSDK(clientId);
  await sdk.ready();
  instanceId = sdk.instanceId;

  const { code } = await sdk.commands.authorize({
    client_id: clientId, response_type: 'code',
    state: '', prompt: 'none', scope: ['identify'],
  });
  const { access_token } = await fetch('/api/token', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code }),
  }).then(r => r.json());

  const auth = await sdk.commands.authenticate({ access_token });
  me = auth.user;
}

// ── Socket ────────────────────────────────────────────────────────────────────
const socket = io();

// ── Active ducks: id → { type, fromLeft, yFraction, el, rafId } ──────────────
const ducks = new Map();

let myScore = 0, myKills = 0;

// ── Duck animation ────────────────────────────────────────────────────────────
function addDuck(duck) {
  if (ducks.has(duck.id)) return;

  const el = document.createElement('div');
  el.className   = 'duck';
  el.textContent = duck.type.emoji;
  duckLayer.appendChild(el);

  const bob  = BOB[duck.type.id] || BOB.common;
  const gw   = W(), gh = H();
  // Travel duration = 5000ms / speed  (faster ducks cross the screen quicker)
  const dur  = 5000 / duck.type.speed;
  const sx   = duck.fromLeft ? -80  : gw + 80;
  const ex   = duck.fromLeft ? gw + 80 : -80;
  const yMid = duck.yFraction * gh;

  el.style.transform = duck.fromLeft ? 'scaleX(1)' : 'scaleX(-1)';

  const t0 = performance.now();

  function frame(now) {
    const p = Math.min((now - t0) / dur, 1);
    const x = sx + (ex - sx) * p;
    const y = yMid + Math.sin((now / 1000) * bob.freq * Math.PI * 2) * bob.amp;
    el.style.left = x + 'px';
    el.style.top  = y + 'px';
    if (p < 1) {
      const entry = ducks.get(duck.id);
      if (entry) entry.rafId = requestAnimationFrame(frame);
    }
  }

  const rafId = requestAnimationFrame(frame);

  function shoot(e) { e.stopPropagation(); socket.emit('duck:shoot', { duckId: duck.id }); }
  el.addEventListener('click',    shoot);
  el.addEventListener('touchend', shoot, { passive: false });

  ducks.set(duck.id, { ...duck, el, rafId });
}

function removeDuck(id) {
  const d = ducks.get(id);
  if (!d) return;
  cancelAnimationFrame(d.rafId);
  d.el.remove();
  ducks.delete(id);
}

// ── Canvas BANG effect ────────────────────────────────────────────────────────
function bang(cx, cy) {
  const t0 = performance.now();
  const parts = Array.from({ length: 16 }, () => ({
    x: cx, y: cy,
    vx: (Math.random() - 0.5) * 10,
    vy: (Math.random() - 0.5) * 10,
    life: 1,
    r: 3 + Math.random() * 5,
    hue: 15 + Math.random() * 55,
  }));

  function draw(now) {
    const t = now - t0;
    fxCtx.clearRect(0, 0, fxCanvas.width, fxCanvas.height);

    if (t < 700) {
      const a = 1 - t / 700;
      fxCtx.save();
      fxCtx.font         = 'bold 3rem Impact';
      fxCtx.textAlign    = 'center';
      fxCtx.lineWidth    = 5;
      fxCtx.strokeStyle  = `rgba(0,0,0,${a})`;
      fxCtx.fillStyle    = `rgba(255,220,0,${a})`;
      fxCtx.strokeText('BANG!', cx, cy - 24);
      fxCtx.fillText  ('BANG!', cx, cy - 24);
      fxCtx.restore();
    }

    let alive = false;
    for (const p of parts) {
      p.x += p.vx; p.y += p.vy; p.vy += 0.2; p.life -= 0.026;
      if (p.life > 0) {
        alive = true;
        fxCtx.beginPath();
        fxCtx.arc(p.x, p.y, p.r * p.life, 0, Math.PI * 2);
        fxCtx.globalAlpha = p.life;
        fxCtx.fillStyle   = `hsl(${p.hue},100%,58%)`;
        fxCtx.fill();
        fxCtx.globalAlpha = 1;
      }
    }
    if (alive || t < 700) requestAnimationFrame(draw);
    else fxCtx.clearRect(0, 0, fxCanvas.width, fxCanvas.height);
  }
  requestAnimationFrame(draw);
}

// ── Floating text ─────────────────────────────────────────────────────────────
function floatText(x, y, text, cls) {
  const el = document.createElement('div');
  el.className   = cls;
  el.textContent = text;
  el.style.left  = x + 'px';
  el.style.top   = y + 'px';
  world.appendChild(el);
  setTimeout(() => el.remove(), 1400);
}

// ── HUD / status ──────────────────────────────────────────────────────────────
function setMsg(text, highlight = false) {
  const el = $('hud-msg');
  el.textContent = text;
  el.classList.toggle('pop', highlight);
}

function updateHud() {
  $('hud-score').textContent = myScore + ' pts';
  $('hud-kills').textContent = myKills + ' 🦆';
}

// ── Leaderboard ───────────────────────────────────────────────────────────────
const MEDALS = ['🥇', '🥈', '🥉'];

function renderLB(scores) {
  const sorted = Object.entries(scores).sort((a, b) => b[1].score - a[1].score).slice(0, 10);
  const lb = $('lb');
  lb.innerHTML = '';
  sorted.forEach(([uid, d], i) => {
    const row = document.createElement('div');
    row.className = 'row' + (uid === me?.id ? ' me' : '');
    row.innerHTML = `
      <span class="row-rank ${i === 0 ? 'g1' : i === 1 ? 'g2' : i === 2 ? 'g3' : ''}">${MEDALS[i] ?? '#' + (i + 1)}</span>
      <span class="row-name">${d.username}</span>
      <span class="row-score">${d.score}</span>
    `;
    lb.appendChild(row);
  });
}

// ── Socket events ─────────────────────────────────────────────────────────────
socket.on('state:sync', ({ scores, activeDuck }) => {
  renderLB(scores);
  if (activeDuck) { addDuck(activeDuck); setMsg(`🦆 A ${activeDuck.type.name} is here — click it!`, true); }
});

socket.on('scores:update', renderLB);

socket.on('duck:spawn', duck => {
  addDuck(duck);
  setMsg(`🦆 ${duck.type.emoji} A ${duck.type.name} appeared! Click it!`, true);
  setTimeout(() => setMsg('Waiting for ducks…'), 3000);
});

socket.on('duck:killed', ({ duckId, shooterId, shooterName, points, duckType, scores }) => {
  const entry = ducks.get(duckId);
  if (entry) {
    const rect = entry.el.getBoundingClientRect();
    const wr   = world.getBoundingClientRect();
    const cx   = rect.left - wr.left + rect.width  / 2;
    const cy   = rect.top  - wr.top  + rect.height / 2;
    bang(cx, cy);
    floatText(cx - 20, cy - 50, `+${points}`, 'pts-popup');
  }
  removeDuck(duckId);
  renderLB(scores);

  if (shooterId === me?.id) {
    myScore += points; myKills++;
    updateHud();
    setMsg(`🎯 You got the ${duckType.name}! +${points} pts`, true);
  } else {
    setMsg(`💨 ${shooterName} got the ${duckType.name}! (+${points})`, false);
  }
  setTimeout(() => setMsg('Waiting for ducks…'), 3500);
});

socket.on('duck:escaped', ({ duckId }) => {
  const entry = ducks.get(duckId);
  if (entry) {
    const rect = entry.el.getBoundingClientRect();
    const wr   = world.getBoundingClientRect();
    floatText(rect.left - wr.left, rect.top - wr.top - 20, `${entry.type.emoji} Got away!`, 'miss-popup');
  }
  removeDuck(duckId);
  setMsg('🌊 The duck got away!', false);
  setTimeout(() => setMsg('Waiting for ducks…'), 2500);
});

// ── Boot ──────────────────────────────────────────────────────────────────────
async function main() {
  const { clientId } = await fetch('/api/config').then(r => r.json());

  try {
    await discordInit(clientId);
  } catch (err) {
    console.warn('Discord SDK unavailable (dev mode):', err.message);
    me         = { id: 'dev-' + Math.random().toString(36).slice(2, 7), username: 'Dev Player' };
    instanceId = 'dev-room';
  }

  $('loading').hidden = true;
  $('app').hidden     = false;
  resizeFx();

  $('hud-name').textContent = me.username;
  updateHud();

  socket.emit('join', { instanceId, userId: me.id, username: me.username });
}

main().catch(err => {
  $('loading').innerHTML = `<p style="color:#f66;font-size:1.1rem">Error: ${err.message}</p>`;
});
