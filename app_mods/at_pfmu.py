"""
File: at_pfmu.py
Author: [Tarakeshwar NC]
Date: January 15, 2024
Description: AutoTrailer Manager - Independent service for trailing stop-loss automation
"""
# Copyright (c) [2024] [Tarakeshwar N.C]
# This file is part of the Tez project.
# It is subject to the terms and conditions of the MIT License.
# See the file LICENSE in the top-level directory of this distribution
# for the full text of the license.

__author__ = "Tarakeshwar N.C"
__copyright__ = "2024"
__date__ = "2024/3/22"
__deprecated__ = False
__email__ = "tarakesh.nc_at_google_mail_dot_com"
__license__ = "MIT"
__maintainer__ = "Tarak"
__status__ = "Development"

import sys
import traceback
import time
from threading import Thread, Event
from typing import Optional, Dict, Any

from app_utils import app_logger
logger = app_logger.get_logger(__name__)

try:
    from .shared_classes import AutoTrailerData, AutoTrailerEvent
    from .auto_trailer import AutoTrailer
    from .pfmu import PFMU
    from .notification_factory import NotificationFactory
    from .notification_system import NotificationLogger
except Exception as e:
    logger.debug(traceback.format_exc())
    logger.error(("Import Error " + str(e)))
    sys.exit(1)


