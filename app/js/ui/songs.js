// Pantalla «Canciones»: biblioteca local, reproducción, búsqueda, volumen y A–B.

import { $ } from './dom.js';
import { ABLoop, clock } from '../songs/abLoop.js';
import { listSongs } from '../songs/library.js';

const PLAY = '<svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>';
const PAUSE = '<svg viewBox="0 0 24 24"><path d="M6 5h4v14H6zM14 5h4v14h-4z"/></svg>';

export class SongsScreen {
  constructor() {
    this.audio = $('song-audio');
    this.loop = new ABLoop();
    this.objectUrls = [];
    const audio = this.audio;
    audio.volume = Number($('song-volume').value);
    $('song-play').innerHTML = PLAY;

    $('song-list').addEventListener('change', () => this.select());
    $('song-file').addEventListener('change', (e) => this.openFile(e.target.files[0]));
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
    audio.addEventListener('error', () => { $('song-status').textContent = 'No se pudo reproducir el audio.'; });
  }

  async load() {
    const songs = await listSongs();
    const list = $('song-list');
    list.innerHTML = '';
    for (const song of songs) list.add(new Option(song.name, song.url));
    if (!songs.length) list.add(new Option('No hay audios en la carpeta «canciones»', ''));
    this.select();
  }

  select() {
    const list = $('song-list');
    this.audio.pause();
    this.loop.reset();
    $('loop').checked = false;
    $('loop').disabled = true;
    $('segment').textContent = 'Elige un inicio y un final para practicar por partes.';
    $('song-status').textContent = '';
    const option = list.selectedOptions[0];
    $('song-title').textContent = option?.value ? option.text : 'Añade audio a la carpeta «canciones»';
    if (option?.value) this.audio.src = option.value;
  }

  openFile(file) {
    if (!file) return;
    const url = URL.createObjectURL(file);
    this.objectUrls.push(url);
    const list = $('song-list');
    [...list.options].filter((o) => !o.value).forEach((o) => o.remove());
    list.add(new Option(file.name.replace(/\.[^.]+$/, ''), url));
    list.selectedIndex = list.options.length - 1;
    this.select();
  }

  toggle() {
    const audio = this.audio;
    if (!audio.src) return;
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
