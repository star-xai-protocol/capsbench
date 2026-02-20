# -*- coding: utf-8 -*-
"""
green_agent.py
Version: 4.0 (Gymnasium Server Bridge + STAR-XAI)
Authors: STAR-XAI Team

DESCRIPTION:
HTTP Server that exposes a standardized Gymnasium environment via a REST API.
Allows remote agents (Agent-to-Agent) to interact with 'Caps i Caps'
following the strict Reinforcement Learning protocol.
The HTTP Server acts as the "Evaluator Agent" (Green Agent) defined in the AAA architecture.
It encapsulates the reference environment, issues tasks, and collects results.
Exposes an A2A-compatible API to enable interoperability with any evaluated agent (Purple Agent).

DATA FLOW:
Client (Purple Agent) -> HTTP POST -> Green Agent (Flask) -> CapsiCapsEnv (Gym) -> GameLogic (Engine)

FEATURES:
- Native Gymnasium support (step/reset).
- Automatic logging of RL metrics (Reward, Done).
- Detection and relay of Entropy alerts (⚠️).
- Support for optional 'reasoning' field (STAR-XAI).
- Injection of Entropy events (⚠️) into game history to ensure reproducibility (Replayability). v2.2
- RECORDING_MODE: Switch to enable/disable recording. v3.1
- Dynamic filenames with Level (replay_L1_...). v3.1
- Folder renamed to 'results'. v4.0
- Filename clean (timestamp based). v4.0
- 'agent_id' injected into metadata. v4.0
- 'reasoning' injected into data snapshot. v4.0
- Log label changed to REASONING. v4.0

AAA -> Agentified Agent Assessment
"""
import json
import time
import glob

import logging
import os
import sys
import re
from datetime import datetime, timezone
import json
import shutil
import argparse  # <--- Asegúrate de importar esto arriba del todo

# from flask import Flask, request, jsonify
# from flask import Flask, request, jsonify, Response, stream_with_context
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS


# --- PARCHE DE EMERGENCIA (GPS TOTAL) ---
# 1. Obtiene la ruta de este archivo (src/ixentbench/green_agent.py)
current_dir = os.path.dirname(os.path.abspath(__file__))
# 2. Obtiene la ruta padre (src/)
parent_dir = os.path.dirname(current_dir)
# 3. Obtiene la raíz del proyecto
root_dir = os.path.dirname(parent_dir)

# 4. AÑADIMOS TODO AL PATH para que Python encuentre los archivos sí o sí
sys.path.append(current_dir) # Para encontrar capsicaps_env.py
sys.path.append(parent_dir)  # Para encontrar paquetes hermanos
sys.path.append(root_dir)    # Para encontrar configs en raiz

# --- FIN DEL PARCHE ---

# Import Gymnasium Wrapper
try:
    from capsicaps_env import CapsiCapsEnv # antes .capsicaps_env
except ImportError as e:
    print(f"CRITICAL ERROR: Could not import 'capsicaps_env'. Detail: {e}")
    exit(1)

# =============================================================================
# 1. CONFIGURATION
# =============================================================================

class EndpointFilter(logging.Filter):
    """
    Filters GET /get_state requests that return:
    - Code 200 (OK): Normal refresh noise.
    - Code 400 (Bad Request): "Waiting for game start" noise.
    """
    def filter(self, record):
        msg = record.getMessage()
        if "GET /get_state" in msg:
            if " 200 " in msg or " 400 " in msg:
                return False
        return True

app = Flask(__name__)
CORS(app)

# =============================================================================
# 🟢 USER CONFIGURATION (MASTER SWITCH)
# =============================================================================
# RECORDING_MODE: Controls whether session logs/replays are saved to disk.
# Usage: python3 green_agent.py --no-record
RECORDING_MODE = "--no-record" not in sys.argv

# =============================================================================
# 📂 FOLDER MANAGEMENT (IXENTBENCH STRUCTURE - ROOT LEVEL)
# =============================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Define directories relative to script location
RESULTS_DIR = os.path.join(BASE_DIR, "results")      # Lightweight JSONs for Leaderboard
REPLAYS_DIR = os.path.join(BASE_DIR, "replays")      # Heavy JSONL for Visualizer
LOG_DIR = os.path.join(BASE_DIR, "logs")             # Technical debug logs
RECORD_DIR = os.path.join(BASE_DIR, "match_records") # Manual TXTs for sharing

# Ensure required directories exist
for d in [RESULTS_DIR, REPLAYS_DIR, LOG_DIR, RECORD_DIR]:
    if not os.path.exists(d): os.makedirs(d)

