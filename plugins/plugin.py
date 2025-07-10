# src/plugin.py
# v0.1.0

import sys
import os
from pathlib import Path

# Ajoute la racine du projet au PYTHONPATH (pour "from src.deadbot_diag import ...")
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


import json
import logging
from typing import Optional

from src.deadbot_diag import full_diagnose
from src.deadbot_graph_launcher import launch_realtime_graph
from src.deadbot_perfscan import get_system_metrics, start_scan
from src.deadbot_eventlog import log_event

LOG_FILE = os.path.join(os.environ.get("USERPROFILE", "."), 'deadbot_plugin.log')
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def main():
    TOOL_CALLS_PROPERTY = 'tool_calls'
    CONTEXT_PROPERTY = 'messages'
    SYSTEM_INFO_PROPERTY = 'system_info'
    FUNCTION_PROPERTY = 'func'
    PARAMS_PROPERTY = 'properties'
    INITIALIZE_COMMAND = 'initialize'
    SHUTDOWN_COMMAND = 'shutdown'
    ERROR_MESSAGE = 'Plugin Error!'

    commands = {
        'initialize': execute_initialize_command,
        'shutdown': execute_shutdown_command,
        'diagnose_env': execute_diagnose_env,
        'show_graph': execute_show_graph,
        'export_log': execute_export_log
    }

    cmd = ''
    logging.info('DeadBot plugin started')
    while cmd != SHUTDOWN_COMMAND:
        input_data = read_command()
        if input_data is None:
            logging.error('Error reading command')
            continue

        response = None
        if TOOL_CALLS_PROPERTY in input_data:
            tool_calls = input_data[TOOL_CALLS_PROPERTY]
            for tool_call in tool_calls:
                cmd = tool_call.get(FUNCTION_PROPERTY, '')
                logging.info(f'Processing command: {cmd}')
                if cmd in commands:
                    if cmd in ['initialize', 'shutdown']:
                        response = commands[cmd]()
                    else:
                        params = tool_call.get(PARAMS_PROPERTY, {})
                        context = input_data.get(CONTEXT_PROPERTY, {})
                        system_info = input_data.get(SYSTEM_INFO_PROPERTY, {})
                        response = commands[cmd](params, context, system_info)
                else:
                    response = generate_failure_response(f'{ERROR_MESSAGE} Unknown command: {cmd}')
        else:
            response = generate_failure_response(f'{ERROR_MESSAGE} Malformed input.')

        write_response(response)

        if cmd == SHUTDOWN_COMMAND:
            break
    logging.info('DeadBot plugin stopped.')
    return 0

def execute_initialize_command() -> dict:
    logging.info('Initializing DeadBot plugin')
    return generate_success_response('DeadBot initialized.')

def execute_shutdown_command() -> dict:
    logging.info('Shutting down DeadBot plugin')
    return generate_success_response('DeadBot shutdown.')

def execute_diagnose_env(params=None, context=None, system_info=None) -> dict:
    """
    Diagnostique l'environnement à partir des métriques fournies.
    Attendu : params["metrics"] = dict des métriques système, params["symptom"] (optionnel)
    """
    metrics = params.get("metrics")
    symptom = params.get("symptom", "")
    if not metrics:
        # Par défaut, tente de lire les métriques temps réel (fail-safe)
        try:
            metrics = get_system_metrics()
        except Exception:
            return generate_failure_response("Aucune métrique transmise ni détectée.")

    try:
        result = full_diagnose(metrics, symptom)
        # Event log pour trace ou démo
        log_event(f"DIAGNOSE: {result}")
        return generate_success_response(result)
    except Exception as e:
        logging.error(f"Diagnose failed: {e}")
        return generate_failure_response(f"Erreur diagnostic: {e}")

def execute_show_graph(params=None, context=None, system_info=None) -> dict:
    # Affiche la fenêtre graphique matplotlib (bloquante)
    try:
        duration = params.get("duration", 8)
        launch_realtime_graph()
        log_event("SHOW_GRAPH called.")
        return generate_success_response(f"Graphe affiché ({duration}s).")
    except Exception as e:
        logging.error(f"Show graph failed: {e}")
        return generate_failure_response(f"Erreur graph: {e}")

def execute_export_log(params=None, context=None, system_info=None) -> dict:
    import csv
    from datetime import datetime
    try:
        format_ = params.get("format", "csv")
        path = params.get("path", f"deadbot_export_{datetime.now().strftime('%H%M%S')}.{format_}")
        results = start_scan(interval=0.5, duration=3)
        keys = ["cpu", "gpu", "ram", "disk"]
        if format_ == "csv":
            with open(path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                for r in results:
                    row = {k: r.get(k, 0) for k in keys}
                    writer.writerow(row)
        else:
            import json
            with open(path, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2)
        log_event(f"EXPORT_LOG: {path}")
        return generate_success_response(f"Log exporté dans {path}.")
    except Exception as e:
        logging.error(f"Export log failed: {e}")
        return generate_failure_response(f"Erreur export log: {e}")

def read_command() -> Optional[dict]:
    try:
        line = input()
        if not line:
            return None
        return json.loads(line)
    except Exception:
        return None

def write_response(response: dict) -> None:
    try:
        print(json.dumps(response), flush=True)
    except Exception:
        pass

def generate_failure_response(message: str = None) -> dict:
    return {'success': False, 'message': message or 'Failure'}

def generate_success_response(message: str = None) -> dict:
    return {'success': True, 'message': message or 'Success'}

if __name__ == '__main__':
    main()
