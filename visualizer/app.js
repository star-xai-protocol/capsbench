/* app.js - Version 2.4 (Clean & Fast Refresh) */

let currentState = null;
let autoRefreshInterval = null;
let lastHistoryLength = 0; 
let isReplayMode = false; 
// If using Docker or local network, the HTML input will overwrite this automatically.
let API_BASE_URL = 'http://localhost:9009';

window.onload = function() {
    console.log("🚀 Visualizer Loaded v2.4");

    // --- Smart IP Detection ---
    // This code will work automatically.
    const ipInput = document.getElementById('server-ip-config');
    if (ipInput) {
        ipInput.value = API_BASE_URL.replace('http://', '');
        
        ipInput.addEventListener('change', (e) => {
            let cleanIp = e.target.value.trim();
            // Ensure it starts with http://
            if (!cleanIp.startsWith('http')) cleanIp = 'http://' + cleanIp;
            // Remove trailing slash if user added it
            API_BASE_URL = cleanIp.replace(/\/$/, ""); 
            console.log(`🔌 Backend target updated: ${API_BASE_URL}`);
            detectAgentMode(); 
        });
    }

    detectAgentMode(); 
    fetchAndRender();
    startAutoRefresh();
};

function startAutoRefresh() {
    if (autoRefreshInterval) clearInterval(autoRefreshInterval);
    // Fast refresh (200ms) for smooth playback
    autoRefreshInterval = setInterval(fetchAndRender, 200);
}

// --- CORE: FETCH & RENDER ---
async function fetchAndRender() {
    try {
        const response = await fetch(`${API_BASE_URL}/get_state`);
        if (!response.ok) return; 

        const state = await response.json();
        currentState = state; 

        renderBoard(state);
        updateStatusPanel(state);
        updateLevelSelector(state);
         updateReasoning(state);

    } catch (error) {
        // Silent fail on connection lost
    }
}

function updateLevelSelector(state) {
    const levelSelect = document.getElementById('level-select');
    if (levelSelect && levelSelect.options.length <= 1 && state.meta && state.meta.available_levels) {
        levelSelect.innerHTML = ''; 
        state.meta.available_levels.forEach(lvl => {
            const option = document.createElement('option');
            option.value = lvl;
            option.text = `Level ${lvl}`;
            levelSelect.appendChild(option);
        });
        levelSelect.value = state.meta.level_id;
    }
}

