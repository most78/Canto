// Modo canción en Canvas: LA LETRA ES LA PISTA.
//
// - Horizontal = tiempo: la letra avanza de derecha a izquierda; el «ahora» es
//   una línea muy tenue. Se ve `lookahead` segundos de letra futura.
// - Vertical = altura relativa: cada sílaba se escribe a la altura de su nota.
//   No hay nombres de nota, cents ni pentagrama.
// - Duración: cada sílaba ocupa el ancho de su duración; un trazo fino bajo el
//   texto dibuja la trayectoria de la melodía (y la de un melisma: una palabra,
//   varias alturas). Las sílabas de una misma palabra se unen con ese trazo.
// - Tu voz = una línea continua (no un punto) sobre esa misma trayectoria:
//   verde afinado, cyan por debajo, naranja por encima (con histéresis).
// - Acierto consolidado: fondo verde detrás de la sílaba, que se va llenando
//   mientras la cantas bien. Los errores no se castigan: la línea ya los muestra.
//
// Sólo LEE el estado de SingSession: dibujar no puntúa.

const PLAYHEAD = 0.24;       // posición del «ahora» (fracción del ancho)
const MARGIN_SEMITONES = 3;
const PAST_FADE = 0.55;

function palette() {
  const css = getComputedStyle(document.documentElement);
  const v = (n) => css.getPropertyValue(n).trim();
  return { bg: v('--bg'), text: v('--text'), muted: v('--muted'), dim: v('--dim'), ink: v('--ink'),
    violet: v('--violet'), green: v('--green'), cyan: v('--cyan'), orange: v('--orange'), gold: v('--gold'), font: v('--font') };
}

