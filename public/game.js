// Duck Hunt — Discord Activity client
// Uses the Discord Embedded App SDK (loaded from esm.sh CDN)
import { DiscordSDK } from 'https://esm.sh/@discord/embedded-app-sdk@1';

// ── Per duck-type animation params (bobbing difficulty) ───────────────────────
const BOB = {
  common: { freq: 1.2, amp: 18 },
  baby:   { freq: 2.0, amp: 28 },
  eagle:  { freq: 3.0, amp: 38 },
  royal:  { freq: 4.5, amp: 50 },
};

// ── DOM refs ──────────────────────────────────────────────────────────────────
const loadingEl  = document.getElementById('loading');
const appEl      = document.getElementById('app');
const duckLayer  = document.getElementById('duck-layer');
const fxCanvas   = document.getElementById('fx');
const fxCtx      = fxCanvas.getContext('2d');
const hudName    = document.getElementById('hud-name');
const hudPts     = document.getElementById('hud-pts');
const hudKills   = document.getElementById('hud-kills');
const hudStatus  = document.getElementById('hud-status');
const lbList     = document.getElementById('lb-list');
const gameArea   = document.getElementById('game-area');

function gw() { return gameArea.clientWidth; }
function gh() { return gameArea.clientHeight; }

function resizeFx() {
  fxCanvas.width  = gw();
  fxCanvas.height = gh();
}
window.addEventListener('resize', resizeFx);

// ── Discord SDK ───────────────────────────────────────────────────────────────
let sdk        = null;
let myUser     = null;
let instanceId = 'dev-room';

async function initDiscord(clientId) {
  sdk = new DiscordSDK(clientId);
  await sdk.ready();
  instanceId = sdk.instanceId;

  const { code } = await sdk.commands.authorize({
    client_id:     clientId,
    response_type: 'code',
    state:         '',
    prompt:        'none',
    scope:         ['identify'],
  });

  const resp = await fetch('/api/token', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ code }),
  });
  const { access_token } = await resp.json();
  const auth = await sdk.commands.authenticate({ access_token });
  myUser = auth.user;
}

// ── Socket.io ─────────────────────────────────────────────────────────────────
const socket = io();

// ── Active ducks: duckId → { type, fromLeft, yFraction, el, animId } ─────────
const activeDucks = new Map();

// ── My local score (mirrors server) ──────────────────────────────────────────
let myScore = 0;
let myKills = 0;

// ── Duck rendering ─────────────────────────────────────────────────────────────
function addDuck(duck) {
  if (activeDucks.has(duck.id)) return;

  const el = document.createElement('div');
  el.className = 'duck';
  el.textContent = duck.type.emoji;
  el.dataset.id = duck.id;
  duckLayer.appendChild(el);

  const bob   = BOB[duck.type.id] || BOB.common;
  const W     = gw();
  const H     = gh();
  const yBase = duck.yFraction * H;

  // Start/end x values (outside visible area)
  const startX = duck.fromLeft ? -70 : W + 70;
  const endX   = duck.fromLeft ? W + 70 : -70;

  // All ducks traverse in 5 000 ms (matching server escape timer)
  const duration = 5000;

  // Flip sprite for direction
  el.style.transform = duck.fromLeft ? 'scaleX(1)' : 'scaleX(-1)';

  const startTime = performance.now();

  function frame(now) {
    const elapsed  = now - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const x = startX + (endX - startX) * progress;
    const y = yBase  + Math.sin((elapsed / 1000) * bob.freq * Math.PI * 2) * bob.amp;

    el.style.left = x + 'px';
    el.style.top  = y + 'px';

    if (progress < 1) {
      const id = requestAnimationFrame(frame);
      const entry = activeDucks.get(duck.id);
      if (entry) entry.animId = id;
    }
  }

  const animId = requestAnimationFrame(frame);
  activeDucks.set(duck.id, { ...duck, el, animId });

  // Click / tap to shoot
  function shoot(e) {
    e.stopPropagation();
    socket.emit('duck:shoot', { duckId: duck.id });
  }
  el.addEventListener('click',    shoot);
  el.addEventListener('touchend', shoot, { passive: false });
}

function removeDuck(duckId) {
  const entry = activeDucks.get(duckId);
  if (!entry) return;
  cancelAnimationFrame(entry.animId);
  entry.el.remove();
  activeDucks.delete(duckId);
}

// ── Canvas BANG effect ────────────────────────────────────────────────────────
function bang(cx, cy) {
  const t0 = performance.now();
  const particles = Array.from({ length: 14 }, () => ({
    x: cx, y: cy,
    vx: (Math.random() - 0.5) * 9,
    vy: (Math.random() - 0.5) * 9,
    life: 1,
    r: 3 + Math.random() * 5,
    hue: Math.random() * 60 + 15,
  }));

  function step(now) {
    const elapsed = now - t0;
    fxCtx.clearRect(0, 0, fxCanvas.width, fxCanvas.height);

    // BANG! text for 600 ms
    if (elapsed < 600) {
      const a = 1 - elapsed / 600;
      fxCtx.font         = 'bold 2.8rem Impact';
      fxCtx.textAlign    = 'center';
      fxCtx.lineWidth    = 4;
      fxCtx.strokeStyle  = `rgba(0,0,0,${a})`;
      fxCtx.fillStyle    = `rgba(255,220,0,${a})`;
      fxCtx.strokeText('BANG!', cx, cy - 28);
      fxCtx.fillText  ('BANG!', cx, cy - 28);
    }

    let anyAlive = false;
    for (const p of particles) {
      p.x    += p.vx;
      p.y    += p.vy;
      p.vy   += 0.18;
      p.life -= 0.028;
      if (p.life > 0) {
        anyAlive = true;
        fxCtx.beginPath();
        fxCtx.arc(p.x, p.y, p.r * p.life, 0, Math.PI * 2);
        fxCtx.globalAlpha = p.life;
        fxCtx.fillStyle   = `hsl(${p.hue},100%,60%)`;
        fxCtx.fill();
        fxCtx.globalAlpha = 1;
      }
    }

    if (anyAlive || elapsed < 600) requestAnimationFrame(step);
    else fxCtx.clearRect(0, 0, fxCanvas.width, fxCanvas.height);
  }
  requestAnimationFrame(step);
}