// --- BOARD RENDERING (Dynamic Scaling) ---
function renderBoard(state) {
    const gameGrid = document.getElementById('board-grid');
    const exitBay = document.getElementById('exit-bay');
    const waitingBay = document.getElementById('waiting-bay');

    if (!gameGrid || !exitBay || !waitingBay) return;

    const boardData = state.data.board_encoding;
    const dimsStr = state.meta.dimensions.split('x'); 
    const dims = [parseInt(dimsStr[0]), parseInt(dimsStr[1])]; 

    // Cell size configuration (reference)
    let cellSize = 150;
    const maxDim = Math.max(dims[0], dims[1]);
    if (maxDim > 6) cellSize = 70;       
    else if (maxDim > 4) cellSize = 100; 
    else cellSize = 150;                 

    // --- ALIGNMENT FIX ---
    // Define column style AND gap size equal for all three containers.
    const gapSize = '4px'; // Uniform gap between cells
    const colStyle = `repeat(${dims[0]}, 1fr)`; 

    // 1. Apply identical Grid to all 3 sections
    [gameGrid, exitBay, waitingBay].forEach(el => {
        el.style.display = 'grid';
        el.style.gridTemplateColumns = colStyle;
        el.style.gap = gapSize;      // KEY: Same gap for all
        el.style.width = '100%';     // Ensure they occupy full width
        el.style.boxSizing = 'border-box';
        el.style.padding = '0';      // Remove internal padding that causes misalignment
    });

    // 2. Render Exit Bay
    exitBay.innerHTML = '';
    for (let x = 1; x <= dims[0]; x++) {
        const slot = document.createElement('div');
        slot.className = 'waiting-slot exit-slot';
        slot.id = `slot-EXIT-${x}`; 
        slot.style.height = `${Math.max(40, cellSize/3)}px`; 
        slot.innerHTML = `<small style="position:absolute; top:2px; right:2px; opacity:0.6; font-size:10px;">EXIT ${x}</small>`;
        exitBay.appendChild(slot);
    }

    // 3. Render Main Board
    gameGrid.innerHTML = '';
    for (let y = dims[1]; y >= 1; y--) {
        for (let x = 1; x <= dims[0]; x++) {
            const cellId = `P${x}${y}`;
            const cellData = boardData[cellId] || "obstacle";
            
            const cellDiv = document.createElement('div');
            cellDiv.className = 'cell';
            cellDiv.id = cellId; 

            
            // --- REMOVED: fixed cellDiv.style.width and height ---
            // Let CSS (.game-grid aspect-ratio) control the size
            
            const label = document.createElement('div');
            label.className = 'cell-label';
            label.textContent = cellId;
            cellDiv.appendChild(label);

            if ((x + y) % 2 === 0) cellDiv.classList.add('even');
            else cellDiv.classList.add('odd');

            if (cellData === "obstacle") {
                cellDiv.classList.add('obstacle');
            } else {
                if (cellData.startsWith("G")) {
                    const match = cellData.match(/(G\d)(P\d+)([RL])(\d)B(\d{4})/);
                    if (match) {
                        const gType = match[1].toLowerCase();
                        const rot = parseInt(match[4]);
                        const basesCode = match[5];

                        const gearDiv = document.createElement('div');
                        gearDiv.className = `gear ${gType}`;
                        gearDiv.style.transform = `rotate(${rot * -90}deg)`;

                        for (let i = 0; i < 4; i++) {
                            if (basesCode[i] !== '2') {
                                const baseDiv = document.createElement('div');
                                baseDiv.className = 'base';
                                const positions = ['N', 'W', 'S', 'E']; 
                                baseDiv.setAttribute('data-phys-pos', positions[i]);
                                const dot = document.createElement('div');
                                dot.className = 'base-indicator';
                                baseDiv.appendChild(dot);
                                gearDiv.appendChild(baseDiv);
                            }
                        }
                        cellDiv.appendChild(gearDiv);
                    }
                }
            }
            gameGrid.appendChild(cellDiv);
        }
    }

    // 4. Waiting Bay
    waitingBay.innerHTML = '';
    for (let x = 1; x <= dims[0]; x++) {
        const slot = document.createElement('div');
        slot.className = 'waiting-slot';
        const startId = `P${x}0`; 
        slot.id = startId; 
        
        // Ensure relative position so absolute text stays inside
        slot.style.position = 'relative'; 
        slot.style.height = `${Math.max(40, cellSize/3)}px`; 
        
        const label = document.createElement('div');
        // --- CHANGE: Stick text to bottom left corner ---
        label.style.position = 'absolute';
        label.style.bottom = '2px';
        label.style.left = '5px';
        label.style.fontSize = '0.8em';
        label.style.color = '#999';
        label.textContent = startId;
        slot.appendChild(label);

        waitingBay.appendChild(slot);
    }

    renderMiceLogic(state, cellSize);
}

