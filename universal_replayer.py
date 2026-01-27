# -*- coding: utf-8 -*-
"""
universal_replayer.py
Version: 2.3 (Non-Blocking Engine + Web API)
Description: Universal Replayer with full browser control support.
Solution: Non-blocking background loop for smooth playback and instant response.
"""

import os
import json
import time
import threading
import logging
from flask import Flask, jsonify, request
from flask_cors import CORS

# Silence internal Flask logs
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)
CORS(app)

# --- CONFIGURATION ---
RESULT_DIR = "replays"
RECORD_DIR = "match_records" # <--- Folder to save text records (Download Match Record)

# Create folders if they don't exist
for d in [RESULT_DIR, RECORD_DIR]:
    if not os.path.exists(d): os.makedirs(d)

# --- GLOBAL STATE ---
timeline = []       
current_frame = 0   
playback_speed = 2.0 
is_playing = False 

def scan_results():
    """Scans the folder and returns a list of .jsonl files sorted by date."""
    if not os.path.exists(RESULT_DIR): return []
    files = [f for f in os.listdir(RESULT_DIR) if f.endswith('.jsonl')]
    # Sort: Newest first
    files.sort(key=lambda x: os.path.getmtime(os.path.join(RESULT_DIR, x)), reverse=True)
    return files

def load_replay_file(filename):
    """Loads a specific file requested by the frontend."""
    global timeline, current_frame, is_playing
    path = os.path.join(RESULT_DIR, filename)
    if not os.path.exists(path): return False
    
    print(f"📼 Loading tape: {filename} ...")
    is_playing = False # Stop playback when loading new file
    current_frame = 0
    
    raw_frames = []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip(): raw_frames.append(json.loads(line))
        
        # Logic Start Filter (Clean Setup)
        if raw_frames:
            setup_frames = [f for f in raw_frames if f['meta']['turn'] == 0]
            game_frames = [f for f in raw_frames if f['meta']['turn'] > 0]
            clean_timeline = []
            if setup_frames: clean_timeline.append(setup_frames[-1])
            clean_timeline.extend(game_frames)
            timeline = clean_timeline
        else:
            timeline = []
            
        print(f"✅ Load complete: {len(timeline)} frames.")
        return True
    except Exception as e:
        print(f"❌ Load Error: {e}")
        return False

# --- AUTO-PLAY ENGINE (NON-BLOCKING) ---
# Instead of sleeping for 2 seconds, we check time constantly.
def autoplay_loop():
    global current_frame, is_playing, playback_speed
    last_update_time = time.time()
    
    while True:
        if is_playing and timeline:
            now = time.time()
            # Check if enough time has passed based on playback_speed
            if now - last_update_time >= playback_speed:
                if current_frame < len(timeline) - 1:
                    current_frame += 1
                    last_update_time = now # Reset timer
                else:
                    is_playing = False # End of tape
            
            # Sleep briefly (50ms) to save CPU but remain responsive
            time.sleep(0.05)
        else:
            # If paused, keep updating timer to avoid sudden jumps on resume
            last_update_time = time.time()
            time.sleep(0.1)

# --- API ENDPOINTS (Connects to Web Buttons) ---

@app.route('/status', methods=['GET'])
def status():
    """Frontend calls this to identify the Replayer and sync state."""
    return jsonify({
        "status": "replay_mode", 
        "agent": "Universal Replayer v2.3",
        "total_frames": len(timeline),
        "current_frame": current_frame,
        "is_playing": is_playing,
        "speed": playback_speed
    })

@app.route('/get_state', methods=['GET'])
def get_state():
    if not timeline: return jsonify({"error": "No replay loaded"}), 400
    return jsonify(timeline[current_frame])

# --- NEW ENDPOINTS FOR REPLAY PANEL ---

@app.route('/api/list_replays', methods=['GET'])
def list_replays():
    return jsonify({"files": scan_results()})

@app.route('/api/load_replay', methods=['POST'])
def api_load_replay():
    data = request.json
    if load_replay_file(data.get('filename')): return jsonify({"success": True})
    return jsonify({"success": False}), 400

@app.route('/api/control', methods=['POST'])
def api_control():
    global current_frame, is_playing
    cmd = request.json.get('command')
    
    # Button Logic
    if cmd == 'next':
        is_playing = False
        if current_frame < len(timeline) - 1: current_frame += 1
    elif cmd == 'prev':
        is_playing = False
        if current_frame > 0: current_frame -= 1
    elif cmd == 'rewind':
        is_playing = False
        current_frame = 0
    elif cmd == 'play_pause':
        is_playing = not is_playing # Toggle ON/OFF
        
    return jsonify({"success": True, "frame": current_frame, "playing": is_playing})

# --- NEW: SAVE MATCH RECORD ENDPOINT ---
@app.route('/api/save_record', methods=['POST'])
def api_save_record():
    try:
        data = request.json
        filename = data.get('filename')
        content = data.get('content')
        
        if not filename or not content:
            return jsonify({"success": False, "msg": "Missing data"}), 400

        # Save to 'match_records' folder
        filepath = os.path.join(RECORD_DIR, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
            
        print(f"💾 Match Record Saved: {filepath}")
        return jsonify({"success": True, "path": filepath})
        
    except Exception as e:
        print(f"❌ Save Error: {e}")
        return jsonify({"success": False, "msg": str(e)}), 500

# --- MAIN ENTRY POINT ---
if __name__ == "__main__":
    # 1. Load the latest available replay by default
    files = scan_results()
    if files: load_replay_file(files[0])
    
    # 2. Start the Auto-Play thread in background
    t_play = threading.Thread(target=autoplay_loop, daemon=True)
    t_play.start()

    print("\n🎮 UNIVERSAL REPLAYER v2.3 - READY")
    print(f"📂 Reading from: ./{RESULT_DIR}/")
    print(f"📂 Saving records to: ./{RECORD_DIR}/")
    print("👉 Open index.html in your browser")
    
    # 3. Start Web Server
    app.run(port=9009, use_reloader=False)