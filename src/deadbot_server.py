# src\deadbot_server.py
# v0.1.0

import os
import sys
import time
import threading
from pathlib import Path
from typing import Dict, Any
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import yaml
from deadbot_diag import full_diagnose, load_thresholds_from_config
from deadbot_backend import AVAILABLE_BACKENDS, CURRENT_BACKEND, detect_backends, switch_backend, prompt_llm

# ============ DeadBot modules à importer ============
from deadbot_perfscan import get_system_metrics
from deadbot_diag import full_diagnose

try:
    from ctransformers import AutoModelForCausalLM
except ImportError:
    print("[ERREUR] ctransformers n'est pas installé.")
    sys.exit(1)

# ============ Chargement Config ============
import os
from pathlib import Path

# Cherche la config à la racine du projet, pas au cwd
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = PROJECT_ROOT / "config" / "config.yaml"
print(f"[DEBUG] Chargement de la configuration depuis {CONFIG_FILE}")  # Debug
with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)
print(f"[DEBUG] Configuration chargée: {config}")  # Debug

MODEL_DIR = PROJECT_ROOT / "models"

# ============ Setup FastAPI ============
app = FastAPI()
MODEL_CACHE = {"model": None, "path": None, "type": None}
MODEL_LOCK = threading.Lock()

# ============ Gestion modèle global ============
def get_llm_model(model_path: str, model_type: str):
    with MODEL_LOCK:
        if (
            MODEL_CACHE["model"] is not None
            and MODEL_CACHE["path"] == model_path
            and MODEL_CACHE["type"] == model_type
        ):
            print(f"[DEBUG] Utilisation du modèle en cache: {model_path}")  # Debug
            return MODEL_CACHE["model"]
        
        print(f"[DeadBot] Chargement du modèle : {model_path}")
        t0 = time.time()
        model = AutoModelForCausalLM.from_pretrained(model_path, model_type=model_type)
        load_time = time.time() - t0
        print(f"[DeadBot] Modèle chargé en {load_time:.2f}s")
        print(f"[DEBUG] Type modèle: {model_type}, Chemin: {model_path}")  # Debug
        
        MODEL_CACHE["model"] = model
        MODEL_CACHE["path"] = model_path
        MODEL_CACHE["type"] = model_type
        return model

def unload_llm_model():
    with MODEL_LOCK:
        print("[DEBUG] Vidage du cache du modèle")  # Debug
        MODEL_CACHE["model"] = None
        MODEL_CACHE["path"] = None
        MODEL_CACHE["type"] = None

# ============ Endpoints ============

@app.get("/backends")
def list_backends():
    return {"backends": AVAILABLE_BACKENDS, "current": CURRENT_BACKEND}

@app.post("/switch_backend")
def switch_backend_route(req: dict):
    name = req.get("name")
    ok = switch_backend(name)
    return {"success": ok, "current": CURRENT_BACKEND}

@app.post("/prompt")
def prompt_route(req: dict):
    prompt = req.get("prompt", "")
    return {"response": prompt_llm(prompt)}

@app.post("/prompt")
async def llama_prompt(request: Request):
    try:
        data = await request.json()
        prompt = data.get("prompt", "").strip()
        if not prompt:
            print("[DEBUG] Prompt vide reçu")  # Debug
            return JSONResponse(status_code=400, content={"error": "Prompt vide."})
        
        model_file = config['llm']['last_model']
        model_path = str(MODEL_DIR / model_file)
        model_type = config['llm'].get('model_type', 'llama')
        print(f"[DEBUG] Utilisation du modèle: {model_file} (type: {model_type})")  # Debug

        model = get_llm_model(model_path, model_type)

        print(f"[PROMPT] => {prompt}")
        print(f"[DEBUG] Longueur du prompt: {len(prompt)} caractères")  # Debug
        t0 = time.time()
        response = model(prompt, max_new_tokens=256)
        response_time = time.time() - t0
        print(f"[PROMPT][Réponse LLM en {response_time:.2f}s]")
        print(f"[DEBUG] Longueur réponse: {len(response)} caractères")  # Debug
        return {"response": response.strip()}
    except Exception as e:
        print(f"[ERREUR] Endpoint /prompt: {str(e)}")  # Debug
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/diag")
async def get_diag():
    try:
        print("[DEBUG] Collecte des métriques système")  # Debug
        metrics = get_system_metrics()
        print(f"[DEBUG] Métriques collectées: {metrics}")  # Debug

        print("[DEBUG] Exécution du diagnostic complet")  # Debug
        thresholds = load_thresholds_from_config()
        diag = full_diagnose(metrics, thresholds=thresholds)
        print(f"[DEBUG] Résultat diagnostic: {diag}")  # Debug

        return {"diagnostic": diag}
    except Exception as e:
        print(f"[ERREUR] Endpoint /diag: {str(e)}")  # Debug
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/switch")
async def switch_model(new_model: Dict[str, str]) -> Dict[str, str]:
    model_file = new_model.get("model_file")
    model_type = new_model.get("model_type", config['llm'].get('model_type', 'llama'))
    if not model_file:
        print("[DEBUG] Changement de modèle: fichier non spécifié")  # Debug
        return {"error": "No model file specified"}
    
    try:
        print(f"[DEBUG] Changement de modèle: {model_file} (type: {model_type})")  # Debug
        config['llm']['last_model'] = model_file
        config['llm']['model_type'] = model_type
        
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f)
        print("[DEBUG] Configuration mise à jour")  # Debug
        
        unload_llm_model()
        return {"status": "ok", "message": f"Modèle changé pour : {model_file}"}
    except Exception as e:
        print(f"[ERREUR] Changement de modèle: {str(e)}")  # Debug
        return {"status": "error", "message": str(e)}

@app.get("/metrics")
async def get_metrics():
    try:
        print("[DEBUG] Collecte des métriques système (endpoint /metrics)")  # Debug
        metrics = get_system_metrics()
        print(f"[DEBUG] Métriques retournées: {list(metrics.keys())}")  # Debug
        return metrics
    except Exception as e:
        print(f"[ERREUR] Endpoint /metrics: {str(e)}")  # Debug
        return JSONResponse(status_code=500, content={"error": str(e)})

# ============ (option) Ajouter d'autres endpoints ============

# Ajoute ici tes autres endpoints /export, /overlay, etc., selon ton usage.

# ============ Main ============

if __name__ == "__main__":
    import uvicorn
    print("[DEBUG] Démarrage du serveur Uvicorn")  # Debug
    uvicorn.run("deadbot_server:app", host="127.0.0.1", port=8080, reload=True)
