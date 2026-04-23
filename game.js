// ============================================================================
// TEKKEN MINI — game.js
// Ported from tekken_mini.ino (Adafruit Metro RP2040)
// Controls: P1 = WASD + F/G/H  |  P2 = Arrows + J/K/L
// ============================================================================

// ============================================================================
// CONSTANTS — mirrored from Arduino source
// ============================================================================
const ROUNDS_TO_WIN    = 2;
const MOVE_SPEED       = 200;    // px/sec (scaled up from 65 for larger screen)
const JUMP_VEL         = -520;   // px/sec upward
const GRAVITY          = 1300;   // px/sec²
const KNOCKBACK_SPD    = 160;    // px/sec horizontal on hit

const SPRITE_SCALE      = 2;     // single knob for fighter/body size
const PLAYER_W          = Math.round(28 * SPRITE_SCALE);
const PLAYER_H          = Math.round(56 * SPRITE_SCALE);
const PLAYER_CROUCH_H   = Math.round(34 * SPRITE_SCALE);

const LIGHT_DMG        = 8;
const LIGHT_RANGE      = Math.round(56 * SPRITE_SCALE);
const LIGHT_CD_MS      = 400;
const LIGHT_ACTIVE_MS  = 120;

const HEAVY_DMG        = 22;
const HEAVY_RANGE      = Math.round(80 * SPRITE_SCALE);
const HEAVY_CD_MS      = 1050;
const HEAVY_WINDUP_MS  = 160;
const HEAVY_ACTIVE_MS  = 200;

const BLOCK_DMG_MULT   = 0.2;   // 20% damage gets through a block

const HITSTOP_LIGHT_MS = 45;
const HITSTOP_HEAVY_MS = 75;

const HIT_FLASH_MS     = 200;
const ROUND_END_DELAY  = 2800;
const COUNTDOWN_STEP   = 700;

// Colors (canvas fillStyle strings)
const C_BG       = '#050a14';
const C_FLOOR    = '#1a2a1a';
const C_FLOOR_LN = '#3a6b3a';
const C_P1       = '#2266ff';
const C_P1_ATK   = '#66aaff';
const C_P2       = '#ff2222';
const C_P2_ATK   = '#ff8866';
const C_GRAY     = '#556677';
const C_WHITE    = '#ffffff';
const C_YELLOW   = '#ffe000';
const C_RED      = '#ff2222';
const C_GREEN    = '#00ee44';

const CHARACTERS = [
  { name: 'BRICK',  portrait: 'WALL BREAKER', color: '#2266ff', atkColor: '#66aaff', spriteId: 'brick' },
  { name: 'CITRON', portrait: 'FLASH SLICE',  color: '#ff2f2f', atkColor: '#ff8888', spriteId: 'citron' },
  { name: 'GREB',   portrait: 'DARK RUSH',    color: '#2ecf53', atkColor: '#84ee9d', spriteId: 'greb' },
  { name: 'SPLINT', portrait: 'QUICK JACKAL', color: '#ffcf2f', atkColor: '#ffe98a', spriteId: 'splint' },
];
const spriteCache = {};

// ============================================================================
// GAME STATE ENUM
// ============================================================================
const STATE = { MENU: 0, COUNTDOWN: 1, PLAYING: 2, ROUND_END: 3, GAME_OVER: 4 };

let gameState = STATE.MENU;
let menuPhase = 'title'; // title | character_select
let menuReadyAt = 0;
const menuSel = { 1: 0, 2: 1 };
const menuLock = { 1: false, 2: false };
const menuPrev = {
  1: { left: false, right: false, light: false, heavy: false, block: false },
  2: { left: false, right: false, light: false, heavy: false, block: false },
};
let roundNum  = 1;
let p1, p2;
let hitstopEnd = 0;
let roundEndAt = 0;
let roundEndMsg = '';
let lastMs  = 0;
let cdStep  = 0;
let cdNext  = 0;
let animId  = null;
let frameCount = 0;
let startInputPrev = false;

// Canvas & layout (set by resizeCanvas)
const canvas = document.getElementById('game-canvas');
const ctx    = canvas.getContext('2d');
let CW, CH, FLOOR_Y, FLOOR_THICK, START_Y;

// ============================================================================
// INPUT STATE
// ============================================================================
const inp = {
  1: { left: false, right: false, up: false, down: false, light: false, heavy: false, block: false },
  2: { left: false, right: false, up: false, down: false, light: false, heavy: false, block: false },
};

// Keyboard mapping: P1 = WASD + F G H  |  P2 = Arrows + J K L
const keyMap = {
  'a': '1-left',  'd': '1-right',  'w': '1-up',  's': '1-down',
  'f': '1-light', 'g': '1-heavy',  'h': '1-block',
  'ArrowLeft': '2-left', 'ArrowRight': '2-right',
  'ArrowUp':   '2-up',   'ArrowDown':  '2-down',
  'j': '2-light', 'k': '2-heavy',  'l': '2-block',
};

document.addEventListener('keydown', e => {
  const m = keyMap[e.key];
  if (m) { const [pl, a] = m.split('-'); inp[pl][a] = true; e.preventDefault(); }
});
document.addEventListener('keydown', e => {
  if (e.key !== 'Enter' || e.repeat) return;
  if ((gameState === STATE.MENU && menuPhase === 'title') || gameState === STATE.GAME_OVER) {
    overlayBtnPressed();
    e.preventDefault();
  }
});
document.addEventListener('keyup', e => {
  const m = keyMap[e.key];
  if (m) { const [pl, a] = m.split('-'); inp[pl][a] = false; }
});