function rgba(hex, a = 1) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${Math.max(0, Math.min(1, a))})`;
}

export class LyricsTrack {
  constructor(canvas, session) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.session = session;
    this.c = palette();
    this.u = 1;
    this.particles = [];
    this.lastFrame = null;
    new ResizeObserver(() => this.resize()).observe(canvas);
    session.addEventListener('hit', (e) => this.burst(e.detail));
  }

  resize() {
    const dpr = window.devicePixelRatio || 1;
    this.canvas.width = Math.round(this.canvas.clientWidth * dpr);
    this.canvas.height = Math.round(this.canvas.clientHeight * dpr);
    this.u = parseFloat(getComputedStyle(document.documentElement).fontSize) / 16;
  }

  px(n) { return n * this.u; }
  font(size, weight = 400) { return `${weight} ${this.px(size)}px ${this.c.font}`; }

  geometry() {
    const w = this.canvas.clientWidth, h = this.canvas.clientHeight;
    const units = this.session.units;
    const pitches = units.flatMap((u) => u.events.map((e) => e.pitch));
    const lo = Math.min(...pitches) - MARGIN_SEMITONES, hi = Math.max(...pitches) + MARGIN_SEMITONES;
    const top = this.px(90), bottom = h - this.px(80);
    const semi = Math.max(this.px(10), Math.min(this.px(44), (bottom - top) / Math.max(1, hi - lo)));
    const mid = (lo + hi) / 2;
    const playhead = w * PLAYHEAD;
    const lookahead = this.session.params.lookahead;
    return { w, h, top, bottom, semi, mid, cy: (top + bottom) / 2, playhead, pps: (w - playhead - this.px(40)) / lookahead, lookahead };
  }

  y(g, midi) {
    const y = g.cy - (midi - g.mid) * g.semi;
    return Math.max(g.top - this.px(20), Math.min(g.bottom + this.px(20), y));
  }

  x(g, time, now) { return g.playhead + (time - now) * g.pps; }

  burst(unit) {
    const g = this.geometry();
    const now = this.session.visualTime();
    const x = Math.max(this.x(g, unit.start, now), 0) + this.px(20);
    const y = this.y(g, unit.events[0].pitch) - this.px(22);
    for (let i = 0; i < 14; i++) {
      const a = Math.random() * Math.PI * 2, s = 60 + Math.random() * 140;
      this.particles.push({ x, y, vx: Math.cos(a) * s, vy: Math.sin(a) * s - 40, age: 0, life: 0.5 + Math.random() * 0.3,
        color: i % 4 === 0 ? this.c.gold : this.c.green, size: 2 + Math.random() * 2 });
    }
  }

  step() {
    const t = performance.now() / 1000;
    const dt = this.lastFrame ? Math.min(0.1, t - this.lastFrame) : 0.016;
    this.lastFrame = t;
    for (const p of this.particles) {
      p.x += p.vx * dt * this.u; p.y += p.vy * dt * this.u; p.vy += 140 * dt; p.age += dt;
    }
    this.particles = this.particles.filter((p) => p.age < p.life);
  }

  draw() {
    const ctx = this.ctx;
    const dpr = this.canvas.width / Math.max(1, this.canvas.clientWidth);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const s = this.session;
    const g = this.geometry();
    ctx.fillStyle = this.c.bg;
    ctx.fillRect(0, 0, g.w, g.h);
    if (!s.run || g.bottom - g.top < 20) return;
    const now = s.visualTime();

    // «Ahora»: una línea casi invisible; los ojos siguen las palabras.
    ctx.fillStyle = rgba(this.c.text, 0.07);
    ctx.fillRect(g.playhead - 1, g.top - this.px(40), 2, g.bottom - g.top + this.px(80));

    const from = now - g.playhead / g.pps - 1, to = now + g.lookahead + 0.5;
    const visible = s.run.units.filter((u) => u.end >= from && u.start <= to);
    this.drawTrajectories(g, now, visible);
    this.drawSyllables(g, now, visible);
    this.drawVoice(g, now);        // tu voz siempre visible, por encima de todo
    this.drawParticles();
    this.drawHud(g);
    if (s.paused) {
      ctx.fillStyle = rgba(this.c.bg, 0.8);
      ctx.fillRect(0, 0, g.w, g.h);
      this.text('En pausa', g.w / 2, g.h / 2 - this.px(20), this.font(40, 600), this.c.text, 'center');
      this.text('Espacio para seguir', g.w / 2, g.h / 2 + this.px(24), this.font(18), this.c.muted, 'center');
    }
  }

  text(str, x, y, font, color, align = 'left', baseline = 'middle') {
    const ctx = this.ctx;
    ctx.font = font; ctx.fillStyle = color; ctx.textAlign = align; ctx.textBaseline = baseline;
    ctx.fillText(str, x, y);
  }

  alphaFor(unit, now) {
    if (unit.end < now) return unit.judgement === 'hit' ? 0.9 : PAST_FADE;
    return 1;
  }

  /** Trayectoria de la melodía: tramos a la altura de cada nota, unidos dentro de la palabra. */
  drawTrajectories(g, now, units) {
    const ctx = this.ctx;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    for (let i = 0; i < units.length; i++) {
      const u = units[i];
      const active = now >= u.start - 0.05 && now <= u.end && !u.hit;
      const alpha = this.alphaFor(u, now);
      ctx.strokeStyle = active ? rgba(this.c.violet, 0.95) : rgba(this.c.text, 0.18 * alpha);
      ctx.lineWidth = active ? this.px(4) : this.px(2.5);
      ctx.beginPath();
      u.events.forEach((e, k) => {
        const x0 = this.x(g, e.start, now), x1 = this.x(g, e.end, now), y = this.y(g, e.pitch);
        if (k === 0) ctx.moveTo(x0, y);
        else ctx.lineTo(x0, y);             // en un melisma, deslizamiento hasta la nota siguiente
        ctx.lineTo(x1, y);
      });
      ctx.stroke();
      // Dentro de una palabra, un trazo tenue une una sílaba con la siguiente.
      const next = units[i + 1];
      if (next && !u.lastOfWord && next.wordId === u.wordId) {
        const a = u.events[u.events.length - 1], b = next.events[0];
        ctx.strokeStyle = rgba(this.c.text, 0.1 * alpha);
        ctx.lineWidth = this.px(2);
        ctx.beginPath();
        ctx.moveTo(this.x(g, a.end, now), this.y(g, a.pitch));
        ctx.lineTo(this.x(g, b.start, now), this.y(g, b.pitch));
        ctx.stroke();
      }
    }
  }

  /** Sílabas: texto sobre su trayectoria; fondo verde que se llena al acertar. */
  drawSyllables(g, now, units) {
    const ctx = this.ctx;
    const size = 30;
    for (const u of units) {
      const x0 = this.x(g, u.start, now), x1 = this.x(g, u.end, now);
      // El texto va justo encima de su trayectoria: la línea de voz corre por debajo del texto.
      const y = this.y(g, u.events[0].pitch) - this.px(31);
      const label = u.lastOfWord ? u.text : `${u.text}-`;
      ctx.font = this.font(size, 600);
      const textW = ctx.measureText(label).width;
      const padX = this.px(12), padY = this.px(7);
      const boxW = Math.max(x1 - x0, textW) + padX * 2;
      const boxH = this.px(size) + padY * 2;
      const bx = x0 - padX, by = y - boxH / 2;
      const r = this.px(12);
      const progress = this.session.run.progress(u);
      if (u.hit) {
        const flash = this.session.flashes.find((f) => f.unit.index === u.index);
        const glow = flash ? Math.max(0, 1 - (now - flash.at) / 0.6) : 0;
        if (glow > 0) { ctx.shadowColor = rgba(this.c.green, 0.8 * glow); ctx.shadowBlur = this.px(24) * glow; }
        ctx.fillStyle = rgba(this.c.green, 0.92);
        ctx.beginPath(); ctx.roundRect(bx, by, boxW, boxH, r); ctx.fill();
        ctx.shadowBlur = 0;
        this.text(label, x0, y, this.font(size, 700), this.c.ink);
        continue;
      }
      if (progress > 0 && !u.judgement) {
        // Relleno progresivo, discreto: se va completando mientras aciertas.
        ctx.save();
        ctx.beginPath(); ctx.roundRect(bx, by, boxW, boxH, r); ctx.clip();
        ctx.fillStyle = rgba(this.c.green, 0.22);
        ctx.fillRect(bx, by, boxW * progress, boxH);
        ctx.restore();
      }
      const active = now >= u.start - 0.05 && now <= u.end;
      const upcoming = u.start > now;
      const soon = upcoming && u.start - now < 1.2;
      const color = u.end < now ? rgba(this.c.muted, PAST_FADE) : active || soon ? this.c.text : rgba(this.c.text, 0.72);
      this.text(label, x0, y, this.font(size, active ? 700 : 600), color);
    }
  }

  /** Tu voz: línea continua por encima o por debajo de la letra, del color de su estado. */
  drawVoice(g, now) {
    const ctx = this.ctx;
    const colors = { in: this.c.green, low: this.c.cyan, high: this.c.orange, none: this.c.muted };
    const trail = this.session.trail;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    let prev = null;
    for (const p of trail) {
      if (p.break || p.midi === null) { prev = null; continue; }
      if (prev && p.time - prev.time < 0.15) {
        const x0 = this.x(g, prev.time, now), x1 = this.x(g, p.time, now);
        if (x1 > -10 && x0 < g.playhead + 20) {
          const color = colors[p.state] ?? this.c.muted;
          const fade = Math.max(0.25, 1 - (now - p.time) / 5);
          ctx.strokeStyle = rgba(color, (p.state === 'none' ? 0.35 : 0.95) * fade);
          ctx.lineWidth = this.px(5);
          if (p.state !== 'none') { ctx.shadowColor = rgba(color, 0.5 * fade); ctx.shadowBlur = this.px(8); }
          ctx.beginPath();
          ctx.moveTo(x0, this.y(g, prev.midi));
          ctx.lineTo(x1, this.y(g, p.midi));
          ctx.stroke();
          ctx.shadowBlur = 0;
        }
      }
      prev = p;
    }
  }

  drawParticles() {
    const ctx = this.ctx;
    for (const p of this.particles) {
      ctx.fillStyle = rgba(p.color, 0.9 * (1 - p.age / p.life));
      ctx.beginPath(); ctx.arc(p.x, p.y, this.px(p.size), 0, Math.PI * 2); ctx.fill();
    }
  }

  /** Lo mínimo arriba y en voz baja: título, y puntos/racha en dorado. */
  drawHud(g) {
    const s = this.session;
    this.text(s.song.metadata.title, this.px(32), this.px(34), this.font(16, 600), this.c.dim);
    this.text(s.run.score.toLocaleString('es-ES'), g.w - this.px(32), this.px(34), this.font(22, 700), rgba(this.c.gold, 0.9), 'right');
    if (s.run.combo >= 3) this.text(`racha ×${s.run.combo}`, g.w - this.px(32), this.px(62), this.font(15, 600), rgba(this.c.gold, 0.75), 'right');
  }
}
