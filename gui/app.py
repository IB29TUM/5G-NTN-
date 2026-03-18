"""
OAI-NTN-ZeroRF: Lightweight web dashboard (Flask)
Serves system status, KPIs, and call flow. WSL-compatible; bind 0.0.0.0:5000.
"""
import json
import os
import subprocess
from pathlib import Path

from flask import Flask, render_template, jsonify

app = Flask(__name__)
ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "reports"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/summary")
def api_summary():
    p = REPORTS_DIR / "summary.json"
    if not p.exists():
        return jsonify({"error": "No report yet", "timestamp": None}), 404
    try:
        data = json.loads(p.read_text())
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/callflow")
def api_callflow():
    p = REPORTS_DIR / "callflow.md"
    if not p.exists():
        return "", 404
    return p.read_text(errors="replace"), 200, {"Content-Type": "text/markdown; charset=utf-8"}


@app.route("/api/status")
def api_status():
    """Container health from docker compose ps."""
    out = []
    try:
        res = subprocess.run(
            ["docker", "compose", "ps", "--format", "json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if res.returncode != 0:
            res = subprocess.run(
                ["docker-compose", "ps", "--format", "json"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=10,
            )
        if res.returncode == 0 and res.stdout.strip():
            for line in res.stdout.strip().splitlines():
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return jsonify({"containers": out})


if __name__ == "__main__":
    # Use 5001 to avoid conflict with Windows port 5000 (e.g. Airplay Receiver)
    app.run(host="0.0.0.0", port=5001, debug=False)