// Touch button handlers (called from HTML via inline events)
function dpadPress(e, pl, dir)   { e.preventDefault(); inp[pl][dir]  = true;  e.currentTarget.classList.add('pressed'); }
function dpadRelease(e, pl, dir) { e.preventDefault(); inp[pl][dir]  = false; e.currentTarget.classList.remove('pressed'); }
function atkPress(e, pl, act)    { e.preventDefault(); inp[pl][act]  = true;  e.currentTarget.classList.add('pressed'); }
function atkRelease(e, pl, act)  { e.preventDefault(); inp[pl][act]  = false; e.currentTarget.classList.remove('pressed'); }

// Prevent page scroll during touch gameplay
document.addEventListener('touchmove', e => e.preventDefault(), { passive: false });

// ============================================================================
// PLAYER FACTORY
// ============================================================================
function makePlayer(x, y, facingRight, color, atkColor) {
  return {
    x, y, vx: 0, vy: 0,
    onGround: true, facingRight,
    health: 100, roundWins: 0, isKO: false,
    // action: idle | walk | jump | crouch | light | heavy | block | ko
    action: 'idle',
    lightCdEnd: 0, heavyCdEnd: 0,
    attackEnd: 0, windupEnd: 0,
    attackActive: false, hitRegistered: false, currentAtk: 0,
    flashEnd: 0,
    color, atkColor,
  };
}

function resetPlayerForRound(p, x, y, facingRight) {
  p.x = x; p.y = y;
  p.vx = 0; p.vy = 0;
  p.onGround = true; p.facingRight = facingRight;
  p.health = 100; p.isKO = false;
  p.action = 'idle';
  p.lightCdEnd = 0; p.heavyCdEnd = 0;
  p.attackEnd = 0; p.windupEnd = 0;
  p.attackActive = false; p.hitRegistered = false; p.currentAtk = 0;
  p.flashEnd = 0;
}

function applyMenuCharacters() {
  const c1 = CHARACTERS[menuSel[1]];
  const c2 = CHARACTERS[menuSel[2]];
  p1.color = c1.color;
  p1.atkColor = c1.atkColor;
  p1.charId = c1.spriteId;
  p2.color = c2.color;
  p2.atkColor = c2.atkColor;
  p2.charId = c2.spriteId;
}

function getSpriteImage(charId, spriteName) {
  if (!charId) return null;
  const key = `${charId}/${spriteName}`;
  if (!spriteCache[key]) {
    const img = new Image();
    img.src = `assets/fighters/${charId}/${spriteName}.png`;
    spriteCache[key] = img;
  }
  return spriteCache[key];
}

function getPlayerSpriteName(p) {
  if (p.action === 'light') return 'light';
  if (p.action === 'heavy') return 'heavy';
  if (p.action === 'block') return 'block';
  if (p.action === 'crouch') return 'crouch';
  if (p.action === 'jump') return 'jump';
  if (p.action === 'ko') return 'ko';
  if (p.action === 'walk') return (Math.floor(frameCount / 8) % 2 === 0) ? 'walk_0' : 'walk_1';
  return 'idle';
}

// ============================================================================
// GEOMETRY — axis-aligned bounding boxes
// ============================================================================
function playerRect(p) {
  const h = (p.action === 'crouch') ? PLAYER_CROUCH_H : PLAYER_H;
  const offset = PLAYER_H - h;       // anchor feet to floor
  return { x: p.x, y: p.y + offset, w: PLAYER_W, h };
}

function attackRect(p) {
  if (!p.attackActive) return null;
  let reach = p.currentAtk === 1 ? LIGHT_RANGE : HEAVY_RANGE;
  // Align left-side (Player 2 side) heavy gameplay range with perceived UI range.
  if (p.currentAtk === 2 && !p.facingRight) {
    reach = Math.floor(reach * 0.82);
  }
  const ax = p.facingRight ? p.x + PLAYER_W : p.x - reach;
  return { x: ax, y: p.y + 10, w: reach, h: PLAYER_H - 20 };
}

function rectsOverlap(a, b) {
  return a.x < b.x + b.w && a.x + a.w > b.x &&
         a.y < b.y + b.h && a.y + a.h > b.y;
}

// ============================================================================
// PHYSICS
// ============================================================================
function updatePhysics(p, dt) {
  if (!p.onGround) p.vy += GRAVITY * dt;
  p.x += p.vx * dt;
  p.y += p.vy * dt;

  // Floor collision
  const floorTop = FLOOR_Y - PLAYER_H;
  if (p.y >= floorTop) {
    p.y = floorTop;
    p.vy = 0;
    if (!p.onGround) {
      p.onGround = true;
      if (p.action === 'jump') p.action = 'idle';
    }
  }

  // Screen edge clamp
  if (p.x < 0)             p.x = 0;
  if (p.x > CW - PLAYER_W) p.x = CW - PLAYER_W;
}

// ============================================================================
// ATTACK WINDOW (millis-based timers, matching Arduino logic)
// ============================================================================
function updateAttackWindow(p) {
  if (p.action !== 'light' && p.action !== 'heavy') return;
  const now = performance.now();

  // Heavy windup done → activate hitbox
  if (p.windupEnd && now >= p.windupEnd) {
    p.windupEnd = 0;
    p.attackActive = true;
    p.hitRegistered = false;
  }

  // Active window expired → return to idle
  if (p.attackEnd && now >= p.attackEnd) {
    p.attackEnd = 0;
    p.attackActive = false;
    p.currentAtk = 0;
    p.action = 'idle';
  }
}