// --- MICE LOGIC (V4: Adjusted Text + Large Waiting Mice) ---
function renderMiceLogic(state, cellSize) {
    const miceData = state.data.mice || {};
    const sortedMice = Object.keys(miceData).sort();
    let escapedCounter = 1;

    // --- DYNAMIC FONT CALCULATION (ADJUSTED) ---
    
    // 1. BOARD TEXT: 
    // Lowered multiplier to 0.18 (previously 0.22) to make it slightly smaller.
    // Lowered minimum to 8px (previously 10px) so it doesn't look giant on dense boards.
    const fontBoard = Math.max(8, Math.floor(cellSize * 0.18)) + 'px';

    // 2. WAITING/EXIT TEXT: 
    // Slightly adjusted to match the new circle size.
    const fontSmall = Math.max(9, Math.floor(cellSize * 0.14)) + 'px';

    sortedMice.forEach(mId => {
        const mouse = miceData[mId];
        let targetDiv = null;
        let visualMode = "default"; 

        if (mouse.status === "ESCAPED") {
            targetDiv = document.getElementById(`slot-EXIT-${escapedCounter}`);
            visualMode = "escaped";
            escapedCounter++;
        }
        else if (mouse.status === "WAITING") {
            targetDiv = document.getElementById(mouse.pos);
            visualMode = "waiting"; 
        }
        else if (mouse.status === "IN_PLAY") {
            targetDiv = document.getElementById(mouse.pos);
            visualMode = "rim";
        }

        if (targetDiv) {
            const mouseDiv = document.createElement('div');
            mouseDiv.className = 'mouse';
            mouseDiv.textContent = mId; 
            
            // Base styles
            mouseDiv.style.position = 'absolute';
            mouseDiv.style.borderRadius = '50%';
            mouseDiv.style.display = 'flex';
            mouseDiv.style.justifyContent = 'center';
            mouseDiv.style.alignItems = 'center';
            mouseDiv.style.zIndex = '100';
            mouseDiv.style.fontWeight = 'bold';
            
            // --- ZONE LOGIC ---

            // 1. IN GAME (Board)
            if (visualMode === "rim") {
                mouseDiv.style.width = '35%';
                mouseDiv.style.height = '35%';
                mouseDiv.style.fontSize = fontBoard; // <--- More controlled font
                
                const gearCode = state.data.board_encoding[mouse.pos];
                let visualPosIndex = 0;
                
                if (gearCode && gearCode.startsWith("G")) {
                    const match = gearCode.match(/([RL])(\d)B/);
                    if (match) {
                        const gearRot = parseInt(match[2]); 
                        const mouseBase = mouse.on_base;    
                        visualPosIndex = (gearRot + mouseBase) % 4;
                    }
                }
                
                const gap = '1%'; 
                switch(visualPosIndex) {
                    case 0: 
                        mouseDiv.style.top = gap;
                        mouseDiv.style.left = '50%';
                        mouseDiv.style.transform = 'translateX(-50%)'; 
                        break;
                    case 1: 
                        mouseDiv.style.top = '50%';
                        mouseDiv.style.left = gap;
                        mouseDiv.style.transform = 'translateY(-50%)';
                        break;
                    case 2: 
                        mouseDiv.style.bottom = gap;
                        mouseDiv.style.left = '50%';
                        mouseDiv.style.transform = 'translateX(-50%)';
                        break;
                    case 3: 
                        mouseDiv.style.top = '50%';
                        mouseDiv.style.right = gap;
                        mouseDiv.style.transform = 'translateY(-50%)';
                        break;
                }
            }
            
            // 2. WAITING ZONE (P10...) - NOW LARGER!
            else if (visualMode === "waiting") {
                // INCREASED: From 60% to 85% to look big and clear
                mouseDiv.style.height = '85%'; 
                mouseDiv.style.width = 'auto'; 
                mouseDiv.style.aspectRatio = '1 / 1'; 
                mouseDiv.style.fontSize = fontSmall;
                
                mouseDiv.style.top = '50%';
                mouseDiv.style.left = '50%';
                mouseDiv.style.transform = 'translate(-50%, -50%)';
            }

            // 3. EXIT
            else if (visualMode === "escaped") {
                mouseDiv.classList.add('rescued-anim');
                // Adjusted here too for consistency
                mouseDiv.style.height = "80%";    
                mouseDiv.style.width = "auto";
                mouseDiv.style.aspectRatio = '1 / 1';
                mouseDiv.style.fontSize = fontSmall;
                
                mouseDiv.style.position = "relative";
                mouseDiv.style.margin = "0 auto";
            }       

            targetDiv.appendChild(mouseDiv);
        }
    });
}

