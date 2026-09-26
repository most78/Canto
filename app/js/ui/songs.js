// Reproductor de escucha de la sección Canciones: reproducir, buscar, volumen y A–B.
// La canción la elige la lista del catálogo (ui/sing.js).

import { $ } from './dom.js';
import { ABLoop, clock } from '../songs/abLoop.js';

const PLAY = '<svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>';
const PAUSE = '<svg viewBox="0 0 24 24"><path d="M6 5h4v14H6zM14 5h4v14h-4z"/></svg>';

export class ListenPlayer {
  constructor() {
    this.audio = $('song-audio');
    this.loop = new ABLoop();
    const audio = this.audio;
    audio.volume = Number($('song-volume').value);
    $('song-play').innerHTML = PLAY;

    $('song-play').addEventListener('click', () => this.toggle());
    $('song-seek').addEventListener('input', (e) => { audio.currentTime = Number(e.target.value); });
    $('song-volume').addEventListener('input', (e) => { audio.volume = Number(e.target.value); });
    $('mark-a').addEventListener('click', () => this.setA());
    $('mark-b').addEventListener('click', () => this.setB());
    $('loop').addEventListener('change', (e) => { this.loop.enabled = e.target.checked; });

    audio.addEventListener('loadedmetadata', () => { $('song-seek').max = audio.duration || 0; this.showTime(); });
    audio.addEventListener('timeupdate', () => this.onTime());
    audio.addEventListener('play', () => { $('song-play').innerHTML = PAUSE; });
    audio.addEventListener('pause', () => { $('song-play').innerHTML = PLAY; });
    audio.addEventListener('error', () => { if (audio.src) $('song-status').textContent = 'No se pudo reproducir el audio.'; });
  }

  /** Cambia de audio (null = esta canción no tiene archivo que escuchar). */
  setSource(url) {
    this.audio.pause();
    this.loop.reset();
    $('loop').checked = false;
    $('loop').disabled = true;
    $('segment').textContent = 'Elige un inicio y un final para practicar por partes.';
    $('song-status').textContent = '';
    $('listen-player').hidden = !url;
    if (url) this.audio.src = url;
    else this.audio.removeAttribute('src');
  }

  toggle() {
    const audio = this.audio;
    if (!audio.getAttribute('src')) return;
    if (!audio.paused) { audio.pause(); return; }
    const jump = this.loop.startPosition(audio.currentTime);
    if (jump !== null) audio.currentTime = jump;
    audio.play().catch(() => { $('song-status').textContent = 'No se pudo reproducir el audio.'; });
  }

  pause() { this.audio.pause(); }

  setA() {
    $('segment').textContent = this.loop.setA(this.audio.currentTime);
    $('loop').checked = false;
    $('loop').disabled = true;
  }

  setB() {
    const [ok, message] = this.loop.setB(this.audio.currentTime);
    if (!ok) { $('song-status').textContent = message; return; }
    $('song-status').textContent = '';
    $('segment').textContent = message;
    $('loop').disabled = false;
  }

  onTime() {
    const jump = this.loop.wrap(this.audio.currentTime);
    if (jump !== null) {
      this.audio.currentTime = jump;
      this.audio.play();
    }
    if (document.activeElement !== $('song-seek')) $('song-seek').value = this.audio.currentTime;
    this.showTime();
  }

  showTime() {
    $('song-time').textContent = `${clock(this.audio.currentTime)} / ${clock(this.audio.duration)}`;
  }
}
