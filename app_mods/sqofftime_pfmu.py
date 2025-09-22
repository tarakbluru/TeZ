"""
File: sqofftime_pfmu.py
Author: [Tarakeshwar NC]
Date: January 15, 2024
Description: SquareOff Timer Manager - Independent service for timer-based square-off automation
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
from datetime import datetime, time as dt_time
from typing import Dict, Any, Optional

from app_utils import app_logger
logger = app_logger.get_logger(__name__)

try:
    from .pfmu import PFMU
except Exception as e:
    logger.debug(traceback.format_exc())
    logger.error(("Import Error " + str(e)))
    sys.exit(1)


class SquareOffTimeManager:
    """
    Independent service for timer-based square-off automation
    Handles time-based square-off operations with enhanced validation and push notifications
    
    Responsibilities:
    - Timer-based square-off automation
    - Market close square-off coordination
    - Time validation and scheduling  
    - Push notifications for timer events
    - Enhanced error handling for timing operations
    """
    
    def __init__(self, pfmu_service: PFMU, notification_port=None):
        """
        Initialize SquareOff Timer Manager with service injection
        
        Args:
            pfmu_service: Injected PFMU service for portfolio operations
            notification_port: Port for push notifications (0ms latency)
        """
        logger.info("Creating SquareOff Timer Manager with service injection...")
        
        # Service injection - no ownership
        self.pfmu = pfmu_service
        self.notification_port = notification_port
        
        # Timer configuration (from system config)
        self.market_close_time = self._load_market_timing()
        self.squareoff_time = self._load_squareoff_timing()
        self.squareoff_window = self._load_timing_windows()
        
        # Timer state
        self._timer_active = False
        self._last_execution_time = None
        
        logger.info("Timer Square-off Manager initialized")

    def _load_market_timing(self) -> str:
        """Load market timing configuration"""
        try:
            # Default market close time - should be loaded from config
            return "15:30"  # Market close time for Indian equity markets
        except Exception as e:
            logger.error(f"Error loading market timing: {e}")
            return "15:30"  # Fallback

    def _load_squareoff_timing(self) -> str:
        """Load square-off timing configuration"""
        try:
            # Default square-off time - should be loaded from config
            return "15:20"  # 10 minutes before market close
        except Exception as e:
            logger.error(f"Error loading squareoff timing: {e}")
            return "15:20"  # Fallback

    def _load_timing_windows(self) -> Dict[str, str]:
        """Load timing windows configuration"""
        try:
            # Default timing window - should be loaded from config
            return {
                "start": "15:00",  # Start of square-off window
                "end": "15:30"     # End of square-off window (market close)
            }
        except Exception as e:
            logger.error(f"Error loading timing windows: {e}")
            return {"start": "15:00", "end": "15:30"}  # Fallback

    # =============================================================================
    # CORE TIMER OPERATIONS
    # =============================================================================

    def execute_timer_squareoff(self, current_time: str) -> bool:
        """
        Execute timer-based square-off - MOVED FROM PFMU with enhancements
        Enhanced with better time validation and push notifications
        
        Args:
            current_time: Current time in HH:MM format
            
        Returns:
            bool: True if square-off executed successfully
        """
        try:
            # Validate timing window
            if not self.is_within_squareoff_window(current_time):
                logger.warning(f"Timer square-off requested outside window: {current_time}")
                self._notify_timer_event("timer_squareoff_rejected", {
                    "time": current_time,
                    "reason": "Outside timing window",
                    "window": self.squareoff_window
                })
                return False
                
            # Check for duplicate execution
            if self._last_execution_time == current_time:
                logger.debug(f"Timer square-off already executed for {current_time}")
                return True
            
            logger.info(f"Executing timer square-off at {current_time}")
            
            # Store context for logging and notifications
            sq_off_triggered_by = "timer_manager"
            trigger_reason = f"Market close timer at {current_time}"
            additional_data = {
                "timer_time": current_time,
                "squareoff_window": self.squareoff_window,
                "market_close_time": self.market_close_time
            }
            
            # Execute square-off via PFMU service with valid parameters only
            success = self.pfmu.square_off_position(
                mode='ALL',
                ul_index=None,
                per=100,
                inst_type='ALL',
                partial_exit=False,
                exit_flag=True,
                trigger_source="TIMER"
            )
            
            if success:
                # Record successful execution
                self._last_execution_time = current_time
                
                # Check position closure
                remaining_qty = self.pfmu.portfolio.available_qty(ul_index=None)
                actual_success = remaining_qty is None or remaining_qty == 0
                
                if actual_success:
                    final_pnl = self.pfmu.intra_day_pnl()
                    
                    # PUSH NOTIFICATION - Immediate UI update (0ms latency)
                    self._notify_timer_event("timer_squareoff_completed", {
                        "time": current_time,
                        "final_pnl": final_pnl,
                        "positions_closed": True,
                        "success": True
                    })
                    
                    logger.info(f"Timer square-off completed successfully: {trigger_reason} by {sq_off_triggered_by}")
                    return True
                else:
                    logger.warning(f"Timer square-off incomplete: {trigger_reason} by {sq_off_triggered_by}, remaining qty: {remaining_qty}")
                    self._notify_timer_event("timer_squareoff_partial", {
                        "time": current_time,
                        "remaining_qty": remaining_qty,
                        "success": False
                    })
                    return False
            else:
                logger.error(f"Timer square-off execution failed: {trigger_reason} by {sq_off_triggered_by}")
                self._notify_timer_event("timer_squareoff_failed", {
                    "time": current_time,
                    "error": "Square-off execution failed",
                    "success": False
                })
                return False
                
        except Exception as e:
            logger.error(f"Timer square-off error: {e}")
            logger.error(traceback.format_exc())
            self._notify_timer_event("timer_squareoff_error", {
                "time": current_time,
                "error": str(e),
                "success": False
            })
            return False

    def schedule_squareoff(self, time_str: str) -> bool:
        """Schedule square-off for specific time"""
        try:
            if self.validate_squareoff_time(time_str):
                self.squareoff_time = time_str
                self._notify_timer_event("squareoff_scheduled", {
                    "scheduled_time": time_str,
                    "current_time": datetime.now().strftime("%H:%M")
                })
                logger.info(f"Square-off scheduled for {time_str}")
                return True
            else:
                logger.error(f"Invalid schedule time: {time_str}")
                return False
        except Exception as e:
            logger.error(f"Error scheduling square-off: {e}")
            return False

    def is_timer_active(self) -> bool:
        """Check if timer operations are active"""
        return self._timer_active

    # =============================================================================
    # TIME VALIDATION AND COORDINATION
    # =============================================================================

    def validate_squareoff_time(self, time_str: str) -> bool:
        """Validate square-off time format and range"""
        try:
            # Parse time format
            datetime.strptime(time_str, "%H:%M")
            
            # Check if within market hours
            return self.is_within_squareoff_window(time_str)
            
        except ValueError:
            logger.error(f"Invalid time format: {time_str}")
            return False
        except Exception as e:
            logger.error(f"Time validation error: {e}")
            return False

    def is_within_squareoff_window(self, current_time: str) -> bool:
        """
        Check if current time is within allowed square-off window
        Enhanced time validation logic
        """
        try:
            # Parse current time
            current_dt = datetime.strptime(current_time, "%H:%M").time()
            
            # Parse squareoff window
            start_time = datetime.strptime(self.squareoff_window['start'], "%H:%M").time()
            end_time = datetime.strptime(self.squareoff_window['end'], "%H:%M").time()
            
            # Check if within window
            within_window = start_time <= current_dt <= end_time
            
            logger.debug(f"Time validation: {current_time} within [{self.squareoff_window['start']}-{self.squareoff_window['end']}]: {within_window}")
            
            return within_window
            
        except Exception as e:
            logger.error(f"Time validation error: {e}")
            return False

    def get_time_until_squareoff(self, current_time: str) -> Dict[str, Any]:
        """Get time remaining until scheduled square-off"""
        try:
            current_dt = datetime.strptime(current_time, "%H:%M")
            squareoff_dt = datetime.strptime(self.squareoff_time, "%H:%M")
            
            if squareoff_dt > current_dt:
                time_diff = squareoff_dt - current_dt
                minutes_remaining = int(time_diff.total_seconds() / 60)
                
                return {
                    "minutes_remaining": minutes_remaining,
                    "scheduled_time": self.squareoff_time,
                    "current_time": current_time,
                    "is_pending": True
                }
            else:
                return {
                    "minutes_remaining": 0,
                    "scheduled_time": self.squareoff_time,
                    "current_time": current_time,
                    "is_pending": False
                }
                
        except Exception as e:
            logger.error(f"Error calculating time until square-off: {e}")
            return {
                "minutes_remaining": -1,
                "error": str(e),
                "is_pending": False
            }

    def get_market_close_time(self) -> str:
        """Get configured market close time"""
        return self.market_close_time

    # =============================================================================
    # PUSH NOTIFICATIONS
    # =============================================================================

    def _notify_timer_event(self, event_type: str, data: Dict[str, Any]):
        """Push timer events directly to UI (0ms latency)"""
        if not self.notification_port:
            return
            
        try:
            notification = {
                "type": "timer_squareoff_event",
                "event": event_type,
                "data": data,
                "timestamp": time.time()
            }
            
            self.notification_port.send_data(notification)
            logger.debug(f"Timer event pushed: {event_type}")
            
        except Exception as e:
            logger.error(f"Error sending timer notification: {e}")

    # =============================================================================
    # SYSTEM OPERATIONS
    # =============================================================================

    def start_timer_monitoring(self) -> None:
        """Start timer monitoring operations"""
        try:
            self._timer_active = True
            self._notify_timer_event("timer_monitoring_started", {
                "market_close_time": self.market_close_time,
                "squareoff_time": self.squareoff_time,
                "timing_window": self.squareoff_window
            })
            logger.info("Timer monitoring started")
        except Exception as e:
            logger.error(f"Error starting timer monitoring: {e}")
            raise

    def shutdown(self) -> None:
        """Shutdown timer manager"""
        try:
            logger.info("Shutting down Timer Square-off Manager...")
            
            self._timer_active = False
            
            # Final state notification
            if self.notification_port:
                self._notify_timer_event("timer_manager_shutdown", {
                    "last_execution_time": self._last_execution_time,
                    "final_squareoff_time": self.squareoff_time,
                    "timestamp": time.time()
                })
            
            logger.info("Timer Square-off Manager shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during Timer Manager shutdown: {e}")
            logger.error(traceback.format_exc())

    # =============================================================================
    # UTILITY AND STATUS METHODS
    # =============================================================================

    def get_timer_status(self) -> Dict[str, Any]:
        """Get comprehensive timer status"""
        try:
            current_time = datetime.now().strftime("%H:%M")
            
            return {
                "timer_active": self._timer_active,
                "market_close_time": self.market_close_time,
                "squareoff_time": self.squareoff_time,
                "timing_window": self.squareoff_window,
                "last_execution_time": self._last_execution_time,
                "current_time": current_time,
                "within_window": self.is_within_squareoff_window(current_time),
                "time_until_squareoff": self.get_time_until_squareoff(current_time),
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error(f"Error getting timer status: {e}")
            return {
                "timer_active": False,
                "error": str(e),
                "timestamp": time.time()
            }

    def update_timing_configuration(self, config: Dict[str, Any]) -> bool:
        """Update timing configuration dynamically"""
        try:
            if 'market_close_time' in config:
                if self.validate_squareoff_time(config['market_close_time']):
                    self.market_close_time = config['market_close_time']
                    
            if 'squareoff_time' in config:
                if self.validate_squareoff_time(config['squareoff_time']):
                    self.squareoff_time = config['squareoff_time']
                    
            if 'timing_window' in config:
                if isinstance(config['timing_window'], dict):
                    self.squareoff_window.update(config['timing_window'])
            
            # Notify configuration update
            self._notify_timer_event("timer_config_updated", {
                "new_config": {
                    "market_close_time": self.market_close_time,
                    "squareoff_time": self.squareoff_time,
                    "timing_window": self.squareoff_window
                }
            })
            
            logger.info("Timer configuration updated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error updating timer configuration: {e}")
            return False

    def get_position_status_for_timer(self) -> Dict[str, Any]:
        """Get position status specifically for timer operations"""
        try:
            if not self.pfmu or not self.pfmu.portfolio:
                return {'available': False, 'error': 'Portfolio not available'}
                
            current_qty = self.pfmu.portfolio.available_qty(ul_index=None)
            current_pnl = self.pfmu.intra_day_pnl()
            
            return {
                'positions_available': current_qty is not None and current_qty > 0,
                'current_qty': current_qty,
                'current_pnl': current_pnl,
                'requires_squareoff': current_qty is not None and current_qty > 0,
                'timestamp': time.time()
            }
        except Exception as e:
            logger.error(f"Error getting position status for timer: {e}")
            return {
                'available': False,
                'error': str(e),
                'timestamp': time.time()
            }