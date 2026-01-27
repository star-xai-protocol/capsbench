# -*- coding: utf-8 -*-
"""
capsicaps_env.py
Version: 1.0 (Gymnasium Wrapper)
Standard Adapter for STAR-XAI Protocol

DESCRIPTION:
This file wraps 'game_logic.py' inside a gym.Env class.
It makes the game compatible with standard Reinforcement Learning libraries
(Stable Baselines3, Ray Rllib, etc.).

GYMNASIUM COMPLIANCE:
- Implements reset(seed) and step(action).
- Defines action_space (Text/Commands) and observation_space (Dict/JSON).
- Calculates marginal reward (Delta Score) per step.
"""

import gymnasium as gym
from gymnasium import spaces
import numpy as np
import json

# Import our logic engine (The Source of Truth)
from game_logic import CapsiCapsGame

class CapsiCapsEnv(gym.Env):
    """
    Custom Gymnasium Environment for Caps i Caps.
    
    Render Modes:
    - "human": Print ASCII text to console.
    - "json": Return raw data state (useful for Green Agent/Server).
    """
    metadata = {"render_modes": ["human", "json"], "render_fps": 4}

    def __init__(self, level_id="1"):
        super(CapsiCapsEnv, self).__init__()
        
        self.game = CapsiCapsGame()
        self.level_id = level_id
        
        # Variable for Step-by-Step Reward Calculation (Reward Shaping)
        # Gymnasium needs the marginal delta for the specific step, not the accumulated total.
        self._last_score = 0

        # 1. Define ACTION SPACE (The AI's "Keyboard")
        # Since moves are complex text commands (e.g., "G4@P21(b=0)+90"), 
        # we use spaces.Text. The AI must generate strings.
        self.action_space = spaces.Text(max_length=50)

        # 2. Define OBSERVATION SPACE (The AI's "Eyes")
        # The AI "sees" the game state as a structured Dictionary.
        # Ideally this would be numerical Tensors, but for the A2A Benchmark 
        # we send the raw JSON structure for the Agent to process.
        self.observation_space = spaces.Dict({
            "status": spaces.Text(max_length=20),
            "game_over": spaces.Discrete(2), # 0=No, 1=Yes
            # Full board data is sent via the 'info' channel
        })

    def reset(self, seed=None, options=None):
        """
        Resets the environment. 
        Implements 'seed' for framework reproducibility, even if the engine 
        uses just-in-time entropy.
        """
        super().reset(seed=seed)
        
        # Handle Options (Level Selection)
        lvl = options.get("level_id", self.level_id) if options else self.level_id
        
        # Reset Physics Engine
        raw_state = self.game.reset(level_id=lvl)
        
        # Reset Metrics
        self._last_score = 0
        
        # Format Output
        observation = self._format_observation(raw_state)
        # Pass the full raw state in 'info' for the Evaluator/Green Agent
        info = raw_state 
        
        return observation, info

    def step(self, action):
        """
        Executes a step in the environment.
        Args:
            action (str): The move command (e.g., "G4@P21...")   
        Returns:
            observation, reward, terminated, truncated, info
        """
        # 1. Execute Move
        # The engine handles validation, physics, and entropy triggers.
        result = self.game.process_move(str(action))
        
        state = result["state"]
        msg = result["msg"]
        
        # 2. Calculate REWARD (Delta)
        # RL Agents understand immediate change better than accumulated score.
        # We calculate: Points_Now - Points_Before = Step_Reward
        current_total_score = state["scoring"]["raw_points"]
        step_reward = current_total_score - self._last_score
        self._last_score = current_total_score
        
        # Negative Reinforcement for Illegal Moves
        # If the move failed (syntax/rule error), penalize slightly to discourage 
        # invalid actions (cost > 0 prevents infinite loops on invalid moves).
        if not result["success"]:
            step_reward -= 1 
        
        # 3. Determine Termination
        terminated = state["status"]["game_over"]
        
        # Truncated is False because the engine manages its own 'max_moves' limit.
        truncated = False 
        
        # 4. Format Observation
        # Adapt complex engine state to the strict Gym observation space.
        observation = self._format_observation(state)
        
        # 5. Extra Info (Entropy Channel)
        # We hide the full JSON and Entropy alerts in 'info' for the wrapper/server.
        info = {
            "msg": msg,           # "OK" or "⚠️ ENTROPY..."
            "full_state": state,  # Complete JSON state
            "is_success": result["success"]
        }
        
        return observation, step_reward, terminated, truncated, info

    def _format_observation(self, raw_state):
        """
        Adapts the complex game_logic JSON to a minimal Gymnasium-compliant dict.
        The intelligent agent is expected to read 'info' for real data.
        """
        return {
            "status": "RUNNING" if not raw_state["status"]["game_over"] else "DONE",
            "game_over": 1 if raw_state["status"]["game_over"] else 0
        }

    def render(self):
        """Displays the state in console (ASCII)"""
        print(f"--- Turn {self.game.moves_count} ---")
        print(f"Score: {self.game.score_accumulated}")
        # Pretty print the board encoding for human debugging
        print(json.dumps(self.game.get_state()["data"]["board_encoding"], indent=2))