// ── Floating score popup ──────────────────────────────────────────────────────
function popup(x, y, text, color, size = '1.5rem') {
  const el = document.createElement('div');
  el.className   = 'popup';
  el.textContent = text;
  el.style.left      = x + 'px';
  el.style.top       = y + 'px';
  el.style.color     = color;
  el.style.fontSize  = size;
  gameArea.appendChild(el);
  setTimeout(() => el.remove(), 1300);
}

function escapedPopup(duckType) {
  const el = document.createElement('div');
  el.className   = 'popup-escaped';
  el.textContent = `${duckType.emoji} Got away!`;
  el.style.left  = (gw() / 2 - 60) + 'px';
  el.style.top   = (gh() * 0.38) + 'px';
  gameArea.appendChild(el);
  setTimeout(() => el.remove(), 1500);
}

// ── HUD helpers ───────────────────────────────────────────────────────────────
function setStatus(text, highlight = false) {
  hudStatus.textContent = text;
  hudStatus.classList.toggle('highlight', highlight);
}

function updateMyHud() {
  hudPts.textContent   = myScore + ' pts';
  hudKills.textContent = myKills + ' kills';
}

// ── Leaderboard ───────────────────────────────────────────────────────────────
function renderLB(scores) {
  const sorted = Object.entries(scores).sort((a, b) => b[1].score - a[1].score).slice(0, 10);
  const medals = ['🥇', '🥈', '🥉'];

  lbList.innerHTML = '';
  sorted.forEach(([uid, data], i) => {
    const row   = document.createElement('div');
    row.className = 'lb-row' + (uid === myUser?.id ? ' me' : '');

    const rank  = document.createElement('span');
    rank.className = 'lb-rank' + (i < 3 ? ` g${i + 1}` : '');
    rank.textContent = medals[i] ?? `#${i + 1}`;

    const name  = document.createElement('span');
    name.className   = 'lb-name';
    name.textContent = data.username;

    const score = document.createElement('span');
    score.className   = 'lb-score';
    score.textContent = data.score + ' pts';

    row.append(rank, name, score);
    lbList.appendChild(row);
  });
}

// ── Socket events ─────────────────────────────────────────────────────────────
socket.on('state:sync', ({ scores, activeDuck }) => {
  renderLB(scores);
  if (activeDuck) {
    addDuck(activeDuck);
    setStatus(`🦆 A ${activeDuck.type.name} is here — click it!`, true);
  }
});

socket.on('scores:update', renderLB);

socket.on('duck:spawn', (duck) => {
  addDuck(duck);
  setStatus(`🦆 A ${duck.type.name} appeared — click it!`, true);
});

socket.on('duck:killed', ({ duckId, shooterId, shooterName, points, duckType, scores }) => {
  const entry = activeDucks.get(duckId);
  if (entry) {
    const rect    = entry.el.getBoundingClientRect();
    const gRect   = gameArea.getBoundingClientRect();
    const cx      = rect.left - gRect.left + rect.width  / 2;
    const cy      = rect.top  - gRect.top  + rect.height / 2;
    bang(cx, cy);
    popup(cx - 25, cy - 50, `+${points}`, '#FFD700', '1.6rem');
  }

  removeDuck(duckId);
  renderLB(scores);

  if (shooterId === myUser?.id) {
    myScore += points;
    myKills += 1;
    updateMyHud();
    setStatus(`🎯 You bagged the ${duckType.name}! +${points} pts`, true);
  } else {
    setStatus(`💨 ${shooterName} got the ${duckType.name}! (+${points})`, false);
  }

  setTimeout(() => setStatus('Waiting for the next duck…'), 3000);
});

socket.on('duck:escaped', ({ duckId }) => {
  const entry = activeDucks.get(duckId);
  if (entry) escapedPopup(entry.type);
  removeDuck(duckId);
  setStatus('🌊 The duck got away!', false);
  setTimeout(() => setStatus('Waiting for the next duck…'), 2500);
});

// ── Main entry point ──────────────────────────────────────────────────────────
async function main() {
  // Fetch client ID from server
  const { clientId } = await fetch('/api/config').then(r => r.json());

  try {
    await initDiscord(clientId);
  } catch (err) {
    // Fallback for local development (no Discord iframe)
    console.warn('Discord SDK unavailable — running in dev mode:', err.message);
    myUser     = { id: 'dev-' + Math.random().toString(36).slice(2, 8), username: 'Dev Player' };
    instanceId = 'dev-room';
  }

  // Show game
  loadingEl.hidden = true;
  appEl.hidden     = false;
  resizeFx();

  hudName.textContent = myUser.username;
  updateMyHud();
  setStatus('Waiting for the first duck…');

  // Join the Socket.io room for this activity instance
  socket.emit('join', {
    instanceId,
    userId:   myUser.id,
    username: myUser.username,
  });
}

main().catch(err => {
  console.error('Fatal init error:', err);
  document.getElementById('loading').innerHTML =
    `<p style="color:#f88">Failed to load: ${err.message}</p>`;
});
