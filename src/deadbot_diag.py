# src/deadbot_diag.py
# v0.1.0

"""
Module : deadbot_diag.py
Diagnostic système multi-métriques, structuré et niveau d'alerte, G-Assist ready.
"""

import yaml

def load_thresholds_from_config(config_path="config/config.yaml"):
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    alert = config.get("alert", {})
    # Génère un dict: {metric: (warning, critical)}
    return {
        metric: (
            float(values.get("warning", 70)),
            float(values.get("critical", 90))
        )
        for metric, values in alert.items()
    }

def analyze_metric(name, value, warning, critical):
    if value >= critical:
        level = "CRITICAL"
        msg = f"[CRITICAL][{name.upper()}] {name} à {value:.1f}% : Surcharge critique"
    elif value >= warning:
        level = "WARNING"
        msg = f"[WARNING][{name.upper()}] {name} à {value:.1f}% : Usage élevé"
    else:
        level = "INFO"
        msg = f"[INFO][{name.upper()}] {name} à {value:.1f}% : Tout va bien"
    return {"metric": name, "value": value, "level": level, "message": msg}

def full_diagnose(metrics, symptom=None, thresholds=None, system_info=None):
    # Calcul de la VRAM (%) si possible
    if "vram_used" in metrics and "vram_total" in metrics and metrics["vram_total"] > 0:
        vram_percent = (metrics["vram_used"] / metrics["vram_total"]) * 100
        metrics["vram"] = round(vram_percent, 1)

    metrics.pop("vram_used", None)
    metrics.pop("vram_total", None)

    if thresholds is None:
        thresholds = load_thresholds_from_config()

    results = []
    for name, value in metrics.items():
        warn, crit = thresholds.get(name, (70, 90))
        results.append(analyze_metric(name, value, warn, crit))

    levels = [r["level"] for r in results]
    if "CRITICAL" in levels:
        overall = "CRITICAL"
    elif "WARNING" in levels:
        overall = "WARNING"
    else:
        overall = "INFO"

    summary = next((r["message"] for r in results if r["level"] == overall), "Rien à signaler.")
    if overall == "INFO":
        summary = "[INFO] Aucun goulot d'étranglement détecté. Système OK."
    if symptom:
        summary = f"{summary} (Symptôme utilisateur : {symptom})"

    return {
        "diagnostics": results,
        "overall_level": overall,
        "summary": summary,
        "symptom": symptom,
    }

# === Export diagnostic vers fichier (JSON / CSV) ===
import json
import csv
import datetime
from pathlib import Path

try:
    from utils.path_utils import get_logs_dir
except ImportError:
    def get_logs_dir():
        return Path.cwd() / "logs"

def export_log(diagnostic_result: dict, format: str = "json", path: str = None):
    log_dir = get_logs_dir()
    log_dir.mkdir(parents=True, exist_ok=True)

    if path is None:
        filename = f"diagnostic_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.{format}"
        path = log_dir / filename
    else:
        path = Path(path)

    if format == "json":
        with open(path, "w", encoding="utf-8") as f:
            json.dump(diagnostic_result, f, indent=2, ensure_ascii=False)
    elif format == "csv":
        with open(path, "w", newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Metric", "Value", "Level", "Message"])
            for entry in diagnostic_result.get("diagnostics", []):
                writer.writerow([
                    entry.get("metric", ""),
                    entry.get("value", ""),
                    entry.get("level", ""),
                    entry.get("message", "")
                ])
    else:
        raise ValueError("Format non supporté. Utilise 'json' ou 'csv'.")

    return str(path)

# === Test local (pour debug rapide) ===
if __name__ == "__main__":
    metrics = {
        "cpu": 91.0,
        "ram": 78.2,
        "gpu": 84.5,
        "disk": 42.1,
        "vram_used": 11500,
        "vram_total": 16384
    }
    thresholds = load_thresholds_from_config()
    result = full_diagnose(metrics, symptom="stutter + drop fps", thresholds=thresholds)
    export_path = export_log(result, format="csv")
    print(f"Diagnostic exporté : {export_path}")