# Benchmark Metadata
BENCHMARK_NAME = "iXentBench-v1.0"
GREEN_AGENT_VERSION = "ixentbench-logic-v1"

# Logging Setup
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
log_filename = os.path.join(LOG_DIR, f"session_{timestamp}.log")

mis_handlers = [logging.StreamHandler()]
if RECORDING_MODE:
    mis_handlers.append(logging.FileHandler(log_filename, encoding='utf-8'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=mis_handlers 
)
logger = logging.getLogger("GreenAgent-Gym")

# Global Environment State (Flask is stateless)
env_instance = None
current_replay_file = None 

# --- Benchmark Summary Generator (Root Level) ---
def save_benchmark_summary(game_info, replay_filepath, token_usage=None):
    """
    1. Moves the replay (.jsonl) to /replays folder.
    2. Generates the summary (.json) in /results folder for Leaderboard.
    """
    if not replay_filepath: return None

    try:
        # 1. Prepare paths
        filename_only = os.path.basename(replay_filepath)
        timestamp_iso = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        
        # 2. MOVE heavy file to /replays
        dest_replay_path = os.path.join(REPLAYS_DIR, filename_only)
        if os.path.abspath(replay_filepath) != os.path.abspath(dest_replay_path):
            if os.path.exists(replay_filepath):
                shutil.move(replay_filepath, dest_replay_path)
                logger.info(f"📦 Replay archived at: {dest_replay_path}")

        # 3. EXTRACT metrics
        full_state = game_info.get("full_state", {})
        metrics = full_state.get("scoring", {})
        meta = full_state.get("meta", {})
        status = full_state.get("status", {})

        # 4. BUILD LIGHTWEIGHT JSON (iXentBench Schema)
        summary_data = {
            "benchmark_version": BENCHMARK_NAME,
            "timestamp": timestamp_iso,
            "participants": {
                "agent_id": meta.get("agent_id", "Unknown"), 
                "green_agent": GREEN_AGENT_VERSION
            },
            "results": [
                {
                    "level_played": meta.get("level_id", "Unknown"),
                    "success": status.get("result") == "VICTORY", 
                    "outcome": status.get("result", "UNKNOWN"),
                    "efficiency_score": metrics.get("benchmark_score", 0),
                    "moves_used": meta.get("turn", 0),
                    "ideal_moves": meta.get("ideal_moves", 0),
                    "max_moves": meta.get("max_moves", 999), 
                    "mice_rescued_percentage": status.get("completion_percent", 0),
                    "token_usage": token_usage if token_usage else {
                        "total": 0
                    },
                    "replay_file": f"replays/{filename_only}"
                }
            ]
        }

        # 5. SAVE in /results
        summary_filename = f"summary_{filename_only.replace('.jsonl', '.json')}"
        summary_path = os.path.join(RESULTS_DIR, summary_filename)
        
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, indent=2)
            
        logger.info(f"📊 iXentBench Summary generated: {summary_path}")
        return summary_path

    except Exception as e:
        logger.error(f"❌ Error generating summary: {e}")
        return None

# =============================================================================
# 2. ENDPOINTS (REST API)
# =============================================================================

def save_snapshot(state):
    """Saves full state IF recording is enabled."""
    if not RECORDING_MODE or not current_replay_file:
        return
    try:
        with open(current_replay_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(state) + "\n")
    except Exception as e:
        print(f"Error saving snapshot: {e}")


@app.route('/status', methods=['GET'])
def status():
    """Health Check and Capabilities Handshake."""
    return jsonify({   
        "status": "online", 
        "agent": "Green Agent v3.1 (Smart Recorder)",   
        "env_wrapper": "CapsiCapsEnv v1.0",   
        "protocol": "A2A/Gymnasium",   
        "recording_mode": RECORDING_MODE, 
        "features": [
            "gymnasium_wrapper",
            "star_xai_reasoning",
            "entropy_events",
            "snapshot_replay"
        ]
    })


