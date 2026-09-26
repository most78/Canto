// Ejercicio «Escalas»: preparar (micro, tu nota, nivel) → ronda → resultado.
// Port de la lógica de legacy/src/ui/practice.py, SIN DOM: la interfaz sólo
// lee `setupView()`, `message`, `resultsView()` y escucha eventos.
//
// Eventos: 'change' (estado de preparación), 'screen', 'message', 'judgement'
// (detail: {index, judgement}), 'results'.

import { LEVELS, placements } from '../game/levels.js';
import { HITS, JUDGEMENT_TEXT, buildRound, classify } from '../game/noteRun.js';
import { ReferenceFinder } from '../game/reference.js';
import { midiFrequency, nearestMidi, noteName } from '../pitch/notes.js';

export const NO_DATA_AFTER = 1.2;    // sin bloques del micro = aviso
export const MESSAGE_HOLD = 0.6;     // una indicación de afinación se lee al menos esto
export const LISTEN_SECONDS = 1.2;   // «Escuchar mi nota»
export const CUE_LOOKAHEAD = 0.12;   // el piano se programa un poco antes para ir exacto
const PITCH_MESSAGES = new Set(['hit', 'low', 'high', 'unclear']);

export class ScalesSession extends EventTarget {
  /**
   * @param progress  Progress (state/progress.js)
   * @param piano     objeto con phrase(notes, when) y stopAll()
   * @param clock     función → segundos (reloj del AudioContext)
   */
  constructor({ progress, piano, clock }) {
    super();
    this.progress = progress;
    this.piano = piano;
    this.clock = clock;
    this.finder = new ReferenceFinder();
    this.finding = false;
    this.findText = progress.anchor_midi !== null
      ? 'Tu nota guardada. Puedes buscar otra cuando quieras.'
      : 'Haz una «u» o un «do» cómodo durante un segundo y para. Las escalas se colocarán alrededor de esa nota.';
    this.hearing = '';
    this.findProgress = progress.anchor_midi !== null ? 1 : 0;
    this.micOn = false;
    this.micStatus = 'Tu voz no se graba ni se envía.';
    this.visible = true;
    this.screen = 'setup';
    this.run = null;
    this.levelIndex = progress.unlocked;
    this.roundLevel = null;
    this.lastBlock = null;
    this.toneUntil = 0;
    this.message = { key: null, text: '', tone: 'neutral', pitch: false, since: 0 };
    this.results = null;
  }

  emit(type, detail) { this.dispatchEvent(new CustomEvent(type, { detail })); }

  get anchorMidi() { return this.progress.anchor_midi; }
  get frequency() { return this.anchorMidi !== null ? midiFrequency(this.anchorMidi) : null; }

  setScreen(screen) {
    if (this.screen === screen) return;
    this.screen = screen;
    this.emit('screen', screen);
  }

  // ================================================================ preparar
  setupView() {
    const found = this.anchorMidi !== null;
    const level = LEVELS[this.levelIndex];
    const starts = found ? placements(level, this.progress.lo, this.progress.hi) : [];
    const [low, high] = found ? this.progress.rangeMidi() : [null, null];
    return {
      step: !this.micOn ? 0 : (!found || this.finding) ? 1 : 2,
      micOn: this.micOn,
      micStatus: this.micStatus,
      finding: this.finding,
      findText: this.findText,
      hearing: this.hearing,
      findProgress: this.findProgress,
      noteLabel: found && !this.finding ? noteName(this.anchorMidi) : (this.finding ? '…' : '—'),
      noteHz: found && !this.finding ? `${Math.round(this.frequency)} Hz` : '',
      canFind: this.micOn && !this.finding,
      findLabel: this.finding ? 'Escuchando…' : found ? 'Buscar otra' : 'Encontrar mi nota',
      canListen: found && !this.finding,
      levels: LEVELS.map((lv, i) => ({ name: lv.name, index: i, unlocked: i <= this.progress.unlocked, selected: i === this.levelIndex })),
      levelDescription: `${level.description} Margen ±${level.tolerance} cents.`,
      preview: found && starts.length ? level.pattern.map((k) => noteName(this.anchorMidi + starts[0] + k)) : [],
      rangeNeeded: found && !starts.length
        ? `Necesita ${level.span + 1} notas de rango y ahora tienes ${this.progress.hi - this.progress.lo + 1}. Tu rango crece al acertar los bordes y decir que fue cómodo.`
        : '',
      rangeText: found ? `Tu rango de trabajo: ${noteName(low)} – ${noteName(high)} (${high - low + 1} notas)` : 'Primero encuentra tu nota de partida.',
      canStart: found && this.micOn && !this.finding && starts.length > 0,
    };
  }

