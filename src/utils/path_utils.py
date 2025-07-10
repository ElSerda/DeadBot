# src/utils/path_utils.py
# v0.1.0

from pathlib import Path

def get_project_root():
    """Retourne le chemin absolu du dossier racine du projet."""
    return Path(__file__).resolve().parents[2]

def get_config_dir():
    return get_project_root() / "config"

def get_logs_dir():
    return get_project_root() / "logs"

def get_models_dir():
    return get_project_root() / "models"

def get_docs_dir():
    return get_project_root() / "docs"

def get_network_share_dir():
    # Adapter ici selon ton infra (ex: OVH, NAS, etc.)
    return Path(r"\\NAS\shared_folder")

# (ajoute ici tout autre répertoire utile à l’avenir)