@app.route('/start_game', methods=['POST'])
def start_game():
    """
    Resets the Gymnasium environment (env.reset).
    Complies with AAA Reproducibility requirement.
    """
    global env_instance, current_replay_file
    try: 
        data = request.get_json(silent=True) or {}
        level_id = data.get("level_id", "1")
        
        # 1. Capture Agent Identity
        raw_agent_name = data.get("agent_id", "Anonymous")
        clean_agent_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '', raw_agent_name)
        
        # 2. Setup Filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"replay_L{level_id}_{clean_agent_name}_{timestamp}.jsonl"
        current_replay_file = os.path.join(REPLAYS_DIR, filename)

        logger.info(f"*** 🏆 NEW MATCH | Agent: {clean_agent_name} | Level: {level_id} ***")

        if RECORDING_MODE:
            logger.info(f"📼 Recording to: {current_replay_file}")

        # 3. Instantiate Environment
        if env_instance is None:
            env_instance = CapsiCapsEnv(level_id=level_id)
        
        # Inject identity
        if hasattr(env_instance, 'game'):
            env_instance.game.set_agent_metadata(clean_agent_name)

        # 4. Reset Environment
        obs, info = env_instance.reset(options={"level_id": level_id})
        
        # Record Frame 0
        save_snapshot(info) 

        return jsonify({
            "status": "started",
            "level": level_id,
            "state": info 
        })

    except Exception as e:
        logger.error(f"Reset Error: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/submit_move', methods=['POST'])
def submit_move():
    """
    Executes a step in the environment (env.step).
    Standard Gymnasium Step.
    """
    global env_instance
    
    if env_instance is None:
        return jsonify({"success": False, "msg": "Environment not initialized."}), 400

    try:
        data = request.get_json(silent=True)
        if data is None:
            return jsonify({"success": False, "msg": "Invalid or missing JSON"}), 400
        
        action_cmd = data.get("command")
        agent_reasoning = data.get("reasoning")

        if not action_cmd:
            return jsonify({"success": False, "msg": "Missing 'command' field."}), 400

        # --- SMART LOGGING ---
        if agent_reasoning:
            logger.info(f"🧠 REASONING: {agent_reasoning}")
            logger.info(f"🤖 ACTION (Gym): {action_cmd}")
            if hasattr(env_instance, 'game'):
                env_instance.game.set_last_reasoning(agent_reasoning)
        else:
            logger.info(f"🤖 ACTION (Gym): {action_cmd}")

        # --- GYMNASIUM EXECUTION ---
        observation, reward, terminated, truncated, info = env_instance.step(action_cmd)
        
        # Record Snapshot
        full_state = info.get("full_state", info)
        if "data" in full_state:
            full_state["data"]["last_reasoning"] = agent_reasoning
        save_snapshot(full_state)

        # Result Analysis
        msg = info.get("msg", "")
        success = info.get("is_success", False)
        
        # Entropy Persistence
        if "⚠️" in msg:
            logger.warning("!!! ENTROPY DETECTED - RECORDING IN HISTORY !!!")
            if hasattr(env_instance, 'game') and hasattr(env_instance.game, 'history'):
                entropy_entry = f"[EVENT] {msg}" 
                env_instance.game.history.append(entropy_entry)

        # Logging
        log_level = logging.WARNING if "⚠️" in msg else logging.INFO
        logger.log(log_level, f"RWD: {reward} | DONE: {terminated} | MSG: {msg}")
        
        # --- Final Report Generation ---
        if terminated:
            request_meta = data.get("meta", {})
            token_usage = request_meta.get("token_usage", None)
            
            save_benchmark_summary(
                game_info=info, 
                replay_filepath=current_replay_file, 
                token_usage=token_usage
            )

        # Response Construction
        response = {
            "success": success,
            "state": info.get("full_state"),
            "msg": msg,
            "gym_metrics": {
                "reward": reward,
                "terminated": terminated,
                "truncated": truncated
            }
        }
        return jsonify(response)

    except Exception as e:
        logger.error(f"Exception in env.step(): {str(e)}")
        return jsonify({"success": False, "msg": f"Gym Error: {str(e)}"}), 500


@app.route('/get_state', methods=['GET'])
def get_current_state():
    """Passive state retrieval (Accesses wrapped engine directly)."""
    if env_instance is None:
        return jsonify({"error": "No environment active"}), 400
    return jsonify(env_instance.game.get_state())

@app.route('/api/save_record', methods=['POST'])
def api_save_record():
    """Endpoint to save manual text records."""
    try:
        data = request.json
        filename = data.get('filename')
        content = data.get('content')
        
        if not filename or not content:
            return jsonify({"success": False, "msg": "Missing data"}), 400

        if not os.path.exists(RECORD_DIR):
            os.makedirs(RECORD_DIR)

        filepath = os.path.join(RECORD_DIR, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
            
        print(f"💾 Match Record Saved: {filepath}")
        return jsonify({"success": True, "path": filepath})
        
    except Exception as e:
        print(f"❌ Save Error: {e}")
        return jsonify({"success": False, "msg": str(e)}), 500

if __name__ == '__main__':
    # Configuración de logs básica para asegurar que vemos todo
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("GreenAgent-Startup")

    print("\n" + "="*60)
    print("🟢 GREEN AGENT v3.1 (PRODUCTION MODE)")
    print(f"📼 REC MODE: {RECORDING_MODE}")
    print("="*60 + "\n")
    
    # Filtro de ruido
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.addFilter(EndpointFilter()) 

    # Intentamos cargar el nivel (envuelto en Try-Except para ver si falla)
    try:
        print("⚙️ Auto-initializing Level 1...")
        env_instance = CapsiCapsEnv(level_id="1")
        obs, info = env_instance.reset()
        save_snapshot(info)
        print("✅ Level 1 Initialized successfully.")
    except Exception as e:
        print(f"⚠️ WARNING: Could not auto-initialize Level 1 (Maybe files missing?): {e}")
        print("⚠️ The server will start anyway so Docker doesn't crash.")

# =============================================================================
# 🚀 A2A COMPATIBILITY LAYER (AGENTBEATS CLIENT SUPPORT)
# =============================================================================

@app.route('/.well-known/agent-card.json', methods=['GET'])
def agent_card():
    """Returns the Agent Card required by the A2A protocol."""
    return jsonify({
        "name": "iXentBench Green Agent",
        "description": "Legacy Wrapper for iXentBench evaluation",
        "url": "http://green-agent:9009/", 
        "version": "1.0.0",
        "capabilities": {
            "streaming": True
        },
        "defaultInputModes": ["text"],
        "defaultOutputModes": ["text"],
        "skills": [
            {
                "id": "ixentbench_eval",
                "name": "iXentBench Evaluation",
                "description": "Handles agent evaluation tasks",
                "tags": ["evaluation"]
            }
        ],
        "protocolVersion": "0.3.0"
    })

@app.route('/', methods=['POST', 'GET'])
def dummy_rpc():
    """
    VIGILANTE INTEGRADO:
    1. Mantiene la conexión con AgentBeats enviando 'working'.
    2. Vigila la carpeta 'results/' buscando archivos .json.
    3. Cuando aparece el resultado, envía 'completed' para que GitHub suba los archivos.
    """
    def generate():
        print('👁️ VIGILANTE NATIVO ACTIVO: Esperando resultados...')
        while True:
            # Buscamos si se ha generado el resultado del juego
            # NOTA: Ajustamos la ruta para buscar en el directorio actual o src/results
            results = glob.glob('results/*.json') + glob.glob('src/results/*.json')
            
            if results:
                print(f'🏁 JUEGO TERMINADO. Archivo encontrado: {results[0]}')
                # Esperamos un poco para asegurar que el disco termine de escribir
                time.sleep(2)
                yield 'data: ' + json.dumps({
                    "jsonrpc": "2.0",
                    "result": {
                        "contextId": "ctx-ixentbench",
                        "taskId": "task-ixentbench",
                        "status": {"state": "completed"}, 
                        "final": True,
                        "artifacts": []
                    },
                    "id": 1
                }) + '\n\n'
                break
            
            # Si no hay resultados, seguimos "trabajando"
            yield 'data: ' + json.dumps({
                "jsonrpc": "2.0",
                "result": {
                    "contextId": "ctx-ixentbench",
                    "taskId": "task-ixentbench",
                    "status": {"state": "working"}, 
                    "final": False,
                    "artifacts": []
                },
                "id": 1
            }) + '\n\n'
            time.sleep(2)

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

# =============================================================================
# END A2A COMPATIBILITY
# =============================================================================

# ==========================================
# 🏁 ARRANQUE ROBUSTO (COMPATIBLE CON LEADERBOARD)
# ==========================================
if __name__ == '__main__':
    # 🛡️ BLINDAJE: Preparamos el script para aceptar los comandos del Leaderboard
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0", help="Host IP")
    parser.add_argument("--port", default=9009, type=int, help="Port")
    parser.add_argument("--card-url", default="", help="Ignored")
    
    # parse_known_args es VITAL: ignora basura extra sin romper el script
    args, unknown = parser.parse_known_args()

    print(f"🚀 Green Agent Starting on {args.host}:{args.port}...")

    # debug=False y use_reloader=False son OBLIGATORIOS para Docker
    app.run(host=args.host, port=args.port, debug=False, use_reloader=False)
