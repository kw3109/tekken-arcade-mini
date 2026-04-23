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

const PLAYER_W         = 28;
const PLAYER_H         = 56;
const PLAYER_CROUCH_H  = 34;

const LIGHT_DMG        = 8;
const LIGHT_RANGE      = 56;
const LIGHT_CD_MS      = 400;
const LIGHT_ACTIVE_MS  = 120;

const HEAVY_DMG        = 22;
const HEAVY_RANGE      = 80;
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

// ============================================================================
// GAME STATE ENUM
// ============================================================================
const STATE = { MENU: 0, COUNTDOWN: 1, PLAYING: 2, ROUND_END: 3, GAME_OVER: 4 };

let gameState = STATE.MENU;
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
  const reach = p.currentAtk === 1 ? LIGHT_RANGE : HEAVY_RANGE;
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

function drawPlayer(p) {
  const now = performance.now();
  const r   = playerRect(p);

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

  // Main body rectangle
  ctx.fillStyle = col;
  ctx.fillRect(r.x, r.y + yOff, r.w, r.h);
  ctx.shadowBlur = 0;

  // White outline
  ctx.strokeStyle = 'rgba(255,255,255,0.5)';
  ctx.lineWidth = 1.5;
  ctx.strokeRect(r.x + 0.5, r.y + yOff + 0.5, r.w - 1, r.h - 1);

  // Eye dot (indicates facing direction)
  const eyeX = p.facingRight ? r.x + r.w - 5 : r.x + 4;
  ctx.fillStyle = '#000000';
  ctx.fillRect(eyeX, r.y + yOff + 6, 3, 3);

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
      ctx.fillStyle   = (p.currentAtk === 2) ? 'rgba(255,120,0,0.25)' : 'rgba(100,180,255,0.2)';
      ctx.fillRect(atk.x, atk.y, atk.w, atk.h);
      ctx.strokeStyle = (p.currentAtk === 2) ? 'rgba(255,140,0,0.7)' : 'rgba(100,200,255,0.6)';
      ctx.lineWidth   = 1.5;
      ctx.strokeRect(atk.x, atk.y, atk.w, atk.h);
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
  const t = performance.now() / 1000;
  ctx.save();
  ctx.globalAlpha = 0.12 + 0.04 * Math.sin(t);
  ctx.fillStyle   = C_P1;
  ctx.fillRect(CW * 0.25 - 20, FLOOR_Y - PLAYER_H - 4, PLAYER_W + 8, PLAYER_H + 4);
  ctx.fillStyle   = C_P2;
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
  document.getElementById('overlay-title').textContent  = title;
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
  el.style.display = 'block';
  // Re-trigger CSS animation
  el.style.animation = 'none';
  el.offsetHeight;           // force reflow
  el.style.animation = '';
}

function hideCountdownText() {
  document.getElementById('countdown-text').style.display = 'none';
}

// ============================================================================
// STATE MACHINE
// ============================================================================

// Called by the overlay button (touch or click)
function overlayBtnPressed() {
  ensureAudio();
  sndBeep();
  if (gameState === STATE.MENU || gameState === STATE.GAME_OVER) {
    const px1 = CW * 0.2, px2 = CW * 0.75;
    if (!p1) {
      p1 = makePlayer(px1, START_Y, true,  C_P1, C_P1_ATK);
      p2 = makePlayer(px2, START_Y, false, C_P2, C_P2_ATK);
    } else {
      p1.roundWins = 0; p2.roundWins = 0;
      resetPlayerForRound(p1, px1, START_Y, true);
      resetPlayerForRound(p2, px2, START_Y, false);
    }
    roundNum = 1;
    hideOverlay();
    enterCountdown();
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
      `<span style="color:${C_RED};font-size:1.2em;letter-spacing:16px">K.O.</span>`;
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
  let winner;
  if      (p1.roundWins >= ROUNDS_TO_WIN) winner = `<span style="color:var(--p1);font-size:1.4em">P1 WINS THE MATCH!</span>`;
  else if (p2.roundWins >= ROUNDS_TO_WIN) winner = `<span style="color:var(--p2);font-size:1.4em">P2 WINS THE MATCH!</span>`;
  else                                    winner = `<span style="color:var(--yellow);font-size:1.4em">IT'S A DRAW!</span>`;
  showOverlay('GAME OVER', winner + '<br><br>Press Start to play again', '▶ PLAY AGAIN');
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

  drawBackground();

  switch (gameState) {
    case STATE.COUNTDOWN:
      updateCountdown();
      if (p1) { drawPlayer(p1); drawPlayer(p2); }
      break;
    case STATE.PLAYING:
      updatePlaying();
      drawPlayer(p1);
      drawPlayer(p2);
      break;
    case STATE.ROUND_END:
      updateRoundEnd();
      if (p1) { drawPlayer(p1); drawPlayer(p2); }
      break;
    default:  // MENU / GAME_OVER
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
  'Two-player arcade fighter<br><span style="color:#8899aa;font-size:0.85em">Keyboard: WASD+FGH &nbsp;|&nbsp; Arrows+JKL</span>',
  '▶ START GAME'
);

requestAnimationFrame(gameLoop);