function startAttack(p, type) {
  const now = performance.now();
  p.vx = 0;
  p.currentAtk = type;
  p.hitRegistered = false;

  if (type === 1) {                       // Light: instant hitbox
    p.action = 'light';
    p.attackActive = true;
    p.windupEnd = 0;
    p.attackEnd = now + LIGHT_ACTIVE_MS;
    p.lightCdEnd = now + LIGHT_CD_MS;
  } else {                                // Heavy: windup → hitbox
    p.action = 'heavy';
    p.attackActive = false;
    p.windupEnd = now + HEAVY_WINDUP_MS;
    p.attackEnd = now + HEAVY_WINDUP_MS + HEAVY_ACTIVE_MS;
    p.heavyCdEnd = now + HEAVY_CD_MS;
  }
}

// ============================================================================
// INPUT → ACTION STATE (direct port of handle_input from .ino)
// ============================================================================
function handleInput(p, i) {
  if (p.isKO) return;
  const now = performance.now();
  const inAtk = p.action === 'light' || p.action === 'heavy';

  if (!inAtk) {
    // Horizontal movement
    if (i.left)        p.vx = -MOVE_SPEED;
    else if (i.right)  p.vx =  MOVE_SPEED;
    else               p.vx = 0;

    // Jump (ground only)
    if (i.up && p.onGround) {
      p.vy = JUMP_VEL;
      p.onGround = false;
      p.action = 'jump';
    }

    // Crouch (ground only)
    if (i.down && p.onGround) {
      p.vx = 0;
      p.action = 'crouch';
    } else if (!i.down && p.action === 'crouch') {
      p.action = 'idle';
    }

    // Block (ground only, held)
    if (i.block && p.onGround) {
      p.vx = 0;
      p.action = 'block';
    } else if (!i.block && p.action === 'block') {
      p.action = 'idle';
    }

    // Attacks (cooldown-gated)
    if (i.light && now >= p.lightCdEnd) {
      startAttack(p, 1);
    } else if (i.heavy && now >= p.heavyCdEnd) {
      startAttack(p, 2);
    }
  }

  // Sync idle/walk/jump label from physics state
  if (p.onGround && !['crouch', 'block', 'light', 'heavy', 'ko'].includes(p.action))
    p.action = p.vx !== 0 ? 'walk' : 'idle';
  if (!p.onGround && !['light', 'heavy', 'ko'].includes(p.action))
    p.action = 'jump';
}

function autoFace(p, opp) {
  p.facingRight = (opp.x + PLAYER_W / 2) > (p.x + PLAYER_W / 2);
}

// ============================================================================
// DAMAGE & HIT RESOLUTION
// ============================================================================
function takeDamage(defender, damage, kbDir) {
  if (defender.action === 'block') {
    damage = Math.floor(damage * BLOCK_DMG_MULT);
    defender.vx = kbDir * KNOCKBACK_SPD * 0.35;
  } else {
    defender.vx = kbDir * KNOCKBACK_SPD;
  }

  defender.health -= damage;
  if (defender.health < 0) defender.health = 0;
  defender.flashEnd = performance.now() + HIT_FLASH_MS;

  if (defender.health === 0) {
    defender.isKO    = true;
    defender.action  = 'ko';
    defender.vy      = -220;   // small upward pop on KO
    defender.vx      = 0;
  }
}

// Returns: 0 = miss | 1 = hit | 2 = blocked
function checkAndResolveHit(attacker, defender) {
  if (!attacker.attackActive || attacker.hitRegistered) return 0;
  const atk = attackRect(attacker);
  if (!atk) return 0;
  const def = playerRect(defender);
  if (!rectsOverlap(atk, def)) return 0;

  const isHeavy    = attacker.currentAtk === 2;
  const wasBlocking = defender.action === 'block';
  const kbDir      = attacker.facingRight ? 1 : -1;

  takeDamage(defender, isHeavy ? HEAVY_DMG : LIGHT_DMG, kbDir);
  attacker.hitRegistered = true;
  return wasBlocking ? 2 : 1;
}

// ============================================================================
// AUDIO (Web Audio API — replaces tone() / PAM8302)
// ============================================================================
let audioCtx = null;

function ensureAudio() {
  if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  if (audioCtx.state === 'suspended') audioCtx.resume();
}

function playTone(freq, dur, type = 'square', vol = 0.15) {
  try {
    ensureAudio();
    const osc  = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = type;
    osc.frequency.value = freq;
    gain.gain.setValueAtTime(vol, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + dur / 1000);
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.start();
    osc.stop(audioCtx.currentTime + dur / 1000);
  } catch (e) { /* silence audio errors */ }
}

const sndLight = () => playTone(880,  40);
const sndHeavy = () => playTone(440,  85);
const sndBlock = () => playTone(1400, 25);
const sndKO    = () => playTone(180, 550, 'sawtooth', 0.25);
const sndFight = () => playTone(660, 100, 'square',   0.2);
const sndBeep  = () => playTone(880,  50);

// ============================================================================
// RENDERING
// ============================================================================
function drawBackground() {
  // Sky
  ctx.fillStyle = C_BG;
  ctx.fillRect(0, 0, CW, CH);

  // Vertical grid lines (arena depth feel)
  ctx.strokeStyle = 'rgba(50,80,120,0.12)';
  ctx.lineWidth = 1;
  for (let x = 0; x < CW; x += 40) {
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, FLOOR_Y); ctx.stroke();
  }

  // Floor surface
  ctx.fillStyle = C_FLOOR;
  ctx.fillRect(0, FLOOR_Y, CW, FLOOR_THICK);

  // Floor edge highlight
  ctx.strokeStyle = C_FLOOR_LN;
  ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(0, FLOOR_Y); ctx.lineTo(CW, FLOOR_Y); ctx.stroke();

  // Floor grid lines
  ctx.strokeStyle = 'rgba(50,100,50,0.3)';
  ctx.lineWidth = 1;
  for (let x = 0; x < CW; x += 40) {
    ctx.beginPath(); ctx.moveTo(x, FLOOR_Y); ctx.lineTo(x, FLOOR_Y + FLOOR_THICK); ctx.stroke();
  }
}

