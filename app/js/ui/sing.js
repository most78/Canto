// Pantallas del modo Canción: catálogo + preparar, cantar y resultado.
// Sólo presentación: la lógica vive en exercises/singSong.js.

import { $, el } from './dom.js';
import { LyricsTrack } from './lyricsTrack.js';
import { loadCatalog } from '../songs/catalog.js';

export class SingScreens {
  /**
   * @param session  SingSession
   * @param listen   ListenPlayer (escuchar y A–B)
   * @param actions  {toggleMic(), withAudio(fn)}
   */
  constructor(session, listen, actions) {
    this.session = session;
    this.listen = listen;
    this.actions = actions;
    this.entries = [];
    this.track = new LyricsTrack($('lyrics'), session);
    this.frame = null;

    $('sing-start').addEventListener('click', () => actions.withAudio(async () => {
      listen.pause();
      try { await session.start(); } catch (error) { $('song-error').textContent = `No se pudo empezar: ${error.message}`; }
    }));
    $('sing-mic').addEventListener('click', () => actions.toggleMic());
    $('lat-minus').addEventListener('click', () => session.nudgeLatency(-10));
    $('lat-plus').addEventListener('click', () => session.nudgeLatency(10));
    document.querySelectorAll('#octaves .seg').forEach((b) => b.addEventListener('click', () => session.setTranspose(Number(b.dataset.transpose))));
    $('sing-pause').addEventListener('click', () => actions.withAudio(() => session.togglePause()));
    $('sing-stop').addEventListener('click', () => session.stop());
    $('sr-again').addEventListener('click', () => actions.withAudio(() => session.start()));
    $('sr-back').addEventListener('click', () => session.backToPick());
    $('song-file').addEventListener('change', (e) => this.openFile(e.target.files[0]));

    session.addEventListener('change', () => this.renderPick());
    session.addEventListener('results', (e) => this.renderResults(e.detail));
  }

  async load() {
    this.entries = await loadCatalog();
    this.renderCatalog();
    if (this.entries.length && !this.session.entry) this.choose(this.entries[0]);
  }

  renderCatalog() {
    const list = $('song-catalog');
    list.innerHTML = '';
    for (const entry of this.entries) {
      const b = el('button', `option${entry === this.session.entry ? ' selected' : ''}`);
      b.append(el('span', '', entry.title), el('span', 'sub', entry.source === 'builtin' ? 'Canción de práctica' : entry.playable ? 'Lista para cantar' : 'Sólo escuchar · faltan datos'));
      b.addEventListener('click', () => this.choose(entry));
      list.append(b);
    }
  }

  async choose(entry) {
    this.listen.setSource(entry.audioUrl);
    await this.session.select(entry);
    this.renderCatalog();
  }

  openFile(file) {
    if (!file) return;
    const entry = { id: `file:${file.name}`, title: file.name.replace(/\.[^.]+$/, ''), source: 'file',
      audioUrl: URL.createObjectURL(file), dataUrl: null, playable: false, missing: [], expectedData: null };
    this.entries.push(entry);
    this.choose(entry);
  }

  // ---------------------------------------------------------------- preparar
  renderPick() {
    const v = this.session.pickView();
    const entry = v.entry;
    $('song-title').textContent = entry ? entry.title : 'Elige una canción';
    $('song-source').textContent = !entry ? '' : entry.source === 'builtin' ? 'Canción de práctica' : 'Tu biblioteca';
    $('song-subtitle').textContent = v.song?.metadata.license ?? v.song?.metadata.artist ?? '';
    $('song-error').textContent = v.error;
    $('sing-panel').hidden = !v.song;
    const missing = !!entry && !entry.playable;
    $('missing-panel').hidden = !missing;
    if (missing) {
      $('missing-list').innerHTML = '';
      for (const item of entry.missing.length ? entry.missing : ['Datos de letra y melodía para este audio.']) $('missing-list').append(el('li', '', item));
      $('missing-file').textContent = entry.expectedData ?? 'un archivo .canto.json junto al audio';
    }
    if (!v.song) return;

    $('part-choice').hidden = v.parts.length < 2;       // una sola voz: sin opciones de dueto
    this.segmented($('parts'), v.parts.map((p, i) => ({ label: p.label, selected: p.selected, on: () => this.session.setPart(i) })));
    this.segmented($('levels-song'), v.levels.map((l) => ({ label: l.name, selected: l.selected, on: () => this.session.setLevel(l.key) })));
    document.querySelectorAll('#octaves .seg').forEach((b) => b.classList.toggle('selected', Number(b.dataset.transpose) === v.transpose));
    $('song-suggestion').textContent = v.suggestion ? `Lo estás cantando muy bien: prueba el nivel ${v.suggestion}.` : '';
    $('song-range').textContent = v.outOfRange.length && v.rangeLabel
      ? `Fuera de tu rango cómodo (${v.rangeLabel}): «${v.outOfRange.map((f) => f.text).join('», «')}». No se cambia ninguna nota; puedes elegir otra octava.`
      : '';
    $('lat-value').textContent = `${v.adjustMs > 0 ? '+' : ''}${v.adjustMs} ms`;
    $('sing-start').disabled = !v.canSing;
    $('sing-mic').hidden = this.session.micOn;
  }

  segmented(container, items) {
    container.innerHTML = '';
    for (const item of items) {
      const b = el('button', `seg${item.selected ? ' selected' : ''}`, item.label);
      b.addEventListener('click', item.on);
      container.append(b);
    }
  }

  // ---------------------------------------------------------------- cantar
  startLoop() {
    if (this.frame !== null) return;
    this.track.resize();
    const loop = () => {
      this.session.tick();
      this.track.step();
      this.track.draw();
      $('sing-pause').textContent = this.session.paused ? 'Seguir' : 'Pausa';
      this.frame = requestAnimationFrame(loop);
    };
    this.frame = requestAnimationFrame(loop);
  }

  stopLoop() {
    if (this.frame !== null) cancelAnimationFrame(this.frame);
    this.frame = null;
  }

  // ---------------------------------------------------------------- resultado
  renderResults(r) {
    $('sr-level').textContent = `${r.title} · ${r.levelName}`;
    $('sr-title').textContent = r.hitRate >= 0.8 ? '¡Qué bien ha sonado!' : r.hitRate >= 0.5 ? '¡Buen trabajo!' : 'Cada vez te saldrá mejor';
    $('sr-hits').textContent = `${Math.round(r.hitRate * 100)} %`;
    $('sr-pitch').textContent = r.pitchAccuracy === null ? '—' : `${Math.round(r.pitchAccuracy * 100)} %`;
    $('sr-combo').textContent = String(r.bestCombo);
    $('sr-score').textContent = r.score.toLocaleString('es-ES');
    if (r.timing === null) $('sr-timing').textContent = '';
    else {
      const ms = Math.round(r.timing * 1000);
      $('sr-timing').textContent = Math.abs(ms) < 60 ? 'Entras a tiempo en las sílabas.'
        : ms > 0 ? `Sueles entrar un poco tarde (unos ${ms} ms).` : `Sueles adelantarte un poco (unos ${-ms} ms).`;
    }
    $('sr-hardest').innerHTML = '';
    if (r.hardest) {
      $('sr-hardest').append('Este fragmento fue el que más te costó: ', el('span', 'quote', `«${r.hardest.text}»`));
    }
    const extra = [];
    if (r.newBest) extra.push('Nuevo récord en esta canción.');
    if (r.suggestion) extra.push(`Cuando quieras, prueba el nivel ${r.suggestion}.`);
    $('sr-extra').textContent = extra.join(' ');
  }
}
