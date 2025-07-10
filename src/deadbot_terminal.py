# v0.1.0

import sys
import deadbot_backend
import os
import re
import threading
import csv
import datetime
import time
from deadbot_perfscan import get_system_metrics
from deadbot_diag import full_diagnose, load_thresholds_from_config


BANNER = """
██████╗ ███████╗ █████╗ ██████╗ ██████╗  ██████╗ ████████╗
██╔══██╗██╔════╝██╔══██╗██╔══██╗██╔══██╗██╔═══██╗╚══██╔══╝
██║  ██║█████╗  ███████║██║  ██║██████╔╝██║   ██║   ██║   
██║  ██║██╔══╝  ██╔══██║██║  ██║██╔══██╗██║   ██║   ██║   
██████╔╝███████╗██║  ██║██████╔╝██████╔╝╚██████╔╝   ██║   
╚═════╝ ╚══════╝╚═╝  ╚═╝╚═════╝ ╚═════╝  ╚═════╝    ╚═╝   

                    DeadBot v0.1.0
---------------------------------------------------------
# ========================================
# Born at midnight. DeadBot never sleeps.
# ========================================
"""
def print_banner():
    print(BANNER)

BENCH_DIR = "./benchs"
os.makedirs(BENCH_DIR, exist_ok=True)

LOGGING = {"active": False, "file": None, "writer": None, "lock": threading.Lock(), "lines": 0, "path": None}

def start_bench_and_thread():
    start_bench_log()
    # On ne démarre la boucle que si pas déjà active
    with LOGGING["lock"]:
        active = LOGGING["active"]
    if active:
        threading.Thread(target=bench_log_loop, daemon=True).start()



def get_menu_choice(prompt, valid_choices):
    raw_input = input(prompt).strip()
    match = re.match(r'^(\d{1,2})$', raw_input)
    if match:
        choice = match.group(1)
        if choice in valid_choices:
            return choice
    return None

def menu():
    actions = {
        "1": lambda: handle_prompt(),
        "2": lambda: switch_backend(),
        "3": lambda: test_fallback(),
        "4": lambda: show_backends(),
        "5": lambda: reload_backends(),
        "6": lambda: sys.exit(print("[DeadBot] Bye !")),
        "7": lambda: start_bench_and_thread(),
        "8": lambda: stop_bench_log()
    }

    valid_choices = actions.keys()

    while True:
        print("\n=== DeadBot CLI Menu ===")
        deadbot_backend.print_backend_status()
        print("Actions :\n"
              " 1. Envoyer un prompt LLM\n"
              " 2. Switch de backend IA\n"
              " 3. Tester le fallback\n"
              " 4. Voir la liste complète des backends\n"
              " 5. Rescanner/recharger les backends IA\n"
              " 6. Quitter\n"
              " 7. Démarrer l’export CSV bench\n"
              " 8. Arrêter l’export CSV bench\n")

        choix = get_menu_choice("\n[DeadBot] Choix (1/2/3/4/5/6/7/8) : ", valid_choices)
        if choix:
            actions[choix]()
        else:
            print("[DeadBot] Entrée incorrecte. Veuillez entrer un nombre valide.")

def handle_prompt():
    prompt = input("[DeadBot] Tape ton prompt : ")
    rep = deadbot_backend.prompt_llm(prompt)
    print(f"[DeadBot][Réponse LLM]\n{rep}")

def switch_backend():
    for idx, name in enumerate(deadbot_backend.AVAILABLE_BACKENDS):
        actif = " [ACTIF]" if name == deadbot_backend.CURRENT_BACKEND else ""
        status = "✅" if deadbot_backend.BACKEND_STATUS.get(name, False) else "❌"
        print(f" [{idx}] {name} {status}{actif}")
    
    try:
        idx = int(input("Numéro du backend à activer : "))
        name = deadbot_backend.AVAILABLE_BACKENDS[idx]
        if deadbot_backend.switch_backend(name):
            print(f"[DeadBot] Backend IA changé pour : {name}")
        else:
            print("[DeadBot] Impossible de changer de backend.")
    except (ValueError, IndexError):
        print("[DeadBot] Sélection invalide.")

def test_fallback():
    print("[DeadBot][TEST] Simulation d’un crash backend IA…")
    try:
        deadbot_backend.simulate_crash()
    except Exception as e:
        print(f"[DeadBot] Crash détecté : {e}\n[DeadBot] Activation du fallback…")
        backend_after = deadbot_backend.handle_fallback()
        if backend_after:
            print(f"[DeadBot] Nouveau backend courant : {backend_after}")
        else:
            print("[DeadBot] Aucun backend IA disponible après fallback.")
    input("[DeadBot] Appuie sur Entrée pour continuer...")

def show_backends():
    deadbot_backend.print_backend_status()
    input("[DeadBot] Appuie sur Entrée pour continuer...")

def reload_backends():
    print("[DeadBot] Rechargement/détection des backends IA...")
    deadbot_backend.detect_backends()
    deadbot_backend.print_backend_status()
    input("[DeadBot] Appuie sur Entrée pour continuer...")

def start_bench_log():
    with LOGGING["lock"]:
        if LOGGING["active"]:
            print(f"[LOG] Bench déjà en cours ! (CSV : {LOGGING['path']})")
            return
        filename = f"benchlog_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path = os.path.join(BENCH_DIR, filename)
        LOGGING["file"] = open(path, "w", newline="", encoding="utf-8")
        LOGGING["writer"] = csv.writer(LOGGING["file"])
        LOGGING["writer"].writerow([
            "timestamp", "cpu", "ram", "gpu", "disk", "vram", "level", "message"
        ])
        LOGGING["active"] = True
        LOGGING["lines"] = 0
        LOGGING["path"] = path
        print(f"[LOG] Export CSV bench démarré : {path}")

def stop_bench_log():
    with LOGGING["lock"]:
        if not LOGGING["active"]:
            print("[LOG] Aucun bench en cours.")
            return
        LOGGING["file"].close()
        n = LOGGING["lines"]
        path = LOGGING["path"]
        LOGGING["active"] = False
        LOGGING["file"] = None
        LOGGING["writer"] = None
        LOGGING["lines"] = 0
        LOGGING["path"] = None
        print(f"[LOG] Export CSV bench terminé : {path} ({n} lignes loggées)")

def bench_log_loop(interval=1.0):
    thresholds = load_thresholds_from_config()
    try:
        while True:
            with LOGGING["lock"]:
                if not LOGGING["active"]:
                    break
            metrics = get_system_metrics()
            diag = full_diagnose(metrics, thresholds=thresholds)
            ts = datetime.datetime.now().isoformat()
            with LOGGING["lock"]:
                if LOGGING["active"] and LOGGING["writer"]:
                    LOGGING["writer"].writerow([
                        ts,
                        metrics.get("cpu", ""),
                        metrics.get("ram", ""),
                        metrics.get("gpu", ""),
                        metrics.get("disk", ""),
                        metrics.get("vram", ""),
                        diag.get("overall_level", ""),
                        diag.get("summary", "")
                    ])
                    LOGGING["file"].flush()
                    LOGGING["lines"] += 1
            time.sleep(interval)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    print_banner()
    menu()