class AutoTrailerManager:
    """
    Independent AutoTrailer service manager
    Handles trailing stop-loss automation with push notifications
    
    Responsibilities:
    - AutoTrailer activation/deactivation coordination
    - P&L caching and change detection  
    - AutoTrailer event coordination with push notifications
    - Persistent thread management
    - Square-off execution coordination
    """
    
    def __init__(self, pfmu_service: PFMU, notification_port=None):
        """
        Initialize AutoTrailer Manager with service injection
        
        Args:
            pfmu_service: Injected PFMU service for portfolio operations
            notification_port: Port for push notifications (0ms latency)
        """
        logger.info("Creating AutoTrailer Manager with service injection...")
        
        # Service injection - no ownership
        self.pfmu = pfmu_service
        self.notification_port = notification_port
        self._notification_logger = NotificationLogger("AutoTrailerManager.notifications")
        
        # Initialize AutoTrailer as pure calculation library
        self._auto_trailer = AutoTrailer()
        
        # Persistent AutoTrailer thread - runs throughout manager lifecycle
        self._pnl_event = Event()
        self._exit_event = Event()
        self._autotrailer_thread = None
        self._autotrailer_running = True  # Set to True for persistent thread
        self._autotrailer_enabled = False  # Control flag for enable/disable
        self._autotrailer_reset_requested = False  # Control flag for state reset
        self._cached_pnl = None  # Cache P&L to detect changes
        
        # Start persistent AutoTrailer thread immediately
        self._start_persistent_autotrailer_thread()
        
        logger.info("AutoTrailer Manager initialization completed")
        
    def _start_persistent_autotrailer_thread(self):
        """Start persistent AutoTrailer thread - runs throughout manager lifecycle"""
        if self._autotrailer_thread is None or not self._autotrailer_thread.is_alive():
            self._exit_event.clear()
            self._autotrailer_thread = Thread(
                target=self._persistent_autotrailer_event_loop,
                name=f"AutoTrailerManager-Persistent-{id(self)}",
                daemon=True
            )
            self._autotrailer_thread.start()
            logger.info("Persistent AutoTrailer thread started")

    def _persistent_autotrailer_event_loop(self):
        """
        Persistent AutoTrailer event loop - runs throughout manager lifecycle
        Handles enable/disable/reset controls without thread creation/destruction
        """
        logger.info("Persistent AutoTrailer event loop started")
        
        while self._autotrailer_running and not self._exit_event.is_set():
            try:
                # Wait for P&L event or exit signal (with timeout for responsiveness)
                event_occurred = self._pnl_event.wait(timeout=1.0)
                
                if self._exit_event.is_set():
                    logger.debug("Exit event set, breaking from persistent AutoTrailer event loop")
                    break
                
                # Handle reset request if flagged
                if self._autotrailer_reset_requested:
                    self._handle_autotrailer_reset()
                    self._autotrailer_reset_requested = False
                    continue
                
                # Only process AutoTrailer logic when enabled AND active AND event occurred
                if (event_occurred and 
                    self._autotrailer_enabled and 
                    self._auto_trailer and 
                    self._auto_trailer.is_active()):
                    
                    # Process AutoTrailer logic using cached P&L
                    self._process_autotrailer_conditions()
                    # Clear event only after successful processing
                    self._pnl_event.clear()
                
                # Update AutoTrailer state with current cached P&L (even when inactive/disabled)
                if self._cached_pnl is not None:
                    self._auto_trailer._current_state.pnl = self._cached_pnl
               
            except Exception as e:
                logger.error(f"Error in persistent AutoTrailer event loop: {e}")
                logger.error(traceback.format_exc())
                time.sleep(0.1)  # Small delay to prevent busy loop on errors
        
        logger.info("Persistent AutoTrailer event loop ended")

    def _handle_autotrailer_reset(self):
        """Handle AutoTrailer state reset - clears cached P&L and events"""
        try:
            self._cached_pnl = None
            self._pnl_event.clear()
            logger.info("AutoTrailer state reset completed")
        except Exception as e:
            logger.error(f"Error in AutoTrailer reset: {e}")

    def _process_autotrailer_conditions(self):
        """
        Process AutoTrailer conditions when P&L changes
        Called by event handler when P&L event is posted
        """
        try:
            # Validate AutoTrailer state
            if not self._auto_trailer or not self._auto_trailer.is_active() or not self._auto_trailer._params:
                logger.debug("AutoTrailer not active or missing parameters, skipping condition processing")
                return
            
            # Validate cached P&L is available
            if self._cached_pnl is None:
                logger.warning("No cached P&L available for AutoTrailer processing")
                return
                
            # Get current data using cached P&L and portfolio method
            current_pnl = self._cached_pnl
            try:
                position_qty = self.pfmu.portfolio.available_qty(ul_index=None)
            except Exception as e:
                logger.error(f"Error getting position quantity: {e}")
                return
            
            # Check auto-trading conditions (AutoTrailer manages its own state internally)
            action = self._auto_trailer.check_conditions(
                current_pnl=current_pnl,
                position_qty=position_qty, 
                params=self._auto_trailer._params
            )
            
            # Handle results with push notifications
            if action and action.should_square_off:
                logger.info(f"Auto-trading square-off triggered: {action.reason} at P&L {action.pnl}")
                self._execute_auto_squareoff(action.reason, action.pnl)
                
        except Exception as e:
            logger.error(f"Error processing AutoTrailer conditions: {e}")
            logger.error(f"AutoTrailer active: {self._auto_trailer.is_active() if self._auto_trailer else 'None'}")
            logger.error(f"Cached P&L: {self._cached_pnl}")
            logger.error(traceback.format_exc())

    def _execute_auto_squareoff(self, reason: str, pnl: float):
        """Execute square-off triggered by auto-trading with push notification"""
        try:
            # Store context for logging and notifications
            sq_off_triggered_by = "autotrailer_manager"
            trigger_reason = reason
            additional_data = {"auto_pnl": pnl}
            
            # Call PFMU with valid parameters only
            success = self.pfmu.square_off_position(mode="ALL", trigger_source="AUTOTRAILER")
            
            if success:
                # PUSH NOTIFICATION - Immediate UI update (0ms latency)
                self._notify_state_change("square_off_executed", {
                    "reason": reason,
                    "pnl": pnl,
                    "timestamp": time.time()
                })
                logger.info(f"AutoTrailer square-off completed successfully: {trigger_reason} by {sq_off_triggered_by}, pnl={pnl}")
            else:
                # PUSH ERROR NOTIFICATION
                self._notify_state_change("square_off_failed", {
                    "reason": reason,
                    "pnl": pnl,
                    "timestamp": time.time()
                })
                logger.error(f"AutoTrailer square-off failed with error: {trigger_reason} by {sq_off_triggered_by}, pnl={pnl}")
            
            # Auto-deactivate AutoTrailer after square-off attempt (success or failure)
            deactivation_success = self.deactivate_auto_trading()
            if deactivation_success:
                logger.info("AutoTrailer automatically deactivated after square-off execution")
            else:
                logger.warning("Failed to automatically deactivate AutoTrailer after square-off")
                
        except Exception as e:
            logger.error(f"Error executing auto square-off: {e}")
            # PUSH ERROR NOTIFICATION
            self._notify_state_change("square_off_error", {
                "reason": reason,
                "pnl": pnl,
                "error": str(e),
                "timestamp": time.time()
            })
            
            # Still attempt to deactivate AutoTrailer even on exception
            try:
                deactivation_success = self.deactivate_auto_trading()
                if deactivation_success:
                    logger.info("AutoTrailer automatically deactivated after square-off error")
                else:
                    logger.warning("Failed to automatically deactivate AutoTrailer after square-off error")
            except Exception as deactivation_error:
                logger.error(f"Error deactivating AutoTrailer after square-off error: {deactivation_error}")

    def _notify_state_change(self, event_type: str, data: Dict[str, Any]):
        """Push AutoTrailer state changes directly to UI using structured notifications"""
        if not self.notification_port:
            return
            
        try:
            # Map event types to structured notifications
            if event_type == "autotrailer_activated":
                notification = NotificationFactory.autotrailer_activated(
                    symbol=data.get('params', {}).get('symbol', 'Unknown'),
                    sl_price=data.get('params', {}).get('sl', 0.0),
                    target_price=data.get('params', {}).get('target', 0.0)
                )
                
            elif event_type == "autotrailer_deactivated":
                notification = NotificationFactory.autotrailer_deactivated(
                    symbol=data.get('symbol', 'Unknown'),
                    reason=data.get('reason', 'Manual deactivation')
                )
                
            elif event_type == "autotrailer_shutdown":
                notification = NotificationFactory.autotrailer_deactivated(
                    symbol=data.get('symbol', 'Unknown'),
                    reason="System shutdown"
                )
                
            else:
                # Generic AutoTrailer status update for other events
                from .notification_types import NotificationID, NotificationCategory, NotificationPriority
                from .notification_system import Notification
                
                notification = Notification(
                    id=NotificationID.AUTOTRAILER_STATUS_UPDATE,
                    category=NotificationCategory.AUTOTRAILER,
                    priority=NotificationPriority.NORMAL,
                    message=f"AutoTrailer status update: {event_type}",
                    data={
                        'event_type': event_type,
                        'status_data': data
                    },
                    source="AutoTrailer"
                )
            
            # Add original data for compatibility
            notification.data.update({
                'original_event_type': event_type,
                'original_data': data
            })
            
            # Log the structured notification
            self._notification_logger.log_notification(notification, "sending")
            
            # Send structured notification
            self.notification_port.send_data(notification.to_dict())
            logger.debug(f"AutoTrailer state pushed: {event_type} -> {notification.id.name}")
            
        except Exception as e:
            logger.error(f"Error sending AutoTrailer notification: {e}")
            # Log the error through notification logger
            self._notification_logger.log_notification_error(e, f"notify_state_change_{event_type}")

    # =============================================================================
    # PUBLIC API - Interface for app_be
    # =============================================================================

    def update_pnl_and_process(self) -> float:
        """
        Primary P&L coordination method - called by app_be every 1 second
        Handles P&L caching and AutoTrailer event posting
        
        Returns:
            float: Current P&L for app_be to publish to UI
        """
        try:
            # Get fresh P&L calculation from PFMU service
            current_pnl = self.pfmu.intra_day_pnl()
            
            # Check if P&L actually changed
            previous_pnl = self._cached_pnl
            if previous_pnl is None or previous_pnl != current_pnl:
                self._cached_pnl = current_pnl  # Update cache
                
                # Only post event if auto-trader is enabled AND active AND P&L changed
                if (self._autotrailer_enabled and 
                    self._auto_trailer and 
                    self._auto_trailer.is_active()):
                    # Use set() - it's safe to call multiple times before clear()
                    self._pnl_event.set()
                    logger.debug(f"P&L event posted by AutoTrailer Manager: {current_pnl} (changed from {previous_pnl})")
            
            return current_pnl
            
        except Exception as e:
            logger.error(f"Error in P&L coordination: {e}")
            logger.error(traceback.format_exc())
            return self._cached_pnl or 0.0

    def activate_auto_trading(self, params: AutoTrailerData) -> bool:
        """
        Activate auto-trading with parameters
        Public interface for app_be to activate AutoTrailer
        
        Args:
            params: AutoTrailerData with sl, target, trailing parameters
            
        Returns:
            bool: True if activation successful
        """
        try:
            # Use cached P&L or get fresh calculation
            current_pnl = self._cached_pnl
            if current_pnl is None:
                current_pnl = self.pfmu.intra_day_pnl()
                self._cached_pnl = current_pnl
            
            # Activate AutoTrailer with current P&L
            success = self._auto_trailer.activate(params, current_pnl)
            
            if success:
                # Reset state and enable persistent AutoTrailer
                self._autotrailer_reset_requested = True
                self._autotrailer_enabled = True
                logger.info("Auto-trading activated with push notifications")
                
                # PUSH NOTIFICATION (NEW) - Immediate UI update
                self._notify_state_change("autotrailer_activated", {
                    "params": {
                        "sl": params.sl,
                        "target": params.target,
                        "trail_after": params.trail_after,
                        "trail_by": params.trail_by
                    },
                    "current_pnl": current_pnl
                })
            
            return success
            
        except Exception as e:
            logger.error(f"Error activating auto trading: {e}")
            return False
    
    def deactivate_auto_trading(self) -> bool:
        """
        Deactivate auto-trading
        Public interface for app_be to deactivate AutoTrailer
        
        Returns:
            bool: True if deactivation successful
        """
        try:
            # Disable persistent AutoTrailer without stopping thread
            self._autotrailer_enabled = False
            
            # Deactivate AutoTrailer
            success = self._auto_trailer.deactivate()
            
            if success:
                logger.info("Auto-trading deactivated with persistent thread continuing")
                
                # PUSH NOTIFICATION (NEW) - Immediate UI update
                self._notify_state_change("autotrailer_deactivated", {
                    "final_pnl": self._cached_pnl
                })
            
            return success
            
        except Exception as e:
            logger.error(f"Error deactivating auto trading: {e}")
            return False

    def get_autotrailer_ui_state(self) -> AutoTrailerEvent:
        """
        Get current AutoTrailer state for UI display
        Public interface for UI to get AutoTrailer state
        
        Note: With push notifications, this is rarely needed for state updates
        
        Returns:
            AutoTrailerEvent: Current state for UI display
        """
        try:
            current_pnl = self._cached_pnl or 0.0
            return self._auto_trailer.get_current_state(current_pnl)
        except Exception as e:
            logger.error(f"Error getting AutoTrailer UI state: {e}")
            # Return default state on error
            return AutoTrailerEvent(pnl=0.0, sl_hit=False, target_hit=False, mvto_cost_hit=False)

    def is_auto_trading_active(self) -> bool:
        """
        Check if auto-trading is currently active
        Public interface for app_be to check AutoTrailer status
        
        Returns:
            bool: True if auto-trading is active
        """
        try:
            return self._auto_trailer.is_active()
        except Exception as e:
            logger.error(f"Error checking AutoTrailer status: {e}")
            return False

    def reset_autotrailer_state(self) -> bool:
        """
        Reset AutoTrailer cached state
        Public interface for cleaning P&L cache and event state
        
        Returns:
            bool: True if reset successful
        """
        try:
            self._autotrailer_reset_requested = True
            logger.info("AutoTrailer state reset requested")
            return True
        except Exception as e:
            logger.error(f"Error requesting AutoTrailer reset: {e}")
            return False

    def shutdown(self) -> None:
        """Shutdown AutoTrailer manager - stop persistent thread"""
        try:
            logger.info("Shutting down AutoTrailer Manager...")
            
            # Signal thread to exit
            self._autotrailer_running = False
            self._exit_event.set()
            
            # Wait for thread to finish
            if self._autotrailer_thread and self._autotrailer_thread.is_alive():
                self._autotrailer_thread.join(timeout=2.0)
                if self._autotrailer_thread.is_alive():
                    logger.warning("AutoTrailer thread did not shut down gracefully")
                else:
                    logger.info("AutoTrailer thread shut down successfully")
            
            # Final state notification
            if self.notification_port:
                self._notify_state_change("autotrailer_shutdown", {
                    "final_pnl": self._cached_pnl,
                    "timestamp": time.time()
                })
            
            logger.info("AutoTrailer Manager shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during AutoTrailer Manager shutdown: {e}")
            logger.error(traceback.format_exc())