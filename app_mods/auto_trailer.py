"""
File: auto_trailer.py
Author: [Tarakeshwar NC]
Date: May 15, 2024
Description: This module provides automatic trading functionality with thread safety.
"""
# Copyright (c) [2024] [Tarakeshwar N.C]
# This file is part of the TeZ project.
# It is subject to the terms and conditions of the MIT License.
# See the file LICENSE in the top-level directory of this distribution
# for the full text of the license.

import sys
import traceback
import threading
import time
import copy  # Add import for copy module

import app_utils as utils
import app_mods

from app_utils import app_logger
logger = app_logger.get_logger(__name__)

from .shared_classes import AutoTrailerData, AutoTrailerEvent, UI_State
from .pfmu import MOVE_TO_COST_STATE, TRAIL_SL_STATE

class AutoTrailer:
    """
    Thread-safe AutoTrailer class that monitors positions and executes trading logic.
    
    This class runs in its own thread and provides a clean interface to control
    auto trading functionality. All threading details are encapsulated within.
    """
    
    def __init__(self, pfmu):
        """
        Initialize the AutoTrailer with a reference to the PFMU
        
        Args:
            pfmu: Portfolio Management Unit reference
        """
        self.pfmu = pfmu
        self._thread = None
        self._active = False  # Flag to control whether auto trading is processing
        self._running = False  # Flag to control the monitoring thread
        self._lock = threading.Lock()
        self.current_pnl = 0.0
        self.current_state = AutoTrailerEvent(pnl=0.0)
        self.auto_trailer_data = None
        self._last_deactivation_time = 0  # To prevent reactivation loops
        self._last_failed_params = None  # To store parameters that caused deactivation
        
        # Copy initial state from PFMU
        self.mov_to_cost_state = self.pfmu.mov_to_cost_state
        self.trail_sl_state = self.pfmu.trail_sl_state
        self.max_pnl = self.pfmu.max_pnl
        self.mv_to_cost_pnl = self.pfmu.mv_to_cost_pnl
        
        # Start thread immediately
        self.start()
        
    def start(self):
        """Start the auto trailer monitoring thread"""
        with self._lock:
            if not self._running:
                self._running = True
                self._thread = threading.Thread(target=self._run_loop, daemon=True)
                self._thread.name = "AutoTrailerThread"
                self._thread.start()
                logger.info("Auto trailer thread started")
            
    def stop(self):
        """Stop the auto trailer monitoring thread"""
        with self._lock:
            self._running = False
            self._active = False
        
        # Wait for thread to finish if it's running
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
            logger.info("Auto trailer thread stopped")
            self._thread = None
    
    def process(self, atd=None):
        """
        Process auto trailer logic based on the provided data
        
        Args:
            atd: AutoTrailerData with parameters, or None to disable auto trading
            
        Returns:
            AutoTrailerEvent with current state
        """
        # Safeguard against hanging due to rapid or repeated activation attempts
        try:
            # Use a non-blocking lock with timeout
            lock_acquired = self._lock.acquire(timeout=0.5)  # 500ms timeout
            if not lock_acquired:
                logger.error("DEADLOCK PREVENTION: Auto trader is busy. Please wait a moment.")
                # Return current state without modifying anything
                return self.current_state
                
            # If atd is None, disable auto trading (Manual mode)
            # If atd is provided, enable auto trading with parameters (Auto mode)
            if atd is not None:
                # Store the original parameters for comparison
                if not hasattr(self, '_last_failed_params'):
                    self._last_failed_params = None
                
                # Check if these are the same parameters that just failed
                if self._last_failed_params is not None:
                    same_params = (
                        atd.sl == self._last_failed_params.sl and
                        atd.target == self._last_failed_params.target and
                        atd.mvto_cost == self._last_failed_params.mvto_cost and
                        atd.trail_after == self._last_failed_params.trail_after and
                        atd.trail_by == self._last_failed_params.trail_by
                    )
                    
                    # Check the current PNL condition
                    current_pnl = self.pfmu.intra_day_pnl()
                    
                    # If parameters are invalid for current PNL, block activation regardless of time
                    if (current_pnl <= atd.sl or current_pnl >= atd.target):
                        logger.warning(f"Cannot activate - current PNL ({current_pnl}) doesn't work with these parameters (SL: {atd.sl}, Target: {atd.target})")
                        # Create a UI-friendly event to show the warning
                        warning_ate = AutoTrailerEvent(pnl=current_pnl)
                        warning_ate.sq_off_done = True  # This will keep the UI in Manual mode
                        return warning_ate
                    
                    # If using the same parameters that just caused a deactivation, block activation for a time period
                    if same_params and time.time() - self._last_deactivation_time < 10.0:
                        logger.warning("Cannot activate with the same parameters so quickly. Please wait or adjust parameters.")
                        # Create a UI-friendly event to show the warning
                        warning_ate = AutoTrailerEvent(pnl=current_pnl)
                        warning_ate.sq_off_done = True  # This will keep the UI in Manual mode
                        return warning_ate
                
                # Anti-loop protection: Don't allow reactivation within 2 seconds of deactivation
                current_time = time.time()
                if current_time - self._last_deactivation_time < 2.0:
                    logger.warning("Preventing rapid reactivation - please wait a moment before activating again")
                    return self.current_state
                    
                was_active = self._active
                
                # Validate the parameters to ensure they make sense
                current_pnl = self.pfmu.intra_day_pnl()
                
                if atd.sl >= 0:
                    logger.warning(f"Stop loss value should be negative: {atd.sl}")
                    # Don't activate if SL values don't make sense
                    return self.current_state
                
                # Check if parameters are already met
                total_qty = self.pfmu.portfolio.available_qty(ul_index=None)
                positions_exist = total_qty is not None and total_qty != 0
                
                if current_pnl <= atd.sl:
                    logger.info(f"Current PNL ({current_pnl}) already below SL threshold ({atd.sl})")
                    
                    if positions_exist:
                        logger.info("Positions exist - executing immediate square-off")
                        try:
                            # Execute square off directly
                            self.pfmu.square_off_position(mode='ALL', ul_index=None, per=100, inst_type='ALL', partial_exit=False, exit_flag=False)
                            self.pfmu.show()
                            
                            # Check if positions are actually closed
                            remaining_qty = self.pfmu.portfolio.available_qty(ul_index=None)
                            immediate_ate = AutoTrailerEvent(pnl=current_pnl, sl_hit=True)
                            immediate_ate.sq_off_done = remaining_qty is None or remaining_qty == 0
                            
                            if immediate_ate.sq_off_done:
                                logger.info(f"Immediate square-off completed successfully")
                                # Call system square-off callback if available
                                if hasattr(self.pfmu, '_system_sqoff_cb') and self.pfmu._system_sqoff_cb is not None:
                                    logger.info("Calling system_sqoff_cb to update UI")
                                    self.pfmu._system_sqoff_cb()
                                    
                                # Record deactivation time to prevent immediate reactivation
                                self._last_deactivation_time = time.time()
                            else:
                                logger.warning(f"Immediate square-off attempted but positions remain, remaining qty: {remaining_qty}")
                                
                            # Don't activate auto trading
                            self.current_state = immediate_ate
                            return self.current_state
                            
                        except Exception as e:
                            logger.error(f"Error in immediate square off: {e}")
                            logger.error(traceback.format_exc())
                    else:
                        logger.info("No positions exist - not activating auto trader due to parameters already met")
                        immediate_ate = AutoTrailerEvent(pnl=current_pnl, sl_hit=True)
                        immediate_ate.sq_off_done = True
                        
                        # Rather than relying on system_sqoff_cb (which has a position check),
                        # we'll directly force the UI back to manual mode by updating our event flags
                        immediate_ate.sq_off_done = True  # This should trigger UI to switch to Manual
                        
                        # Call system square-off callback to update UI if available - just for logging
                        if hasattr(self.pfmu, '_system_sqoff_cb') and self.pfmu._system_sqoff_cb is not None:
                            logger.info("Calling system_sqoff_cb to update UI")
                            self.pfmu._system_sqoff_cb()
                            
                        # Remember these parameters as the ones that failed
                        self._last_failed_params = copy.deepcopy(atd)
                        
                        # Record deactivation time to prevent immediate reactivation
                        self._last_deactivation_time = time.time()
                            
                        self.current_state = immediate_ate
                        return self.current_state
                    
                if current_pnl >= atd.target:
                    logger.info(f"Current PNL ({current_pnl}) already above target threshold ({atd.target})")
                    
                    if positions_exist:
                        logger.info("Positions exist - executing immediate square-off")
                        try:
                            # Execute square off directly
                            self.pfmu.square_off_position(mode='ALL', ul_index=None, per=100, inst_type='ALL', partial_exit=False, exit_flag=False)
                            self.pfmu.show()
                            
                            # Check if positions are actually closed
                            remaining_qty = self.pfmu.portfolio.available_qty(ul_index=None)
                            immediate_ate = AutoTrailerEvent(pnl=current_pnl, target_hit=True)
                            immediate_ate.sq_off_done = remaining_qty is None or remaining_qty == 0
                            
                            if immediate_ate.sq_off_done:
                                logger.info(f"Immediate square-off completed successfully")
                                # Call system square-off callback if available
                                if hasattr(self.pfmu, '_system_sqoff_cb') and self.pfmu._system_sqoff_cb is not None:
                                    logger.info("Calling system_sqoff_cb to update UI")
                                    self.pfmu._system_sqoff_cb()
                            else:
                                logger.warning(f"Immediate square-off attempted but positions remain, remaining qty: {remaining_qty}")
                                
                            # Don't activate auto trading
                            self.current_state = immediate_ate
                            return self.current_state
                            
                        except Exception as e:
                            logger.error(f"Error in immediate square off: {e}")
                            logger.error(traceback.format_exc())
                    else:
                        logger.info("No positions exist - not activating auto trader due to parameters already met")
                        immediate_ate = AutoTrailerEvent(pnl=current_pnl, target_hit=True)
                        immediate_ate.sq_off_done = True
                        
                        # Call system square-off callback to update UI if available
                        if hasattr(self.pfmu, '_system_sqoff_cb') and self.pfmu._system_sqoff_cb is not None:
                            logger.info("Calling system_sqoff_cb to update UI")
                            self.pfmu._system_sqoff_cb()
                            
                        self.current_state = immediate_ate
                        return self.current_state
                
                # Reset states if UI reset is requested
                if atd.ui_reset:
                    self.mov_to_cost_state = self.pfmu.mov_to_cost_state = MOVE_TO_COST_STATE.WAITING_UP_CROSS
                    self.trail_sl_state = self.pfmu.trail_sl_state = TRAIL_SL_STATE.WAITING_UP_CROSS
                    self.max_pnl = self.pfmu.max_pnl = None
                    self.mv_to_cost_pnl = self.pfmu.mv_to_cost_pnl = current_pnl
                    logger.info("Auto trailer states reset")
                
                # Check for immediate conditions before activating
                total_qty = self.pfmu.portfolio.available_qty(ul_index=None)
                positions_exist = total_qty is not None and total_qty != 0
                
                if positions_exist:
                    # Check for immediate SL hit
                    if current_pnl <= atd.sl:
                        logger.info(f"Immediate SL condition detected at activation: {current_pnl} <= {atd.sl}")
                        try:
                            # Execute square off directly
                            self.pfmu.square_off_position(mode='ALL', ul_index=None, per=100, inst_type='ALL', partial_exit=False, exit_flag=False)
                            self.pfmu.show()
                            
                            # Check if positions are actually closed
                            remaining_qty = self.pfmu.portfolio.available_qty(ul_index=None)
                            immediate_ate = AutoTrailerEvent(pnl=current_pnl, sl_hit=True)
                            immediate_ate.sq_off_done = remaining_qty is None or remaining_qty == 0
                            
                            if immediate_ate.sq_off_done:
                                logger.info(f"Immediate square-off completed successfully at activation")
                                # Call system square-off callback if available
                                if hasattr(self.pfmu, '_system_sqoff_cb') and self.pfmu._system_sqoff_cb is not None:
                                    logger.info("Calling system_sqoff_cb to update UI")
                                    self.pfmu._system_sqoff_cb()
                                # Don't activate auto trading
                                self.current_state = immediate_ate
                                return self.current_state
                            
                        except Exception as e:
                            logger.error(f"Error in immediate square off at activation: {e}")
                            logger.error(traceback.format_exc())
                    
                    # Check for immediate target hit
                    elif current_pnl >= atd.target:
                        logger.info(f"Immediate target condition detected at activation: {current_pnl} >= {atd.target}")
                        try:
                            # Execute square off directly
                            self.pfmu.square_off_position(mode='ALL', ul_index=None, per=100, inst_type='ALL', partial_exit=False, exit_flag=False)
                            self.pfmu.show()
                            
                            # Check if positions are actually closed
                            remaining_qty = self.pfmu.portfolio.available_qty(ul_index=None)
                            immediate_ate = AutoTrailerEvent(pnl=current_pnl, target_hit=True)
                            immediate_ate.sq_off_done = remaining_qty is None or remaining_qty == 0
                            
                            if immediate_ate.sq_off_done:
                                logger.info(f"Immediate square-off completed successfully at activation")
                                # Call system square-off callback if available
                                if hasattr(self.pfmu, '_system_sqoff_cb') and self.pfmu._system_sqoff_cb is not None:
                                    logger.info("Calling system_sqoff_cb to update UI")
                                    self.pfmu._system_sqoff_cb()
                                # Don't activate auto trading
                                self.current_state = immediate_ate
                                return self.current_state
                            
                        except Exception as e:
                            logger.error(f"Error in immediate square off at activation: {e}")
                            logger.error(traceback.format_exc())
                
                # If we get here, either no positions exist or conditions not immediately met
                # Store the parameters and activate auto trading
                self._active = True
                self.auto_trailer_data = atd
                
                if not positions_exist:
                    logger.info("Auto trader activated but no positions to monitor yet - will monitor when positions are taken")
                
                if not was_active:
                    logger.info("Auto trailer activated with parameters")
            else:
                # Only disable if coming from ui_cust_widgets.py in _on_mode_change method
                caller_frame = sys._getframe(1)
                caller_file = caller_frame.f_code.co_filename.split('\\')[-1]
                caller_func = caller_frame.f_code.co_name
                
                # Only allow deactivation from UI _on_mode_change method, not from update_ui
                if caller_file == "ui_cust_widgets.py" and caller_func == "_on_mode_change":
                    # Disable auto trading if currently active
                    if self._active:
                        self._active = False
                        logger.info("Auto trailer deactivated")
            
            # Always sync state with PFMU to ensure consistency
            self.mov_to_cost_state = self.pfmu.mov_to_cost_state
            self.trail_sl_state = self.pfmu.trail_sl_state
            self.max_pnl = self.pfmu.max_pnl
            self.mv_to_cost_pnl = self.pfmu.mv_to_cost_pnl
            
            # Return current state (always available)
            return self.current_state
        finally:
            # Always release the lock, even if an exception occurs
            if self._lock.locked():
                self._lock.release()
            
    def _run_loop(self):
        """Main monitoring loop - always running but processing conditionally"""
        # Get update interval from config with a default value
        try:
            # FIX: Use only 2 parameters, not 3
            update_interval = float(app_mods.get_system_info("SYSTEM", "AUTO_TRAILER_UPDATE_FREQUENCY"))
        except Exception as e:
            logger.error(f"Error getting update interval: {str(e)}")
            # Provide a default value if there's an error
            update_interval = 1.0
        
        # Sleep for a short time initially to ensure the main thread can complete initialization
        time.sleep(0.5)
        
        while self._running:
            try:
                # Always update PNL regardless of active state
                pnl = self.pfmu.intra_day_pnl()
                
                with self._lock:
                    self.current_pnl = pnl
                    
                    # Always update the basic PNL in state
                    ate = AutoTrailerEvent(pnl=pnl)
                    
                    # Only process auto trading logic if active
                    if self._active and self.auto_trailer_data is not None:
                        # Check if any positions are open
                        total_qty = self.pfmu.portfolio.available_qty(ul_index=None)
                        if total_qty is None or total_qty == 0:
                            # No positions to monitor yet - just wait
                            logger.debug("Auto trader active but no positions to monitor yet")
                        else:
                            # Check if positions should be immediately squared off based on parameters
                            if pnl <= self.auto_trailer_data.sl:
                                logger.info(f"Position PNL {pnl} already below SL threshold {self.auto_trailer_data.sl} - immediate square off")
                                try:
                                    # Execute square off directly
                                    self.pfmu.square_off_position(mode='ALL', ul_index=None, per=100, inst_type='ALL', partial_exit=False, exit_flag=False)
                                    self.pfmu.show()
                                    
                                    # Check if positions are actually closed
                                    remaining_qty = self.pfmu.portfolio.available_qty(ul_index=None)
                                    ate.sq_off_done = remaining_qty is None or remaining_qty == 0
                                    ate.sl_hit = True
                                    
                                    if ate.sq_off_done:
                                        logger.info(f"Immediate square-off completed successfully")
                                    else:
                                        logger.warning(f"Immediate square-off attempted but positions remain, remaining qty: {remaining_qty}")
                                    
                                except Exception as e:
                                    logger.error(f"Error in immediate square off: {e}")
                                    logger.error(traceback.format_exc())
                            # Also check for target condition immediately
                            elif pnl >= self.auto_trailer_data.target:
                                logger.info(f"Position PNL {pnl} already above target threshold {self.auto_trailer_data.target} - immediate square off")
                                try:
                                    # Execute square off directly
                                    self.pfmu.square_off_position(mode='ALL', ul_index=None, per=100, inst_type='ALL', partial_exit=False, exit_flag=False)
                                    self.pfmu.show()
                                    
                                    # Check if positions are actually closed
                                    remaining_qty = self.pfmu.portfolio.available_qty(ul_index=None)
                                    ate.sq_off_done = remaining_qty is None or remaining_qty == 0
                                    ate.target_hit = True
                                    
                                    if ate.sq_off_done:
                                        logger.info(f"Immediate square-off completed successfully")
                                    else:
                                        logger.warning(f"Immediate square-off attempted but positions remain, remaining qty: {remaining_qty}")
                                    
                                except Exception as e:
                                    logger.error(f"Error in immediate square off: {e}")
                                    logger.error(traceback.format_exc())
                            # Process auto trading logic when positions exist and not already squared off
                            else:
                                self._process_auto_trading(ate, pnl)
                    
                    # Update the current state
                    self.current_state = ate
                        
            except Exception as e:
                logger.error(f"Error in auto trailer cycle: {e}")
                logger.error(traceback.format_exc())
            
            # Sleep for the configured interval
            time.sleep(update_interval)
                
    def _process_auto_trading(self, ate, pnl):
        """
        Process the auto trading logic - only called when active
        
        Args:
            ate: AutoTrailerEvent to update with current state
            pnl: Current PNL value
        """
        atd = self.auto_trailer_data
        
        # Check if any positions are open by looking at the portfolio
        # We'll check if there are any available quantities (positive or negative)
        positions_open = False
        try:
            # Get the available quantities from the portfolio
            total_qty = self.pfmu.portfolio.available_qty(ul_index=None)
            positions_open = total_qty is not None and total_qty != 0
        except Exception as e:
            logger.error(f"Error checking positions: {e}")
        
        # If no positions are open, we should not trigger SL/Target
        if not positions_open:
            # Still update UI states but don't trigger square off
            if self.mov_to_cost_state == MOVE_TO_COST_STATE.WAITING_DOWN_CROSS:
                ate.mvto_cost_ui = UI_State.DISABLE

            if self.trail_sl_state == TRAIL_SL_STATE.TRAIL_STARTED:
                ate.trail_sl_ui = UI_State.DISABLE
            
            # No positions to monitor - deactivate auto trader
            logger.info("No positions to monitor - deactivating auto trader")
            self._active = False
            ate.sq_off_done = True  # Indicate no positions to square off
            
            # Early return - don't process SL/Target conditions
            return
        
        # Set default UI states
        if self.mov_to_cost_state == MOVE_TO_COST_STATE.WAITING_DOWN_CROSS:
            ate.mvto_cost_ui = UI_State.DISABLE

        if self.trail_sl_state == TRAIL_SL_STATE.TRAIL_STARTED:
            ate.trail_sl_ui = UI_State.DISABLE
        
        sq_off = False
        
        # Check if target hit
        if pnl >= atd.target:
            sq_off = True
            logger.info(f'Target Achieved: Squaring off')
            ate.target_hit = True

        # Check if stop loss hit
        if not sq_off and pnl <= atd.sl:
            logger.info(f'SL Hit: Squaring off')
            sq_off = True
            ate.sl_hit = True

        # Process move to cost logic if no square off yet
        if not sq_off:
            match self.mov_to_cost_state:
                case MOVE_TO_COST_STATE.WAITING_UP_CROSS:
                    if pnl >= atd.mvto_cost:
                        self.mov_to_cost_state = self.pfmu.mov_to_cost_state = MOVE_TO_COST_STATE.WAITING_DOWN_CROSS
                        ate.mvto_cost_ui = UI_State.DISABLE
                        logger.info(f'mvto_cost - Threshold hit {MOVE_TO_COST_STATE.WAITING_UP_CROSS.name} -> {MOVE_TO_COST_STATE.WAITING_DOWN_CROSS.name}')

                case MOVE_TO_COST_STATE.WAITING_DOWN_CROSS:
                    if pnl <= self.mv_to_cost_pnl:
                        self.mov_to_cost_state = self.pfmu.mov_to_cost_state = MOVE_TO_COST_STATE.WAITING_UP_CROSS
                        logger.info(f'mvto_cost - Threshold hit {MOVE_TO_COST_STATE.WAITING_DOWN_CROSS.name} -> {MOVE_TO_COST_STATE.WAITING_UP_CROSS.name}')
                        sq_off = True
                case _:
                    pass

        # Process trailing stop loss logic if no square off yet
        if not sq_off:
            match self.trail_sl_state:
                case TRAIL_SL_STATE.WAITING_UP_CROSS:
                    if pnl >= atd.trail_after:
                        self.max_pnl = self.pfmu.max_pnl = pnl
                        self.trail_sl_state = self.pfmu.trail_sl_state = TRAIL_SL_STATE.TRAIL_STARTED
                        ate.trail_sl_ui = UI_State.DISABLE
                        logger.info(f'trail_sl_state - {atd.trail_after:.2f} hit {TRAIL_SL_STATE.WAITING_UP_CROSS.name} -> {TRAIL_SL_STATE.TRAIL_STARTED.name}')

                case TRAIL_SL_STATE.TRAIL_STARTED:
                    if pnl > self.max_pnl:
                        self.max_pnl = self.pfmu.max_pnl = pnl
                    pnl_th = self.max_pnl - atd.trail_by
                    if pnl_th > 0 and pnl <= pnl_th:
                        self.trail_sl_state = self.pfmu.trail_sl_state = TRAIL_SL_STATE.TRAIL_SL_HIT
                        sq_off = True
                        logger.info(f'trail_sl_state - max_pnl: {self.max_pnl:.2f} trail_by: {atd.trail_by:.2f} {pnl_th:.2f} hit {TRAIL_SL_STATE.TRAIL_STARTED.name} -> {TRAIL_SL_STATE.TRAIL_SL_HIT.name}')
                case _:
                    pass

        # Execute square off if needed
        if sq_off:
            try:
                # Execute square off directly in this thread (no separate thread needed)
                self.pfmu.square_off_position(mode='ALL', ul_index=None, per=100, inst_type='ALL', partial_exit=False, exit_flag=False)
                self.pfmu.show()
                
                # Check if positions are actually closed
                remaining_qty = self.pfmu.portfolio.available_qty(ul_index=None)
                ate.sq_off_done = remaining_qty is None or remaining_qty == 0
                
                # Update mv_to_cost_pnl after square off
                self.mv_to_cost_pnl = self.pfmu.mv_to_cost_pnl = self.pfmu.intra_day_pnl()
                
                # Deactivate auto trailer if square-off succeeded
                if ate.sq_off_done:
                    logger.info(f"Square-off completed successfully, positions closed")
                    self._active = False
                else:
                    logger.warning(f"Square-off attempted but positions remain, remaining qty: {remaining_qty}")
                
            except Exception as e:
                logger.error(f"Error in square off: {e}")
                logger.error(traceback.format_exc())