function drawStartScreenBackground() {
  const t = performance.now() * 0.001;
  const grad = ctx.createLinearGradient(0, 0, 0, CH);
  grad.addColorStop(0, '#040812');
  grad.addColorStop(0.55, '#09162b');
  grad.addColorStop(1, '#060a14');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, CW, CH);

  // Neon skyline bars
  for (let i = 0; i < 18; i++) {
    const w = 18 + (i % 4) * 8;
    const h = 40 + ((i * 37) % 130);
    const x = (i * 57 + Math.sin(t + i) * 6) % (CW + 60) - 30;
    const y = FLOOR_Y - h;
    ctx.fillStyle = `rgba(70,180,255,${0.07 + (i % 3) * 0.03})`;
    ctx.fillRect(x, y, w, h);
  }

  // Horizon glow
  const horizon = ctx.createLinearGradient(0, FLOOR_Y - 40, 0, FLOOR_Y + 35);
  horizon.addColorStop(0, 'rgba(80,160,255,0)');
  horizon.addColorStop(0.5, 'rgba(80,160,255,0.22)');
  horizon.addColorStop(1, 'rgba(80,160,255,0)');
  ctx.fillStyle = horizon;
  ctx.fillRect(0, FLOOR_Y - 40, CW, 75);

  // Sweep lines
  ctx.strokeStyle = 'rgba(120,200,255,0.1)';
  ctx.lineWidth = 1;
  for (let y = 0; y < FLOOR_Y; y += 24) {
    ctx.beginPath();
    ctx.moveTo(0, y + Math.sin(t * 2 + y * 0.05) * 1.5);
    ctx.lineTo(CW, y + Math.sin(t * 2 + y * 0.05) * 1.5);
    ctx.stroke();
  }

  // Keep stage floor consistent.
  ctx.fillStyle = C_FLOOR;
  ctx.fillRect(0, FLOOR_Y, CW, FLOOR_THICK);
  ctx.strokeStyle = C_FLOOR_LN;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(0, FLOOR_Y);
  ctx.lineTo(CW, FLOOR_Y);
  ctx.stroke();
}

function drawLoadingBackground() {
  const t = performance.now() * 0.001;
  const grad = ctx.createLinearGradient(0, 0, 0, CH);
  grad.addColorStop(0, '#090611');
  grad.addColorStop(0.6, '#120d1f');
  grad.addColorStop(1, '#080b15');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, CW, CH);

  // Rotating ring scanner behind countdown text.
  ctx.save();
  ctx.translate(CW * 0.5, CH * 0.42);
  ctx.rotate(t * 0.65);
  for (let i = 0; i < 6; i++) {
    ctx.rotate(Math.PI / 3);
    ctx.strokeStyle = `rgba(255,80,180,${0.08 + i * 0.02})`;
    ctx.lineWidth = 5 - i * 0.6;
    ctx.beginPath();
    ctx.arc(0, 0, 70 + i * 16, -0.75, -0.15);
    ctx.stroke();
  }
  ctx.restore();

  // Vertical loading beams
  for (let i = 0; i < 10; i++) {
    const x = (i + 1) * (CW / 11);
    const pulse = 0.15 + 0.12 * Math.sin(t * 3 + i);
    ctx.fillStyle = `rgba(120,90,255,${pulse})`;
    ctx.fillRect(x - 2, 0, 4, FLOOR_Y);
  }

  ctx.fillStyle = C_FLOOR;
  ctx.fillRect(0, FLOOR_Y, CW, FLOOR_THICK);
  ctx.strokeStyle = C_FLOOR_LN;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(0, FLOOR_Y);
  ctx.lineTo(CW, FLOOR_Y);
  ctx.stroke();
}

function drawFightBackground() {
  const t = performance.now() * 0.001;
  const sky = ctx.createLinearGradient(0, 0, 0, FLOOR_Y);
  sky.addColorStop(0, '#060b18');
  sky.addColorStop(0.55, '#0a1530');
  sky.addColorStop(1, '#0f1f34');
  ctx.fillStyle = sky;
  ctx.fillRect(0, 0, CW, FLOOR_Y);

  // Arena depth lines
  ctx.strokeStyle = 'rgba(80,150,220,0.14)';
  ctx.lineWidth = 1;
  const horizonY = FLOOR_Y * 0.38;
  for (let x = -CW; x <= CW * 2; x += 45) {
    ctx.beginPath();
    ctx.moveTo(CW * 0.5, horizonY);
    ctx.lineTo(x + Math.sin(t + x * 0.01) * 8, FLOOR_Y);
    ctx.stroke();
  }

  // Horizontal bands
  ctx.strokeStyle = 'rgba(80,180,255,0.09)';
  for (let y = horizonY; y < FLOOR_Y; y += 24) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(CW, y);
    ctx.stroke();
  }

  // Side light columns
  for (const side of [0.1, 0.9]) {
    const x = CW * side;
    const pulse = 0.18 + 0.12 * Math.sin(t * 3 + side * 5);
    const glow = ctx.createRadialGradient(x, FLOOR_Y - 110, 8, x, FLOOR_Y - 110, 120);
    glow.addColorStop(0, `rgba(70,220,255,${pulse})`);
    glow.addColorStop(1, 'rgba(70,220,255,0)');
    ctx.fillStyle = glow;
    ctx.fillRect(x - 120, FLOOR_Y - 230, 240, 240);
  }

  // Floor
  ctx.fillStyle = C_FLOOR;
  ctx.fillRect(0, FLOOR_Y, CW, FLOOR_THICK);
  ctx.strokeStyle = C_FLOOR_LN;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(0, FLOOR_Y);
  ctx.lineTo(CW, FLOOR_Y);
  ctx.stroke();

  // Floor grid
  ctx.strokeStyle = 'rgba(70,140,90,0.32)';
  ctx.lineWidth = 1;
  for (let x = 0; x < CW; x += 40) {
    ctx.beginPath();
    ctx.moveTo(x, FLOOR_Y);
    ctx.lineTo(x, FLOOR_Y + FLOOR_THICK);
    ctx.stroke();
  }
}

