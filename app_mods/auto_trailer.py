"""
File: auto_trailer.py  
Author: [Tarakeshwar NC]
Date: September 4, 2025 (Refactored)
Description: AutoTrailer as PFMU-owned module with proper encapsulation
"""
# Copyright (c) [2024] [Tarakeshwar N.C]
# This file is part of the TeZ project.
# It is subject to the terms and conditions of the MIT License.
# See the file LICENSE in the top-level directory of this distribution
# for the full text of the license.

import traceback
import copy
from typing import Dict, Optional, Any, NamedTuple
from enum import Enum
from dataclasses import dataclass

from app_utils import app_logger
logger = app_logger.get_logger(__name__)

from .shared_classes import AutoTrailerData, AutoTrailerEvent


class MOVE_TO_COST_STATE(Enum):
    WAITING_UP_CROSS = 0
    WAITING_DOWN_CROSS = 1


class TRAIL_SL_STATE(Enum):
    WAITING_UP_CROSS = 0
    TRAIL_STARTED = 1
    TRAIL_SL_HIT = 2


@dataclass
class AutoTrailerAction:
    """Result of auto-trader condition checking"""
    should_square_off: bool = False
    reason: Optional[str] = None
    pnl: Optional[float] = None


class AutoTrailer:
    """
    AutoTrailer as pure calculation library
    Provides stateless auto-trading condition checking and calculations
    """
    
    def __init__(self):
        """
        Initialize AutoTrailer as pure calculation library
        """
        self._active = False  # Auto-trading active state
        
        # Internal state 
        self._params = None  # AutoTrailerData when active
        self._current_state = AutoTrailerEvent(pnl=0.0)
        
        # Internal trailing state (moved from PFMU for true encapsulation)
        self.mov_to_cost_state = MOVE_TO_COST_STATE.WAITING_UP_CROSS
        self.trail_sl_state = TRAIL_SL_STATE.WAITING_UP_CROSS
        self.max_pnl = None
        self.mv_to_cost_pnl = None
        self.trail_sl_level = None  # Dynamic trailing stop-loss level
        
        logger.info("AutoTrailer initialized as pure calculation library with internal state management")
    
    def activate(self, params: AutoTrailerData, current_pnl: float) -> bool:
        """
        Activate auto-trading with parameters and initialize internal state
        Called by PFMU.activate_auto_trading()
        
        Args:
            params: AutoTrailerData with sl, target, trailing parameters
            current_pnl: Current P&L for initializing trailing state
            
        Returns:
            bool: True if activation successful
        """
        try:
            # Validate parameters
            validation_result = self._validate_parameters(params)
            if not validation_result["valid"]:
                logger.error(f"Invalid parameters: {validation_result['error']}")
                return False
            
            # Store parameters
            self._params = params
            self._active = True
            
            # Reset/Initialize internal trailing state (no external ui_reset needed)
            self.mov_to_cost_state = MOVE_TO_COST_STATE.WAITING_UP_CROSS
            self.trail_sl_state = TRAIL_SL_STATE.WAITING_UP_CROSS
            self.max_pnl = None
            self.mv_to_cost_pnl = current_pnl
            self.trail_sl_level = None

            # Reset event state flags to clear previous session's target/SL hits
            self._current_state.target_hit = False
            self._current_state.sl_hit = False
            self._current_state.sq_off_done = False
            self._current_state.pnl = current_pnl

            logger.info(f"AutoTrailer activated with SL: {params.sl}, Target: {params.target}, Initial P&L: {current_pnl}")
            logger.info("AutoTrailer internal state initialized/reset")
            return True
            
        except Exception as e:
            logger.error(f"Error activating AutoTrailer: {e}")
            return False

    def deactivate(self) -> bool:
        """
        Deactivate auto-trading
        Called by PFMU.deactivate_auto_trading()

        Returns:
            bool: True if deactivation successful
        """
        try:
            self._active = False
            self._params = None

            # Note: Do NOT set sq_off_done here - it should only be set when actual square-off occurs
            # Setting it here incorrectly blocks manual trading after deactivation

            logger.info("AutoTrailer deactivated")
            return True

        except Exception as e:
            logger.error(f"Error deactivating AutoTrailer: {e}")
            return False

    def get_current_state(self, current_pnl: float) -> AutoTrailerEvent:
        """
        Get current AutoTrailer state
        Called by PFMU.get_ui_state()
        
        Args:
            current_pnl: Current P&L value from PFMU
        
        Returns:
            AutoTrailerEvent: Current state for UI display
        """
        # Update state with provided P&L
        self._current_state.pnl = current_pnl
        
        return copy.deepcopy(self._current_state)


    def is_active(self) -> bool:
        """Check if auto-trading is currently active"""
        return self._active

    def check_conditions(self, current_pnl: float, position_qty: Optional[int], 
                        params: AutoTrailerData) -> AutoTrailerAction:
        """
        Pure function to check auto-trading conditions using internal state
        
        Args:
            current_pnl: Current P&L value
            position_qty: Current position quantity (None or 0 means no positions)
            params: Auto-trader parameters (SL, target, etc.)
            
        Returns:
            AutoTrailerAction: Action to take based on conditions
        """
        # Check if positions exist
        if position_qty is None or position_qty == 0:
            return AutoTrailerAction()  # No action needed
        
        # Check trailing stop-loss condition first (takes precedence over fixed SL)
        if (self.trail_sl_state == TRAIL_SL_STATE.TRAIL_STARTED and
            self.trail_sl_level is not None and
            current_pnl <= self.trail_sl_level):
            logger.info(f"Trailing SL hit: PnL {current_pnl} <= Trailing SL {self.trail_sl_level}")
            self.trail_sl_state = TRAIL_SL_STATE.TRAIL_SL_HIT

            # Update state flags to indicate SL hit and square-off triggered
            self._current_state.sl_hit = True
            self._current_state.sq_off_done = True

            return AutoTrailerAction(
                should_square_off=True,
                reason="TRAIL_SL_HIT",
                pnl=current_pnl
            )

        # Check fixed stop-loss condition
        if current_pnl <= params.sl:
            logger.info(f"SL condition hit: PnL {current_pnl} <= SL {params.sl}")

            # Update state flags to indicate SL hit and square-off triggered
            self._current_state.sl_hit = True
            self._current_state.sq_off_done = True

            return AutoTrailerAction(
                should_square_off=True,
                reason="SL_HIT",
                pnl=current_pnl
            )

        # Check target condition
        elif current_pnl >= params.target:
            logger.info(f"Target condition hit: PnL {current_pnl} >= Target {params.target}")

            # Update state flags to indicate target hit and square-off triggered
            self._current_state.target_hit = True
            self._current_state.sq_off_done = True

            return AutoTrailerAction(
                should_square_off=True,
                reason="TARGET_HIT",
                pnl=current_pnl
            )
        
        # Process trailing logic if neither SL nor target hit
        else:
            self._update_trailing_state(current_pnl, params)
            return AutoTrailerAction()  # No action needed, just state updated

    def _update_trailing_state(self, current_pnl: float, params: AutoTrailerData) -> None:
        """
        Update internal trailing logic state based on current P&L
        
        Args:
            current_pnl: Current P&L value
            params: Auto-trader parameters
        """
        # Move-to-cost logic
        if (self.mov_to_cost_state == MOVE_TO_COST_STATE.WAITING_UP_CROSS and 
            current_pnl >= params.mvto_cost):
            
            logger.info(f"Move-to-cost triggered: PnL {current_pnl} >= {params.mvto_cost}")
            self.mov_to_cost_state = MOVE_TO_COST_STATE.WAITING_DOWN_CROSS
            self.mv_to_cost_pnl = current_pnl
            
        # Trailing stop-loss logic - update max P&L if higher
        if self.max_pnl is None or current_pnl > self.max_pnl:
            self.max_pnl = current_pnl
            logger.debug(f"Updated max P&L: {self.max_pnl}")
            
        # Trailing stop-loss state machine
        if self.trail_sl_state == TRAIL_SL_STATE.WAITING_UP_CROSS:
            # Check if P&L crosses trail_after threshold to start trailing
            if current_pnl >= params.trail_after:
                logger.info(f"Trail started: PnL {current_pnl} >= Trail-after {params.trail_after}")
                self.trail_sl_state = TRAIL_SL_STATE.TRAIL_STARTED
                # Initialize trailing stop-loss level
                if self.max_pnl is not None:
                    self.trail_sl_level = self.max_pnl - params.trail_by
                    logger.info(f"Initial trailing SL set: {self.trail_sl_level} (max_pnl: {self.max_pnl} - trail_by: {params.trail_by})")
        
        elif self.trail_sl_state == TRAIL_SL_STATE.TRAIL_STARTED:
            # Update trailing stop-loss level when max P&L increases
            if self.max_pnl is not None:
                new_trail_sl_level = self.max_pnl - params.trail_by
                if self.trail_sl_level is None or new_trail_sl_level > self.trail_sl_level:
                    self.trail_sl_level = new_trail_sl_level
                    logger.debug(f"Trailing SL updated: {self.trail_sl_level} (max_pnl: {self.max_pnl} - trail_by: {params.trail_by})")
        
        # Note: TRAIL_SL_HIT state is handled in check_conditions() method

    def shutdown(self) -> None:
        """
        Shutdown AutoTrailer module - simplified (no threads)
        Called by PFMU.hard_exit()
        """
        logger.info("Shutting down AutoTrailer...")
        
        # Clear state
        self._active = False
        self._params = None
        
        logger.info("AutoTrailer shutdown complete")
    


    def _validate_parameters(self, params: AutoTrailerData) -> dict:
        """
        Validate auto-trading parameters
        
        Args:
            params: AutoTrailerData to validate
            
        Returns:
            dict: {"valid": bool, "error": str}
        """
        if params.sl >= 0:
            return {"valid": False, "error": "Stop loss must be negative"}
            
        if params.target <= 0:
            return {"valid": False, "error": "Target must be positive"}
            
        if params.sl >= params.target:
            return {"valid": False, "error": "Stop loss must be less than target"}
            
        if params.mvto_cost <= params.sl:
            return {"valid": False, "error": "Move-to-cost must be greater than stop loss"}
            
        if params.trail_after <= params.mvto_cost:
            return {"valid": False, "error": "Trail-after must be greater than move-to-cost"}
            
        if params.trail_by <= 0:
            return {"valid": False, "error": "Trail-by must be positive"}
            
        # Note: Real-time P&L validation happens during monitoring, not parameter validation
        
        return {"valid": True, "error": ""}