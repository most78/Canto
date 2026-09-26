"""Página «Pista de voz»: preparar tu nota → jugar la secuencia → resultado."""
import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from audio.pitch import hz_to_note
from game.note_run import HITS, JUDGEMENT_TEXT, NoteRun, classify, CUE_LENGTH
from game.reference import ReferenceFinder
from ui import theme
from ui.panda import PandaBadge
from ui.theme import px
from ui.track import TrackView

NO_DATA_AFTER = 1.2        # sin bloques del micro durante este tiempo = aviso
PITCH_MESSAGES = {'hit', 'low', 'high', 'unclear'}
MESSAGE_HOLD = .6          # un mensaje de afinación se lee al menos esto


def label(text, name=None, wrap=True, align=None):
    w = QLabel(text)
    if name:
        w.setObjectName(name)
    w.setWordWrap(wrap)
    if align is not None:
        w.setAlignment(align)
    return w


def button(text, name=None):
    b = QPushButton(text)
    if name:
        b.setObjectName(name)
    b.setCursor(Qt.PointingHandCursor)
    b.setFocusPolicy(Qt.NoFocus)
    return b


def card():
    frame = QFrame()
    frame.setObjectName('card')
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(px(30), px(26), px(30), px(26))
    layout.setSpacing(px(14))
    return frame, layout