function drawPlayer(p) {
  const now = performance.now();
  const r   = playerRect(p);
  const spriteName = getPlayerSpriteName(p);
  const sprite = getSpriteImage(p.charId, spriteName);

  ctx.save();

  // Pick body color
  let col;
  if (p.isKO) {
    col = C_GRAY;
  } else if (p.flashEnd && now < p.flashEnd) {
    col = (Math.floor(now / 60) % 2 === 0) ? C_WHITE : p.color;
  } else if (p.action === 'light' || p.action === 'heavy') {
    col = p.atkColor;
  } else if (p.action === 'block') {
    col = C_GRAY;
  } else {
    col = p.color;
  }

  // Glow shadow
  ctx.shadowColor = col;
  ctx.shadowBlur  = (p.action === 'light' || p.action === 'heavy') ? 16 : 6;

  // Walk bob (subtle vertical oscillation)
  let yOff = 0;
  if (p.action === 'walk' && p.onGround) {
    yOff = Math.sin(frameCount * 0.25) * 2;
  }

  // Prefer sprite draw, fallback to rectangle body if not loaded yet
  if (sprite && sprite.complete && sprite.naturalWidth > 0) {
    if (!p.facingRight) {
      // Isolate flip transform so later FX/hitbox draws stay in world coordinates.
      ctx.save();
      ctx.translate(r.x + r.w, 0);
      ctx.scale(-1, 1);
      ctx.drawImage(sprite, 0, r.y + yOff, r.w, r.h);
      ctx.restore();
    } else {
      ctx.drawImage(sprite, r.x, r.y + yOff, r.w, r.h);
    }
  } else {
    ctx.fillStyle = col;
    ctx.fillRect(r.x, r.y + yOff, r.w, r.h);
    ctx.shadowBlur = 0;

    ctx.strokeStyle = 'rgba(255,255,255,0.5)';
    ctx.lineWidth = 1.5;
    ctx.strokeRect(r.x + 0.5, r.y + yOff + 0.5, r.w - 1, r.h - 1);

    const eyeX = p.facingRight ? r.x + r.w - 5 : r.x + 4;
    ctx.fillStyle = '#000000';
    ctx.fillRect(eyeX, r.y + yOff + 6, 3, 3);
  }
  ctx.shadowBlur = 0;

  // Block shield visual
  if (p.action === 'block') {
    ctx.strokeStyle = 'rgba(100,200,255,0.7)';
    ctx.lineWidth = 3;
    const sx = p.facingRight ? r.x - 4 : r.x + r.w + 4;
    ctx.beginPath();
    ctx.roundRect(sx - 4, r.y + 4, 12, r.h - 8, 3);
    ctx.stroke();
  }

  // Active hitbox glow
  if (p.attackActive) {
    const atk = attackRect(p);
    if (atk) {
      let drawAtk = atk;
      // Visual-only tweak: keep gameplay hitbox untouched, align Citron heavy FX to sprite.
      if (p.charId === 'citron' && p.currentAtk === 2) {
        const w = Math.floor(HEAVY_RANGE * 0.78);
        drawAtk = {
          // Anchor from body rect to keep left/right placement consistent.
          x: p.facingRight ? r.x + r.w : r.x - w,
          y: r.y + 16,
          w,
          h: PLAYER_H - 26,
        };
      }
      // Force world-space draw so hitbox FX cannot inherit sprite flip transforms.
      ctx.save();
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.fillStyle   = (p.currentAtk === 2) ? 'rgba(255,120,0,0.25)' : 'rgba(100,180,255,0.2)';
      ctx.fillRect(drawAtk.x, drawAtk.y, drawAtk.w, drawAtk.h);
      ctx.strokeStyle = (p.currentAtk === 2) ? 'rgba(255,140,0,0.7)' : 'rgba(100,200,255,0.6)';
      ctx.lineWidth   = 1.5;
      ctx.strokeRect(drawAtk.x, drawAtk.y, drawAtk.w, drawAtk.h);
      ctx.restore();
    }
  }

  // Heavy windup orange glow outline
  if (p.action === 'heavy' && !p.attackActive) {
    ctx.strokeStyle = 'rgba(255,100,0,0.8)';
    ctx.lineWidth   = 3;
    ctx.strokeRect(r.x - 2, r.y + yOff - 2, r.w + 4, r.h + 4);
  }

  ctx.restore();
}

