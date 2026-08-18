"""تجارت‌یار — professional, evidence-first trade decision web server."""

from __future__ import annotations

import json
import os
import secrets
import threading
import time
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, request, send_file, send_from_directory

from agent.exports import export_all
from agent.pipeline import run_pipeline

ROOT = Path(__file__).resolve().parent
JOBS_DIR = ROOT / "jobs"
OUT_DIR = ROOT / "outputs"
STATIC = ROOT / "static"
JOBS_DIR.mkdir(exist_ok=True)
OUT_DIR.mkdir(exist_ok=True)

app = Flask(__name__, static_folder=str(STATIC), static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024

JOBS: dict[str, dict] = {}
LOCK = threading.Lock()
MAX_ACTIVE_JOBS = max(1, int(os.environ.get("MAX_ACTIVE_JOBS", "3")))
JOB_TTL_HOURS = max(1, int(os.environ.get("JOB_TTL_HOURS", "24")))
LOCAL_TZ = ZoneInfo(os.environ.get("APP_TIMEZONE", "Asia/Tehran"))


def _now() -> datetime:
    return datetime.now(LOCAL_TZ)


def _clean(value, max_len: int = 500) -> str:
    value = str(value or "").replace("\x00", "").strip()
    return value[:max_len]


def _save(job: dict) -> None:
    path = JOBS_DIR / f"{job['id']}.json"
    serial = {k: v for k, v in job.items() if k != "thread"}
    path.write_text(json.dumps(serial, ensure_ascii=False, indent=2), encoding="utf-8")


def _load(job_id: str) -> dict | None:
    with LOCK:
        job = JOBS.get(job_id)
    if job:
        return job
    path = JOBS_DIR / f"{job_id}.json"
    if not path.exists():
        return None
    try:
        job = json.loads(path.read_text(encoding="utf-8"))
        with LOCK:
            JOBS[job_id] = job
        return job
    except Exception:
        return None


def _authorized(job: dict) -> bool:
    supplied = request.headers.get("X-Job-Token") or request.args.get("token") or ""
    expected = job.get("access_token") or ""
    return bool(supplied and expected and secrets.compare_digest(supplied, expected))


def _cleanup_old_jobs() -> None:
    cutoff_ts = time.time() - JOB_TTL_HOURS * 3600
    for path in JOBS_DIR.glob("*.json"):
        try:
            if path.stat().st_mtime >= cutoff_ts:
                continue
            job_id = path.stem
            path.unlink(missing_ok=True)
            out = OUT_DIR / job_id
            if out.exists():
                for f in out.iterdir():
                    if f.is_file():
                        f.unlink(missing_ok=True)
                out.rmdir()
            with LOCK:
                JOBS.pop(job_id, None)
        except Exception:
            continue


def _emit_factory(job_id: str):
    def emit(stage: str, message: str, payload=None):
        with LOCK:
            job = JOBS.get(job_id)
            if not job:
                return
            previous = job.get("current_stage") or "init"
            if stage.startswith("stage"):
                try:
                    current_n = int(stage.replace("stage", ""))
                except ValueError:
                    current_n = 0
                if previous.startswith("stage") and previous != stage:
                    try:
                        prev_n = int(previous.replace("stage", ""))
                        if prev_n < current_n and previous not in job["completed"]:
                            job["completed"].append(previous)
                    except ValueError:
                        pass
                job["current_stage"] = stage
                job["progress"] = min(94, max(5, (current_n - 1) * 13 + (5 if payload else 2)))
            if stage == "done":
                if previous.startswith("stage") and previous not in job["completed"]:
                    job["completed"].append(previous)
                job["progress"] = 97
                job["current_stage"] = "done"
            job["logs"].append({"t": _now().strftime("%H:%M:%S"), "stage": stage, "message": _clean(message, 600)})
            if payload:
                job.setdefault("partial", {})[stage] = True
            _save(job)
    return emit


def _worker(job_id: str, payload: dict) -> None:
    emit = _emit_factory(job_id)
    try:
        dossier = run_pipeline(payload, emit)
        files = export_all(dossier, OUT_DIR / job_id)
        with LOCK:
            job = JOBS[job_id]
            job.update({"status": "done", "progress": 100, "current_stage": "done", "dossier": dossier, "files": files, "finished": _now().isoformat(timespec="seconds")})
            job["logs"].append({"t": _now().strftime("%H:%M:%S"), "stage": "done", "message": "فایل‌های تحویل و گزارش کنترل کیفیت آماده است."})
            _save(job)
    except Exception as exc:
        with LOCK:
            job = JOBS[job_id]
            job["status"] = "error"
            job["error"] = _clean(str(exc), 500) or "خطای داخلی در اجرای پرونده"
            job["error_detail"] = traceback.format_exc()[-4000:]
            job["logs"].append({"t": _now().strftime("%H:%M:%S"), "stage": "error", "message": job["error"]})
            _save(job)


@app.after_request
def after(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "same-origin"
    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.path.startswith("/static/") or request.path == "/":
        resp.headers["Cache-Control"] = "no-store"
    return resp


@app.get("/")
def index():
    return send_from_directory(STATIC, "index.html")


@app.post("/api/run")
def api_run():
    _cleanup_old_jobs()
    data = request.get_json(force=True, silent=True) or {}
    name_fa = _clean(data.get("name_fa") or data.get("product_fa"), 160)
    name_en = _clean(data.get("name_en") or data.get("product_en"), 160)
    if not name_fa and not name_en:
        return jsonify({"ok": False, "error": "نام محصول را فارسی یا انگلیسی وارد کنید."}), 400
    with LOCK:
        active = sum(1 for j in JOBS.values() if j.get("status") == "running")
    if active >= MAX_ACTIVE_JOBS:
        return jsonify({"ok": False, "error": "ظرفیت اجرای هم‌زمان تکمیل است؛ چند دقیقه دیگر دوباره تلاش کنید."}), 429

    owner_fa = _clean(data.get("owner_fa"), 100)
    owner_en = _clean(data.get("owner_en"), 100)
    payload = {
        "name_fa": name_fa or name_en, "name_en": name_en,
        "product_category": _clean(data.get("product_category") or "auto", 40),
        "application": _clean(data.get("application"), 300),
        "specs": _clean(data.get("specs"), 1000),
        "grade_model": _clean(data.get("grade_model"), 300),
        "unit": _clean(data.get("unit"), 100),
        "target_customer": _clean(data.get("target_customer"), 200),
        "qty_hint": _clean(data.get("qty_hint"), 150),
        "origin_pref": _clean(data.get("origin_pref"), 200),
        "owner_fa": owner_fa, "owner_en": owner_en,
        "organization": _clean(data.get("organization"), 160),
        "project_title": _clean(data.get("project_title"), 220),
        "report_purpose": _clean(data.get("report_purpose"), 300),
        "buyer_name": _clean(data.get("buyer_name") or owner_fa, 100),
        "buyer_name_en": _clean(data.get("buyer_name_en") or owner_en, 100),
        "buyer_email": _clean(data.get("buyer_email"), 160),
        "buyer_city": _clean(data.get("buyer_city") or "Tehran, Iran", 120),
    }
    job_id = uuid.uuid4().hex[:24]
    access_token = secrets.token_urlsafe(24)
    job = {
        "id": job_id, "access_token": access_token, "status": "running", "progress": 2,
        "current_stage": "init", "completed": [], "logs": [],
        "created": _now().isoformat(timespec="seconds"), "input": payload,
        "dossier": None, "files": {}, "error": "",
    }
    with LOCK:
        JOBS[job_id] = job
        _save(job)
    thread = threading.Thread(target=_worker, args=(job_id, payload), daemon=True)
    thread.start()
    return jsonify({"ok": True, "job_id": job_id, "access_token": access_token})


@app.get("/api/job/<job_id>")
def api_job(job_id: str):
    job = _load(job_id)
    if not job:
        return jsonify({"ok": False, "error": "job not found"}), 404
    if not _authorized(job):
        return jsonify({"ok": False, "error": "unauthorized"}), 403
    return jsonify({
        "ok": True, "id": job["id"], "status": job["status"], "progress": job["progress"],
        "current_stage": job["current_stage"], "completed": job["completed"], "logs": job["logs"],
        "error": job.get("error") or "", "files": job.get("files") or {},
        "dossier": job.get("dossier"), "input": job.get("input"), "created": job.get("created"),
    })


@app.get("/api/job/<job_id>/file/<kind>")
def api_file(job_id: str, kind: str):
    if kind not in {"report", "excel", "rfq", "prompts"}:
        return jsonify({"error": "invalid file kind"}), 400
    job = _load(job_id)
    if not job:
        return jsonify({"error": "not found"}), 404
    if not _authorized(job):
        return jsonify({"error": "unauthorized"}), 403
    fname = (job.get("files") or {}).get(kind)
    if not fname:
        return jsonify({"error": "file not ready"}), 404
    fpath = (OUT_DIR / job_id / fname).resolve()
    expected_root = (OUT_DIR / job_id).resolve()
    if expected_root not in fpath.parents or not fpath.exists():
        return jsonify({"error": "missing"}), 404
    return send_file(fpath, as_attachment=True, download_name=fname)


@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "tejaratyar", "version": "4.1-premium", "developer": "Setayesh Jafari"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
