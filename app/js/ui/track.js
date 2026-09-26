// Pista de voz en Canvas: las notas avanzan de derecha a izquierda hacia la línea AHORA.
//
// Eje vertical = altura (cada línea es un semitono con su nombre, La2, Si2…).
// Eje horizontal = tiempo. Primero pasan las barras tenues de ESCUCHA (el piano
// las toca, no puntúan) y después las violeta de TU TURNO. La bola es tu voz y
// la estela, lo que acabas de cantar.
//
// Dirección visual: tranquila mientras escuchas y viva cuando cantas. Una
// «energía» suavizada sube con la fase y los aciertos y controla brillos y halo.
// Color = significado: violeta objetivo, verde acierto, cyan «sube», naranja
// «baja», dorado recompensa, rosa momento especial.
//
// Esta vista sólo LEE el estado de NoteRun: animar no puntúa.

import { HITS, JUDGEMENT_TEXT } from '../game/noteRun.js';
import { noteName } from '../pitch/notes.js';

const LOOKAHEAD = 5.5;      // segundos visibles por delante de la línea
const HIT_FRACTION = 0.26;  // posición de la línea AHORA dentro del carril
const MARGIN_CENTS = 350;   // aire por encima y por debajo de la frase
const PHASE_ENERGY = { intro: 0.1, listen: 0.3, turn: 0.5, sing: 0.6, rest: 0.2, end: 0.2 };
const BURST = { perfect: 40, great: 22, ok: 10 };

function palette() {
  const css = getComputedStyle(document.documentElement);
  const v = (name) => css.getPropertyValue(name).trim();
  return {
    bg: v('--bg'), surface: v('--surface'), card: v('--card'), line: v('--line'),
    text: v('--text'), muted: v('--muted'), dim: v('--dim'), ink: v('--ink'),
    violet: v('--violet'), green: v('--green'), cyan: v('--cyan'), orange: v('--orange'),
    gold: v('--gold'), pink: v('--pink'), font: v('--font'),
  };
}

