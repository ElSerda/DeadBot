#╦ v0.1.0

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))
from utils.path_utils import get_logs_dir

import os
import json
import time
import yaml
import requests
from datetime import datetime
from deadbot_perfscan import get_system_metrics

LOGS_DIR = "./logs"
os.makedirs(LOGS_DIR, exist_ok=True)
EVENT_LOG_PATH = os.path.join(LOGS_DIR, "deadbot_critical_log.json")
DISCORD_WEBHOOK = ""  # TODO: Renseigner dans config.yaml


def load_thresholds_from_config(config_path="config/config.yaml"):
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    alert = config.get("alert", {})
    return {
        metric: (
            float(values.get("warning", 70)),
            float(values.get("critical", 90))
        )
        for metric, values in alert.items()
    }

def detect_critical(metrics: dict, thresholds: dict) -> str | None:
    """
    Détermine si une métrique dépasse un seuil critique
    Returns:
        str | None : message si alerte déclenchée
    """
    for name in ["cpu", "gpu", "ram", "disk"]:
        crit = thresholds.get(name, (70, 90))[1]
        if metrics.get(name, 0) >= crit:
            return f"[ALERTE] {name.upper()} > {crit}%"
    return None

def log_event(message: str):
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "event": message
    }
    with open(EVENT_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")

def send_to_discord(message: str):
    if not DISCORD_WEBHOOK:
        return
    requests.post(DISCORD_WEBHOOK, json={"content": message})

def read_metrics():
    # Optionnel: lecture metrics depuis fichier JSON comme overlay
    try:
        with open("logs/metrics_overlay.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def monitor_critical_events(interval=2):
    print("[DeadBot] Surveillance des événements critiques...")
    thresholds = load_thresholds_from_config()
    try:
        while True:
            metrics = get_system_metrics()
            alert = detect_critical(metrics, thresholds)
            if alert:
                log_event(alert)
                send_to_discord(alert)
                print(alert)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("[DeadBot] Arrêt surveillance.")

if __name__ == "__main__":
    monitor_critical_events()
