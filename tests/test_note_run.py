"""Reglas de puntuación de «Pista de voz», sin Qt ni micrófono."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from game.note_run import NoteRun, classify, HITS  # noqa: E402
from game.reference import ReferenceFinder  # noqa: E402

TARGET = 200.0
VOICE = .05   # nivel de señal normal


def cents(c):
    return TARGET * 2 ** (c / 1200)


def sing(run, t0, t1, frequency, level=VOICE, step=.08, origin=100.0):
    """Alimenta bloques de `step` segundos que terminan en song time t0+step…t1."""
    t = t0 + step
    while t <= t1 + 1e-9:
        run.feed(origin + t, step, frequency, level)
        t += step


def finish(run, origin=100.0):
    run.update(origin + run.end + 1)


def new_run(**kw):
    run = NoteRun(TARGET, **kw)
    run.start(100.0)
    return run


class ClassifyTests(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(classify(TARGET, 0, TARGET)[0], 'silence')
        self.assertEqual(classify(None, VOICE, TARGET)[0], 'unclear')
        self.assertEqual(classify(cents(40), VOICE, TARGET)[0], 'hit')
        self.assertEqual(classify(cents(-80), VOICE, TARGET)[0], 'low')
        self.assertEqual(classify(cents(80), VOICE, TARGET)[0], 'high')
        # Una octava no cuenta como acierto; algo absurdo es lectura dudosa.
        self.assertEqual(classify(TARGET * 2, VOICE, TARGET)[0], 'high')
        self.assertEqual(classify(TARGET * 4, VOICE, TARGET)[0], 'unclear')

    def test_volume_never_multiplies(self):
        for level in (.003, .05, .9):
            self.assertEqual(classify(TARGET, level, TARGET), ('hit', 0.0))


class NoteRunTests(unittest.TestCase):
    def test_perfect_run_regardless_of_block_size(self):
        for step in (.02, .05, .08, .128):
            run = new_run()
            for note in run.notes:
                sing(run, note.start, note.end, TARGET, step=step)
            finish(run)
            self.assertTrue(all(n.judgement == 'perfect' for n in run.notes), step)
            self.assertEqual(run.summary()['hits'], 5)
            self.assertEqual(run.summary()['stars'], 3)
            self.assertEqual(run.state, 'finished')

    def test_singing_in_rests_scores_nothing(self):
        run = new_run()
        n0, n1 = run.notes[0], run.notes[1]
        sing(run, n0.end, n1.start, TARGET)
        self.assertEqual(sum(n.hit for n in run.notes), 0)

    def test_holding_longer_does_not_add(self):
        run = new_run()
        note = run.notes[0]
        sing(run, note.start - 1, note.end + 2, TARGET)
        self.assertAlmostEqual(note.hit, note.duration, places=6)
        self.assertLessEqual(note.ratio, 1)

    def test_louder_is_not_better(self):
        scores = []
        for level in (.004, .5):
            run = new_run()
            sing(run, run.notes[0].start, run.notes[0].end, TARGET, level=level)
            finish(run)
            scores.append(run.score)
        self.assertEqual(scores[0], scores[1])

    def test_silence_and_noise_are_not_misses(self):
        run = new_run()
        sing(run, run.notes[0].start, run.notes[0].end, TARGET, level=0)
        sing(run, run.notes[1].start, run.notes[1].end, None, level=.2)
        finish(run)
        self.assertEqual(run.notes[0].judgement, 'silent')
        self.assertEqual(run.notes[1].judgement, 'unclear')
        self.assertEqual(run.streak, 0)
        s = run.summary()
        self.assertEqual(s['misses'], 0)
        self.assertIsNone(s['stars'])     # nada medible: no se presenta como fallo

    def test_direction_of_miss(self):
        run = new_run()
        sing(run, run.notes[0].start, run.notes[0].end, cents(-150))
        sing(run, run.notes[1].start, run.notes[1].end, cents(150))
        finish(run)
        self.assertEqual(run.notes[0].judgement, 'miss_low')
        self.assertEqual(run.notes[1].judgement, 'miss_high')
        self.assertLess(run.summary()['tendency'], 0 + 151)

    def test_octave_is_a_miss(self):
        run = new_run()
        sing(run, run.notes[0].start, run.notes[0].end, TARGET * 2)
        finish(run)
        self.assertEqual(run.notes[0].judgement, 'miss_high')

    def test_blocks_are_counted_once(self):
        run = new_run()
        note = run.notes[0]
        stamp = 100.0 + note.start + .5
        run.feed(stamp, .5, TARGET, VOICE)
        run.feed(stamp, .5, TARGET, VOICE)        # repetido
        run.feed(stamp - .2, .08, TARGET, VOICE)  # antiguo
        self.assertAlmostEqual(note.hit, .5)

    def test_pause_discards_old_audio_and_freezes_time(self):
        run = new_run()
        note = run.notes[0]
        run.pause(100.0 + note.start)
        self.assertIsNone(run.feed(100.0 + note.start + .1, .08, TARGET, VOICE))
        run.resume(200.0)
        self.assertAlmostEqual(run.time(200.0), note.start)
        # Bloque capturado durante la pausa pero entregado después: no suma.
        run.feed(200.0 + .02, .5, TARGET, VOICE)
        self.assertAlmostEqual(note.hit, .02, places=6)

    def test_reference_audio_is_not_scored(self):
        run = new_run(guide=True)
        run.cues = []
        note = run.notes[0]
        run.mute(note.start, note.start + .5)
        sing(run, note.start, note.start + .5, TARGET)
        self.assertEqual(note.hit, 0)
        self.assertEqual(run.live.kind, 'muted')

    def test_due_cues_mute_their_window(self):
        run = new_run()
        self.assertEqual(run.due_cues(100.0 + .5), [.4])
        self.assertEqual(run.due_cues(100.0 + .6), [])
        reading = run.feed(100.0 + 1.0, .08, TARGET, VOICE)
        self.assertEqual(reading.kind, 'muted')

    def test_hint_needs_persistence_and_fresh_data(self):
        run = new_run()
        run.feed(100.0 + 1.0, .08, cents(-120), VOICE)
        self.assertIsNone(run.hint(100.0 + 1.0))
        for i in range(1, 6):
            run.feed(100.0 + 1.0 + i * .08, .08, cents(-120), VOICE)
        self.assertEqual(run.hint(100.0 + 1.4), 'low')
        self.assertEqual(run.hint(100.0 + 3.0), 'silence')   # lectura antigua
        self.assertIsNone(run.current_reading(100.0 + 3.0))

    def test_target_is_fixed(self):
        run = new_run()
        sing(run, run.notes[0].start, run.notes[0].end, cents(300))
        self.assertEqual(run.target, TARGET)

    def test_streak_and_results(self):
        run = new_run()
        for i, note in enumerate(run.notes):
            if i != 2:
                sing(run, note.start, note.end, cents(10))
            else:
                sing(run, note.start, note.end, cents(-200))
        finish(run)
        s = run.summary()
        self.assertEqual((s['hits'], s['misses'], s['best_streak']), (4, 1, 2))
        self.assertEqual(s['stars'], 3)
        self.assertTrue(set(n.judgement for n in run.notes) <= set(HITS) | {'miss_low'})


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
