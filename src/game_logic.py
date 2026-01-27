# -*- coding: utf-8 -*-
"""
game_logic.py
Version: 5.2 (Unified Engine & Server)
Authors: STAR-XAI Team

Description:
Deterministic Rules Engine for 'Caps i Caps'.
Evaluates: Reasoning (Validity), Planning (Sequence), and Strategy (Efficiency).
Operates in a hallucination-free environment ensuring operational reliability.
Implements literal truth tables for rotation and vectors.

Changes v3.2:
- Added self._check_entries() call AFTER rotation and entropy.
- Allows mice to enter the board if a gear rotation aligns a base with the Waiting Bay.

DISRUPTIVE MOVE (TOTAL ENTROPY v3.5):
    Executes once, exactly when inventory reaches 0.
    Instead of swapping just 2 pieces, it identifies ALL gears in the
    second-to-last row, shuffles their positions, AND randomizes the
    rotation of EACH one. Prevents column memorization.

MODULE DESCRIPTION:
This file contains the "Source of Truth" (Environment) for 'Caps i Caps'.
It is a deterministic system (no AI) that manages board state, validates move
legality, and calculates physical consequences (turns, propagation, jumps)
based strictly on modular arithmetic and Look-up Tables.

RESPONSIBILITIES:
1. Maintain immutable board state (Single Source of Truth).
2. Validate move syntax and logic (Outcome Validity).
3. Execute game physics: Unified Rotation and Motion Vectors.
4. Calculate Benchmark performance metrics (Scoring & Efficiency).
"""

import re
import random

# =============================================================================
# 1. CONFIGURATION AND TRUTH TABLES (IMMUTABLE CONSTANTS)
# =============================================================================

# Level Definitions
# Defines initial configuration for each test scenario.
GAME_LEVELS = {
    "1": {
        "board_size": (3, 3),       # (Cols x, Rows y)
        "game_map": "111101111",    # Linear map: 1=Playable, 0=Obstacle
        "inventory": {"G1": 2, "G2": 3, "G3": 1, "G4": 2}, 
        "max_moves": 22,            # Hard limit for benchmark
        "ideal_moves": 12           # Efficiency target
    },
    "2": {
        "board_size": (4, 4),
        "game_map": "1111110110111111",    # P32=0, P23=0
        "inventory": {"G1": 3, "G2": 4, "G3": 5, "G4": 2},
        "max_moves": 36,
        "ideal_moves": 22
    },
    "3": {
        "board_size": (5, 5),
        "game_map": "1111111110011111101111111",
        "inventory": {"G1": 6, "G2": 5, "G3": 6, "G4": 5},
        "max_moves": 48,
        "ideal_moves": 28
    },
    "4": {
        "board_size": (6, 6),
        "game_map": "111111111101011111110111111101110111",
        "inventory": {"G1": 8, "G2": 5, "G3": 11, "G4":7},
        "max_moves": 58,
        "ideal_moves": 44
    },
    "5": {
        "board_size": (7, 7),
        "game_map": "1111111110111101111111101111111101111101101111111",
        "inventory": {"G1": 13, "G2": 7, "G3": 15, "G4": 8},
        "max_moves": 88,
        "ideal_moves": 60
    },
    "6": {
        "board_size": (8, 8),
        "game_map": "1111111111111101111010110111111011110111110111111011111111111111",
        "inventory": {"G1": 18, "G2": 13, "G3": 10, "G4": 15},
        "max_moves": 111,
        "ideal_moves": 78
    }
}

# Physical Bases by Gear Type
# Indicates which 'b' indices (0-3) physically exist on each piece.
GEAR_BASES = {
    "G1": [0],             # B0222 (North Only)
    "G2": [0, 2],          # B0202 (North & South)
    "G3": [1, 2, 3],       # B2000 (East, South, West)
    "G4": [0, 1, 2, 3]     # B0000 (All bases)
}

