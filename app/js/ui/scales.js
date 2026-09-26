// Pantallas del ejercicio «Escalas»: preparar, jugar y resultado.
// Sólo presentación: la lógica vive en exercises/scales.js.

import { $, el, setTone } from './dom.js';
import { TrackRenderer } from './track.js';
import { renderVoiceMap } from './voicemap.js';
import { LEVELS } from '../game/levels.js';

export class ScalesScreens {
  /**
   * @param session   ScalesSession
   * @param actions   {toggleMic(), withAudio(fn)} — withAudio despierta el audio tras un gesto
   */
  constructor(session, actions) {
    this.session = session;
    this.actions = actions;
    this.track = new TrackRenderer($('track'), session.clock);
    this.frame = null;

    // --- preparar ---
    $('mic-toggle').addEventListener('click', () => actions.toggleMic());
    $('find').addEventListener('click', () => actions.withAudio(() => session.startFinding()));
    $('listen').addEventListener('click', () => actions.withAudio(() => session.listen()));
    $('start').addEventListener('click', () => actions.withAudio(() => session.startRun()));
    const levels = $('levels');
    LEVELS.forEach((level, i) => {
      const b = el('button', 'option');
      b.append(el('span', 'num', String(i + 1)), el('span', '', level.name));
      b.addEventListener('click', () => session.selectLevel(i));
      levels.append(b);
    });

    // --- jugar ---
    $('pause').addEventListener('click', () => actions.withAudio(() => session.togglePause()));
    $('play-listen').addEventListener('click', () => actions.withAudio(() => session.listen()));
    $('quit').addEventListener('click', () => session.endEarly());

    // --- resultado ---
    $('comfort-yes').addEventListener('click', () => session.answerComfort(true));
    $('comfort-no').addEventListener('click', () => session.answerComfort(false));
    $('again').addEventListener('click', () => actions.withAudio(() => session.startRun()));
    $('next-level').addEventListener('click', () => session.nextLevel());
    $('change-level').addEventListener('click', () => session.backToSetup());

    session.addEventListener('change', () => this.renderSetup());
    session.addEventListener('message', (e) => this.renderMessage(e.detail));
    session.addEventListener('judgement', (e) => this.track.judgement(e.detail.index, e.detail.judgement));
    session.addEventListener('results', (e) => this.renderResults(e.detail));
    session.addEventListener('round', (e) => {
      this.track.setRun(session.run, session.anchorMidi, `Nivel ${e.detail.levelIndex + 1} · ${e.detail.level.name}`);
      $('banner').innerHTML = '&nbsp;';
    });
    this.renderSetup();
  }

  // ---------------------------------------------------------------- preparar
  renderSetup() {
    const v = this.session.setupView();
    document.querySelectorAll('.step').forEach((step) => step.classList.toggle('active', Number(step.dataset.step) === v.step));
    $('mic-toggle').textContent = v.micOn ? 'Desactivar micrófono' : 'Activar micrófono';
    $('mic-toggle').classList.toggle('primary', !v.micOn);
    $('devices').disabled = v.micOn;
    $('mic-status').textContent = v.micStatus;
    $('find-text').textContent = v.findText;
    $('note-big').textContent = v.noteLabel;
    $('note-big').classList.toggle('idle', !v.noteHz);
    $('note-hz').innerHTML = v.noteHz || '&nbsp;';
    $('find-meter').style.width = `${Math.round(v.findProgress * 100)}%`;
    $('hearing').innerHTML = v.hearing || '&nbsp;';
    $('find').disabled = !v.canFind;
    $('find').textContent = v.findLabel;
    $('find').classList.toggle('primary', v.micOn && v.noteHz === '');
    $('listen').disabled = !v.canListen;
    [...$('levels').children].forEach((b, i) => {
      const level = v.levels[i];
      b.disabled = !level.unlocked;
      b.classList.toggle('selected', level.selected);
      b.title = level.unlocked ? '' : 'Se desbloquea al superar el nivel anterior';
    });
    $('level-text').textContent = v.levelDescription;
    $('preview').textContent = v.preview.join(' · ');
    $('range-needed').textContent = v.rangeNeeded;
    $('range-text').textContent = v.rangeText;
    $('start').disabled = !v.canStart;
  }

  // ---------------------------------------------------------------- jugar
  renderMessage(message) {
    const banner = $('banner');
    banner.textContent = message.text || ' ';
    setTone(banner, message.tone);
    const paused = this.session.paused;
    $('pause').textContent = paused ? 'Seguir' : 'Pausa';
    $('play-listen').disabled = !paused;
  }

  startLoop() {
    if (this.frame !== null) return;
    const loop = () => {
      this.session.tick();
      this.track.step();
      this.track.draw();
      this.frame = requestAnimationFrame(loop);
    };
    this.track.resize();
    this.frame = requestAnimationFrame(loop);
  }

  stopLoop() {
    if (this.frame !== null) cancelAnimationFrame(this.frame);
    this.frame = null;
  }

  // ---------------------------------------------------------------- resultado
  renderResults(r) {
    const shown = r.stars ?? 0;
    $('stars').innerHTML = `<span class="on">${'★'.repeat(shown)}</span><span class="off">${'★'.repeat(3 - shown)}</span>`;
    $('result-title').textContent = r.title;
    $('result-score').textContent = `${r.score.toLocaleString('es-ES')} puntos`;
    $('result-level').textContent = r.levelLabel;
    $('result-headline').textContent = r.headline;

    const attempts = $('attempts');
    attempts.innerHTML = '';
    for (const a of r.attempts) {
      const row = el('div', 'attempt');
      const pct = el('span', 'pct', `${Math.round(a.score * 100)} %`);
      setTone(pct, a.score >= 0.8 - 1e-9 ? 'reward' : 'quiet');
      const notes = el('span', 'notes');
      for (const n of a.notes) {
        const name = el('span', n.hit ? 'j-hit' : `j-${n.judgement}`, n.name);
        name.title = n.text;
        notes.append(name);
      }
      row.append(el('span', 'label', `Intento ${a.number}`), pct, notes);
      attempts.append(row);
    }

    const lines = [];
    if (r.inZone !== null) lines.push(`El <b>${Math.round(r.inZone * 100)} %</b> del tiempo que cantaste estuvo dentro de la nota.`);
    if (r.tendency !== null) {
      lines.push(`Tendencia: un poco <b class="${r.tendency < 0 ? 'tone-low' : 'tone-high'}">${r.tendency < 0 ? 'grave' : 'aguda'}</b> (${Math.abs(Math.round(r.tendency))} cents; 100 cents = 1 semitono).`);
    }
    if (r.noSignal) lines.push('Revisa el micrófono o acércate un poco. No hace falta cantar más fuerte.');
    if (r.unlocked) lines.push(`<b class="tone-special">Desbloqueado: ${r.unlocked}</b>`);
    $('result-lines').innerHTML = lines.join('<br>');

    renderVoiceMap($('voicemap'), this.session.progress, r.played);
    $('comfort-yes').disabled = !r.canRate || r.comfortAnswered;
    $('comfort-no').disabled = !r.canRate || r.comfortAnswered;
    $('comfort-note').textContent = r.comfortNote;
    setTone($('comfort-note'), r.comfortTone);
    $('next-level').disabled = !r.canNext;
  }
}