def set_prop(widget, name, value):
    widget.setProperty(name, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def note_label(frequency):
    reading = hz_to_note(frequency)
    return reading.label


def cents_words(cents):
    return f'{abs(round(cents))} cents'


class PracticePage(QWidget):
    tone_requested = Signal(float, float)       # frecuencia, segundos
    mic_toggle_requested = Signal()
    songs_requested = Signal()

    def __init__(self, clock=time.monotonic):
        super().__init__()
        self.clock = clock
        self.finder = ReferenceFinder()
        self.finding = False
        self.frequency = None
        self.run = None
        self.mic_on = False
        self.page_visible = False
        self.last_block = None
        self.tone_until = 0.0
        self.message_key = None
        self.message_since = 0.0
        self.stack = QStackedWidget()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.stack)
        self.build_setup()
        self.build_play()
        self.build_results()
        self.refresh_setup()

    # ================================================================ vistas
    def build_setup(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(px(56), px(36), px(56), px(36))
        layout.setSpacing(px(22))
        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(px(6))
        titles.addWidget(label('PISTA DE VOZ', 'eyebrow'))
        titles.addWidget(label('Canta tu nota cuando llegue a la línea', 'display'))
        titles.addWidget(label('Una nota tuya, cinco veces, con descansos para respirar entre medias.', 'lead'))
        head.addLayout(titles, 1)
        head.addWidget(PandaBadge(96), 0, Qt.AlignBottom)
        layout.addLayout(head)

        cards = QHBoxLayout()
        cards.setSpacing(px(24))
        # 1 · micrófono
        self.card_mic, c = card()
        c.addLayout(self.step_title('1', 'Micrófono'))
        self.devices = QComboBox()
        self.devices.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.devices.setMinimumContentsLength(8)
        c.addWidget(self.devices)
        self.mic_button = button('Activar micrófono', 'primary')
        self.mic_button.clicked.connect(self.mic_toggle_requested.emit)
        c.addWidget(self.mic_button)
        self.mic_status = label('Usa auriculares: así la música y la referencia no entran en el micro.', 'muted')
        c.addWidget(self.mic_status)
        c.addStretch()
        tips = label('<b>Antes de empezar</b><br>'
                     '· Auriculares puestos.<br>'
                     '· Voz cómoda, como al hablar: no hace falta cantar fuerte.<br>'
                     '· Si algo molesta o cansa, para. Descansar también cuenta.', 'lead')
        tips.setTextFormat(Qt.RichText)
        c.addWidget(tips)
        cards.addWidget(self.card_mic, 1)
        # 2 · tu nota
        self.card_note, c = card()
        c.addLayout(self.step_title('2', 'Encuentra tu nota'))
        c.addSpacing(px(4))
        self.find_text = label('Haz una «u» cómoda durante un segundo y para. No hace falta aguantar.', 'muted')
        c.addWidget(self.find_text)
        self.note_big = label('—', 'bignote', align=Qt.AlignCenter)
        c.addWidget(self.note_big)
        self.find_progress = QProgressBar()
        self.find_progress.setRange(0, 100)
        c.addWidget(self.find_progress)
        self.hearing = label(' ', 'muted', align=Qt.AlignCenter)
        c.addWidget(self.hearing)
        c.addStretch()
        row = QHBoxLayout()
        self.find_button = button('Encontrar mi nota', 'primary')
        self.find_button.clicked.connect(self.start_finding)
        row.addWidget(self.find_button, 2)
        self.listen_button = button('Escuchar')
        self.listen_button.clicked.connect(self.listen)
        row.addWidget(self.listen_button, 1)
        c.addLayout(row)
        cards.addWidget(self.card_note, 1)
        # 3 · jugar
        self.card_play, c = card()
        c.addLayout(self.step_title('3', '¿Te resulta cómoda?'))
        c.addWidget(label('Sólo tú sabes si esa altura te sale fácil. Si no, busca otra: '
                          'el juego usará esta nota fija durante toda la partida.', 'muted'))
        self.guide = QCheckBox('Oírla antes de cada nota')
        self.guide.setChecked(True)
        c.addWidget(self.guide)
        c.addStretch()
        self.start_button = button('Sí, ¡a jugar!', 'primary')
        self.start_button.clicked.connect(self.start_run)
        c.addWidget(self.start_button)
        self.again_find = button('Buscar otra nota')
        self.again_find.clicked.connect(self.start_finding)
        c.addWidget(self.again_find)
        cards.addWidget(self.card_play, 1)
        layout.addLayout(cards, 1)

        legend = QHBoxLayout()
        legend.setSpacing(px(20))
        for mark, colour, text in [
            ('▬', theme.PINK, 'La barra es tu nota: canta mientras cruza la línea AHORA.'),
            ('●', theme.GREEN, 'La bola es tu voz: arriba = más agudo, abajo = más grave.'),
            ('~', theme.CYAN, 'Entre notas, respira. Ahí no se puntúa nada.'),
        ]:
            item = QHBoxLayout()
            icon = label(mark, wrap=False)
            icon.setStyleSheet(f'color: {colour}; font-size: {px(40)}px; font-weight: 900;')
            item.addWidget(icon)
            item.addWidget(label(text, 'lead'), 1)
            legend.addLayout(item, 1)
        layout.addLayout(legend)
        self.stack.addWidget(page)
        self.setup_page = page

    def step_title(self, number, text):
        row = QHBoxLayout()
        row.setSpacing(px(14))
        badge = label(number, 'step', wrap=False, align=Qt.AlignCenter)
        row.addWidget(badge)
        row.addWidget(label(text, 'h2'), 1)
        return row

    def build_play(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(px(28), px(20), px(28), px(20))
        layout.setSpacing(px(12))
        self.track = TrackView(self.clock)
        layout.addWidget(self.track, 1)
        self.banner = label('', 'banner', align=Qt.AlignCenter)
        self.banner.setMinimumHeight(px(70))
        layout.addWidget(self.banner)
        row = QHBoxLayout()
        row.setSpacing(px(16))
        self.pause_button = button('Pausa')
        self.pause_button.clicked.connect(self.toggle_pause)
        row.addWidget(self.pause_button)
        self.play_listen = button('Escuchar mi nota')
        self.play_listen.clicked.connect(self.listen)
        row.addWidget(self.play_listen)
        row.addStretch()
        row.addWidget(label('Espacio: pausa / seguir', 'muted', wrap=False))
        row.addStretch()
        self.quit_button = button('Terminar')
        self.quit_button.clicked.connect(self.end_early)
        row.addWidget(self.quit_button)
        layout.addLayout(row)
        self.stack.addWidget(page)
        self.play_page = page

    def build_results(self):
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(px(72), px(48), px(72), px(48))
        layout.setSpacing(px(48))
        left = QVBoxLayout()
        left.setSpacing(px(12))
        left.addStretch()
        self.result_panda = PandaBadge(170, waving=True)
        left.addWidget(self.result_panda, 0, Qt.AlignHCenter)
        self.stars = label('', wrap=False, align=Qt.AlignCenter)
        left.addWidget(self.stars)
        self.result_title = label('', 'display', align=Qt.AlignCenter)
        left.addWidget(self.result_title)
        self.result_score = label('', 'lead', align=Qt.AlignCenter)
        left.addWidget(self.result_score)
        left.addStretch()
        layout.addLayout(left, 2)

        right_card, right = card()
        right.setSpacing(px(18))
        right.addWidget(label('TU PARTIDA', 'eyebrow'))
        self.result_hits = label('', 'h1')
        right.addWidget(self.result_hits)
        self.chips = QGridLayout()
        self.chips.setSpacing(px(10))
        right.addLayout(self.chips)
        self.result_lines = label('', 'lead')
        self.result_lines.setTextFormat(Qt.RichText)
        right.addWidget(self.result_lines)
        right.addStretch()
        comfort = QHBoxLayout()
        comfort.addWidget(label('¿Te resultó cómodo?', 'h2'))
        yes = button('Sí')
        yes.clicked.connect(lambda: self.result_note.setText('¡Genial! Repite cuando quieras, con calma.'))
        comfort.addWidget(yes)
        hard = button('Me costó')
        hard.clicked.connect(self.found_it_hard)
        comfort.addWidget(hard)
        comfort.addStretch()
        right.addLayout(comfort)
        self.result_note = label('', 'muted')
        right.addWidget(self.result_note)
        buttons = QHBoxLayout()
        buttons.setSpacing(px(16))
        self.again_button = button('↻  Otra vez', 'primary')
        self.again_button.clicked.connect(self.start_run)
        buttons.addWidget(self.again_button)
        change = button('Cambiar de nota')
        change.clicked.connect(self.back_to_setup)
        buttons.addWidget(change)
        songs = button('Canciones')
        songs.clicked.connect(self.songs_requested.emit)
        buttons.addWidget(songs)
        right.addLayout(buttons)
        layout.addWidget(right_card, 3)
        self.stack.addWidget(page)
        self.results_page = page

    # ============================================================ estado
    def refresh_setup(self):
        found = self.frequency is not None
        self.devices.setEnabled(not self.mic_on)
        self.mic_button.setText('Desactivar micrófono' if self.mic_on else 'Activar micrófono')
        self.mic_button.setObjectName('' if self.mic_on else 'primary')
        self.find_button.setEnabled(self.mic_on and not self.finding)
        self.find_button.setText('Escuchando…' if self.finding else 'Buscar otra vez' if found else 'Encontrar mi nota')
        self.find_button.setObjectName('primary' if self.mic_on and not found else '')
        self.listen_button.setEnabled(found and not self.finding)
        self.start_button.setEnabled(found and self.mic_on and not self.finding)
        self.again_find.setEnabled(found and self.mic_on and not self.finding)
        step = 0 if not self.mic_on else 1 if not found or self.finding else 2
        for i, frame in enumerate((self.card_mic, self.card_note, self.card_play)):
            set_prop(frame, 'active', 'true' if i == step else 'false')
        for b in (self.mic_button, self.find_button):
            b.style().unpolish(b)
            b.style().polish(b)
        if found:
            self.note_big.setText(note_label(self.frequency))
            self.find_progress.setValue(100)

    def set_mic(self, on, message=None):
        self.mic_on = on
        self.last_block = None
        if message:
            self.mic_status.setText(message)
        if not on:
            if self.finding:
                self.finding = False
                self.find_text.setText('Micrófono desactivado. Actívalo para buscar tu nota.')
            if self.run and self.run.state == 'running':
                self.run.pause(self.clock())
                self.update_pause_button()
                self.show_message('nomic', 'Micrófono desactivado · actívalo para seguir', theme.ORANGE, force=True)
        self.refresh_setup()

    def set_page_visible(self, visible):
        self.page_visible = visible
        if not visible and self.run and self.run.state == 'running':
            self.run.pause(self.clock())
            self.update_pause_button()
        if not visible and self.finding:
            self.finding = False
            self.find_text.setText('Búsqueda detenida. Pulsa «Encontrar mi nota» cuando quieras.')
            self.refresh_setup()

    # ============================================================ encontrar nota
    def start_finding(self):
        if not self.mic_on:
            return
        self.finder.reset()
        self.finding = True
        self.frequency = None
        self.note_big.setText('…')
        self.find_progress.setValue(0)
        self.find_text.setText('Haz una «u» cómoda de un segundo y después para. Termina sola en 4 s como máximo.')
        self.stack.setCurrentWidget(self.setup_page)
        self.refresh_setup()

    def feed_finder(self, stamp, duration, frequency, level):
        if stamp < self.tone_until:
            return
        kind, _ = classify(frequency, level, frequency or 1)
        self.hearing.setText({'silence': 'Silencio', 'unclear': 'Oigo sonido, pero sin nota clara',
                              'hit': '♪ Te oigo'}.get(kind, ' '))
        result = self.finder.feed(frequency, level, stamp, duration)
        self.find_progress.setValue(round(self.finder.progress * 100))
        if result is not None:
            self.finding = False
            self.frequency = result
            self.hearing.setText(f'≈ {result:.0f} Hz')
            self.find_text.setText('¡La tengo! Escúchala si quieres y confirma si es cómoda.')
            self.refresh_setup()
        elif self.finder.failed:
            self.finding = False
            reason, action = self.finder.failed
            self.note_big.setText('—')
            self.find_progress.setValue(0)
            self.find_text.setText(f'Paramos aquí. {reason} {action}')
            self.hearing.setText(self.finder.diagnostic())
            self.refresh_setup()

    # ============================================================ partida
    def start_run(self):
        if self.frequency is None or not self.mic_on:
            return
        self.run = NoteRun(self.frequency, guide=self.guide.isChecked())
        self.track.set_run(self.run, note_label(self.frequency))
        self.message_key = None
        self.stack.setCurrentWidget(self.play_page)
        self.run.start(self.clock())
        self.last_block = self.clock()
        self.update_pause_button()

    def toggle_pause(self):
        if not self.run:
            return
        now = self.clock()
        if self.run.state == 'running':
            self.run.pause(now)
        elif self.run.state == 'paused' and self.mic_on:
            self.run.resume(now)
            self.last_block = now
            self.message_key = None
        self.update_pause_button()

    def update_pause_button(self):
        paused = self.run is not None and self.run.state == 'paused'
        self.pause_button.setText('Seguir' if paused else 'Pausa')
        self.play_listen.setEnabled(paused)
        if paused:
            self.show_message('paused', 'En pausa · el tiempo está detenido', theme.MUTED, force=True)

    def end_early(self):
        if self.run and self.run.state in ('running', 'paused'):
            self.run.stop(self.clock())
            self.show_results()

    def primary_action(self):
        """Barra espaciadora: la acción principal de la vista actual."""
        current = self.stack.currentWidget()
        if current is self.play_page:
            self.toggle_pause()
        elif current is self.results_page:
            self.start_run()
        elif self.start_button.isEnabled():
            self.start_run()
        elif self.find_button.isEnabled():
            self.start_finding()

    def escape_action(self):
        if self.run and self.run.state == 'running' and self.stack.currentWidget() is self.play_page:
            self.toggle_pause()
            return True
        return False

    def listen(self):
        if self.frequency is None:
            return
        if self.run and self.run.state == 'running':
            return      # durante la partida la referencia la programa el juego
        self.tone_until = self.clock() + CUE_LENGTH + .35
        self.tone_requested.emit(self.frequency, CUE_LENGTH)

    def feed(self, stamp, duration, frequency, level):
        """Un bloque analizado del micrófono (marca monotónica de final)."""
        self.last_block = self.clock()
        if not self.page_visible:
            return
        if self.finding:
            self.feed_finder(stamp, duration, frequency, level)
        elif self.run and self.run.state == 'running':
            self.run.feed(stamp, duration, frequency, level)

    def tick(self):
        """Llamado por la ventana ~30 veces por segundo: juicios, referencias y mensajes."""
        run = self.run
        if not run or run.state != 'running':
            return
        now = self.clock()
        for cue in run.due_cues(now):
            self.tone_requested.emit(run.target, CUE_LENGTH)
        for index, judgement in run.update(now):
            self.track.add_judgement(index, judgement)
        if run.state == 'finished':
            self.show_results()
            return
        self.update_banner(now)

    def update_banner(self, now):
        run = self.run
        t = run.time(now)
        if self.last_block is not None and now - self.last_block > NO_DATA_AFTER:
            self.show_message('nodata', 'No llegan datos del micrófono · revisa la conexión', theme.ORANGE, now)
            return
        first = run.notes[0]
        hint = run.hint(now)
        if t < first.start:
            if hint == 'muted' or t < .4 + CUE_LENGTH:
                self.show_message('intro', 'Escucha tu nota… (no puntúa)', theme.TEXT, now)
            else:
                self.show_message('ready', 'Prepárate: canta cuando la barra llegue a la línea', theme.TEXT, now)
            return
        if run.active_note(now) is not None:
            if hint is None:
                return
            text, colour = {
                'hit': ('¡Ahí! Suave y cómodo', theme.GREEN),
                'low': ('Un poco más agudo  ▲', theme.CYAN),
                'high': ('Un poco más grave  ▼', theme.ORANGE),
                'unclear': ('No te oigo claro · no cuenta como fallo', theme.MUTED),
                'muted': ('Suena la referencia · no puntúa', theme.MUTED),
                'silence': ('¡Ahora! Canta tu nota', theme.PINK),
            }[hint]
            self.show_message(hint if hint != 'silence' else 'go', text, colour, now)
            return
        if hint == 'muted':
            self.show_message('cue', 'Escucha tu nota… (no puntúa)', theme.TEXT, now)
        elif run.next_note(now) is not None:
            self.show_message('rest', 'Respira… la siguiente llega sola', theme.MUTED, now)
        else:
            self.show_message('end', '¡Última hecha!', theme.GOLD, now)

    def show_message(self, key, text, colour, now=None, force=False):
        now = self.clock() if now is None else now
        if not force and key == self.message_key:
            return
        if (not force and self.message_key in PITCH_MESSAGES and key in PITCH_MESSAGES
                and now - self.message_since < MESSAGE_HOLD):
            return
        self.message_key = key
        self.message_since = now
        self.banner.setText(text)
        self.banner.setStyleSheet(f'color: {colour};')

    # ============================================================ resultado
    def show_results(self):
        run = self.run
        s = run.summary()
        stars = s['stars']
        if stars is None:
            title = 'No he podido oírte bien'
        else:
            title = ['¡Sigue probando!', '¡Buen comienzo!', '¡Muy bien!', '¡Increíble!'][stars]
        self.result_title.setText(title)
        self.result_panda.waving = bool(stars and stars >= 2)
        shown = stars or 0
        self.stars.setText(
            f'<span style="color:{theme.GOLD}">{"★" * shown}</span>'
            f'<span style="color:{theme.SURFACE_2}">{"★" * (3 - shown)}</span>')
        self.stars.setStyleSheet(f'font-size: {px(84)}px;')
        self.result_score.setText(f'{s["score"]:,} puntos'.replace(',', '.'))
        self.result_hits.setText(f'{s["hits"]} de {s["notes"]} notas acertadas')
        while self.chips.count():
            item = self.chips.takeAt(0)
            item.widget().deleteLater()
        for i, note in enumerate(run.notes):
            j = note.judgement
            text = JUDGEMENT_TEXT.get(j, 'Sin jugar')
            bg = (theme.GOLD if j in HITS else '#5d548f' if j and j.startswith('miss') else theme.SURFACE_2)
            fg = theme.INK if j in HITS else theme.TEXT
            chip = label(f'{i + 1} · {text}', wrap=False, align=Qt.AlignCenter)
            chip.setStyleSheet(f'background:{bg}; color:{fg}; border-radius:{px(18)}px; '
                               f'padding:{px(10)}px {px(14)}px; font-size:{px(20)}px; font-weight:800;')
            self.chips.addWidget(chip, i // 3, i % 3)
        lines = []
        if s['in_zone'] is not None:
            lines.append(f'El <b>{round(s["in_zone"] * 100)} %</b> del tiempo que cantaste estuvo dentro de tu nota.')
        tendency = s['tendency']
        if tendency is not None:
            if abs(tendency) < 15:
                lines.append('Tu voz quedó centrada en la nota.')
            else:
                side = 'grave' if tendency < 0 else 'aguda'
                lines.append(f'Tendencia: un poco <b>{side}</b> ({cents_words(tendency)}; 100 cents = 1 semitono).')
        unmeasured = s['unclear'] + s['silent']
        if unmeasured:
            lines.append(f'{unmeasured} nota{"s" if unmeasured > 1 else ""} sin medir (silencio o señal poco clara): '
                         'no cuentan como fallo.')
        if stars is None:
            lines.append('Revisa el micrófono o acércate un poco. No hace falta cantar más fuerte.')
        if s['best_streak'] >= 2:
            lines.append(f'Mejor racha: {s["best_streak"]} notas seguidas.')
        self.result_lines.setText('<br>'.join(lines))
        self.result_note.setText('')
        self.stack.setCurrentWidget(self.results_page)

    def found_it_hard(self):
        self.result_note.setText('Gracias. Descansa un poco y busca una nota más fácil.')
        self.back_to_setup()
        self.find_text.setText('Descansa y, cuando quieras, busca una nota que te salga más fácil.')

    def back_to_setup(self):
        self.stack.setCurrentWidget(self.setup_page)
        self.refresh_setup()