# Adjacency Table (Direction Vectors)
# Maps base orientation (index 0-3) to coordinate changes (dx, dy).
# Coord System: x increases right, y increases up.
DIRECTION_DELTAS = { 
    0: (0, 1),    # North (Up)
    1: (-1, 0),   # West (Left)
    2: (0, -1),   # South (Down)
    3: (1, 0)     # East (Right)
}

# Scoring Table by Jump Direction
SCORE_POINTS = {
    0: 10,  # Upward Jump (Pure Advance)
    1: 5,   # Lateral Jump (Left) - Strategic
    3: 5,   # Lateral Jump (Right) - Strategic
    2: -10  # Downward Jump (Retreat)
}

class CapsiCapsGame:
    """
    Main Game Engine Class.
    Instantiates an independent game environment.
    """

    def __init__(self):
        """Constructor. Initializes empty data structures and loads default level."""
        # State Structures
        self.board = {}         # Dict: {"P11": {cell_data}, ...}
        self.inventory = {}     # Dict: {"G1": qty, ...}
        self.mice = {}          # Dict: {"M1": {mouse_state}, ...}
        self.dims = (0,0)       # Tuple: (width, height)
        self.agent_id = "Unknown"
        self.last_reasoning = ""

        # Benchmark Metrics
        self.moves_count = 0
        self.max_moves = 0
        self.ideal_moves = 0
        self.score_accumulated = 0

        # History
        self.history = []
        
        # Global State
        self.level_id = "1"
        self.is_game_over = False
        self.game_result = ""   # "VICTORY", "TIMEOUT", "IN_PROGRESS"
        
        # Final Metrics
        self.completion_percent = 0.0
        self.final_benchmark_score = 0

        # Entropy Control
        self.entropy_triggered = False 

        # Load default level
        self.reset("1")

    def set_agent_metadata(self, agent_id):
        """Sanitizes and sets Agent ID."""
        clean_id = str(agent_id).strip()
        clean_id = clean_id.replace(" ", "-")
        self.agent_id = re.sub(r'[^a-zA-Z0-9\-\_\.]', '', clean_id)

    def set_last_reasoning(self, text):
        self.last_reasoning = text

    def reset(self, level_id="1"):
        """
        Resets environment to initial state of a specific level.
        Returns: Initial game state dict.
        """
        if level_id not in GAME_LEVELS:
            level_id = "1"
        
        config = GAME_LEVELS[level_id]
        
        # 1. Load Static Config
        self.level_id = level_id
        self.dims = config["board_size"]
        self.inventory = config["inventory"].copy()
        self.max_moves = config["max_moves"]
        self.ideal_moves = config["ideal_moves"]
        
        # 2. Reset Dynamic Counters
        self.moves_count = 0
        self.score_accumulated = 0
        self.is_game_over = False
        self.game_result = "IN_PROGRESS"
        self.completion_percent = 0.0
        self.final_benchmark_score = 0
        self.history = []
        self.entropy_triggered = False 

        # 3. Build Virtual Board
        self.board = {}
        map_str = config["game_map"]
        idx = 0
        
        for y in range(1, self.dims[1] + 1):
            for x in range(1, self.dims[0] + 1):
                cell_id = f"P{x}{y}"
                char = map_str[idx]
                
                # Calculate Topology (Parity Rule)
                topology = "R" if (x + y) % 2 == 0 else "L"
                
                if char == '0':
                    self.board[cell_id] = "obstacle"
                else:
                    self.board[cell_id] = f"{cell_id}{topology}"

                idx += 1 

        # 4. Initialize Mice in Waiting Bay (Virtual Row 0)
        self.mice = {}
        for i in range(1, self.dims[0] + 1):
            m_id = f"M{i}"
            self.mice[m_id] = {
                "pos": f"P{i}0", 
                "on_base": None, 
                "status": "WAITING"
            }

        return self.get_state()

    # =========================================================================
    #  STATE INTERFACE (Output for Green Agent/A2A)
    # =========================================================================

    def get_state(self):
        """Generates full JSON report of game state for A2A protocol."""
        return {
            "meta": {
                "level_id": self.level_id,
                "agent_id": self.agent_id,
                "available_levels": list(GAME_LEVELS.keys()),
                "dimensions": f"{self.dims[0]}x{self.dims[1]}",
                "turn": self.moves_count,
                "max_moves": self.max_moves,
                "ideal_moves": self.ideal_moves
            },
            "status": {
                "game_over": self.is_game_over,
                "result": self.game_result,
                "mice_rescued": self._count_rescued_mice(),
                "total_mice": len(self.mice),
                "completion_percent": self.completion_percent
            },
            "scoring": {
                "raw_points": self.score_accumulated,
                "benchmark_score": self.final_benchmark_score
            },
            "data": {
                "inventory": self.inventory,
                "mice": self.mice, 
                "board_encoding": self._generate_board_encoding(), 
                "history": self.history,
                "last_reasoning": self.last_reasoning
            }
        }

    def _generate_board_encoding(self):
        """
        Generates full board representation.
        
        Logic:
        1. Gears ("G..."): Dynamically calculated using self.mice to ensure
           occupation code (Bxxxx) is the current Ground Truth.
        2. Others ("PxyR" or "obstacle"): Sent as-is.
        """
        encoded = {}
        
        for cell_id, data in self.board.items():
            
            # CASE A: GEAR PRESENT
            if data.startswith("G"):
                g_data = self._parse_gear_str(data)
                valid_bases = GEAR_BASES[g_data["type"]]
                b_code_list = []
                
                # Check mice presence on this gear
                mice_here = {m["on_base"] for m in self.mice.values() if m["pos"] == cell_id}
                
                # Build B-code (4 digits)
                for i in range(4):
                    if i not in valid_bases:
                        b_code_list.append("2") # Base does not exist
                    elif i in mice_here:
                        b_code_list.append("1") # Occupied by mouse
                    else:
                        b_code_list.append("0") # Empty base
                
                # Reconstruct Full Dynamic String
                static_part = f"{g_data['type']}{cell_id}{g_data['topo']}"
                dynamic_part = f"{g_data['rot']}B{''.join(b_code_list)}"
                encoded[cell_id] = static_part + dynamic_part

            # CASE B: EMPTY OR OBSTACLE
            else:
                encoded[cell_id] = data
                
        return encoded

    def _calculate_final_score(self):
        """
        Calculates Benchmark Efficiency Score.
        Formula: (Accumulated Points * Ideal Moves) / Moves Used
        """
        if self.moves_count == 0: return 0
        raw_score = (self.score_accumulated * self.ideal_moves) / self.moves_count
        return int(raw_score)

    # =========================================================================
    #  STRING PARSING HELPERS (CORE v4.2)
    #  Manipulate board state stored as text strings (e.g., "G4P21L3B1000").
    # =========================================================================

    def _parse_gear_str(self, gear_str):
        """
        Parses encoded gear string into usable dictionary.
        Returns: Dict with keys [type, pos, topo, rot, bases_code] or None.
        """
        if not gear_str.startswith("G"):
            return None
        
        match = re.match(r"(G\d)(P\d+)([RL])(\d)B(\d{4})", gear_str)
        
        if match:
            return {
                "type": match.group(1),
                "pos": match.group(2),
                "topo": match.group(3),
                "rot": int(match.group(4)),
                "bases_code": match.group(5)
            }
        return None

    def _update_gear_str_rotation(self, gear_str, new_rot):
        """Returns new string with updated rotation 'b'."""
        return re.sub(r"(\d)B", f"{new_rot}B", gear_str, count=1)

    def _update_gear_str_bases(self, gear_str, new_bases_code):
        """Returns new string with updated occupation code Bxxxx."""
        return re.sub(r"B(\d{4})", f"B{new_bases_code}", gear_str, count=1)

    def _build_gear_str(self, g_type, pos, topo, rot, bases_code):
        """Constructs a gear string from scratch (used in Placement Phase)."""
        return f"{g_type}{pos}{topo}{rot}B{bases_code}"

    # =========================================================================
    #  MATH HELPERS (Private)
    # =========================================================================

    def _get_coords(self, cell_id):
        """Converts 'P21' to tuple (2, 1)."""
        match = re.match(r"P(\d+)(\d+)", cell_id)
        if match:
            return int(match.group(1)), int(match.group(2))
        return None

    def _get_cell_from_coords(self, x, y):
        """Converts (x, y) to 'Pxy'. Validates boundaries."""
        if not (1 <= x <= self.dims[0]):
            return None 
        if not (0 <= y <= self.dims[1] + 1):
            return None
        return f"P{x}{y}"

    def _calc_rotation(self, current_b, rot_str):
        """Calculates new 'b' index (Mod 4). +90 (CCW) subtracts 1, -90 adds 1."""
        delta = 1 if rot_str == "+90" else -1
        return (current_b + delta) % 4

    def _calc_vector_sum(self, gear_b, base_b):
        """Calculates absolute direction of a base: (Gear Rot + Base Pos) % 4."""
        return (gear_b + base_b) % 4

    # =========================================================================
    #  RULES ENGINE: MOVE PROCESSING
    # =========================================================================

    def _trigger_entropy(self):
        """
        EXECUTES DISRUPTIVE MOVE (ENTROPY - SWAP WITH PAYLOAD).
        Executes once when inventory reaches 0.
        Uses system randomness (random) in real-time.
        """
        # 1. Identify critical row (Second-to-last)
        target_y = self.dims[1] - 1 
        if target_y < 1: target_y = 1 
        
        # 2. Find ALL candidates (Gears) in that row
        row_coords = [] 
        gear_data_list = [] 

        for x in range(1, self.dims[0] + 1):
            cell_id = f"P{x}{target_y}"
            if cell_id in self.board and self.board[cell_id].startswith("G"):
                row_coords.append(cell_id) 
                gear_data_list.append(self._parse_gear_str(self.board[cell_id]))

        if not row_coords:
            return "ENTROPY: No targets."

        # 3. Shuffle Gear Data List
        random.shuffle(gear_data_list)
        
        mouse_moves_map = {} 
        log_entries = [] 

        # 4. Reconstruct row with shuffled positions and NEW rotations
        for i, target_cell in enumerate(row_coords):
            source_data = gear_data_list[i] 
            origin_cell = source_data["pos"]

            # Map mouse movement (Payload)
            mouse_moves_map[origin_cell] = target_cell
            
            # Randomize Rotation (0-3)
            new_b = random.randint(0, 3)
            
            # Recalculate Topology for destination
            tx, ty = self._get_coords(target_cell)
            target_topo = "R" if (tx + ty) % 2 == 0 else "L"
            
            # Reconstruct string
            self.board[target_cell] = self._build_gear_str(
                source_data["type"], target_cell, target_topo, new_b, source_data["bases_code"]
            )

            # Log
            log_entries.append(f"{origin_cell}->{target_cell}(b={new_b})")
        
        # 5. Update Mice Positions (Payload)
        for m in self.mice.values():
            if m["status"] == "IN_PLAY" and m["pos"] in mouse_moves_map:
                m["pos"] = mouse_moves_map[m["pos"]]

        # 6. Final Log
        full_log_str = ", ".join(log_entries)
        return f"TOTAL ENTROPY: {full_log_str}"

    def process_move(self, move_str):
        """
        Executes a move sent by the agent.
        Manages Phases 1 & 2, physics, and entropy injection.
        """
        # 1. Global State Check
        if self.is_game_over:
            return {
                "success": False, 
                "state": self.get_state(), 
                "msg": "Game ended."
            }

        # 2. Determine Phase
        is_placement_phase = (sum(self.inventory.values()) > 0)
        
        try:
            # 3. Parse Compound Moves
            parts = move_str.split(";") 
            main_move = parts[-1].strip()
            pre_move = parts[0].strip() if len(parts) > 1 else None 

            # 4. Phase Logic
            if is_placement_phase: 
                # -------------------------------------------------------------
                # PHASE 1: PLACEMENT
                # -------------------------------------------------------------
                m = re.match(r"(G\d)@(P\d+)\(b=(\d)\)([+-]90)", main_move)
                if not m: raise ValueError("Invalid Format Phase 1")
                
                g_type, cell_id, b_init_str, rot_str = m.groups()
                b_init = int(b_init_str) 
                
                if b_init not in [0, 1, 2, 3]:
                    raise ValueError(f"Invalid b={b_init}. Must be 0, 1, 2, or 3.")

                # A. Rule Validation
                if self.inventory.get(g_type, 0) < 1: 
                    raise ValueError(f"No {g_type} remaining")
                
                content = self.board[cell_id] 
                if content == "obstacle": raise ValueError(f"Is obstacle")
                if content.startswith("G"): raise ValueError(f"Already occupied")
                
                is_first_row = (self._get_coords(cell_id)[1] == 1) 
                
                # Check for empty board (via inventory) to handle first move rules correctly
                current_total_gears = sum(self.inventory.values())
                initial_total_gears = sum(GAME_LEVELS[self.level_id]["inventory"].values())
                
                is_board_empty = (current_total_gears == initial_total_gears)

                if is_board_empty:
                    # CASE 1: EMPTY BOARD
                    if not is_first_row:
                        raise ValueError(f"Start Rule: First gear ({cell_id}) must be in Row 1.")
                else:
                    # CASE 2: EXISTING PIECES
                    if not self._check_adjacency(cell_id):
                        raise ValueError(f"Adjacency Rule: Tile {cell_id} has no occupied neighbors.")
                
                # B. Execution
                topo = content[-1] 
                valid_bases = GEAR_BASES[g_type] 
                b_code_list = ["2" if i not in valid_bases else "0" for i in range(4)]
                bases_code = "".join(b_code_list) 
                
                self.board[cell_id] = self._build_gear_str(g_type, cell_id, topo, b_init, bases_code)
                self.inventory[g_type] -= 1 
                
                # C. Physics
                self._check_entries() 
                self._apply_rotation(cell_id, rot_str) 

            else:
                # -------------------------------------------------------------
                # PHASE 2: ROTATION
                # -------------------------------------------------------------
                m = re.match(r"G@(P\d+)([+-]90)", main_move)
                if not m: raise ValueError("Invalid Format Phase 2") 
                cell_id, rot_str = m.groups() 
                
                if not self.board[cell_id].startswith("G"): 
                    raise ValueError("Not a Gear")
                
                # Execute Pre-Move
                if pre_move:
                    pm = re.match(r"G@(P\d+):b=(\d)", pre_move) 
                    
                    if not pm:
                        raise ValueError(f"Invalid Pre-Move Format: '{pre_move}'. Required: G@Pxy:b=n")

                    p_cell, p_b = pm.groups() 

                    if int(p_b) not in [0, 1, 2, 3]: 
                        raise ValueError(f"Invalid Pre-move b={p_b}. Must be 0, 1, 2, or 3.")

                    if self.board[p_cell].startswith("G"): 
                        self.board[p_cell] = self._update_gear_str_rotation(self.board[p_cell], int(p_b))
                
                # Execute Main Rotation
                self._apply_rotation(cell_id, rot_str) 

            # =================================================================
            # ENTROPY INJECTION BLOCK (v5.0)
            # =================================================================
            is_now_empty = (sum(self.inventory.values()) == 0)
            entropy_msg = "" 
            
            if is_placement_phase and is_now_empty and not self.entropy_triggered:
                entropy_msg = self._trigger_entropy()
                self.entropy_triggered = True 
            # =================================================================

            # Post-Rotation/Entropy Entry Check
            self._check_entries()

            # 5. Post-Movement Physics (Jumps)
            self._check_jumps()
            
            # Record Successful Move
            move_log = f"J{self.moves_count + 1}: {move_str}"
            self.history.append(move_log)

            # 6. Finalize
            self.moves_count += 1
            self._update_metrics() 
            
            # 7. Build Response
            final_msg = "OK"
            if entropy_msg: 
                final_msg += f" | ⚠️ {entropy_msg}"

            return {"success": True, "state": self.get_state(), "msg": final_msg}

        except Exception as e:
            # Log Failed Move
            move_log = f"J{self.moves_count + 1}: [ERROR] {move_str}" 
            self.history.append(move_log)
            
            # 7. Error Handling (Turn Penalty)
            self.moves_count += 1
            self._update_metrics()
            return {
                "success": False, 
                "state": self.get_state(), 
                "msg": f"FAILED MOVE (Turn lost): {str(e)}"
            }

    # =========================================================================
    #  GAME PHYSICS (Internal Logic)
    # =========================================================================

    def _check_adjacency(self, cell_id):
        """Verifies if a tile has any occupied orthogonal neighbor."""
        cx, cy = self._get_coords(cell_id) 
        for _, (dx, dy) in DIRECTION_DELTAS.items():
            nid = self._get_cell_from_coords(cx + dx, cy + dy) 
            if nid and nid in self.board:
                if self.board[nid].startswith("G"): 
                    return True
        return False
    
    def _check_entries(self):
        """
        Applies Entry Rule (Waiting Mice -> Board).
        Occurs if a Gear in Row 1 has a free base pointing SOUTH (2).
        """
        for mid, m in self.mice.items():
            if m["status"] == "WAITING":
                x = self._get_coords(m["pos"])[0] 
                target = f"P{x}1"
                
                if target in self.board and self.board[target].startswith("G"):
                    g_data = self._parse_gear_str(self.board[target])
                    valid_bases = GEAR_BASES[g_data["type"]] 
                    
                    for b_idx in valid_bases: 
                        # Vector Sum: (Gear Rot + Base) % 4
                        pointing = self._calc_vector_sum(g_data["rot"], b_idx) 
                        
                        if pointing == 2: # Points SOUTH (180 deg)
                            # Check if free in Bxxxx
                            if g_data["bases_code"][b_idx] == '0':
                                # Move Mouse
                                m["pos"] = target 
                                m["on_base"] = b_idx 
                                m["status"] = "IN_PLAY"

                                # Update Gear String (Set base to '1')
                                new_code_list = list(g_data["bases_code"]) 
                                new_code_list[b_idx] = '1' 
                                self.board[target] = self._update_gear_str_bases(self.board[target], "".join(new_code_list))
                                print(f"DEBUG: Mouse {mid} entered the board.") 
                                break

    def _apply_rotation(self, driver_cell, rot_str): 
        """
        Implements Unified Rotation Principle (Cascade).
        Compares topology of each gear vs driver. Same=Same Dir, Opp=Opp Dir.
        """
        driver_data = self._parse_gear_str(self.board[driver_cell])
        driver_topo = driver_data["topo"] 
        
        for cell_id, cell_str in self.board.items():
            
            if cell_str.startswith("G"): 
                g_data = self._parse_gear_str(cell_str) 
                
                # Determine relative direction
                current_rot_str = rot_str 
                if g_data["topo"] != driver_topo: 
                    current_rot_str = "-90" if rot_str == "+90" else "+90"
                
                # Calc new 'b'
                new_b = self._calc_rotation(g_data["rot"], current_rot_str)
                
                # Apply changes
                if new_b != g_data["rot"]:
                    self.board[cell_id] = self._update_gear_str_rotation(cell_str, new_b)

    def _check_jumps(self):
        """
        Executes jump physics.
        LOGIC (v5.2): Each mouse can jump MAX 1 TIME per turn.
        """
        # Iterate over a copy of IDs to safely modify state
        active_mice = [mid for mid, m in self.mice.items() if m["status"] == "IN_PLAY"]
        
        for mid in active_mice: 
            m = self.mice[mid] 
            
            if m["pos"] not in self.board: continue 

            # Get fresh data
            curr_gear_str = self.board[m["pos"]] 
            curr_gear_data = self._parse_gear_str(curr_gear_str) 
        
            # 1. Calculate Absolute Output Vector
            pointing = self._calc_vector_sum(curr_gear_data["rot"], m["on_base"])
            
            # 2. Calculate Target Coordinates
            dx, dy = DIRECTION_DELTAS[pointing]
            cx, cy = self._get_coords(m["pos"]) 
            target_cell = self._get_cell_from_coords(cx + dx, cy + dy) 
            
            if not target_cell: continue

            # --- CASE A: BOARD EXIT (Victory) ---
            if self._get_coords(target_cell)[1] > self.dims[1]:
                if pointing == 0:
                    # 1. Free origin base
                    old_code = list(curr_gear_data["bases_code"]) 
                    old_code[m["on_base"]] = '0' 
                    self.board[m["pos"]] = self._update_gear_str_bases(curr_gear_str, "".join(old_code))
                    
                    # 2. Update Mouse
                    m["status"] = "ESCAPED"
                    m["pos"] = "OUT"
                    m["on_base"] = None
                    
                    # 3. Score
                    self.score_accumulated += 10
                continue 

            # --- CASE B: JUMP TO ANOTHER GEAR ---
            if target_cell in self.board and self.board[target_cell].startswith("G"):
                tgt_gear_str = self.board[target_cell] 
                tgt_data = self._parse_gear_str(tgt_gear_str)          
                
                # Calc Required Input Vector (Opposite)
                required = (pointing + 2) % 4
                valid_bases = GEAR_BASES[tgt_data["type"]] 
                
                for tb_idx in valid_bases: 
                    t_pointing = self._calc_vector_sum(tgt_data["rot"], tb_idx)
                    
                    if t_pointing == required: 
                        # Geometric connection OK. Check occupancy.
                        if tgt_data["bases_code"][tb_idx] == '0':

                            # --- EXECUTE JUMP ---

                            # 1. Update Board (Free origin)
                            old_code = list(curr_gear_data["bases_code"]) 
                            old_code[m["on_base"]] = '0'
                            self.board[m["pos"]] = self._update_gear_str_bases(curr_gear_str, "".join(old_code))
                            
                            # 2. Update Board (Occupy destination)
                            current_tgt_str = self.board[target_cell]
                            tgt_bases_updated = list(self._parse_gear_str(current_tgt_str)["bases_code"]) 
                            tgt_bases_updated[tb_idx] = '1' 
                            self.board[target_cell] = self._update_gear_str_bases(current_tgt_str, "".join(tgt_bases_updated))
                            
                            # 3. Move Mouse
                            m["pos"] = target_cell 
                            m["on_base"] = tb_idx 

                            # 4. Score
                            self.score_accumulated += SCORE_POINTS[pointing]
                            
                            break

    def _count_rescued_mice(self):
        """Counts total ESCAPED mice."""
        return len([m for m in self.mice.values() if m["status"] == "ESCAPED"])

    def _update_metrics(self):
        """
        Recalculates global game metrics after each move.
        Updates progress, score, and checks win/loss conditions.
        Benchmark score is calculated only at game end.
        """
        rescued = self._count_rescued_mice() 
        total = len(self.mice) 
        
        self.completion_percent = (rescued / total) * 100
        
        if rescued == total:
            self.is_game_over = True
            self.game_result = "VICTORY"
        elif self.moves_count >= self.max_moves:
            self.is_game_over = True
            self.game_result = "TIMEOUT"

        if self.is_game_over:
            self.final_benchmark_score = self._calculate_final_score()
        else:
            self.final_benchmark_score = 0

if __name__ == "__main__":
    g = CapsiCapsGame()
    print("Initial State:")
    print(g.get_state())
    print("\nExecuting Error Test (Turn Lost)...")
    res = g.process_move ("G4@P21(b=3)+90")
    print(res)