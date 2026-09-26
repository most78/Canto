"""Página «Escalas»: preparar (micro, tu nota, nivel) → ronda → resultado."""
import math
import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

from game.levels import LEVELS, midi_frequency, note_name, placements
from game.note_run import HITS, JUDGEMENT_TEXT, build_round, classify
from game.reference import ReferenceFinder
from ui import theme
from ui.panda import PandaBadge
from ui.theme import px
from ui.track import TrackView
from ui.voicemap import VoiceMap

NO_DATA_AFTER = 1.2        # sin bloques del micro durante este tiempo = aviso
PITCH_MESSAGES = {'hit', 'low', 'high', 'unclear'}
MESSAGE_HOLD = .6          # un mensaje de afinación se lee al menos esto
LISTEN_SECONDS = 1.2       # «Escuchar mi nota»


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


def scrollable(page):
    """Envuelve una pantalla para que se pueda desplazar si no cabe.

    Así la ventana no exige un tamaño mínimo grande (Windows no maximiza bien
    si el contenido pide casi toda la altura) y funciona en pantallas pequeñas.
    """
    area = QScrollArea()
    area.setWidget(page)
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    area.viewport().setAutoFillBackground(False)
    return area


def set_prop(widget, name, value):
    widget.setProperty(name, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def midi_of_frequency(frequency):
    return round(69 + 12 * math.log2(frequency / 440))


class PracticePage(QWidget):
    phrase_requested = Signal(object)           # [(desfase_s, frecuencia, duración_s)]
    mic_toggle_requested = Signal()
    songs_requested = Signal()

    def __init__(self, progress, clock=time.monotonic):
        super().__init__()
        self.progress = progress
        self.clock = clock
        self.finder = ReferenceFinder()
        self.finding = False
        self.run = None
        self.level_index = progress.unlocked
        self.round_level = None
        self.mic_on = False
        self.page_visible = False
        self.last_block = None
        self.tone_until = 0.0
        self.message_key = None
        self.message_pitch = False
        self.message_since = 0.0
        self.comfort_answered = False
        self.stack = QStackedWidget()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.stack)
        self.build_setup()
        self.build_play()
        self.build_results()
        if progress.anchor_midi is not None:
            self.find_text.setText('Tu nota guardada. Puedes buscar otra cuando quieras.')
        self.refresh_setup()

    @property
    def anchor_midi(self):
        return self.progress.anchor_midi

    @property
    def frequency(self):
        return midi_frequency(self.anchor_midi) if self.anchor_midi is not None else None

    # ================================================================ vistas
    def build_setup(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(px(56), px(30), px(56), px(30))
        layout.setSpacing(px(20))
        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(px(6))
        titles.addWidget(label('ESCALAS', 'eyebrow'))
        titles.addWidget(label('Escucha al piano y repite', 'display'))
        titles.addWidget(label('Canta cada nota diciendo su nombre (la, si, do…) o con una vocal. '
                               'Aprenderás qué nota es cada una.', 'lead'))
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
        self.mic_status = label('Tu voz no se graba ni se envía.', 'muted')
        c.addWidget(self.mic_status)
        c.addStretch()
        tips = label('<b>Antes de empezar</b><br>'
                     '· Voz cómoda, como al hablar: no hace falta cantar fuerte.<br>'
                     '· Si algo molesta o cansa, para. Descansar también cuenta.', 'lead')
        tips.setTextFormat(Qt.RichText)
        c.addWidget(tips)
        cards.addWidget(self.card_mic, 4)
        # 2 · tu nota
        self.card_note, c = card()
        c.addLayout(self.step_title('2', 'Tu nota de partida'))
        c.addSpacing(px(4))
        self.find_text = label('Haz una «u» o un «do» cómodo durante un segundo y para. '
                               'Las escalas se colocarán alrededor de esa nota.', 'muted')
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
        cards.addWidget(self.card_note, 4)
        # 3 · nivel
        self.card_play, c = card()
        c.addLayout(self.step_title('3', 'Elige nivel'))
        grid = QGridLayout()
        grid.setSpacing(px(10))
        self.level_buttons = []
        for i, level in enumerate(LEVELS):
            b = button(f'{i + 1} · {level.name}', 'chip')
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, i=i: self.select_level(i))
            grid.addWidget(b, i // 2, i % 2)
            self.level_buttons.append(b)
        c.addLayout(grid)
        self.level_text = label('', 'lead')
        self.level_text.setTextFormat(Qt.RichText)
        c.addWidget(self.level_text)
        c.addStretch()
        self.range_text = label('', 'muted')
        c.addWidget(self.range_text)
        self.start_button = button('¡A jugar!', 'primary')
        self.start_button.clicked.connect(self.start_run)
        c.addWidget(self.start_button)
        cards.addWidget(self.card_play, 6)
        layout.addLayout(cards, 1)

        legend = QHBoxLayout()
        legend.setSpacing(px(20))
        for mark, colour, text in [
            ('▬', theme.VIOLET, 'Barras translúcidas: escucha al piano. No puntúan.'),
            ('▬', theme.PINK, 'Barras rosas: tu turno. Canta la nota que indican al cruzar AHORA.'),
            ('●', theme.GREEN, 'La bola es tu voz: arriba = más agudo, abajo = más grave.'),
        ]:
            item = QHBoxLayout()
            icon = label(mark, wrap=False)
            icon.setStyleSheet(f'color: {colour}; font-size: {px(40)}px; font-weight: 900;')
            item.addWidget(icon)
            item.addWidget(label(text, 'lead'), 1)
            legend.addLayout(item, 1)
        layout.addLayout(legend)
        self.setup_page = scrollable(page)
        self.stack.addWidget(self.setup_page)

    def step_title(self, number, text):
        row = QHBoxLayout()
        row.setSpacing(px(14))
        row.addWidget(label(number, 'step', wrap=False, align=Qt.AlignCenter))
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
        layout.setContentsMargins(px(56), px(36), px(56), px(36))
        layout.setSpacing(px(40))
        left = QVBoxLayout()
        left.setSpacing(px(10))
        left.addStretch()
        self.result_panda = PandaBadge(150, waving=True)
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
        right.setSpacing(px(14))
        self.result_level = label('', 'eyebrow')
        right.addWidget(self.result_level)
        self.result_hits = label('', 'h1')
        right.addWidget(self.result_hits)
        self.attempt_rows = QVBoxLayout()
        self.attempt_rows.setSpacing(px(8))
        right.addLayout(self.attempt_rows)
        self.result_lines = label('', 'lead')
        self.result_lines.setTextFormat(Qt.RichText)
        right.addWidget(self.result_lines)
        right.addWidget(label('MAPA DE TU VOZ · % de acierto por nota', 'eyebrow'))
        self.voice_map = VoiceMap()
        right.addWidget(self.voice_map)
        right.addStretch()
        comfort = QHBoxLayout()
        comfort.addWidget(label('¿Te resultó cómodo?', 'h2'))
        self.comfort_yes = button('Sí')
        self.comfort_yes.clicked.connect(lambda: self.answer_comfort(True))
        comfort.addWidget(self.comfort_yes)
        self.comfort_no = button('Me costó')
        self.comfort_no.clicked.connect(lambda: self.answer_comfort(False))
        comfort.addWidget(self.comfort_no)
        comfort.addStretch()
        right.addLayout(comfort)
        self.result_note = label('', 'lead')
        right.addWidget(self.result_note)
        buttons = QHBoxLayout()
        buttons.setSpacing(px(16))
        self.again_button = button('Otra vez', 'primary')
        self.again_button.clicked.connect(self.start_run)
        buttons.addWidget(self.again_button)
        self.next_button = button('Siguiente nivel')
        self.next_button.clicked.connect(self.next_level)
        buttons.addWidget(self.next_button)
        change = button('Cambiar nivel')
        change.clicked.connect(self.back_to_setup)
        buttons.addWidget(change)
        right.addLayout(buttons)
        layout.addWidget(right_card, 4)
        self.results_page = scrollable(page)
        self.stack.addWidget(self.results_page)

    # ============================================================ estado
    def refresh_setup(self):
        found = self.anchor_midi is not None
        self.devices.setEnabled(not self.mic_on)
        self.mic_button.setText('Desactivar micrófono' if self.mic_on else 'Activar micrófono')
        self.mic_button.setObjectName('' if self.mic_on else 'primary')
        self.find_button.setEnabled(self.mic_on and not self.finding)
        self.find_button.setText('Escuchando…' if self.finding else 'Buscar otra' if found else 'Encontrar mi nota')
        self.find_button.setObjectName('primary' if self.mic_on and not found else '')
        self.listen_button.setEnabled(found and not self.finding)
        if found and not self.finding:
            self.note_big.setText(note_name(self.anchor_midi))
            self.find_progress.setValue(100)
        for i, b in enumerate(self.level_buttons):
            b.setEnabled(i <= self.progress.unlocked)
            b.setChecked(i == self.level_index)
            b.setText(f'{i + 1} · {LEVELS[i].name}' if i <= self.progress.unlocked else f'{i + 1} · bloqueado')
        level = LEVELS[self.level_index]
        starts = placements(level, self.progress.lo, self.progress.hi) if found else []
        text = f'<b>{level.name}.</b> {level.description} Margen ±{level.tolerance} cents.'
        if found and starts:
            names = ' · '.join(note_name(self.anchor_midi + starts[0] + k) for k in level.pattern)
            text += f'<br>Primer intento: <b>{names}</b>'
        elif found:
            text += (f'<br>Necesita {level.span + 1} notas de rango y ahora tienes '
                     f'{self.progress.hi - self.progress.lo + 1}. Tu rango crece al acertar los bordes '
                     'y decir que fue cómodo.')
        self.level_text.setText(text)
        if found:
            low, high = self.progress.range_midi()
            self.range_text.setText(f'Tu rango de trabajo: {note_name(low)} – {note_name(high)} '
                                    f'({high - low + 1} notas)')
        else:
            self.range_text.setText('Primero encuentra tu nota de partida.')
        self.start_button.setEnabled(found and self.mic_on and not self.finding and bool(starts))
        step = 0 if not self.mic_on else 1 if not found or self.finding else 2
        for i, frame in enumerate((self.card_mic, self.card_note, self.card_play)):
            set_prop(frame, 'active', 'true' if i == step else 'false')
        for b in (self.mic_button, self.find_button):
            b.style().unpolish(b)
            b.style().polish(b)

    def select_level(self, index):
        if index <= self.progress.unlocked:
            self.level_index = index
        self.refresh_setup()

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

    # ============================================================ tu nota
    def start_finding(self):
        if not self.mic_on:
            return
        self.finder.reset()
        self.finding = True
        self.note_big.setText('…')
        self.find_progress.setValue(0)
        self.find_text.setText('Haz una «u» o un «do» cómodo de un segundo y después para. '
                               'Termina sola en 4 s como máximo.')
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
            midi = midi_of_frequency(result)
            self.progress.set_anchor(midi)
            self.progress.save()
            off = round(1200 * math.log2(result / midi_frequency(midi)))
            self.hearing.setText(f'Cantaste {result:.0f} Hz ({off:+d} cents de {note_name(midi)})')
            self.find_text.setText('¡La tengo! Ajustada a la nota más cercana. Escúchala al piano '
                                   'y, si no te resulta cómoda, busca otra.')
            self.refresh_setup()
        elif self.finder.failed:
            self.finding = False
            reason, action = self.finder.failed
            self.find_progress.setValue(0)
            self.find_text.setText(f'Paramos aquí. {reason} {action}')
            self.hearing.setText(self.finder.diagnostic())
            self.refresh_setup()

    # ============================================================ ronda
    def start_run(self):
        if self.anchor_midi is None or not self.mic_on:
            return
        level = LEVELS[self.level_index]
        starts = placements(level, self.progress.lo, self.progress.hi)
        if not starts:
            return
        self.round_level = self.level_index
        self.run = build_round(self.frequency, level.pattern, starts, level.note_len, level.tolerance)
        self.track.set_run(self.run, self.anchor_midi, f'Nivel {self.level_index + 1} · {level.name}')
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
            return      # durante la ronda el piano lo programa el juego
        self.tone_until = self.clock() + LISTEN_SECONDS + .6
        self.phrase_requested.emit([(0.0, self.frequency, LISTEN_SECONDS)])

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
        """Llamado por la ventana ~30 veces por segundo: juicios, piano y mensajes."""
        run = self.run
        if not run or run.state != 'running':
            return
        now = self.clock()
        for cue in run.due_cues(now):
            self.phrase_requested.emit([(off, self.frequency * 2 ** (k / 12), d) for off, k, d in cue['notes']])
        for index, judgement in run.update(now):
            self.track.add_judgement(index, judgement)
        if run.state == 'finished':
            self.show_results()
            return
        self.update_banner(now)

    def update_banner(self, now):
        run = self.run
        if self.last_block is not None and now - self.last_block > NO_DATA_AFTER:
            self.show_message('nodata', 'No llegan datos del micrófono · revisa la conexión', theme.ORANGE, now)
            return
        phase, attempt = run.phase(now)
        if phase == 'intro':
            self.show_message('intro', 'Primero escucha al piano (no puntúa)', theme.TEXT, now)
        elif phase == 'listen':
            self.show_message(f'listen{attempt}', 'Escucha… (no puntúa)', theme.TEXT, now)
        elif phase == 'turn':
            first = next(n for n in run.sung if n.attempt == attempt)
            self.show_message(f'turn{attempt}', f'¡Tu turno! Empieza en {note_name(self.anchor_midi + first.semitone)}',
                              theme.PINK, now)
        elif phase == 'sing':
            index = run.active_note(now)
            if index is None:
                return
            name = note_name(self.anchor_midi + run.notes[index].semitone)
            hint = run.hint(now)
            if hint is None:
                return
            text, colour = {
                'hit': (f'¡Ahí! {name}', theme.GREEN),
                'low': (f'{name} · un poco más agudo  ▲', theme.CYAN),
                'high': (f'{name} · un poco más grave  ▼', theme.ORANGE),
                'unclear': ('No te oigo claro · no cuenta como fallo', theme.MUTED),
                'muted': ('Suena el piano · no puntúa', theme.MUTED),
                'free': (f'Canta: {name}', theme.PINK),
                'silence': (f'Canta: {name}', theme.PINK),
            }[hint]
            self.show_message(f'{hint}{index}', text, colour, now, pitch=hint in PITCH_MESSAGES)
        elif phase == 'rest':
            self.show_message(f'rest{attempt}', 'Respira… el piano tocará el siguiente intento', theme.MUTED, now)
        else:
            self.show_message('end', '¡Ronda terminada!', theme.GOLD, now)

    def show_message(self, key, text, colour, now=None, force=False, pitch=False):
        now = self.clock() if now is None else now
        if not force and key == self.message_key:
            return
        # Dos indicaciones de afinación seguidas: la primera se lee al menos MESSAGE_HOLD.
        if not force and pitch and self.message_pitch and now - self.message_since < MESSAGE_HOLD:
            return
        self.message_key = key
        self.message_pitch = pitch
        self.message_since = now
        self.banner.setText(text)
        self.banner.setStyleSheet(f'color: {colour};')

    # ============================================================ resultado
    def show_results(self):
        run = self.run
        s = run.summary()
        level = LEVELS[self.round_level]
        measured = [(self.anchor_midi + n.semitone, n.ratio) for n in run.sung
                    if n.judgement and n.judgement not in ('unclear', 'silent')]
        unlocked_new = self.progress.record_round(self.round_level, s, measured) if measured else False
        stars = s['stars']
        passes = sum(x >= .8 - 1e-9 for x in s['attempt_scores'])
        if stars is None:
            title = 'No he podido oírte bien'
        elif s['passed']:
            title = '¡Nivel superado!' if stars < 3 else '¡Perfecto!'
        else:
            title = '¡Casi!' if passes == 1 else '¡Sigue probando!'
        self.result_title.setText(title)
        self.result_panda.waving = bool(s['passed'])
        shown = stars or 0
        self.stars.setText(
            f'<span style="color:{theme.GOLD}">{"★" * shown}</span>'
            f'<span style="color:{theme.SURFACE_2}">{"★" * (3 - shown)}</span>')
        self.stars.setStyleSheet(f'font-size: {px(84)}px;')
        self.result_score.setText(f'{s["score"]:,} puntos'.replace(',', '.'))
        self.result_level.setText(f'NIVEL {self.round_level + 1} · {level.name.upper()}')
        self.result_hits.setText(f'{passes} de {len(s["attempt_scores"])} intentos con 80 % o más')
        while self.attempt_rows.count():
            row = self.attempt_rows.takeAt(0).layout()
            while row.count():
                row.takeAt(0).widget().deleteLater()
        for a, score in zip(run.attempts, s['attempt_scores']):
            row = QHBoxLayout()
            row.setSpacing(px(6))
            row.addWidget(label(f'Intento {a + 1} · {round(score * 100)} %', 'lead', wrap=False))
            for note in (n for n in run.sung if n.attempt == a):
                j = note.judgement
                bg = theme.GOLD if j in HITS else '#5d548f' if j and j.startswith('miss') else theme.SURFACE_2
                fg = theme.INK if j in HITS else theme.TEXT
                chip = label(note_name(self.anchor_midi + note.semitone), wrap=False, align=Qt.AlignCenter)
                chip.setToolTip(JUDGEMENT_TEXT.get(j, 'Sin jugar'))
                chip.setStyleSheet(f'background:{bg}; color:{fg}; border-radius:{px(14)}px; '
                                   f'padding:{px(6)}px {px(10)}px; font-size:{px(18)}px; font-weight:800;')
                row.addWidget(chip)
            row.addStretch()
            self.attempt_rows.addLayout(row)
        lines = ['Dorado = acertada · morado = fallada · gris = sin medir (no cuenta como fallo).']
        if s['in_zone'] is not None:
            lines.append(f'El <b>{round(s["in_zone"] * 100)} %</b> del tiempo que cantaste estuvo dentro de la nota.')
        tendency = s['tendency']
        if tendency is not None and abs(tendency) >= 15:
            side = 'grave' if tendency < 0 else 'aguda'
            lines.append(f'Tendencia: un poco <b>{side}</b> ({abs(round(tendency))} cents; 100 cents = 1 semitono).')
        if stars is None:
            lines.append('Revisa el micrófono o acércate un poco. No hace falta cantar más fuerte.')
        if unlocked_new:
            lines.append(f'<b>Desbloqueado:</b> nivel {self.progress.unlocked + 1} · {LEVELS[self.progress.unlocked].name}.')
        self.result_lines.setText('<br>'.join(lines))
        self.voice_map.set_progress(self.progress, {m for m, _ in measured})
        self.comfort_answered = False
        self.comfort_yes.setEnabled(bool(measured))
        self.comfort_no.setEnabled(bool(measured))
        self.result_note.setText('')
        self.next_button.setEnabled(self.round_level < self.progress.unlocked)
        self.stack.setCurrentWidget(self.results_page)

    def answer_comfort(self, comfortable):
        if self.comfort_answered:
            return
        self.comfort_answered = True
        self.comfort_yes.setEnabled(False)
        self.comfort_no.setEnabled(False)
        if not comfortable:
            self.result_note.setText('Gracias. Descansa un poco; puedes repetir un nivel anterior. '
                                     'Tu rango no se amplía tras una ronda incómoda.')
            return
        grown = self.progress.grow_range()
        if grown:
            names = ', '.join(f'{note_name(m)} ({side})' for side, m in grown)
            self.result_note.setText(f'¡Tu rango crece! Nueva nota: {names}.')
        else:
            low, high = self.progress.range_midi()
            self.result_note.setText(f'¡Bien! Tu rango crecerá cuando afiances los bordes: '
                                     f'{note_name(low)} y {note_name(high)}.')
        self.voice_map.set_progress(self.progress, self.voice_map.highlight)

    def next_level(self):
        if self.round_level < self.progress.unlocked:
            self.level_index = self.round_level + 1
            self.back_to_setup()

    def back_to_setup(self):
        self.stack.setCurrentWidget(self.setup_page)
        self.refresh_setup()
