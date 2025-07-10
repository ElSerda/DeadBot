# v0.1.0

import os
import requests
import yaml
from utils.path_utils import get_config_dir

# === Chargement config + credentials (séparés, fusionnés) ===
CONFIG_DIR = get_config_dir()
CONFIG_PATH = CONFIG_DIR / "config.yaml"
CREDENTIALS_PATH = CONFIG_DIR / "credentials.yaml"

def load_yaml(path):
    if not os.path.exists(path):
        print(f"[DeadBot][WARN] Fichier {path} non trouvé.")
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def deep_merge(a, b):
    """Fusion récursive, b écrase a"""
    for k, v in b.items():
        if isinstance(v, dict) and k in a and isinstance(a[k], dict):
            deep_merge(a[k], v)
        else:
            a[k] = v
    return a

# Chargement des fichiers
CONFIG = load_yaml(CONFIG_PATH)
CREDENTIALS = load_yaml(CREDENTIALS_PATH)
CONFIG = deep_merge(CONFIG, CREDENTIALS)


print(CONFIG)
print("[DEBUG] model_path brut:", CONFIG.get("local_llm", {}).get("model_path"))

print("[DeadBot][DEBUG] config.yaml chargé :", CONFIG_PATH)
print("[DeadBot][DEBUG] credentials.yaml chargé :", CREDENTIALS_PATH)
print("[DeadBot][DEBUG] OpenAI key présente :", bool(CONFIG.get("openai", {}).get("api_key", "")))
print("[DeadBot][DEBUG] LLM local path :", CONFIG.get("local_llm", {}).get("model_path", "Non défini"))

# === Détection backends ===
BACKEND_STATUS = {}
AVAILABLE_BACKENDS = []
CURRENT_BACKEND = None
_LOCAL_MODEL_CACHE = None

def check_openai(api_key):
    if not api_key:
        return False
    try:
        r = requests.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=4
        )
        return r.status_code == 200
    except requests.RequestException:
        return False

def check_ollama(url, model):
    if not (url and model):
        return False
    try:
        resp = requests.get(f"{url}/api/tags", timeout=2)
        return resp.status_code == 200 and any(
            m['name'] == model for m in resp.json().get('models', [])
        )
    except requests.RequestException:
        return False

def check_local_llm(model_path):
    #print("[DEBUG] local_llm path testé :", model_path, "->", os.path.exists(model_path))

    return bool(model_path and os.path.exists(model_path))

def detect_backends():
    global AVAILABLE_BACKENDS, CURRENT_BACKEND, BACKEND_STATUS
    backends = []
    old_current = CURRENT_BACKEND
    cfg = CONFIG

    # Statut de chaque backend
    BACKEND_STATUS.clear()
    BACKEND_STATUS["openai"] = check_openai(cfg.get("openai", {}).get("api_key"))
    BACKEND_STATUS["ollama"] = check_ollama(
        cfg.get("ollama", {}).get("url"),
        cfg.get("ollama", {}).get("model")
    )
    BACKEND_STATUS["local_llm"] = check_local_llm(
        cfg.get("local_llm", {}).get("model_path")
    )

    for name, status in BACKEND_STATUS.items():
        if status:
            backends.append(name)
            print(f"[DeadBot] Backend {name} disponible.")
        else:
            print(f"[DeadBot] Backend {name} indisponible.")

    AVAILABLE_BACKENDS = backends
    CURRENT_BACKEND = (
        old_current if old_current in backends else
        backends[0] if backends else None
    )
    return backends

# Initialisation (scan direct au lancement)
detect_backends()

def switch_backend(name):
    global CURRENT_BACKEND
    if name in AVAILABLE_BACKENDS:
        CURRENT_BACKEND = name
        print(f"[DeadBot] Backend IA sélectionné : {name}")
        return True
    print(f"[DeadBot] Impossible de sélectionner le backend {name}.")
    return False

def simulate_crash():
    raise RuntimeError("Backend IA simulé en crash !")

def handle_fallback():
    global CURRENT_BACKEND
    if not AVAILABLE_BACKENDS or CURRENT_BACKEND not in AVAILABLE_BACKENDS:
        CURRENT_BACKEND = None
        return None
    if len(AVAILABLE_BACKENDS) < 2:
        return None
    idx = AVAILABLE_BACKENDS.index(CURRENT_BACKEND)
    next_idx = (idx + 1) % len(AVAILABLE_BACKENDS)
    CURRENT_BACKEND = AVAILABLE_BACKENDS[next_idx]
    print(f"[DeadBot] Fallback : bascule sur {CURRENT_BACKEND}")
    return CURRENT_BACKEND

def prompt_llm(prompt):
    tried = {CURRENT_BACKEND} if CURRENT_BACKEND else set()
    for backend in [CURRENT_BACKEND] + AVAILABLE_BACKENDS:
        if backend and backend not in tried:
            tried.add(backend)
            resp = _try_backend(prompt, backend)
            if resp is not None:
                return resp
    return "[DeadBot] Aucun backend IA n'a répondu ou n'est disponible."

def _try_backend(prompt, backend):
    try:
        if backend == "openai":
            openai_cfg = CONFIG["openai"]
            r = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {openai_cfg['api_key']}"},
                json={
                    "model": openai_cfg.get("model", "gpt-4o"),
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 256
                },
                timeout=30
            )
            if r.status_code == 200:
                return r.json()['choices'][0]['message']['content'].strip()
        
        elif backend == "ollama":
            ollama_cfg = CONFIG["ollama"]
            resp = requests.post(
                f"{ollama_cfg['url']}/api/generate",
                json={"model": ollama_cfg["model"], "prompt": prompt, "stream": False},
                timeout=30
            )
            if resp.status_code == 200:
                return resp.json().get("response", "")
        
        elif backend == "local_llm":
            global _LOCAL_MODEL_CACHE
            local_cfg = CONFIG["local_llm"]
            if _LOCAL_MODEL_CACHE is None:
                from ctransformers import AutoModelForCausalLM
                _LOCAL_MODEL_CACHE = AutoModelForCausalLM.from_pretrained(
                    local_cfg["model_path"],
                    model_type=local_cfg.get("model_type", "llama")
                )
            return _LOCAL_MODEL_CACHE(prompt, max_new_tokens=128).strip()
    
    except Exception as e:
        print(f"[{backend}] Exception: {e}")
    return None

def print_backend_status():
    print("\n=== État des backends ===")
    for name in BACKEND_STATUS:
        status = "✅" if BACKEND_STATUS[name] else "❌"
        actif = " [ACTIF]" if name == CURRENT_BACKEND else ""
        print(f" - {name} : {status}{actif}")
    print()
