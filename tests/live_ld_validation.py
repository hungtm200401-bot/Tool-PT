"""Explicit live acceptance run. Uses real game input and isolated local records.

Run: python -B tests/live_ld_validation.py --phase mission --seconds 150 --label trial_1
Not collected by unittest discovery; never runs merely by importing this module.
"""

import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cv2

from core.coverage_planner import atomic_json
from core.glitch_detector import GlitchDetector
from core.google_sheet_sync import GoogleSheetSync
from core.ld_controller import LDController
from core.map_traversal_engine import MapTraversalEngine
from core.runtime_store import RuntimeStore
from core.vision_engine import VisionEngine


def host_ld_process_stats():
    """Read LDPlayer host memory/CPU for soak runs; never sends input to the emulator."""
    if os.name != "nt":
        return {"available": False, "reason": "Windows process counters unavailable"}
    powershell = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                              "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
    script = (
        "$p=Get-Process -Name Ld9BoxHeadless -ErrorAction SilentlyContinue | Select-Object -First 1; "
        "if($p){@{pid=$p.Id;cpu_seconds=$p.CPU;working_set_mb=[math]::Round($p.WorkingSet64/1MB,1)} "
        "| ConvertTo-Json -Compress}"
    )
    try:
        result = subprocess.run([powershell, "-NoProfile", "-NonInteractive", "-Command", script],
                                capture_output=True, text=True, timeout=3,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        pass
    return {"available": False, "reason": "LDPlayer host counters could not be read"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["survey", "mission"], required=True)
    parser.add_argument("--seconds", type=float, default=150)
    parser.add_argument("--label", default="trial_1")
    parser.add_argument("--arrivals", type=int, default=3)
    parser.add_argument("--pause", action="store_true")
    parser.add_argument("--soak", action="store_true",
                        help="Giữ nhiệm vụ chạy đủ thời lượng, ghi số đo định kỳ rồi dừng an toàn; không tự chuyển map")
    parser.add_argument("--metrics-interval", type=float, default=60,
                        help="Khoảng cách giữa các ảnh chụp số đo trong bài soak")
    parser.add_argument("--full-map", action="store_true", help="Chạy quét đến khi xong toàn bộ map, không cố định thời gian")
    parser.add_argument("--auto-next-map", action="store_true", default=False, help="Tự động chuyển tiếp sang các map tiếp theo sau khi xong map")
    parser.add_argument("--maps-target", type=int, default=1, help="Số lượng map cần kiểm thử tự chuyển tiếp")
    args = parser.parse_args()
    if not args.label.replace("_", "").replace("-", "").isalnum():
        parser.error("label must contain letters, digits, underscores or hyphens")
    if args.soak and (args.phase != "mission" or args.full_map or args.auto_next_map):
        parser.error("--soak requires --phase mission and keeps auto map transition disabled")
    if args.metrics_interval < 10:
        parser.error("--metrics-interval must be at least 10 seconds")
    directory = ROOT/"reports"/"live_validation"/"2026-10-16"/args.label
    directory.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    log_file = (directory/"events.jsonl").open("a", encoding="utf-8")

    def log(kind, **payload):
        item = {"elapsed": round(time.monotonic()-started, 3), "kind": kind, **payload}
        line = json.dumps(item, ensure_ascii=False)
        log_file.write(line+"\n")
        log_file.flush()
        print(line, flush=True)

    ctrl = LDController()
    ctrl.config["traversal"] = {**ctrl.config["traversal"], "auto_next_map": args.auto_next_map}
    vision = VisionEngine(controller=ctrl)
    store = RuntimeStore(str(directory/"runtime.sqlite3"))
    sync = GoogleSheetSync(str(directory/"verified_bugs.json"), str(directory/"records.csv"),
                           store=store, config={"endpoint": "", "token_env": "LIVE_TEST_UNUSED_TOKEN"})
    detector = GlitchDetector(str(directory/"evidence"), ctrl.config.get("detection", {}))
    engine = MapTraversalEngine(ctrl, vision, detector, None, sync)
    engine.progress_path = str(directory/"progress.json")
    engine.route_directory = str(directory/"routes")
    if args.phase == "mission" and not (directory/"routes").exists():
        import shutil
        seed_dir = ROOT/"reports"/"routes"
        if not seed_dir.exists():
            seed_dir = ROOT/"reports"/"live_validation"/"2026-10-16"/"mission_4"/"routes"
        if seed_dir.exists():
            shutil.copytree(str(seed_dir), str(directory/"routes"))
    engine.cb_status = lambda message: log("status", message=message)
    result = {"phase": args.phase, "label": args.label, "passed": False}
    pauses = {"requested": False, "acknowledged": False, "resumed": False}
    samples = []
    soak_snapshots = []
    soak_elapsed = 0.0

    def screenshot(name):
        frame = ctrl.capture_frame()
        if frame is not None:
            cv2.imwrite(str(directory/(name+".png")), frame)

    try:
        ctrl.ensure_connection()
        ctrl.check_and_recover_session()
        initial = None
        for _ in range(30):
            initial = vision.get_engine_telemetry()
            if engine._valid_position(initial):
                break
            ctrl.check_and_recover_session()
            time.sleep(1.0)
        if not initial or not engine._valid_position(initial):
            raise RuntimeError("No valid live position")
        result.update(serial=ctrl.device_id, initial_map=initial["map_id"], initial_position=initial["position"])
        screenshot("initial")
        if args.phase == "survey":
            ctrl.lock_session()
            engine._bound = True
            engine.surveyor.screen_size = ctrl.calibrate_resolution()
            engine.is_running = True
            engine._configure_profile()
            engine._prepare_plan()
            screenshot("after_survey")
            cv2.imwrite(str(directory/"route.png"), cv2.cvtColor(engine.plan.render(), cv2.COLOR_RGB2BGR))
            final = vision.get_engine_telemetry()
            result.update(observed=engine.plan.data["observed_fraction"], targets=len(engine.plan.data["targets"]),
                          rings=sorted({point["batch"] for point in engine.plan.data["targets"]}),
                          displacement=math.dist(initial["position"], final["position"]))
            result["passed"] = result["observed"] >= 0.98 and result["displacement"] <= 0.4
        else:
            resolution = ctrl.calibrate_resolution()
            preflight_frame = ctrl.capture_frame(max_age_seconds=0)
            if preflight_frame is None:
                raise RuntimeError("Không chụp được ảnh màn hình trong kiểm tra trước chạy; chưa khởi động di chuyển.")
            cv2.imwrite(str(directory/"preflight.png"), preflight_frame)
            log("preflight", resolution=resolution, screenshot="ok", movement_started=False)
            engine.start()
            run_started = time.monotonic()
            previous_frame = None
            previous_phase = None
            walking_since = None
            ack_time = None
            time_limit = 999999 if (args.full_map or args.auto_next_map) else args.seconds
            next_metrics_at = run_started + args.metrics_interval
            while engine.worker_thread.is_alive() and time.monotonic()-run_started < time_limit:
                sample = vision.get_engine_telemetry()
                now = time.monotonic()
                if engine._valid_position(sample) and sample["position_frame"] != previous_frame:
                    previous_frame = sample["position_frame"]
                    item = {"elapsed": round(now-started, 3), "frame": previous_frame,
                            "map": sample["map_id"], "position": sample["position"], "doing": sample["doing"],
                            "map_open": sample["map_dialog_open"], "phase": engine.route_phase,
                            "leg_id": (engine._leg or {}).get("id")}
                    samples.append(item)
                    log("sample", **item)
                if engine.route_phase != previous_phase:
                    log("phase", value=engine.route_phase)
                    if engine.route_phase in {"paused", "error", "stop_unverified", "planned"}:
                        screenshot("phase_"+engine.route_phase)
                    previous_phase = engine.route_phase
                if engine.route_phase == "walking" and walking_since is None:
                    walking_since = now
                if engine.route_phase != "walking":
                    walking_since = None
                origin = (engine._leg or {}).get("from")
                if (args.pause and not pauses["requested"] and walking_since is not None
                        and now-walking_since >= 1 and origin and sample.get("position")
                        and math.dist(origin, sample["position"]) >= 0.8
                        and sample.get("doing") in engine.MOVING):
                    pauses["requested"] = True
                    pauses["request_time"] = round(now-started, 3)
                    pauses["target_id"] = (engine._leg or {}).get("target_id")
                    pauses["leg_id"] = (engine._leg or {}).get("id")
                    engine.pause()
                    log("pause_requested")
                if pauses["requested"] and engine._pause_ack and not pauses["acknowledged"]:
                    pauses["acknowledged"] = True
                    pauses["position"] = list(sample.get("position") or [])
                    pauses["ack_time"] = round(now-started, 3)
                    ack_time = now
                    log("pause_acknowledged")
                if ack_time and not pauses["resumed"] and now-ack_time >= 3:
                    pauses["hold_displacement"] = math.dist(pauses["position"], sample["position"])
                    pauses["resumed"] = engine.resume()
                    log("resume", accepted=pauses["resumed"], displacement=pauses["hold_displacement"])
                resumed_leg = engine._leg or {}
                if (pauses["resumed"] and "resumed_target_id" not in pauses and resumed_leg.get("id")
                        and resumed_leg["id"] != pauses.get("leg_id")):
                    pauses["resumed_target_id"] = resumed_leg.get("target_id")
                    pauses["resumed_same_target"] = resumed_leg.get("target_id") == pauses.get("target_id")
                    log("resume_target_check", expected=pauses.get("target_id"), actual=resumed_leg.get("target_id"),
                        matched=pauses["resumed_same_target"])
                if args.soak and now >= next_metrics_at:
                    with store.connection() as db:
                        rows = db.execute("SELECT payload FROM events WHERE mission=? AND kind='leg_result'",
                                          (engine._mission_id,)).fetchall()
                    legs_so_far = [json.loads(row[0]) for row in rows]
                    arrivals_so_far = sum(
                        leg.get("state") == "arrived" and math.dist(leg["from"], leg["to"]) >= 1
                        for leg in legs_so_far
                    )
                    progress = engine.plan.progress_summary() if engine.plan else {}
                    snapshot = {
                        "elapsed": round(now-run_started, 2),
                        "phase": engine.route_phase,
                        "map_id": sample.get("map_id"),
                        "position": sample.get("position"),
                        "moving_arrivals": arrivals_so_far,
                        "targets_done": progress.get("done", 0),
                        "targets_total": progress.get("total", 0),
                        "ld_process": host_ld_process_stats(),
                        "metrics": ctrl.metrics.snapshot()
                    }
                    soak_snapshots.append(snapshot)
                    log("soak_metrics", **snapshot)
                    next_metrics_at += args.metrics_interval
                with store.connection() as db:
                    rows = db.execute("SELECT payload FROM events WHERE mission=? AND kind='leg_result'", (engine._mission_id,)).fetchall()
                arrivals = [json.loads(row[0]) for row in rows if json.loads(row[0]).get("state") == "arrived"]
                moving_arrivals = [leg for leg in arrivals if math.dist(leg["from"], leg["to"]) >= 1]
                if args.auto_next_map:
                    if len(engine.visited_maps) >= args.maps_target:
                        log("target_maps_completed", count=len(engine.visited_maps), maps=list(engine.visited_maps))
                        break
                    if not engine.worker_thread.is_alive():
                        log("engine_finished_work", visited_count=len(engine.visited_maps))
                        break
                elif args.full_map:
                    if engine.plan and (engine.plan.complete() or engine.plan.is_route_complete()):
                        log("full_map_completed_all_targets", total=len(engine.plan.data["targets"]))
                        break
                    if not engine.worker_thread.is_alive():
                        log("engine_finished_work")
                        break
                elif (not args.soak and len(moving_arrivals) >= args.arrivals
                      and (not args.pause or pauses.get("resumed_same_target"))):
                    log("requested_arrivals_observed", count=len(moving_arrivals))
                    break
                time.sleep(0.25)
            soak_elapsed = time.monotonic()-run_started
            engine.stop()
            engine.worker_thread.join(timeout=35)
            if engine.worker_thread.is_alive():
                raise RuntimeError("Engine did not finish stop within 35 seconds")
            final = vision.get_engine_telemetry()
            screenshot("final")
            with store.connection() as db:
                rows = db.execute("SELECT payload FROM events WHERE mission=? AND kind='leg_result'", (engine._mission_id,)).fetchall()
            legs = [json.loads(row[0]) for row in rows]
            moving_arrivals = [leg for leg in legs if leg.get("state") == "arrived" and math.dist(leg["from"], leg["to"]) >= 1]
            if args.auto_next_map:
                map_complete = len(engine.visited_maps) >= args.maps_target or bool(engine.plan and (engine.plan.complete() or engine.plan.is_route_complete()))
            elif args.full_map:
                map_complete = bool(engine.plan and (engine.plan.complete() or engine.plan.is_route_complete()))
            else:
                map_complete = None
            arrivals_satisfied = map_complete if (args.full_map or args.auto_next_map) else (len(moving_arrivals) >= args.arrivals)
            map_unchanged = all(item["map"] == initial["map_id"] for item in samples) if not args.auto_next_map else True
            result.update(final_phase=engine.route_phase, final_position=final.get("position"),
                          final_doing=final.get("doing"), legs=legs, moving_arrivals=len(moving_arrivals), pauses=pauses,
                          fresh_samples=len(samples), map_unchanged=map_unchanged,
                          visited_maps=list(engine.visited_maps),
                          map_complete=map_complete, soak=args.soak,
                          soak_elapsed_seconds=round(soak_elapsed, 2), soak_snapshots=soak_snapshots)
            soak_valid = (not args.soak or
                          (soak_elapsed >= args.seconds * 0.95 and len(soak_snapshots) >= 1))
            result["passed"] = (arrivals_satisfied and engine.route_phase not in {"error", "stop_unverified"}
                                and final.get("doing") in engine.STOPPED and map_unchanged
                                and soak_valid
                                and (not args.pause or (pauses.get("resumed_same_target") and pauses.get("hold_displacement", 999) <= 0.1)))
    except BaseException as exc:
        result["error"] = str(exc)
        result["traceback"] = traceback.format_exc()
        log("error", message=str(exc))
        try:
            screenshot("failure")
        except Exception:
            pass
    finally:
        if engine.worker_thread and engine.worker_thread.is_alive():
            engine.stop()
            engine.worker_thread.join(timeout=35)
        elif engine.is_running:
            try:
                engine._cancel_and_verify()
            except Exception as exc:
                result["cleanup_error"] = str(exc)
            engine.is_running = False
        ctrl.unlock_session()
        detector.close(timeout=5)
        sync.close(timeout=3)
        sync.export()
        atomic_json(str(directory/"samples.json"), samples)
        result["elapsed_seconds"] = round(time.monotonic()-started, 2)
        result["metrics"] = ctrl.metrics.snapshot()
        atomic_json(str(directory/"result.json"), result)
        log("result", **result)
        log_file.close()
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