/** '#rrggbb' + alfa 0–1 → rgba(). */
function rgba(hex, alpha = 1) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${Math.max(0, Math.min(1, alpha))})`;
}

export class TrackRenderer {
  constructor(canvas, clock) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.clock = clock;
    this.c = palette();
    this.run = null;
    this.anchorMidi = 57;
    this.levelName = '';
    this.center = 0;
    this.half = 700;
    this.displayCents = null;
    this.energy = 0;
    this.popups = [];     // [índice, juicio, nacimiento]
    this.particles = [];  // {x, y, vx, vy, age, life, color, size}
    this.rings = [];      // {x, y, born, color}
    this.lastFrame = null;
    this.u = 1;           // 1 unidad de diseño = 1px a 1080p
    new ResizeObserver(() => this.resize()).observe(canvas);
  }

  resize() {
    const dpr = window.devicePixelRatio || 1;
    const { clientWidth: w, clientHeight: h } = this.canvas;
    this.canvas.width = Math.round(w * dpr);
    this.canvas.height = Math.round(h * dpr);
    this.u = parseFloat(getComputedStyle(document.documentElement).fontSize) / 16;
  }

  setRun(run, anchorMidi, levelName = '') {
    this.run = run;
    this.anchorMidi = anchorMidi;
    this.levelName = levelName;
    const semis = run.notes.map((n) => n.semitone);
    const lo = Math.min(...semis) * 100, hi = Math.max(...semis) * 100;
    this.center = (lo + hi) / 2;
    this.half = Math.max(650, (hi - lo) / 2 + MARGIN_CENTS);
    this.displayCents = null;
    this.energy = 0;
    this.popups = [];
    this.particles = [];
    this.rings = [];
  }

  px(n) { return n * this.u; }
  font(size, weight = 400) { return `${weight} ${this.px(size)}px ${this.c.font}`; }

  geometry() {
    const w = this.canvas.clientWidth, h = this.canvas.clientHeight;
    const hud = this.px(70), ax = this.px(150);
    const top = hud + this.px(8), bottom = h - this.px(36);
    const hitx = ax + (w - ax) * HIT_FRACTION;
    return { w, h, hud, ax, top, bottom, cy: (top + bottom) / 2, cpp: (bottom - top) / (2 * this.half), hitx, pps: (w - hitx) / LOOKAHEAD };
  }

  yOf(g, cents) {
    const c = Math.max(this.center - this.half - 40, Math.min(this.center + this.half + 40, cents));
    return g.cy - (c - this.center) * g.cpp;
  }

  xOf(g, songTime, t) { return g.hitx + (songTime - t) * g.pps; }

  name(semitone) { return noteName(this.anchorMidi + semitone); }

  // --- eventos del juego -------------------------------------------------
  judgement(index, judgement) {
    const now = this.clock();
    this.popups.push([index, judgement, now]);
    if (!(judgement in BURST) || !this.run) return;
    // Pequeño momento de satisfacción: estallido y onda en la barra acertada.
    const g = this.geometry();
    const note = this.run.notes[index];
    const t = this.run.time(now);
    const x = Math.max(g.ax + this.px(20), (this.xOf(g, note.start, t) + this.xOf(g, note.end, t)) / 2);
    const y = this.yOf(g, note.target);
    const gold = judgement === 'perfect';
    for (let i = 0; i < BURST[judgement]; i++) {
      const angle = Math.random() * Math.PI * 2;
      const speed = 80 + Math.random() * (gold ? 260 : 160);
      this.particles.push({ x, y, vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed, age: 0,
        life: 0.5 + Math.random() * 0.4, color: gold && i % 2 ? this.c.gold : this.c.green, size: 2.5 + Math.random() * 3 });
    }
    this.rings.push({ x, y, born: now, color: gold ? this.c.gold : this.c.green });
  }

  // --- animación (independiente de la puntuación) ------------------------
  step() {
    const nowPerf = performance.now() / 1000;
    const dt = this.lastFrame ? Math.min(0.1, nowPerf - this.lastFrame) : 0.016;
    this.lastFrame = nowPerf;
    const run = this.run;
    if (!run) return;
    const now = this.clock();
    const reading = run.currentReading(now);
    const hitting = !!(reading && reading.kind === 'hit' && run.activeNote(now) !== null);
    let target = run.state === 'paused' ? 0 : (PHASE_ENERGY[run.phase(now)[0]] ?? 0.2);
    if (hitting) target = 1;
    this.energy += (target - this.energy) * Math.min(1, dt * 3);
    if (reading && reading.cents !== null) {
      const goal = Math.max(this.center - this.half, Math.min(this.center + this.half, reading.cents));
      if (this.displayCents === null) this.displayCents = goal;
      this.displayCents += (goal - this.displayCents) * Math.min(1, dt * 16);
      if (hitting) {
        const g = this.geometry();
        const y = this.yOf(g, this.displayCents);
        const count = 2 + (run.streak >= 3 ? 1 : 0);
        for (let i = 0; i < count; i++) {
          this.particles.push({ x: g.hitx, y, vx: -90 - Math.random() * 210, vy: (Math.random() - 0.5) * 340, age: 0,
            life: 0.4 + Math.random() * 0.3, color: Math.random() < 0.2 ? this.c.gold : this.c.green, size: 2 + Math.random() * 2.5 });
        }
      }
    }
    for (const p of this.particles) {
      p.x += p.vx * dt * this.u;
      p.y += p.vy * dt * this.u;
      p.vy += 120 * dt;          // una pizca de gravedad
      p.age += dt;
    }
    this.particles = this.particles.filter((p) => p.age < p.life);
    this.rings = this.rings.filter((r) => now - r.born < 0.6);
    this.popups = this.popups.filter(([, , born]) => now - born < 1.6);
  }

  // --- dibujo --------------------------------------------------------------
  draw() {
    const ctx = this.ctx;
    const dpr = this.canvas.width / Math.max(1, this.canvas.clientWidth);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const g = this.geometry();
    if (g.bottom - g.top < 10 || g.w - g.ax < 10) return;   // aún sin tamaño (primer fotograma)
    const bg = ctx.createLinearGradient(0, 0, 0, g.h);
    bg.addColorStop(0, '#16191c');
    bg.addColorStop(1, this.c.bg);
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, g.w, g.h);
    const run = this.run;
    if (!run) return;
    const now = this.clock();
    const t = run.time(now);
    this.drawAmbient(g, now);
    this.drawLane(g, now);
    ctx.save();
    ctx.beginPath();
    ctx.rect(g.ax, 0, g.w - g.ax, g.h);   // nada asoma bajo el eje
    ctx.clip();
    this.drawLabels(g, t);
    this.drawNotes(g, t);
    this.drawTrail(g, t);
    this.drawHitLine(g, now);
    this.drawEffects(now);
    this.drawVoice(g, now);
    this.drawPopups(g, now);
    ctx.restore();
    this.drawAxis(g);
    this.drawHud(g, now);
    this.drawPhase(g, now);
    if (run.state === 'paused') {
      ctx.fillStyle = rgba(this.c.bg, 0.84);
      ctx.fillRect(0, 0, g.w, g.h);
      this.text('En pausa', g.w / 2, g.cy - this.px(40), this.font(48, 600), this.c.text, 'center');
      this.text('Pulsa «Seguir» o la barra espaciadora. El tiempo está detenido.', g.w / 2, g.cy + this.px(24),
        this.font(20), this.c.muted, 'center');
    }
  }

  text(str, x, y, font, color, align = 'left', baseline = 'middle') {
    const ctx = this.ctx;
    ctx.font = font;
    ctx.fillStyle = color;
    ctx.textAlign = align;
    ctx.textBaseline = baseline;
    ctx.fillText(str, x, y);
  }

  roundRect(x, y, w, h, r) {
    const ctx = this.ctx;
    ctx.beginPath();
    ctx.roundRect(x, y, Math.max(0, w), h, Math.min(r, Math.abs(w) / 2, h / 2));
  }

  semitonesVisible() {
    const lo = Math.ceil((this.center - this.half) / 100);
    const hi = Math.floor((this.center + this.half) / 100);
    const out = [];
    for (let k = lo; k <= hi; k++) out.push(k);
    return out;
  }

  /** Halo suave detrás de la línea: aparece con la energía y toma el color del feedback. */
  drawAmbient(g, now) {
    if (this.energy < 0.05) return;
    const reading = this.run.currentReading(now);
    const kinds = { hit: this.c.green, low: this.c.cyan, high: this.c.orange };
    const tint = (reading && kinds[reading.kind]) || this.c.violet;
    const y = this.displayCents !== null ? this.yOf(g, this.displayCents) : g.cy;
    const radius = (g.bottom - g.top) * 0.75;
    const glow = this.ctx.createRadialGradient(g.hitx, y, 0, g.hitx, y, radius);
    glow.addColorStop(0, rgba(tint, 0.22 * this.energy));
    glow.addColorStop(1, rgba(tint, 0));
    this.ctx.fillStyle = glow;
    this.ctx.fillRect(g.ax, g.top, g.w - g.ax, g.bottom - g.top);
  }

  drawLane(g, now) {
    const ctx = this.ctx;
    const used = new Set(this.run.notes.map((n) => n.semitone));
    const index = this.run.activeNote(now);
    const active = index !== null ? this.run.notes[index].semitone : null;
    for (const k of this.semitonesVisible()) {
      const y = this.yOf(g, k * 100);
      if (k === active) {
        ctx.fillStyle = rgba(this.c.violet, 0.2 * this.energy);
        ctx.fillRect(g.ax, y - this.px(3), g.w - g.ax, this.px(6));
      }
      ctx.strokeStyle = rgba(this.c.text, used.has(k) ? 0.1 : 0.04);
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(g.ax, Math.round(y) + 0.5);
      ctx.lineTo(g.w, Math.round(y) + 0.5);
      ctx.stroke();
    }
  }

  /** «ESCUCHA», «TU TURNO» y «respira» sobre cada tramo de la ronda. */
  drawLabels(g, t) {
    const ctx = this.ctx;
    const top = g.top + this.px(6);
    for (const a of this.run.attempts) {
      const demo = this.run.notes.filter((n) => n.attempt === a && n.demo);
      const sung = this.run.sung.filter((n) => n.attempt === a);
      for (const [group, label, color] of [[demo, 'ESCUCHA', this.c.muted], [sung, 'TU TURNO', this.c.violet]]) {
        if (!group.length) continue;
        const x0 = this.xOf(g, group[0].start, t), x1 = this.xOf(g, group[group.length - 1].end, t);
        if (x1 < g.ax || x0 > g.w) continue;
        ctx.strokeStyle = rgba(color, 0.35);
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(Math.max(x0, g.ax), top + this.px(28));
        ctx.lineTo(x1, top + this.px(28));
        ctx.stroke();
        this.text(label, Math.max(x0, g.ax + this.px(6)), top + this.px(13), this.font(15, 600), color);
      }
      const next = this.run.notes.filter((n) => n.attempt === a + 1);
      if (sung.length && next.length) {
        const x = this.xOf(g, (sung[sung.length - 1].end + next[0].start) / 2, t);
        if (x > g.ax + this.px(60) && x < g.w - this.px(60)) this.text('respira', x, g.cy, this.font(20), this.c.muted, 'center');
      }
    }
  }

  drawNotes(g, t) {
    const ctx = this.ctx;
    const minH = this.px(36);
    const radius = this.px(10);
    for (const note of this.run.notes) {
      const x0 = this.xOf(g, note.start, t), x1 = this.xOf(g, note.end, t);
      if (x1 < g.ax || x0 > g.w) continue;
      const yc = this.yOf(g, note.target);
      const half = Math.max(minH / 2, this.run.tolerance * g.cpp);
      const rect = [x0, yc - half, x1 - x0, 2 * half];
      let labelColor = this.c.text;
      if (note.demo) {
        const playing = note.start <= t && t <= note.end;   // el piano suena: la nota se ilumina
        this.roundRect(...rect, radius);
        if (playing) {
          ctx.shadowColor = rgba(this.c.violet, 0.8);
          ctx.shadowBlur = this.px(18);
        }
        ctx.fillStyle = playing ? rgba(this.c.violet, 0.45) : rgba(this.c.text, 0.05);
        ctx.fill();
        ctx.shadowBlur = 0;
        ctx.strokeStyle = playing ? rgba(this.c.violet, 0.8) : rgba(this.c.text, 0.24);
        ctx.lineWidth = 1.5;
        ctx.stroke();
        labelColor = playing ? this.c.text : this.c.muted;
      } else {
        const j = note.judgement;
        const active = j === null && note.start <= t && t <= note.end;
        this.roundRect(...rect, radius);
        if (HITS.has(j)) {
          ctx.fillStyle = this.c.green;
          ctx.fill();
          labelColor = this.c.ink;
          if (j === 'perfect') {                   // recompensa: filo dorado
            ctx.strokeStyle = this.c.gold;
            ctx.lineWidth = this.px(2.5);
            ctx.stroke();
          }
        } else if (j && j.startsWith('miss')) {
          const tint = j === 'miss_low' ? this.c.cyan : this.c.orange;
          ctx.fillStyle = rgba(tint, 0.11);
          ctx.fill();
          ctx.strokeStyle = rgba(tint, 0.8);
          ctx.lineWidth = 1.5;
          ctx.stroke();
          labelColor = tint;
        } else if (j === 'unclear' || j === 'silent') {
          ctx.setLineDash([this.px(6), this.px(5)]);
          ctx.strokeStyle = this.c.dim;
          ctx.lineWidth = 1.5;
          ctx.stroke();
          ctx.setLineDash([]);
          labelColor = this.c.dim;
        } else {
          if (active) {
            ctx.shadowColor = rgba(this.c.violet, 0.5 + 0.4 * this.energy);
            ctx.shadowBlur = this.px(10 + 22 * this.energy);
          }
          ctx.fillStyle = rgba(this.c.violet, active ? 0.95 : 0.78);
          ctx.fill();
          ctx.shadowBlur = 0;
          if (note.hitSpans.length) {
            ctx.save();
            this.roundRect(...rect, radius);
            ctx.clip();
            ctx.fillStyle = this.c.green;
            for (const [a, b] of note.hitSpans) {
              const xa = this.xOf(g, a, t), xb = this.xOf(g, b, t);
              ctx.fillRect(xa, rect[1], xb - xa, rect[3]);
            }
            ctx.restore();
          }
        }
      }
      const label = this.name(note.semitone);
      if (rect[2] > this.px(64)) this.text(label, x0 + rect[2] / 2, yc, this.font(20, 700), labelColor, 'center');
      else this.text(label, x0 + rect[2] / 2, rect[1] - this.px(14), this.font(20, 700), this.c.text, 'center');
    }
  }

  drawTrail(g, t) {
    const ctx = this.ctx;
    const kinds = { hit: this.c.green, low: this.c.cyan, high: this.c.orange, free: this.c.text };
    ctx.lineCap = 'round';
    ctx.lineWidth = this.px(6);
    let prev = null;
    for (const r of this.run.trail) {
      if (r.time < t - 2.2) { prev = null; continue; }
      const pitched = r.cents !== null;
      if (pitched && prev && r.time - prev.time < 0.3) {
        ctx.strokeStyle = rgba(kinds[r.kind], 0.35 + 0.55 * Math.max(0, 1 - (t - r.time) / 2.2));
        ctx.beginPath();
        ctx.moveTo(this.xOf(g, prev.time, t), this.yOf(g, prev.cents));
        ctx.lineTo(this.xOf(g, r.time, t), this.yOf(g, r.cents));
        ctx.stroke();
      }
      prev = pitched ? r : null;
    }
  }

  drawHitLine(g, now) {
    const ctx = this.ctx;
    const reading = this.run.currentReading(now);
    const hitting = reading && reading.kind === 'hit' && this.run.activeNote(now) !== null;
    if (hitting) {
      ctx.fillStyle = rgba(this.c.green, 0.28 * this.energy);
      ctx.fillRect(g.hitx - this.px(9), g.top, this.px(18), g.bottom - g.top);
    }
    ctx.fillStyle = hitting ? this.c.green : rgba(this.c.text, 0.45);
    ctx.fillRect(g.hitx - 1, g.top, 2, g.bottom - g.top);
    this.text('AHORA', g.hitx, g.bottom + this.px(18), this.font(14, 600), this.c.muted, 'center');
  }

  drawEffects(now) {
    const ctx = this.ctx;
    for (const r of this.rings) {
      const age = (now - r.born) / 0.6;
      ctx.strokeStyle = rgba(r.color, 0.8 * (1 - age));
      ctx.lineWidth = this.px(3);
      ctx.beginPath();
      ctx.arc(r.x, r.y, this.px(18) + this.px(90) * age, 0, Math.PI * 2);
      ctx.stroke();
    }
    for (const p of this.particles) {
      ctx.fillStyle = rgba(p.color, 0.92 * (1 - p.age / p.life));
      ctx.beginPath();
      ctx.arc(p.x, p.y, this.px(p.size), 0, Math.PI * 2);
      ctx.fill();
    }
  }

  drawVoice(g, now) {
    const ctx = this.ctx;
    const reading = this.run.currentReading(now);
    if (!reading) return;
    const x = g.hitx;
    if (reading.kind === 'muted') return;          // durante la escucha no se muestra el micro
    if (reading.kind === 'unclear') {
      if (this.run.activeNote(now) === null) return;
      const w = this.px(230), h = this.px(40);
      this.roundRect(x - w / 2, g.bottom - this.px(54), w, h, this.px(10));
      ctx.fillStyle = rgba(this.c.card, 0.92);
      ctx.fill();
      this.text('no te oigo claro', x, g.bottom - this.px(34), this.font(18, 600), this.c.muted, 'center');
      return;
    }
    if (reading.cents === null || this.displayCents === null) return;
    const colors = { hit: this.c.green, low: this.c.cyan, high: this.c.orange, free: this.c.text };
    const c = colors[reading.kind];
    const y = this.yOf(g, this.displayCents);
    const r = this.px(16);
    const glow = this.px(8 + 22 * this.energy);
    ctx.fillStyle = rgba(c, 0.18);
    ctx.beginPath(); ctx.arc(x, y, r + glow, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = rgba(c, 0.32);
    ctx.beginPath(); ctx.arc(x, y, r + glow / 2, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = c;
    ctx.strokeStyle = this.c.text;     // contorno claro: se distingue incluso sobre una barra verde
    ctx.lineWidth = this.px(2.5);
    ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    if (reading.kind === 'low' || reading.kind === 'high') {
      // Flecha hacia la nota: si estás grave apunta arriba y viceversa.
      const d = reading.kind === 'low' ? -1 : 1;
      ctx.fillStyle = c;
      ctx.beginPath();
      ctx.moveTo(x, y + d * this.px(66));
      ctx.lineTo(x - this.px(16), y + d * this.px(32));
      ctx.lineTo(x + this.px(16), y + d * this.px(32));
      ctx.closePath();
      ctx.fill();
    }
  }

  drawAxis(g) {
    const ctx = this.ctx;
    ctx.fillStyle = this.c.bg;
    ctx.fillRect(0, g.top - this.px(8), g.ax, g.bottom - g.top + this.px(16));
    ctx.fillStyle = this.c.line;
    ctx.fillRect(g.ax - 1, g.top, 1, g.bottom - g.top);
    const used = new Set(this.run.notes.map((n) => n.semitone));
    const visible = this.semitonesVisible();
    const step = visible.length <= 18 ? 1 : 2;
    for (const k of visible) {
      if (!used.has(k) && k % step) continue;
      const y = this.yOf(g, k * 100);
      const strong = used.has(k);
      this.text(this.name(k), g.ax - this.px(14), y, this.font(strong ? 18 : 14, strong ? 600 : 400),
        strong ? this.c.text : this.c.dim, 'right');
      if (k === 0) this.text('TU', this.px(8), y, this.font(12, 600), this.c.violet);
    }
    this.text('▲ agudo', this.px(8), g.top + this.px(12), this.font(14, 600), this.c.muted);
    this.text('▼ grave', this.px(8), g.bottom - this.px(12), this.font(14, 600), this.c.muted);
  }

  drawHud(g, now) {
    const ctx = this.ctx;
    const run = this.run;
    const [, attempt] = run.phase(now);
    const mid = g.hud / 2;
    this.text(`Intento ${attempt + 1} de ${run.attempts.length}`, this.px(24), mid, this.font(19, 600), this.c.muted);
    for (const i of run.attempts) {
      const cx = this.px(236) + i * this.px(30);
      const notes = run.sung.filter((n) => n.attempt === i);
      const done = notes.every((n) => n.judgement);
      ctx.beginPath();
      ctx.arc(cx, mid, this.px(9), 0, Math.PI * 2);
      if (done) {
        ctx.fillStyle = run.attemptScore(i) >= 0.8 ? this.c.gold : this.c.dim;
        ctx.fill();
      }
      ctx.strokeStyle = i === attempt && !done ? this.c.text : this.c.line;
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }
    this.text(run.score.toLocaleString('es-ES'), g.w / 2, mid, this.font(34, 700), this.c.gold, 'center');
    if (run.streak >= 2) this.text(`racha ×${run.streak}`, g.w / 2 + this.px(90), mid, this.font(20, 700), this.c.gold);
    this.text(this.levelName, g.w - this.px(24), mid, this.font(17), this.c.muted, 'right');
  }

  drawPhase(g, now) {
    const [phase, attempt] = this.run.phase(now);
    const x = g.hitx + (g.w - g.hitx) / 2;
    const y = g.bottom - this.px(85);
    if (phase === 'intro') {
      this.text('Primero escucha al piano', x, y, this.font(32, 600), this.c.muted, 'center');
    } else if (phase === 'turn') {
      const first = this.run.sung.find((n) => n.attempt === attempt);
      const left = Math.ceil(first.start - this.run.time(now));
      this.text(`¡Tu turno!  ${left}`, x, y, this.font(48, 700), this.c.pink, 'center');   // momento especial
    }
  }

  drawPopups(g, now) {
    const t = this.run.time(now);
    for (const [index, judgement, born] of this.popups) {
      const note = this.run.notes[index];
      const age = now - born;
      const alpha = Math.max(0, 1 - age / 1.6);
      const rise = this.px(50) * Math.min(1, age / 0.5);
      const color = judgement === 'perfect' ? this.c.gold : HITS.has(judgement) ? this.c.green
        : judgement === 'unclear' || judgement === 'silent' ? this.c.muted
          : judgement === 'miss_low' ? this.c.cyan : this.c.orange;
      // Encima de su propia barra, que ya ha pasado la línea: no tapa las siguientes.
      const xc = (this.xOf(g, note.start, t) + this.xOf(g, note.end, t)) / 2;
      const y = this.yOf(g, note.target) - this.px(52) - rise;
      this.text(JUDGEMENT_TEXT[judgement], xc, y, this.font(judgement === 'perfect' ? 26 : 22, 700), rgba(color, alpha), 'center');
    }
  }
}