  selectLevel(index) {
    if (index <= this.progress.unlocked) this.levelIndex = index;
    this.emit('change');
  }

  setMic(on, status) {
    this.micOn = on;
    this.lastBlock = null;
    if (status) this.micStatus = status;
    if (!on) {
      if (this.finding) {
        this.finding = false;
        this.findText = 'Micrófono desactivado. Actívalo para buscar tu nota.';
      }
      if (this.run?.state === 'running') {
        this.run.pause(this.clock());
        this.piano.stopAll();
        this.showMessage('nomic', 'Micrófono desactivado · actívalo para seguir', 'warn', { force: true });
      }
    }
    this.emit('change');
  }

  /** La página deja de verse (otra sección o pestaña oculta): pausa. */
  setVisible(visible) {
    this.visible = visible;
    if (!visible && this.run?.state === 'running') {
      this.run.pause(this.clock());
      this.piano.stopAll();
      this.showPauseMessage();
    }
    if (!visible && this.finding) {
      this.finding = false;
      this.findText = 'Búsqueda detenida. Pulsa «Encontrar mi nota» cuando quieras.';
      this.emit('change');
    }
  }

  startFinding() {
    if (!this.micOn) return;
    this.finder.reset();
    this.finding = true;
    this.findProgress = 0;
    this.hearing = '';
    this.findText = 'Haz una «u» o un «do» cómodo de un segundo y después para. Termina sola en 4 s como máximo.';
    this.setScreen('setup');
    this.emit('change');
  }

  feedFinder(stamp, duration, frequency, level) {
    if (stamp < this.toneUntil) return;
    const [kind] = classify(frequency, level, frequency || 1);
    this.hearing = { silence: 'Silencio', unclear: 'Oigo sonido, pero sin nota clara', hit: '♪ Te oigo' }[kind] ?? '';
    const result = this.finder.feed(frequency, level, stamp, duration);
    this.findProgress = this.finder.progress;
    if (result !== null) {
      this.finding = false;
      const midi = nearestMidi(result);
      this.progress.setAnchor(midi);
      this.progress.save();
      const off = Math.round(1200 * Math.log2(result / midiFrequency(midi)));
      this.hearing = `Cantaste ${Math.round(result)} Hz (${off >= 0 ? '+' : ''}${off} cents); ajustada a la nota más cercana.`;
      this.findText = 'Escúchala al piano. Si no te resulta cómoda, busca otra.';
    } else if (this.finder.failed) {
      this.finding = false;
      const [reason, action] = this.finder.failed;
      this.findProgress = this.anchorMidi !== null ? 1 : 0;
      this.findText = `Paramos aquí. ${reason} ${action}`;
      this.hearing = this.finder.diagnostic();
    }
    this.emit('change');
  }

  // ================================================================ ronda
  startRun() {
    if (this.anchorMidi === null || !this.micOn) return;
    const level = LEVELS[this.levelIndex];
    const starts = placements(level, this.progress.lo, this.progress.hi);
    if (!starts.length) return;
    this.piano.stopAll();
    this.roundLevel = this.levelIndex;
    this.run = buildRound(this.frequency, level.pattern, starts, level.noteLen, level.tolerance);
    this.message = { key: null, text: '', tone: 'neutral', pitch: false, since: 0 };
    this.results = null;
    this.run.start(this.clock());
    this.lastBlock = this.clock();
    this.setScreen('play');
    this.emit('round', { level, levelIndex: this.levelIndex });
  }

