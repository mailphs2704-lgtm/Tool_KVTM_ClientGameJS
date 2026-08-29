from pathlib import Path
import tempfile
import unittest

from kvtm_function_core import (
    AutoFunction,
    FunctionRecorder,
    FunctionRuntime,
    FunctionValidationError,
)


class FakeEngine:
    def __init__(self):
        self.actions = []
        self.image_result = (400.0, 500.0)

    def click(self, x, y):
        self.actions.append(("click", x, y))

    def swipe_points(self, points, duration):
        self.actions.append(("swipe", points, duration))

    def find_image(self, asset, confidence, region=None):
        self.actions.append(("find", asset.name, confidence, region))
        return self.image_result


class CoreTests(unittest.TestCase):
    def test_round_trip_and_runtime(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "basket.png").write_bytes(b"test")
            data = {
                "schema_version": 1,
                "name": "Thu hoach",
                "logical_size": [1000, 1000],
                "steps": [
                    {"type": "click", "point": [10, 20]},
                    {"type": "swipe_path", "points": [[10, 20], [30, 40]], "duration": 0.5},
                    {"type": "click_image", "asset": "basket.png", "confidence": 0.8, "timeout": 1},
                ],
            }
            function = AutoFunction.from_dict(data)
            path = root / "function.json"
            function.save(path)
            loaded = AutoFunction.load(path)
            engine = FakeEngine()
            events = FunctionRuntime(engine, root, sleep=lambda _seconds: None).run(loaded)
            self.assertEqual([event.status for event in events], ["ok", "ok", "ok"])
            self.assertEqual(engine.actions[-1], ("click", 400.0, 500.0))

    def test_recorder_simplifies_straight_swipe(self):
        recorder = FunctionRecorder()
        recorder.swipe_start(0, 100, now=10)
        for x in range(10, 100, 10):
            recorder.swipe_move(x, 100)
        recorder.swipe_end(100, 100, now=11)
        step = recorder.function.steps[0]
        self.assertEqual(step.type, "swipe_path")
        self.assertEqual(step.data["points"], [[0.0, 100.0], [100.0, 100.0]])
        self.assertEqual(step.data["duration"], 1.0)

    def test_rejects_bad_coordinates(self):
        with self.assertRaises(FunctionValidationError):
            AutoFunction.from_dict({
                "name": "Bad",
                "logical_size": [1000, 1000],
                "steps": [{"type": "click", "point": [1001, 10]}],
            })

    def test_blocks_asset_escape(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            function = AutoFunction.from_dict({
                "name": "Bad asset",
                "steps": [{"type": "wait_image", "asset": "../secret.png", "timeout": 0}],
            })
            with self.assertRaises(FunctionValidationError):
                FunctionRuntime(FakeEngine(), root, sleep=lambda _seconds: None).run(function)

    def test_condition_repeat_and_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "ready.png").write_bytes(b"test")
            engine = FakeEngine()
            function = AutoFunction.from_dict({
                "name": "Control flow",
                "steps": [
                    {"type": "if_image", "asset": "ready.png", "timeout": 0,
                     "then_steps": [{"type": "repeat", "count": 3, "steps": [
                         {"type": "click", "point": [100, 200]}
                     ]}], "else_steps": []},
                    {"type": "retry", "attempts": 2, "delay_seconds": 0,
                     "steps": [{"type": "wait_image", "asset": "ready.png", "timeout": 0}],
                     "on_exhausted": []},
                ],
            })
            events = FunctionRuntime(engine, root, sleep=lambda _seconds: None).run(function)
            clicks = [action for action in engine.actions if action[0] == "click"]
            self.assertEqual(len(clicks), 3)
            self.assertTrue(all(event.status == "ok" for event in events))

    def test_procedure_and_swipe_from_image(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "seed.png").write_bytes(b"test")
            function = AutoFunction.from_dict({
                "name": "Procedure",
                "procedures": {"plant": [{
                    "type": "swipe_from_image", "asset": "seed.png",
                    "confidence": 0.8, "timeout": 0,
                    "points": [[100, 100], [200, 100]], "duration": 0.5
                }]},
                "steps": [{"type": "call", "procedure": "plant"}],
            })
            engine = FakeEngine()
            FunctionRuntime(engine, root, sleep=lambda _seconds: None).run(function)
            swipe = [action for action in engine.actions if action[0] == "swipe"][0]
            self.assertEqual(swipe[1][0], (400.0, 500.0))
            self.assertEqual(swipe[1][-1], (200.0, 100.0))


if __name__ == "__main__":
    unittest.main()
