"""Explicitly test manual cancellation before arrival at a previously visited point."""
import argparse
import json
import math
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import cv2
from core.coverage_planner import MapSurveyor, atomic_json
from core.ld_controller import LDController
from core.vision_engine import VisionEngine


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", choices=["joystick_swipe", "player_tap", "player_swipe"], required=True)
    parser.add_argument("--x", type=float, required=True)
    parser.add_argument("--y", type=float, required=True)
    args = parser.parse_args()
    directory = ROOT/"reports"/"live_validation"/"2026-10-16"/("cancel_"+args.method)
    directory.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    ctrl = LDController()
    ctrl.lock_session()
    ctrl.calibrate_resolution()
    vision = VisionEngine(controller=ctrl)
    surveyor = MapSurveyor(ctrl, vision, ctrl.config["traversal"], lambda: time.monotonic()-started < 100, print)
    goal = [args.x, args.y]
    samples = []
    previous_frame = None
    stable = 0
    previous = None
    acted = False
    action_time = None
    stopped_at = None
    last_sample = None
    result = {"method": args.method, "goal": goal, "passed": False}
    try:
        # Obtain fresh stationary samples before opening the map.
        while time.monotonic()-started < 15:
            sample = vision.get_engine_telemetry()
            if sample.get("position_frame") != previous_frame and sample.get("position"):
                previous_frame = sample["position_frame"]
                stable = stable+1 if previous and sample["doing"] == "stand" and math.dist(previous, sample["position"]) < .08 else 0
                previous = sample["position"]
                if stable >= 2:
                    break
            time.sleep(.15)
        if stable < 2:
            raise RuntimeError("Cannot prove initial stand")
        result["initial_position"] = previous
        surveyor.pin(*goal, sample["map_id"])
        previous_frame, previous, stable = None, None, 0
        while time.monotonic()-started < 75:
            sample = vision.get_engine_telemetry()
            if sample.get("position_frame") == previous_frame or not sample.get("position"):
                time.sleep(.15)
                continue
            previous_frame = sample["position_frame"]
            now = time.monotonic()-started
            entry = {"elapsed": round(now, 3), "position": list(sample["position"]), "doing": sample["doing"],
                     "frame": previous_frame, "distance_to_goal": round(math.dist(sample["position"], goal), 3), "acted": acted}
            samples.append(entry)
            print(json.dumps(entry), flush=True)
            if not acted and sample["doing"] in {"run", "walk"} and entry["distance_to_goal"] > 2:
                acted = True
                action_time = time.monotonic()
                result["request"] = entry
                if args.method == "joystick_swipe":
                    cx, cy = ctrl.joystick_center
                    ctrl.swipe(cx, cy, cx+35, cy, duration_ms=150)
                elif args.method == "player_tap":
                    width, height = ctrl.screen_size
                    ctrl.tap(width//2, height//2, jitter=False, delay=0)
                else:
                    width, height = ctrl.screen_size
                    ctrl.swipe(width//2, height//2, width//2+30, height//2, duration_ms=150)
                previous, stable = None, 0
                continue
            stable = stable+1 if previous and sample["doing"] == "stand" and math.dist(previous, sample["position"]) < .08 else 0
            previous = sample["position"]
            last_sample = entry
            if stable >= 2:
                stopped_at = entry
                break
        result.update(acted=acted, stopped=stopped_at, samples=samples)
        if stopped_at and action_time:
            result["ack_seconds"] = round(time.monotonic()-action_time, 3)
            result["passed"] = stopped_at["distance_to_goal"] > 1.5 and result["ack_seconds"] < 12
        frame = ctrl.capture_frame()
        if frame is not None:
            cv2.imwrite(str(directory/"final.png"), frame)
    except Exception as exc:
        result["error"] = str(exc)
    finally:
        ctrl.unlock_session()
        atomic_json(str(directory/"result.json"), result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