  togglePause() {
    if (!this.run) return;
    const now = this.clock();
    if (this.run.state === 'running') {
      this.run.pause(now);
      this.piano.stopAll();
      this.showPauseMessage();
    } else if (this.run.state === 'paused' && this.micOn) {
      this.run.resume(now);
      this.lastBlock = now;
      this.message.key = null;
      this.emit('message', this.message);
    }
  }

  get paused() { return this.run?.state === 'paused'; }

  showPauseMessage() {
    this.showMessage('paused', 'En pausa · el tiempo está detenido', 'neutral', { force: true });
  }

  endEarly() {
    if (this.run && (this.run.state === 'running' || this.run.state === 'paused')) {
      this.run.stop(this.clock());
      this.piano.stopAll();
      this.finishRound();
    }
  }

  /** Barra espaciadora: la acción principal de la vista actual. */
  primaryAction() {
    if (this.screen === 'play') return this.togglePause();
    if (this.screen === 'results') return this.startRun();
    const view = this.setupView();
    if (view.canStart) return this.startRun();
    if (view.canFind) return this.startFinding();
    return undefined;
  }

  escapeAction() {
    if (this.screen === 'play' && this.run?.state === 'running') {
      this.togglePause();
      return true;
    }
    return false;
  }

  listen() {
    if (this.frequency === null) return;
    if (this.run?.state === 'running') return;   // durante la ronda el piano lo programa el juego
    const now = this.clock();
    this.toneUntil = now + LISTEN_SECONDS + 0.6;
    this.piano.phrase([[0, this.frequency, LISTEN_SECONDS]], now + 0.03);
  }

  /** Un bloque analizado del micrófono (marca de final en el reloj de audio). */
  feed(stamp, duration, frequency, level) {
    this.lastBlock = this.clock();
    if (!this.visible) return;
    if (this.finding) this.feedFinder(stamp, duration, frequency, level);
    else if (this.run?.state === 'running') this.run.feed(stamp, duration, frequency, level);
  }

  /** Llamado en cada fotograma: piano, juicios y mensajes. */
  tick() {
    const run = this.run;
    if (!run || run.state !== 'running') return;
    const now = this.clock();
    for (const cue of run.dueCues(now + CUE_LOOKAHEAD)) {
      const notes = cue.notes.map(([offset, k, d]) => [offset, this.frequency * 2 ** (k / 12), d]);
      this.piano.phrase(notes, Math.max(now, run.origin + cue.time));
    }
    for (const [index, judgement] of run.update(now)) this.emit('judgement', { index, judgement });
    if (run.state === 'finished') {
      this.finishRound();
      return;
    }
    this.updateMessage(now);
  }

  updateMessage(now) {
    const run = this.run;
    if (this.lastBlock !== null && now - this.lastBlock > NO_DATA_AFTER) {
      this.showMessage('nodata', 'No llegan datos del micrófono · revisa la conexión', 'warn', { now });
      return;
    }
    const [phase, attempt] = run.phase(now);
    if (phase === 'intro') {
      this.showMessage('intro', 'Primero escucha al piano (no puntúa)', 'quiet', { now });
    } else if (phase === 'listen') {
      this.showMessage(`listen${attempt}`, 'Escucha… (no puntúa)', 'quiet', { now });
    } else if (phase === 'turn') {
      const first = run.sung.find((n) => n.attempt === attempt);
      this.showMessage(`turn${attempt}`, `¡Tu turno! Empieza en ${noteName(this.anchorMidi + first.semitone)}`, 'special', { now });
    } else if (phase === 'sing') {
      const index = run.activeNote(now);
      if (index === null) return;
      const name = noteName(this.anchorMidi + run.notes[index].semitone);
      const hint = run.hint(now);
      if (hint === null) return;
      const [text, tone] = {
        hit: [`¡Ahí! ${name}`, 'hit'],
        low: [`${name} · un poco más agudo  ▲`, 'low'],
        high: [`${name} · un poco más grave  ▼`, 'high'],
        unclear: ['No te oigo claro · no cuenta como fallo', 'quiet'],
        muted: ['Suena el piano · no puntúa', 'quiet'],
        free: [`Canta: ${name}`, 'target'],
        silence: [`Canta: ${name}`, 'target'],
      }[hint];
      this.showMessage(`${hint}${index}`, text, tone, { now, pitch: PITCH_MESSAGES.has(hint) });
    } else if (phase === 'rest') {
      this.showMessage(`rest${attempt}`, 'Respira… el piano tocará el siguiente intento', 'quiet', { now });
    } else {
      this.showMessage('end', '¡Ronda terminada!', 'reward', { now });
    }
  }

