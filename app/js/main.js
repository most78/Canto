// Arranque de Canto: estado, audio, pantallas, navegación y teclado.

import { audioContext, resumeAudio } from './audio/context.js';
import { Microphone } from './audio/mic.js';
import { Piano } from './audio/piano.js';
import { ScalesSession } from './exercises/scales.js';
import { SingSession } from './exercises/singSong.js';
import { SongPlayer } from './songs/playback.js';
import { Progress, importLegacyProgress } from './state/progress.js';
import { SongStats } from './state/songStats.js';
import { $ } from './ui/dom.js';
import { ScalesScreens } from './ui/scales.js';
import { ListenPlayer } from './ui/songs.js';
import { SingScreens } from './ui/sing.js';

const clock = () => audioContext().currentTime;
const progress = Progress.load();
const piano = new Piano();
const scales = new ScalesSession({ progress, piano, clock });
const sing = new SingSession({
  progress, stats: new SongStats(), player: new SongPlayer(piano), clock,
  outputLatency: () => audioContext().outputLatency || audioContext().baseLatency || 0,
});
// El micrófono alimenta a los dos ejercicios; cada uno ignora lo que no le toca.
const mic = new Microphone((stamp, duration, frequency, level) => {
  scales.feed(stamp, duration, frequency, level);
  sing.feed(stamp, duration, frequency, level);
});
const listen = new ListenPlayer();
let section = 'scales';

/** Tras un gesto del usuario el audio puede arrancar. */
async function withAudio(fn) {
  await resumeAudio();
  return fn();
}

function setMicState(on, message) {
  scales.setMic(on, message);
  sing.setMic(on);
  const pill = $('mic-pill');
  pill.querySelector('.dot').classList.toggle('on', on);
  pill.lastElementChild.textContent = on ? 'Micro activo' : 'Micro apagado';
}

async function toggleMic() {
  if (mic.active) {
    mic.stop();
    setMicState(false, 'Micrófono desactivado.');
    return;
  }
  try {
    const name = await mic.start($('devices').value);
    await refreshDevices();
    setMicState(true, `Escuchando${name ? ` · ${name}` : ''}. Tu voz no se graba ni se envía.`);
  } catch (error) {
    const denied = error?.name === 'NotAllowedError';
    setMicState(false, denied
      ? 'El navegador no tiene permiso para el micrófono. Pulsa el candado de la barra de direcciones y permítelo.'
      : `No se pudo abrir el micrófono: ${error?.message ?? error}`);
  }
}

mic.onEnded = () => {
  mic.stop();
  setMicState(false, 'El micrófono se ha desconectado.');
};

async function refreshDevices() {
  const select = $('devices');
  const current = select.value;
  try {
    const devices = await Microphone.devices();
    select.innerHTML = '';
    select.add(new Option('Micrófono predeterminado', ''));
    devices.filter((d) => d.deviceId && d.deviceId !== 'default').forEach((d, i) => {
      select.add(new Option(d.label || `Micrófono ${i + 1}`, d.deviceId));
    });
    select.value = [...select.options].some((o) => o.value === current) ? current : '';
  } catch { /* sin acceso a dispositivos */ }
}

const scalesScreens = new ScalesScreens(scales, { toggleMic, withAudio });
const singScreens = new SingScreens(sing, listen, { toggleMic, withAudio });

// ------------------------------------------------------------ navegación
function show() {
  const inScales = section === 'scales';
  $('screen-setup').hidden = !(inScales && scales.screen === 'setup');
  $('screen-play').hidden = !(inScales && scales.screen === 'play');
  $('screen-results').hidden = !(inScales && scales.screen === 'results');
  $('screen-songs').hidden = !(!inScales && sing.screen === 'pick');
  $('screen-sing').hidden = !(!inScales && sing.screen === 'sing');
  $('screen-song-results').hidden = !(!inScales && sing.screen === 'results');
  document.querySelectorAll('[data-nav]').forEach((b) => b.classList.toggle('active', b.dataset.nav === section));
  const playingScales = inScales && scales.screen === 'play';
  const singing = !inScales && sing.screen === 'sing';
  document.body.classList.toggle('focus', playingScales || singing);   // al cantar, sólo la pista
  if (playingScales) scalesScreens.startLoop(); else scalesScreens.stopLoop();
  if (singing) singScreens.startLoop(); else singScreens.stopLoop();
}

function updateVisibility() {
  scales.setVisible(section === 'scales' && !document.hidden);
  sing.setVisible(section === 'songs' && !document.hidden);
}

function go(target) {
  section = target;
  if (target === 'scales') listen.pause();            // nada suena mientras se practica
  updateVisibility();
  show();
}

document.querySelectorAll('[data-nav]').forEach((b) => b.addEventListener('click', () => go(b.dataset.nav)));
scales.addEventListener('screen', show);
sing.addEventListener('screen', show);
document.addEventListener('visibilitychange', updateVisibility);

$('fullscreen').addEventListener('click', () => {
  if (document.fullscreenElement) document.exitFullscreen();
  else document.documentElement.requestFullscreen();
});
document.addEventListener('fullscreenchange', () => {
  $('fullscreen').textContent = document.fullscreenElement ? 'Salir de pantalla completa' : 'Pantalla completa';
});

// ------------------------------------------------------------ teclado
document.addEventListener('keydown', (event) => {
  const typing = ['INPUT', 'SELECT', 'TEXTAREA'].includes(event.target.tagName) && event.target.type !== 'range';
  if (event.code === 'Space' && !typing) {
    event.preventDefault();
    if (section === 'scales') withAudio(() => scales.primaryAction());
    else if (sing.screen === 'sing') withAudio(() => sing.togglePause());
    else if (sing.screen === 'pick') listen.toggle();
  } else if (event.code === 'Escape') {
    if (section === 'scales') scales.escapeAction();
    else if (sing.screen === 'sing' && sing.player.playing) sing.togglePause();
  }
});
// Los botones no se quedan con el foco: así la barra espaciadora no los repite.
document.addEventListener('mouseup', (event) => {
  event.target.closest('button')?.blur();
});

// ------------------------------------------------------------ arranque
(async () => {
  show();
  updateVisibility();
  refreshDevices();
  singScreens.load();
  if (await importLegacyProgress(progress)) {
    scales.levelIndex = progress.unlocked;
    scales.findText = 'Tu nota guardada (importada de la versión anterior). Puedes buscar otra cuando quieras.';
    scales.findProgress = 1;
    scales.emit('change');
  }
  try {
    await piano.load();
  } catch (error) {
    scales.micStatus = `Piano no disponible (${error.message}); se usará un tono simple.`;
    scales.emit('change');
  }
})();

// Para depurar desde la consola del navegador.
window.canto = { scales, sing, mic, piano, progress, session: scales };
