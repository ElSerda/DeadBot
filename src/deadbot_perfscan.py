# src/deadbot_perfscan.py
# v0.1.0

import sys
import os
import time
from pathlib import Path
import datetime
import psutil

sys.path.append(str(Path(__file__).resolve().parent))
try:
    import GPUtil
except ImportError:
    GPUtil = None

from utils.path_utils import get_logs_dir

from pathlib import Path

def ensure_logs_dir_exists():
    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir

logs_dir = ensure_logs_dir_exists()
with open(logs_dir / "metrics_overlay.json", "w", encoding="utf-8") as f:
    pass


LOG_PATH = get_logs_dir() / "metrics_overlay.json"
WARNING_LOG_PATH = get_logs_dir() / "perfscan_warnings.log"

# Valeurs par défaut/fallback
DEFAULT_VALUES = {
    "cpu": 0.0, "ram": 0.0, "disk": 0.0, "gpu": 0.0,
    "vram_used": 0.0, "vram_total": 0.0
}
MAX_THRESHOLDS = {
    "cpu": 100.0, "ram": 100.0, "disk": 100.0, "gpu": 100.0,
    "vram_used": 128 * 1024,  # 128 GB
    "vram_total": 128 * 1024
}

def log_critical(msg):
    try:
        with open(WARNING_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now().isoformat()} [CRITICAL] {msg}\n")
    except Exception as e:
        print(f"[ERROR] Impossible de logger le message critique: {e}")

def get_gpu_info():
    if not GPUtil:
        return DEFAULT_VALUES["gpu"], DEFAULT_VALUES["vram_used"], DEFAULT_VALUES["vram_total"]
    try:
        gpus = GPUtil.getGPUs()
        if not gpus:
            return DEFAULT_VALUES["gpu"], DEFAULT_VALUES["vram_used"], DEFAULT_VALUES["vram_total"]
        gpu = gpus[0]
        gpu_percent = gpu.load * 100 if gpu.load is not None else DEFAULT_VALUES["gpu"]
        vram_used = int(gpu.memoryUsed) if gpu.memoryUsed is not None else DEFAULT_VALUES["vram_used"]
        vram_total = int(gpu.memoryTotal) if gpu.memoryTotal is not None else DEFAULT_VALUES["vram_total"]
        # Clamp les valeurs
        gpu_percent = min(max(gpu_percent, 0), MAX_THRESHOLDS["gpu"])
        vram_used = min(max(vram_used, 0), MAX_THRESHOLDS["vram_used"])
        vram_total = min(max(vram_total, 0), MAX_THRESHOLDS["vram_total"])
        return gpu_percent, vram_used, vram_total
    except Exception as e:
        msg = f"GPU driver unavailable (NVIDIA driver crash ?): {e}"
        print(f"[CRITICAL][PERFSCAN] {msg}")
        log_critical(msg)
        return DEFAULT_VALUES["gpu"], DEFAULT_VALUES["vram_used"], DEFAULT_VALUES["vram_total"]

def get_system_metrics():
    metrics = DEFAULT_VALUES.copy()
    # DISK
    try:
        if os.name == "nt":
            disk_root = os.environ.get("SystemDrive", "C:") + "/"
        else:
            disk_root = "/"
        disk_usage = psutil.disk_usage(disk_root).percent
        metrics["disk"] = min(max(round(disk_usage, 1), 0), MAX_THRESHOLDS["disk"])
    except Exception as e:
        print(f"[ERROR][DISK] Failed to get disk usage: {e}")
        log_critical(f"Disk metric error: {e}")
    # CPU
    try:
        cpu = psutil.cpu_percent(interval=0.5)
        metrics["cpu"] = min(max(round(cpu, 1), 0), MAX_THRESHOLDS["cpu"])
    except Exception as e:
        print(f"[ERROR][CPU] Failed to get CPU usage: {e}")
        log_critical(f"CPU metric error: {e}")
    # RAM
    try:
        ram = psutil.virtual_memory().percent
        metrics["ram"] = min(max(round(ram, 1), 0), MAX_THRESHOLDS["ram"])
    except Exception as e:
        print(f"[ERROR][RAM] Failed to get RAM usage: {e}")
        log_critical(f"RAM metric error: {e}")
    # GPU & VRAM
    try:
        gpu_load, vram_used, vram_total = get_gpu_info()
        metrics["gpu"] = gpu_load
        metrics["vram_used"] = vram_used
        metrics["vram_total"] = vram_total
    except Exception as e:
        print(f"[ERROR][GPU] Failed to get GPU info: {e}")
        log_critical(f"GPU metric error: {e}")
    return metrics

def main_loop(interval=0.5):
    while True:
        metrics = get_system_metrics()
        print("[METRIC][DEBUG]", metrics)
        try:
            import json
            with open(LOG_PATH, "w", encoding="utf-8") as f:
                json.dump(metrics, f)
        except Exception as e:
            print("[ERROR] Failed to write overlay metrics:", e)
        time.sleep(interval)

def start_scan(interval=0.5, duration=3):
    """
    Scanne les métriques système toutes les X secondes pendant Y secondes.
    Retourne une liste de dicts (chaque tick = 1 dict métriques).
    """
    results = []
    t_end = time.time() + duration
    while time.time() < t_end:
        metrics = get_system_metrics()
        results.append(metrics.copy())
        time.sleep(interval)
    return results

if __name__ == "__main__":
    print("[SYSTEM] Début du scan de performance DeadBot")
    main_loop()