  showMessage(key, text, tone, { now = this.clock(), force = false, pitch = false } = {}) {
    const m = this.message;
    if (!force && key === m.key) return;
    // Dos indicaciones de afinación seguidas: la primera se lee al menos MESSAGE_HOLD.
    if (!force && pitch && m.pitch && now - m.since < MESSAGE_HOLD) return;
    this.message = { key, text, tone, pitch, since: now };
    this.emit('message', this.message);
  }

  // ================================================================ resultado
  finishRound() {
    const run = this.run;
    const s = run.summary();
    const measured = run.sung
      .filter((n) => n.judgement && n.judgement !== 'unclear' && n.judgement !== 'silent')
      .map((n) => [this.anchorMidi + n.semitone, n.ratio]);
    const unlockedNew = measured.length ? this.progress.recordRound(this.roundLevel, s, measured) : false;
    const passes = s.attemptScores.filter((x) => x >= 0.8 - 1e-9).length;
    let title;
    if (s.stars === null) title = 'No he podido oírte bien';
    else if (s.passed) title = s.stars < 3 ? '¡Nivel superado!' : '¡Perfecto!';
    else title = passes === 1 ? '¡Casi!' : '¡Sigue probando!';
    const level = LEVELS[this.roundLevel];
    this.results = {
      title,
      stars: s.stars,
      score: s.score,
      passed: s.passed,
      levelLabel: `Nivel ${this.roundLevel + 1} · ${level.name}`,
      headline: `${passes} de ${s.attemptScores.length} intentos con 80 % o más`,
      attempts: run.attempts.map((a, i) => ({
        number: a + 1,
        score: s.attemptScores[i],
        notes: run.sung.filter((n) => n.attempt === a).map((n) => ({
          name: noteName(this.anchorMidi + n.semitone),
          judgement: n.judgement ?? 'silent',
          text: JUDGEMENT_TEXT[n.judgement] ?? 'Sin jugar',
          hit: HITS.has(n.judgement),
        })),
      })),
      inZone: s.inZone,
      tendency: s.tendency !== null && Math.abs(s.tendency) >= 15 ? s.tendency : null,
      noSignal: s.stars === null,
      unlocked: unlockedNew ? `Nivel ${this.progress.unlocked + 1} · ${LEVELS[this.progress.unlocked].name}` : null,
      played: new Set(measured.map(([m]) => m)),
      canRate: measured.length > 0,
      comfortAnswered: false,
      comfortNote: '',
      comfortTone: 'quiet',
      canNext: this.roundLevel < this.progress.unlocked,
    };
    this.setScreen('results');
    this.emit('results', this.results);
  }

  answerComfort(comfortable) {
    const r = this.results;
    if (!r || r.comfortAnswered) return;
    r.comfortAnswered = true;
    if (!comfortable) {
      r.comfortNote = 'Gracias. Descansa un poco; puedes repetir un nivel anterior. Tu rango no se amplía tras una ronda incómoda.';
      r.comfortTone = 'quiet';
    } else {
      const grown = this.progress.growRange();
      if (grown.length) {
        r.comfortNote = `¡Tu rango crece! Nueva nota: ${grown.map(([side, m]) => `${noteName(m)} (${side})`).join(', ')}.`;
        r.comfortTone = 'reward';
      } else {
        const [low, high] = this.progress.rangeMidi();
        r.comfortNote = `¡Bien! Tu rango crecerá cuando afiances los bordes: ${noteName(low)} y ${noteName(high)}.`;
        r.comfortTone = 'quiet';
      }
    }
    this.emit('results', r);
  }

  nextLevel() {
    if (this.roundLevel < this.progress.unlocked) {
      this.levelIndex = this.roundLevel + 1;
      this.backToSetup();
    }
  }

  backToSetup() {
    this.setScreen('setup');
    this.emit('change');
  }
}