function drawMenuArt() {
  // Ghosted fighter silhouettes on the menu screen
  const c1 = CHARACTERS[menuSel[1]] || { color: C_P1 };
  const c2 = CHARACTERS[menuSel[2]] || { color: C_P2 };
  const t = performance.now() / 1000;
  ctx.save();
  ctx.globalAlpha = 0.12 + 0.04 * Math.sin(t);
  ctx.fillStyle   = c1.color;
  ctx.fillRect(CW * 0.25 - 20, FLOOR_Y - PLAYER_H - 4, PLAYER_W + 8, PLAYER_H + 4);
  ctx.fillStyle   = c2.color;
  ctx.fillRect(CW * 0.70 - 20, FLOOR_Y - PLAYER_H - 4, PLAYER_W + 8, PLAYER_H + 4);
  ctx.globalAlpha = 1;
  ctx.restore();
}

// ============================================================================
// HUD DOM UPDATES
// ============================================================================
function updateHUD() {
  const p1Bar = document.getElementById('p1-hp-bar');
  const p2Bar = document.getElementById('p2-hp-bar');

  p1Bar.style.width      = p1.health + '%';
  p2Bar.style.width      = p2.health + '%';
  p1Bar.style.background = p1.health <= 30 ? 'var(--hp-low)' : 'var(--hp-ok)';
  p2Bar.style.background = p2.health <= 30 ? 'var(--hp-low)' : 'var(--hp-ok)';

  document.getElementById('round-label').textContent = 'RND ' + roundNum;

  for (let i = 0; i < ROUNDS_TO_WIN; i++) {
    document.getElementById('p1-pip-' + i).classList.toggle('lit', i < p1.roundWins);
    document.getElementById('p2-pip-' + i).classList.toggle('lit', i < p2.roundWins);
  }
}

// ============================================================================
// OVERLAY / COUNTDOWN HELPERS
// ============================================================================
function showOverlay(title, sub, btnText) {
  document.getElementById('overlay').classList.remove('hidden');
  const titleEl = document.getElementById('overlay-title');
  titleEl.textContent  = title;
  titleEl.style.fontSize = '';
  titleEl.style.letterSpacing = '';
  document.getElementById('overlay-sub').innerHTML      = sub;
  const btn = document.getElementById('overlay-btn');
  btn.textContent  = btnText;
  btn.style.display = 'block';
}

function hideOverlay() {
  document.getElementById('overlay').classList.add('hidden');
}

function showCountdownText(txt, color) {
  const el = document.getElementById('countdown-text');
  el.textContent  = txt;
  el.style.color  = color || C_WHITE;
  if (txt.startsWith('ROUND ')) {
    el.style.fontSize = 'clamp(44px, 12vw, 84px)';
  } else if (txt === 'FIGHT!') {
    el.style.fontSize = 'clamp(64px, 17vw, 126px)';
  } else {
    el.style.fontSize = 'clamp(60px, 18vw, 140px)';
  }
  el.style.display = 'block';
  // Re-trigger CSS animation
  el.style.animation = 'none';
  el.offsetHeight;           // force reflow
  el.style.animation = '';
}

function hideCountdownText() {
  document.getElementById('countdown-text').style.display = 'none';
}

function ensurePlayers() {
  const px1 = CW * 0.2, px2 = CW * 0.75;
  if (!p1) {
    p1 = makePlayer(px1, START_Y, true,  C_P1, C_P1_ATK);
    p2 = makePlayer(px2, START_Y, false, C_P2, C_P2_ATK);
  } else {
    p1.roundWins = 0;
    p2.roundWins = 0;
    resetPlayerForRound(p1, px1, START_Y, true);
    resetPlayerForRound(p2, px2, START_Y, false);
  }
}

function renderCharacterSelectOverlay() {
  const p1Char = CHARACTERS[menuSel[1]];
  const p2Char = CHARACTERS[menuSel[2]];
  const p1Name = p1Char.name;
  const p2Name = p2Char.name;
  const p1Status = menuLock[1] ? 'LOCKED' : 'SELECTING';
  const p2Status = menuLock[2] ? 'LOCKED' : 'SELECTING';
  const cards = CHARACTERS.map((ch, idx) => {
    const isP1 = menuSel[1] === idx;
    const isP2 = menuSel[2] === idx;
    const p1Tag = isP1 ? (menuLock[1] ? 'P1 LOCKED' : 'P1 READY') : '';
    const p2Tag = isP2 ? (menuLock[2] ? 'P2 LOCKED' : 'P2 READY') : '';
    const ring = isP1 && isP2
      ? '0 0 0 2px #2266ff, 0 0 0 5px #ff2222, 0 0 18px rgba(255,255,255,0.25)'
      : isP1
        ? '0 0 0 2px #2266ff, 0 0 14px rgba(34,102,255,0.45)'
        : isP2
          ? '0 0 0 2px #ff2222, 0 0 14px rgba(255,34,34,0.45)'
          : '0 0 0 1px rgba(255,255,255,0.14)';
    return (
      `<div style="` +
      `width:min(180px,22vw);min-width:120px;padding:10px 10px 8px;border-radius:9px;` +
      `background:linear-gradient(160deg,rgba(12,22,36,0.96),rgba(7,12,20,0.96));` +
      `box-shadow:${ring};position:relative;">` +
      `<div style="height:72px;border-radius:6px;overflow:hidden;position:relative;` +
      `background:linear-gradient(140deg,${ch.color},${ch.atkColor});">` +
      `<img src="assets/fighters/${ch.spriteId}/idle.png" alt="${ch.name}" ` +
      `style="width:100%;height:100%;object-fit:contain;image-rendering:pixelated;filter:drop-shadow(0 2px 2px rgba(0,0,0,0.5));">` +
      `<div style="position:absolute;left:0;right:0;bottom:4px;text-align:center;` +
      `font-family:'Press Start 2P',monospace;letter-spacing:1px;font-size:8px;color:#f4f8ff;">${ch.portrait}</div>` +
      `</div>` +
      `<div style="margin-top:8px;font-family:'Press Start 2P',monospace;font-size:13px;` +
      `letter-spacing:1px;color:${ch.color};text-shadow:1px 1px 0 #000;">${ch.name}</div>` +
      `<div style="margin-top:6px;display:flex;gap:6px;justify-content:center;min-height:20px;">` +
      (p1Tag ? `<span style="padding:2px 6px;border-radius:4px;background:rgba(34,102,255,0.2);color:#8eb8ff;font-size:10px;letter-spacing:1px;">${p1Tag}</span>` : '') +
      (p2Tag ? `<span style="padding:2px 6px;border-radius:4px;background:rgba(255,34,34,0.2);color:#ffabab;font-size:10px;letter-spacing:1px;">${p2Tag}</span>` : '') +
      `</div>` +
      `</div>`
    );
  }).join('');

  const titleEl = document.getElementById('overlay-title');
  titleEl.textContent = 'CHARACTER SELECT';
  titleEl.style.fontSize = 'clamp(24px, 5vw, 42px)';
  titleEl.style.letterSpacing = '4px';
  document.getElementById('overlay-sub').innerHTML =
    `<div style="max-width:min(760px,94vw);margin:0 auto;text-align:center;">` +
    `<div style="display:flex;gap:8px;justify-content:center;flex-wrap:wrap;">${cards}</div>` +
    `<div style="margin-top:12px;font-size:0.95em;letter-spacing:1px;text-align:center;">` +
    `P1: <span style="color:${p1Char.color}">${p1Name}</span> [${p1Status}] &nbsp;|&nbsp; ` +
    `P2: <span style="color:${p2Char.color}">${p2Name}</span> [${p2Status}]` +
    `</div>` +
    '<div style="margin-top:6px;font-size:0.85em;color:#8899aa;text-align:center;">Move = LEFT/RIGHT | Lock = LIGHT/HEAVY | Unlock = BLOCK</div>' +
    `</div>`;
}

