// Mapa de tu voz: una casilla por semitono; cuanto más verde, más la aciertas.

import { el } from './dom.js';
import { noteName } from '../pitch/notes.js';

export function renderVoiceMap(container, progress, played = new Set()) {
  container.innerHTML = '';
  if (progress.anchor_midi === null) return;
  const [low, high] = progress.rangeMidi();
  const tested = Object.keys(progress.notes).map(Number);
  const first = Math.min(low - 2, ...tested);
  const last = Math.max(high + 2, ...tested);
  for (let midi = first; midi <= last; midi++) {
    const stat = progress.stat(midi);
    const inside = low <= midi && midi <= high;
    const cell = el('div', `vm-cell${inside ? ' inside' : ''}${played.has(midi) ? ' played' : ''}`);
    const box = el('div', 'vm-box');
    if (stat) {
      // Intensidad de verde = acierto: el color es información, no decoración.
      const fill = el('div', 'vm-fill');
      fill.style.opacity = String(0.15 + 0.85 * stat.ema);
      box.append(fill);
      const value = el('span', '', String(Math.round(stat.ema * 100)));
      value.style.color = stat.ema >= 0.55 ? 'var(--ink)' : 'var(--text)';
      box.append(value);
      box.title = `${noteName(midi)}: ${Math.round(stat.ema * 100)} % de acierto (${stat.n} mediciones)`;
    }
    cell.append(box, el('div', 'vm-name', noteName(midi)), el('div', 'vm-anchor', midi === progress.anchor_midi ? '▲' : ''));
    container.append(cell);
  }
}
