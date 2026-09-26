// Arranque de Canto: estado, audio, pantallas, navegación y teclado.

import { audioContext, resumeAudio } from './audio/context.js';
import { Microphone } from './audio/mic.js';
import { Piano } from './audio/piano.js';
import { ScalesSession } from './exercises/scales.js';
import { Progress, importLegacyProgress } from './state/progress.js';
import { $ } from './ui/dom.js';
import { ScalesScreens } from './ui/scales.js';
import { SongsScreen } from './ui/songs.js';

const progress = Progress.load();
const piano = new Piano();
const session = new ScalesSession({ progress, piano, clock: () => audioContext().currentTime });
const mic = new Microphone((stamp, duration, frequency, level) => session.feed(stamp, duration, frequency, level));
const songs = new SongsScreen();
let section = 'scales';

/** Tras un gesto del usuario el audio puede arrancar. */
async function withAudio(fn) {
  await resumeAudio();
  fn();
}

async function toggleMic() {
  if (mic.active) {
    mic.stop();
    session.setMic(false, 'Micrófono desactivado.');
  } else {
    try {
      const name = await mic.start($('devices').value);
      await refreshDevices();
      session.setMic(true, `Escuchando${name ? ` · ${name}` : ''}. Tu voz no se graba ni se envía.`);
    } catch (error) {
      const denied = error?.name === 'NotAllowedError';
      session.setMic(false, denied
        ? 'El navegador no tiene permiso para el micrófono. Pulsa el candado de la barra de direcciones y permítelo.'
        : `No se pudo abrir el micrófono: ${error?.message ?? error}`);
    }
  }
  const pill = $('mic-pill');
  pill.querySelector('.dot').classList.toggle('on', mic.active);
  pill.lastElementChild.textContent = mic.active ? 'Micro activo' : 'Micro apagado';
}

mic.onEnded = () => {
  mic.stop();
  session.setMic(false, 'El micrófono se ha desconectado.');
  $('mic-pill').querySelector('.dot').classList.remove('on');
  $('mic-pill').lastElementChild.textContent = 'Micro apagado';
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

const screens = new ScalesScreens(session, { toggleMic, withAudio });

// ------------------------------------------------------------ navegación
function show() {
  const scales = section === 'scales';
  $('screen-setup').hidden = !(scales && session.screen === 'setup');
  $('screen-play').hidden = !(scales && session.screen === 'play');
  $('screen-results').hidden = !(scales && session.screen === 'results');
  $('screen-songs').hidden = scales;
  document.querySelectorAll('[data-nav]').forEach((b) => b.classList.toggle('active', b.dataset.nav === section));
  const playing = scales && session.screen === 'play';
  document.body.classList.toggle('focus', playing);   // al cantar, sólo la pista
  if (playing) screens.startLoop(); else screens.stopLoop();
}

function go(target) {
  section = target;
  if (target === 'scales') songs.pause();             // la canción nunca suena mientras se practica
  session.setVisible(target === 'scales' && !document.hidden);
  show();
}

document.querySelectorAll('[data-nav]').forEach((b) => b.addEventListener('click', () => go(b.dataset.nav)));
session.addEventListener('screen', show);
document.addEventListener('visibilitychange', () => session.setVisible(section === 'scales' && !document.hidden));

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
    if (section === 'songs') songs.toggle();
    else withAudio(() => session.primaryAction());
  } else if (event.code === 'Escape') {
    session.escapeAction();
  }
});
// Los botones no se quedan con el foco: así la barra espaciadora no los repite.
document.addEventListener('mouseup', (event) => {
  if (event.target.closest('button')) event.target.closest('button').blur();
});

// ------------------------------------------------------------ arranque
(async () => {
  show();
  refreshDevices();
  songs.load();
  if (await importLegacyProgress(progress)) {
    session.levelIndex = progress.unlocked;
    session.findText = 'Tu nota guardada (importada de la versión anterior). Puedes buscar otra cuando quieras.';
    session.findProgress = 1;
    session.emit('change');
  }
  try {
    await piano.load();
  } catch (error) {
    session.micStatus = `Piano no disponible (${error.message}); se usará un tono simple.`;
    session.emit('change');
  }
})();

// Para depurar desde la consola del navegador.
window.canto = { session, mic, piano, progress };