function openCharacterSelect() {
  menuPhase = 'character_select';
  menuReadyAt = 0;
  menuSel[1] = 0;
  menuSel[2] = 1;
  menuLock[1] = false;
  menuLock[2] = false;
  applyMenuCharacters();

  showOverlay('CHARACTER SELECT', '', '▶ WAITING...');
  const btn = document.getElementById('overlay-btn');
  btn.style.display = 'none';
  renderCharacterSelectOverlay();
}

function menuJustPressed(pl, action) {
  const now = inp[pl][action];
  const was = menuPrev[pl][action];
  menuPrev[pl][action] = now;
  return now && !was;
}

function updateMenu() {
  if (menuPhase !== 'character_select') return;

  for (const pl of [1, 2]) {
    if (!menuLock[pl]) {
      if (menuJustPressed(pl, 'left')) {
        menuSel[pl] = (menuSel[pl] + CHARACTERS.length - 1) % CHARACTERS.length;
      }
      if (menuJustPressed(pl, 'right')) {
        menuSel[pl] = (menuSel[pl] + 1) % CHARACTERS.length;
      }
      if (menuJustPressed(pl, 'light') || menuJustPressed(pl, 'heavy')) {
        menuLock[pl] = true;
        sndBeep();
      }
    } else if (menuJustPressed(pl, 'block')) {
      menuLock[pl] = false;
      sndBeep();
    }
  }

  applyMenuCharacters();
  renderCharacterSelectOverlay();

  if (menuLock[1] && menuLock[2]) {
    if (!menuReadyAt) menuReadyAt = performance.now() + 500;
    if (performance.now() >= menuReadyAt) {
      hideOverlay();
      enterCountdown();
    }
  } else {
    menuReadyAt = 0;
  }
}

// ============================================================================
// STATE MACHINE
// ============================================================================

// Called by the overlay button (touch or click)
function overlayBtnPressed() {
  ensureAudio();
  sndBeep();
  if (gameState === STATE.MENU && menuPhase === 'title') {
    ensurePlayers();
    roundNum = 1;
    updateHUD();
    openCharacterSelect();
  } else if (gameState === STATE.GAME_OVER) {
    gameState = STATE.MENU;
    ensurePlayers();
    roundNum = 1;
    updateHUD();
    openCharacterSelect();
  }
}

function enterCountdown() {
  gameState = STATE.COUNTDOWN;
  cdStep = 0;
  cdNext = performance.now() + COUNTDOWN_STEP + 300;
  showCountdownText('ROUND ' + roundNum, C_YELLOW);
  updateHUD();
}

function updateCountdown() {
  if (performance.now() < cdNext) return;
  cdStep++;

  if (cdStep <= 3) {
    showCountdownText(String(4 - cdStep), C_WHITE);
    cdNext = performance.now() + COUNTDOWN_STEP;
  } else if (cdStep === 4) {
    showCountdownText('FIGHT!', C_GREEN);
    cdNext = performance.now() + 500;
  } else {
    hideCountdownText();
    gameState = STATE.PLAYING;
    lastMs = performance.now();
    sndFight();
  }
}