// --- STATUS PANEL UPDATE ---
function updateStatusPanel(state) {
    const inv = state.data.inventory;
    ['G1', 'G2', 'G3', 'G4'].forEach(type => {
        const el = document.getElementById(`inv-${type}`);
        if (el) {
            el.textContent = inv[type] || 0;
            el.parentElement.style.color = (inv[type] > 0) ? 'var(--text-color)' : '#ccc';
        }
    });

    const phaseLabel = document.getElementById('game-phase');
    const totalInv = Object.values(inv).reduce((a, b) => a + b, 0);
    if (totalInv > 0) {
        phaseLabel.textContent = "PHASE 1: PLACEMENT";
        phaseLabel.className = "phase-indicator fase1";
    } else {
        phaseLabel.textContent = "PHASE 2: ROTATION";
        phaseLabel.className = "phase-indicator fase2";
    }

    document.getElementById('raw-score').textContent = state.scoring.raw_points;
    document.getElementById('turn-count').textContent = state.meta.turn;

    // CHANGE: Show Max Moves + Ideal Moves
    // state.meta.ideal_moves comes from game_logic.py
    const ideal = state.meta.ideal_moves || "?";
    document.getElementById('max-moves').textContent = `${state.meta.max_moves} (Ideal: ${ideal})`;
    
    document.getElementById('level-indicator').textContent = state.meta.level_id;
    
    const rescued = state.status.mice_rescued || 0;
    const totalMice = state.status.total_mice || 0;
    document.getElementById('rescued-count').textContent = `${rescued} / ${totalMice}`;

    // Mice List
    const miceList = document.getElementById('mice-list');
    miceList.innerHTML = '';
    Object.keys(state.data.mice).sort().forEach(mId => {
        const m = state.data.mice[mId];
        const li = document.createElement('li');
        let statusClass = m.status.toLowerCase(); 
        if (statusClass === 'in_play') statusClass = 'playing';

        li.innerHTML = `
            <span class="status-dot ${statusClass}"></span>
            <strong>${mId}</strong>: ${m.pos} 
            ${m.on_base !== null ? `(Base ${m.on_base})` : ''}
        `;
        miceList.appendChild(li);
    });

    // Game Over & Metrics
    const gameOverMsg = document.getElementById('game-over-msg');
    const finalScoreRow = document.getElementById('final-score-row');
    
    if (state.status.game_over) {
        gameOverMsg.textContent = `GAME OVER: ${state.status.result}`;
        gameOverMsg.classList.remove('hidden');
        finalScoreRow.classList.remove('hidden');
        document.getElementById('benchmark-score').textContent = state.scoring.benchmark_score;
        document.getElementById('completion-percent').textContent = state.status.completion_percent.toFixed(1);
    } else {
        gameOverMsg.classList.add('hidden');
        finalScoreRow.classList.add('hidden');
    }

    // History Log
    const historyContainer = document.getElementById('history-log');
    const currentMoves = state.data.history || [];
    
    if (currentMoves.length > lastHistoryLength) {
        historyContainer.innerHTML = '';
        currentMoves.forEach(move => {
            const div = document.createElement('div');
            div.className = 'history-item';
            div.textContent = move;
            if (move.includes("EVENT") || move.includes("⚠️")) {
                div.style.color = "#d32f2f";
                div.style.fontWeight = "bold";
            }
            historyContainer.appendChild(div);
        });
        historyContainer.scrollTop = historyContainer.scrollHeight;
        lastHistoryLength = currentMoves.length;
    } else if (currentMoves.length === 0 && lastHistoryLength > 0) {
        historyContainer.innerHTML = '<div class="empty-history">No moves yet.</div>';
        lastHistoryLength = 0;
    }
}

// --- MANUAL CONTROLS ---
async function manualStartGame() {
    const level = document.getElementById('level-select').value;
    try {
        await fetch(`${API_BASE_URL}/start_game`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ level_id: level })
        });
        lastHistoryLength = 0;
        document.getElementById('history-log').innerHTML = '<div class="empty-history">No moves yet.</div>';
        fetchAndRender();
    } catch (e) {
        alert("Error starting game: " + e);
    }
}

async function manualSubmitMove() {
    const cmdInput = document.getElementById('cmd-input');
    const cmd = cmdInput.value.trim();
    if (!cmd) return;

    try {
        const res = await fetch(`${API_BASE_URL}/submit_move`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command: cmd })
        });
        const data = await res.json();
        
        const feedback = document.getElementById('action-feedback');
        if (data.success) {
            feedback.textContent = "Move Accepted";
            feedback.className = "success";
            cmdInput.value = ""; 
        } else {
            feedback.textContent = "Rejected: " + data.msg;
            feedback.className = "";
        }
        fetchAndRender();
    } catch (e) {
        console.error(e);
        document.getElementById('action-feedback').textContent = "Connection Error";
    }
}

function handleEnter(event) {
    if (event.key === 'Enter') manualSubmitMove();
}

