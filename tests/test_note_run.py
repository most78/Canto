"""Reglas de puntuación de las rondas de escalas, sin Qt ni micrófono."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from game.levels import LEVELS, note_name, placements  # noqa: E402
from game.note_run import HITS, Note, NoteRun, build_round, classify  # noqa: E402
from game.progress import Progress  # noqa: E402
from game.reference import ReferenceFinder  # noqa: E402

ANCHOR = 220.0
VOICE = .05   # nivel de señal normal
O = 100.0     # instante monotónico en que empieza la ronda


def freq(semitones, cents=0):
    return ANCHOR * 2 ** ((semitones * 100 + cents) / 1200)


def sing(run, t0, t1, frequency, level=VOICE, step=.08):
    """Bloques de `step` s que terminan en t0+step … t1 (tiempo de juego)."""
    t = t0 + step
    while t <= t1 + 1e-9:
        run.feed(O + t, step, frequency, level)
        t += step


def sing_note(run, note, cents=0, **kw):
    sing(run, note.start, note.end, freq(note.semitone, cents), **kw)


def finish(run):
    run.update(O + run.end + 1)


def new_round(pattern=(0, 2, 4, 2, 0), starts=(0, 1, -1), note_len=.9, **kw):
    run = build_round(ANCHOR, pattern, starts, note_len, **kw)
    run.start(O)
    return run


def single(duration=1.5):
    run = NoteRun(ANCHOR, [Note(1.0, 1.0 + duration, 0)])
    run.start(O)
    return run


class ClassifyTests(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(classify(ANCHOR, 0, ANCHOR)[0], 'silence')
        self.assertEqual(classify(None, VOICE, ANCHOR)[0], 'unclear')
        self.assertEqual(classify(freq(0, 40), VOICE, ANCHOR)[0], 'hit')
        self.assertEqual(classify(freq(2, 30), VOICE, ANCHOR, 200)[0], 'hit')
        self.assertEqual(classify(freq(2, -80), VOICE, ANCHOR, 200)[0], 'low')
        self.assertEqual(classify(freq(0, 80), VOICE, ANCHOR)[0], 'high')
        # Una octava no cuenta como acierto; algo absurdo es lectura dudosa.
        self.assertEqual(classify(ANCHOR * 2, VOICE, ANCHOR)[0], 'high')
        self.assertEqual(classify(ANCHOR * 4, VOICE, ANCHOR)[0], 'unclear')
        # Sin nota que cantar, la voz se muestra sin juzgar.
        kind, cents = classify(freq(3), VOICE, ANCHOR, None)
        self.assertEqual(kind, 'free')
        self.assertAlmostEqual(cents, 300)

    def test_volume_never_multiplies(self):
        for level in (.003, .05, .9):
            self.assertEqual(classify(ANCHOR, level, ANCHOR), ('hit', 0.0))


class RoundTests(unittest.TestCase):
    def test_structure_listen_then_sing(self):
        run = new_round()
        demo = [n for n in run.notes if n.demo]
        self.assertEqual(len(demo), 15)
        self.assertEqual(len(run.sung), 15)
        self.assertEqual(len(run.cues), 3)
        for a in range(3):
            d = [n for n in demo if n.attempt == a]
            s = [n for n in run.sung if n.attempt == a]
            self.assertEqual([n.semitone for n in d], [n.semitone for n in s])
            self.assertLess(d[-1].end, s[0].start)
        self.assertEqual([n.semitone for n in run.sung if n.attempt == 1], [1, 3, 5, 3, 1])

    def test_perfect_round_regardless_of_block_size(self):
        for step in (.02, .05, .08, .128):
            run = new_round()
            for note in run.sung:
                sing_note(run, note, step=step)
            finish(run)
            self.assertTrue(all(n.judgement == 'perfect' for n in run.sung), step)
            s = run.summary()
            self.assertEqual((s['hits'], s['stars'], s['passed']), (15, 3, True))
            self.assertEqual(run.state, 'finished')

    def test_singing_during_listen_is_ignored(self):
        run = new_round()
        for note in [n for n in run.notes if n.demo and n.attempt == 0]:
            sing(run, note.start, note.end, freq(note.semitone))
        self.assertEqual(sum(n.hit for n in run.sung), 0)
        self.assertEqual(run.live.kind, 'muted')

    def test_listen_mute_covers_piano_tail(self):
        run = new_round()
        demo = [n for n in run.notes if n.demo and n.attempt == 0]
        reading = run.feed(O + demo[-1].end + .5, .08, ANCHOR, VOICE)
        self.assertEqual(reading.kind, 'muted')

    def test_each_note_has_its_own_target(self):
        run = new_round()
        first = [n for n in run.sung if n.attempt == 0]
        for note in first:
            sing(run, note.start, note.end, ANCHOR)   # siempre la nota base
        finish(run)
        self.assertEqual([n.judgement in HITS for n in first], [True, False, False, False, True])
        self.assertEqual(first[1].judgement, 'miss_low')

    def test_rests_score_nothing_and_holding_longer_does_not_add(self):
        run = new_round()
        a, b = run.sung[4], run.sung[5]
        sing(run, a.start, b.start - 3, freq(a.semitone))
        self.assertAlmostEqual(a.hit, a.duration, places=6)
        self.assertEqual(b.hit, 0)

    def test_louder_is_not_better(self):
        scores = []
        for level in (.004, .5):
            run = new_round()
            sing_note(run, run.sung[0], level=level)
            finish(run)
            scores.append(run.score)
        self.assertEqual(scores[0], scores[1])

    def test_silence_and_noise_are_not_misses(self):
        run = new_round()
        sing_note(run, run.sung[0], level=0)
        sing(run, run.sung[1].start, run.sung[1].end, None, level=.2)
        finish(run)
        self.assertEqual(run.sung[0].judgement, 'silent')
        self.assertEqual(run.sung[1].judgement, 'unclear')
        s = run.summary()
        self.assertEqual(s['misses'], 0)
        self.assertIsNone(s['stars'])

    def test_pass_needs_80_percent_in_two_attempts(self):
        run = new_round()
        for note in run.sung:
            wrong = note.attempt == 2 or (note.attempt == 1 and note is run.sung[5])
            sing_note(run, note, cents=-150 if wrong else 0)
        finish(run)
        s = run.summary()
        self.assertEqual([round(x, 2) for x in s['attempt_scores']], [1.0, .8, 0.0])
        self.assertTrue(s['passed'])
        self.assertEqual(s['stars'], 2)

    def test_fail_when_only_one_attempt_is_good(self):
        run = new_round()
        for note in run.sung:
            sing_note(run, note, cents=0 if note.attempt == 0 else -150)
        finish(run)
        self.assertFalse(run.summary()['passed'])

    def test_blocks_are_counted_once(self):
        run = single()
        note = run.sung[0]
        stamp = O + note.start + .5
        run.feed(stamp, .5, ANCHOR, VOICE)
        run.feed(stamp, .5, ANCHOR, VOICE)
        run.feed(stamp - .2, .08, ANCHOR, VOICE)
        self.assertAlmostEqual(note.hit, .5)

    def test_pause_discards_old_audio_and_freezes_time(self):
        run = single()
        note = run.sung[0]
        run.pause(O + note.start)
        self.assertIsNone(run.feed(O + note.start + .1, .08, ANCHOR, VOICE))
        run.resume(200.0)
        self.assertAlmostEqual(run.time(200.0), note.start)
        run.feed(200.0 + .02, .5, ANCHOR, VOICE)
        self.assertAlmostEqual(note.hit, .02, places=6)

    def test_due_cues_are_consumed_once(self):
        run = new_round()
        cue = run.due_cues(O + 1.0)
        self.assertEqual(len(cue), 1)
        self.assertEqual([k for _, k, _ in cue[0]['notes']], [0, 2, 4, 2, 0])
        self.assertEqual(run.due_cues(O + 1.1), [])

    def test_hint_needs_persistence_and_fresh_data(self):
        run = single()
        run.feed(O + 1.0, .08, freq(0, -120), VOICE)
        self.assertIsNone(run.hint(O + 1.0))
        for i in range(1, 6):
            run.feed(O + 1.0 + i * .08, .08, freq(0, -120), VOICE)
        self.assertEqual(run.hint(O + 1.4), 'low')
        self.assertEqual(run.hint(O + 3.5), 'silence')
        self.assertIsNone(run.current_reading(O + 3.5))

    def test_phases(self):
        run = new_round()
        demo0 = [n for n in run.notes if n.demo][0]
        self.assertEqual(run.phase(O + .2)[0], 'intro')
        self.assertEqual(run.phase(O + demo0.start + .1), ('listen', 0))
        self.assertEqual(run.phase(O + run.sung[0].start - .8), ('turn', 0))
        self.assertEqual(run.phase(O + run.sung[0].start + .1), ('sing', 0))
        self.assertEqual(run.phase(O + run.sung[4].end + 1)[0], 'rest')


class LevelTests(unittest.TestCase):
    def test_levels_grow_in_span_and_first_fits_start_range(self):
        self.assertTrue(placements(LEVELS[0], -2, 5))
        self.assertEqual(placements(LEVELS[0], -2, 5), [0, 1, -2])
        self.assertEqual(placements(LEVELS[1], -2, 5), [-2, -2, -2])
        self.assertEqual(placements(LEVELS[6], -2, 5), [])      # la octava aún no cabe

    def test_note_names(self):
        self.assertEqual(note_name(69), 'La3')
        self.assertEqual(note_name(57), 'La2')
        self.assertEqual(note_name(61), 'Do#3')


class ProgressTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / 'progreso.json'

    def test_saves_and_loads(self):
        p = Progress.load(self.path)
        p.set_anchor(57)
        p.record_round(0, {'attempt_scores': [1, .8, .6], 'passed': True}, [(57, 1.0), (59, .5)])
        q = Progress.load(self.path)
        self.assertEqual((q.anchor_midi, q.unlocked), (57, 1))
        self.assertEqual(q.stat(59), {'ema': .5, 'n': 1})

    def test_range_grows_only_when_edge_is_solid(self):
        p = Progress.load(self.path)
        p.set_anchor(57)
        high = 57 + p.hi
        self.assertEqual(p.grow_range(), [])
        for _ in range(3):
            p.record_round(0, {'attempt_scores': [1], 'passed': False}, [(high, .9)])
        self.assertEqual(p.grow_range(), [('agudo', high + 1)])
        self.assertEqual(p.hi, 6)

    def test_failing_does_not_unlock(self):
        p = Progress.load(self.path)
        p.set_anchor(57)
        self.assertFalse(p.record_round(0, {'attempt_scores': [.2, .4, .8], 'passed': False}, []))
        self.assertEqual(p.unlocked, 0)

    def test_new_anchor_keeps_absolute_range(self):
        p = Progress.load(self.path)
        p.set_anchor(57)
        before = p.range_midi()
        p.set_anchor(58)
        self.assertEqual(p.range_midi(), before)
        p.set_anchor(62)          # el nivel 1 debe seguir cabiendo por arriba
        self.assertGreaterEqual(p.hi, 4)


class ReferenceFinderTests(unittest.TestCase):
    def test_finds_median_of_consistent_group(self):
        finder = ReferenceFinder()
        for i, f in enumerate([220, 222, None, None, 219, 220]):
            finder.feed(f, VOICE, i * .1, .08)
        self.assertAlmostEqual(finder.frequency, 220, delta=1)

    def test_times_out_with_reason(self):
        for level, reason in [(0, 'muy baja'), (.05, 'no distingo')]:
            finder = ReferenceFinder()
            for i in range(45):
                finder.feed(None, level, i * .1, .08)
            self.assertIsNone(finder.frequency)
            self.assertIn(reason, finder.failed[0])


if __name__ == '__main__':
    unittest.main()