function enterRoundEnd() {
  gameState = STATE.ROUND_END;

  if (p1.isKO && p2.isKO) {
    roundEndMsg = 'DRAW!';
  } else if (p2.isKO) {
    p1.roundWins++;
    roundEndMsg = 'P1 WINS!';
  } else {
    p2.roundWins++;
    roundEndMsg = 'P2 WINS!';
  }

  sndKO();
  updateHUD();

  // Show KO card after a 400 ms dramatic pause
  setTimeout(() => {
    const col = (p2.isKO && !p1.isKO) ? C_P1 : C_P2;
    document.getElementById('overlay').classList.remove('hidden');
    document.getElementById('overlay-title').innerHTML =
      `<span style="display:block;width:100%;text-align:center;color:${C_RED};font-size:1.2em;letter-spacing:16px">K.O.</span>`;
    document.getElementById('overlay-sub').innerHTML =
      `<span style="font-family:'Black Han Sans',sans-serif;font-size:1.5em;letter-spacing:4px;color:${col}">${roundEndMsg}</span>`;
    document.getElementById('overlay-btn').style.display = 'none';
  }, 400);

  roundEndAt = performance.now() + ROUND_END_DELAY;
}

function updateRoundEnd() {
  if (performance.now() < roundEndAt) return;
  hideOverlay();

  if (p1.roundWins >= ROUNDS_TO_WIN || p2.roundWins >= ROUNDS_TO_WIN) {
    enterGameOver();
  } else {
    roundNum++;
    const px1 = CW * 0.2, px2 = CW * 0.75;
    resetPlayerForRound(p1, px1, START_Y, true);
    resetPlayerForRound(p2, px2, START_Y, false);
    enterCountdown();
  }
}

function enterGameOver() {
  gameState = STATE.GAME_OVER;
  menuPhase = 'title';
  let winner;
  if      (p1.roundWins >= ROUNDS_TO_WIN) winner = `<span style="color:var(--p1);font-size:1.4em">P1 WINS THE MATCH!</span>`;
  else if (p2.roundWins >= ROUNDS_TO_WIN) winner = `<span style="color:var(--p2);font-size:1.4em">P2 WINS THE MATCH!</span>`;
  else                                    winner = `<span style="color:var(--yellow);font-size:1.4em">IT'S A DRAW!</span>`;
  showOverlay('GAME OVER', winner + '<br><br>Press Light / Heavy to play again', 'PRESS LIGHT / HEAVY');
}

function updatePlaying() {
  const now = performance.now();
  if (now < hitstopEnd) return;  // hitstop freeze

  let dt = (now - lastMs) / 1000;
  lastMs = now;
  if (dt > 0.05) dt = 0.05;     // cap to avoid spiral-of-death on lag spikes

  updateAttackWindow(p1);
  updateAttackWindow(p2);

  handleInput(p1, inp[1]);
  handleInput(p2, inp[2]);

  autoFace(p1, p2);
  autoFace(p2, p1);

  updatePhysics(p1, dt);
  updatePhysics(p2, dt);

  const h1 = checkAndResolveHit(p1, p2);
  const h2 = checkAndResolveHit(p2, p1);

  if (h1 > 0) {
    const heavy = p1.currentAtk === 2;
    if (h1 === 2) sndBlock(); else if (heavy) sndHeavy(); else sndLight();
    hitstopEnd = now + (heavy ? HITSTOP_HEAVY_MS : HITSTOP_LIGHT_MS);
  }
  if (h2 > 0) {
    const heavy = p2.currentAtk === 2;
    if (h2 === 2) sndBlock(); else if (heavy) sndHeavy(); else sndLight();
    hitstopEnd = now + (heavy ? HITSTOP_HEAVY_MS : HITSTOP_LIGHT_MS);
  }

  updateHUD();

  if (p1.isKO || p2.isKO) enterRoundEnd();
}

// ============================================================================
// MAIN GAME LOOP
// ============================================================================
function gameLoop() {
  animId = requestAnimationFrame(gameLoop);
  frameCount++;
  document.getElementById('hud').style.display = (gameState === STATE.MENU) ? 'none' : 'flex';

  const startInputNow = inp[1].light || inp[1].heavy || inp[2].light || inp[2].heavy;
  const canUseStartInput = (gameState === STATE.MENU && menuPhase === 'title') || gameState === STATE.GAME_OVER;
  if (canUseStartInput && startInputNow && !startInputPrev) {
    overlayBtnPressed();
  }
  startInputPrev = startInputNow;

  switch (gameState) {
    case STATE.MENU:
      drawStartScreenBackground();
      updateMenu();
      drawMenuArt();
      break;
    case STATE.COUNTDOWN:
      drawFightBackground();
      updateCountdown();
      if (p1) { drawPlayer(p1); drawPlayer(p2); }
      break;
    case STATE.PLAYING:
      drawFightBackground();
      updatePlaying();
      drawPlayer(p1);
      drawPlayer(p2);
      break;
    case STATE.ROUND_END:
      drawBackground();
      updateRoundEnd();
      if (p1) { drawPlayer(p1); drawPlayer(p2); }
      break;
    default:  // GAME_OVER
      drawStartScreenBackground();
      drawMenuArt();
      break;
  }
}

// ============================================================================
// CANVAS SIZING
// ============================================================================
function resizeCanvas() {
  const area = document.getElementById('canvas-area');
  CW          = area.clientWidth;
  CH          = area.clientHeight;
  canvas.width  = CW;
  canvas.height = CH;
  FLOOR_Y     = Math.floor(CH * 0.78);
  FLOOR_THICK = Math.floor(CH * 0.22);
  START_Y     = FLOOR_Y - PLAYER_H;
}

window.addEventListener('resize', resizeCanvas);
resizeCanvas();

// ============================================================================
// BOOT
// ============================================================================
showOverlay(
  'TEKKEN MINI',
  'Two-player arcade fighter',
  'PRESS LIGHT / HEAVY'
);

requestAnimationFrame(gameLoop);
