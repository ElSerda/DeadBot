# src\serveur_overlay.py
# v0.1.0

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pathlib import Path
import json

from deadbot_perfscan import get_system_metrics
from deadbot_diag import full_diagnose

app = FastAPI(
    title="DeadBot Overlay API",
    description="Endpoints live for overlay OBS, dashboard, etc.",
    version="0.2"
)

version_file = Path(__file__).parent.parent / "version.txt"
if version_file.exists():
    version = version_file.read_text().strip()
else:
    version = "v0.0.0"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Static files (failsafe overlay) ===
static_dir = Path(__file__).parent / "static"
static_overlay_dir = static_dir / "overlay"
static_overlay_dir.mkdir(parents=True, exist_ok=True)

# Fichiers overlay à garantir
for name in ["gpu.html", "cpu.html", "ram.html", "vram.html"]:
    file_path = static_overlay_dir / name
    if not file_path.exists():
        file_path.write_text(
            f"<html><body><h2>{name.split('.')[0].upper()} Overlay — WIP</h2></body></html>",
            encoding="utf-8"
        )

# (Déjà présent) Crée overlay.html de base si le dossier static/ est vide
if not any(static_dir.iterdir()):
    (static_dir / "overlay.html").write_text(
        "<html><body><h1>Overlay DeadBot (placeholder)</h1></body></html>",
        encoding="utf-8"
    )

app.mount("/static", StaticFiles(directory=static_dir), name="static")

LOG_PATH = Path(__file__).parent.parent / "logs" / "metrics_overlay.json"

app.mount("/static", StaticFiles(directory=static_dir), name="static")

LOG_PATH = Path(__file__).parent.parent / "logs" / "metrics_overlay.json"

@app.get("/metrics")
def metrics_api():
    """Retourne les dernières métriques live depuis le fichier JSON."""
    try:
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            metrics = json.load(f)
    except Exception as e:
        metrics = {
            "cpu": 0, "ram": 0, "disk": 0, "swap": 0,
            "gpu": 0, "vram_used": 0, "vram_total": 0
        }
    return metrics

@app.get("/overlay", response_class=HTMLResponse)
async def get_overlay():
    # Lis le template overlay.html depuis le fichier
    overlay_path = Path(__file__).parent / "static" / "overlay.html"
    html_content = overlay_path.read_text()

    # Injecter la version dans le HTML (exemple basique, remplacer une variable)
    html_content = html_content.replace("{{version}}", version)

    return HTMLResponse(content=html_content, status_code=200)

@app.get("/diagnostics")
def diagnostics_api(symptom: str = None):
    """Analyse et retourne un diagnostic système structuré."""
    metrics = get_system_metrics()

    # Synthétise l’usage VRAM %
    vram_pct = 0
    if metrics.get("vram_used", 0) and metrics.get("vram_total", 0):
        vram_pct = (metrics["vram_used"] / metrics["vram_total"]) * 100
    metrics["vram"] = round(vram_pct, 1)

    # Appelle l’analyseur
    diag = full_diagnose(metrics, symptom=symptom)
    return diag

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("serveur_overlay:app", host="127.0.0.1", port=7860, reload=True)