// --- UPDATED DOWNLOAD FEATURE (SERVER SAVE + DYNAMIC NAMING) ---
async function downloadHistory() {
    // Security check
    if (!currentState || !currentState.data.history || currentState.data.history.length === 0) {
        alert("No history available to download.");
        return;
    }
    
    const now = new Date();
    // Safe date format for filenames (no colons)
    const timestamp = now.toISOString().replace(/[:.]/g, '-').slice(0, 19);
    
    // 1. Detect Level (If not exists, default "1")
    const level = currentState.meta.level_id || "1";
    
    // 2. Generate Name with Level included
    const filename = `CAPS_Benchmark_L${level}_${timestamp}.txt`;
    
    // 3. Generate Text Content
    let content = "================================================\n";
    content += "       THE CAPS BENCHMARK - MATCH RECORD\n";
    content += "================================================\n";
    content += `Date: ${now.toLocaleString()}\n`;
    content += `Level: ${level} (${currentState.meta.dimensions})\n`;
    content += `Session Status: ${currentState.status.game_over ? "COMPLETED" : "IN PROGRESS"}\n`;
    content += `Result: ${currentState.status.result}\n`;
    content += "================================================\n\n";
    
    content += "--- ACTION LOG (Reproducible) ---\n";
    currentState.data.history.forEach((line, index) => {
        content += `${index + 1}. ${line}\n`;
    });
    content += "\n";

    content += "--- FINAL PERFORMANCE METRICS ---\n";
    content += `Raw Score:                    ${currentState.scoring.raw_points}\n`;
    content += `Mice Rescued:                 ${currentState.status.mice_rescued} / ${currentState.status.total_mice}\n`;
    content += `Completion Rate:              ${currentState.status.completion_percent.toFixed(2)}%\n`;
    content += `Adjusted Benchmark Score:     ${currentState.scoring.benchmark_score}\n`;
    content += "\n================================================\n";
    content += "End of Record\n";

    // 4. ATTEMPT 1: Save on Server (Python)
    try {
        const res = await fetch(`${API_BASE_URL}/api/save_record`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ filename: filename, content: content })
        });
        
        if (res.ok) {
            const data = await res.json();
            // Success: Notify and finish
            alert(`✅ Record Saved Successfully!\n\nFolder: match_records/\nFile: ${filename}`);
            return; 
        }
    } catch (e) {
        console.warn("Server save failed (Server might be old), falling back to browser download.");
    }

    // 5. ATTEMPT 2 (Fallback): Browser Download (if server fails)
    const blob = new Blob([content], { type: 'text/plain' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
}

// ==========================================
// REPLAY MODULE (Smart Detection)
// ==========================================

async function detectAgentMode() {
    try {
        const res = await fetch(`${API_BASE_URL}/status`);
        const data = await res.json();
        
        const manualBox = document.getElementById('manual-controls-box');
        const replayBox = document.getElementById('replay-controls-box');

        // Check if backend identifies as a "Replayer"
        if (data.agent && data.agent.includes("Replayer")) {
            console.log("📼 REPLAY MODE DETECTED");
            isReplayMode = true;
            
            if (manualBox) manualBox.style.display = 'none';   
            if (replayBox) replayBox.style.display = 'block';  
            
            loadReplayList(); 
        } else {
            console.log("🎮 GAME MODE DETECTED");
            isReplayMode = false;
            
            if (manualBox) manualBox.style.display = 'block';
            if (replayBox) replayBox.style.display = 'none';
        }
    } catch (e) {
        console.log("Waiting for server connection...");
    }
}

async function loadReplayList() {
    try {
        const res = await fetch(`${API_BASE_URL}/api/list_replays`);
        if (!res.ok) return; 

        const data = await res.json();
        const selector = document.getElementById('replay-file-selector');
        selector.innerHTML = '';
        
        data.files.forEach(f => {
            const opt = document.createElement('option');
            opt.value = f;
            opt.text = f;
            selector.appendChild(opt);
        });

        document.getElementById('btn-load-replay').onclick = async () => {
            const filename = selector.value;
            await fetch(`${API_BASE_URL}/api/load_replay`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ filename })
            });
            document.getElementById('history-log').innerHTML = '<div class="empty-history">Replay Loaded.</div>';
            lastHistoryLength = 0;
            fetchAndRender();
        };

    } catch (e) { console.warn("Replay API not ready."); }
}

async function sendReplayCmd(cmd) {
    try {
        await fetch(`${API_BASE_URL}/api/control`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ command: cmd })
        });
        
        // Instant visual feedback
        setTimeout(fetchAndRender, 50); 
    } catch (e) { console.error(e); }
}

function updateReasoning(state) {
    const box = document.getElementById('reasoning-display');
    const header = document.getElementById('reasoning-header');
    
    if (!box) return;

    const reasoning = state.data.last_reasoning;
    const agentId = state.meta.agent_id || "Unknown Agent";

    // Update title with Agent ID
    if (header) header.innerText = `🧠 REASONING (${agentId})`;

    if (reasoning) {
        if (box.innerText !== reasoning) {
            box.innerText = reasoning;
            box.scrollTop = box.scrollHeight; // Auto-scroll to bottom
        }
    } else {
        box.innerHTML = '<span class="placeholder-text">Waiting for agent reasonings...</span>';
    }
}