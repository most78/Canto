// Utilidades mínimas de DOM.

export const $ = (id) => document.getElementById(id);

export function el(tag, className = '', text = '') {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

const TONES = ['neutral', 'quiet', 'target', 'hit', 'low', 'high', 'reward', 'special', 'warn', 'dim'];

/** Cambia el color semántico de un elemento (ver .tone-* en tokens.css). */
export function setTone(node, tone) {
  for (const t of TONES) node.classList.toggle(`tone-${t}`, t === tone);
}
