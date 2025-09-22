"""
File: ui_port_integration.py
Author: [Tarakeshwar NC] / Claude Code
Date: September 11, 2025
Description: UI port integration layer for non-blocking communication with trading backend
"""
# Copyright (c) [2025] [Tarakeshwar N.C]
# This file is part of the Tez project.
# It is subject to the terms and conditions of the MIT License.
# See the file LICENSE in the top-level directory of this distribution
# for the full text of the license.

__author__ = "Tarakeshwar N.C"
__copyright__ = "2025"
__date__ = "2025/9/11"
__deprecated__ = False
__email__ = "tarakesh.nc_at_google_mail_dot_com"
__license__ = "MIT"
__maintainer__ = "Tarak"
__status__ = "Development"


import time
import random
import threading
from typing import Dict, Any, Optional, List, Set

from app_utils import app_logger
from .shared_classes import AutoTrailerData
from .shared_types import DataPacketType
from .notification_system import Notification, NotificationLogger
from .notification_types import NotificationID, NotificationCategory, NotificationPriority

logger = app_logger.get_logger(__name__)

class SimpleUIPortManager:
    """
    Simplified UI port manager - direct port access without callbacks
    Provides clean interface for UI widgets using basic port operations
    """
    
    _instance_counter = 0  # Class variable to track instances
    
    def __init__(self, ports: Dict[str, Any], frontend=None):
        """
        Initialize with port references

        Args:
            ports: Dictionary with 'command', 'response', 'data' port references
            frontend: Optional reference to frontend (AppFE) for UI updates
        """
        # Assign unique instance ID
        SimpleUIPortManager._instance_counter += 1
        self.instance_id = SimpleUIPortManager._instance_counter
        
        self.command_port = ports["command"]
        self.response_port = ports["response"]
        self._notification_logger = NotificationLogger(f"SimpleUIPortManager.{self.instance_id}")
        self.data_port = ports["data"]
        self.frontend = frontend  # Reference to AppFE for UI updates
        
        # Request ID tracking for command correlation with thread safety
        self._pending_requests: Dict[int, Dict[str, Any]] = {}
        self._pending_requests_lock = threading.Lock()
        
        # Track processed response IDs to prevent duplicate processing
        self._processed_responses: Set[int] = set()
        self._processed_responses_lock = threading.Lock()
        
        # Simple state tracking
        self._auto_mode_active = False
        self._last_pnl = 0.0
        self._last_ltp = 0.0
        
        # Counters for meaningful changes (not just packet receipts)
        self._pnl_change_count = 0
        self._tick_change_count = 0
        
        # Additional state variables for packet handling
        self._sl_hit = False
        self._target_hit = False
        self._sq_off_done = False
        self._move_to_cost_active = False
        self._trail_sl_active = False
        
        # System status tracking
        self._system_status = "unknown"
        self._system_health = "unknown"
        self._data_feed_connected = False
        
        # Auto-trailer status tracking
        self._auto_trailer_state = "INACTIVE"
        self._sl_level = None
        self._target_level = None
        self._trail_sl_level = None
        
        logger.info(f"Simple UI Port Manager initialized (Instance: {self.instance_id})")
    
    def send_command(self, command: str, params: dict = None) -> int:
        """
        Send command to backend with auto-generated request ID
        
        Args:
            command: Command name (e.g., "ACTIVATE_AUTO")
            params: Optional command parameters
            
        Returns:
            int: Generated request ID for this command
        """
        # Generate 6-digit request ID
        request_id = random.randint(100000, 999999)
        
        # Ensure uniqueness (retry if collision) with thread safety
        with self._pending_requests_lock:
            while request_id in self._pending_requests:
                request_id = random.randint(100000, 999999)
            
            # Track the request
            self._pending_requests[request_id] = {
                "command": command,
                "sent_at": time.time(),
                "params": params
            }
            logger.debug(f"[Instance {self.instance_id}] Added request ID {request_id} to pending_requests. Total pending: {len(self._pending_requests)}")
        
        # Send command with request ID
        self.command_port.send_command(command, params, request_id)
        
        logger.info(f"[Instance {self.instance_id}] Sent {command} (ID: {request_id})")
        return request_id
    
    def fetch_responses(self) -> List[dict]:
        """
        Fetch all available responses (non-blocking)
        
        Returns:
            List of response dictionaries
        """
        responses = []
        
        while True:
            response = self.response_port.fetch_data()
            if response is None:
                break
            responses.append(response)
            
        return responses
    
    def fetch_all_data(self) -> List[dict]:
        """
        Fetch all available data packets from queue
        
        Returns:
            List of all data packets
        """
        all_data = []
        
        # Drain data queue, collect all packets
        while True:
            data = self.data_port.fetch_data()
            if data is None:
                break
            all_data.append(data)
            
        return all_data
    
    def fetch_latest_data(self) -> Optional[dict]:
        """
        Fetch only the latest data, discard older updates
        
        Returns:
            Latest data dictionary or None
        """
        latest_data = None
        
        # Drain data queue, keep only latest
        while True:
            data = self.data_port.fetch_data()
            if data is None:
                break
            latest_data = data
            
        return latest_data

    def send_activate_auto(self, auto_params: Dict[str, float]) -> None:
        """
        Send command to activate auto-trading (non-blocking)
        
        Args:
            auto_params: Dictionary with sl, target, mvto_cost, trail_after, trail_by
        """
        self.send_command("ACTIVATE_AUTO", auto_params)
        logger.info("Auto activation command sent")

    def send_deactivate_auto(self) -> None:
        """Send command to deactivate auto-trading (non-blocking)"""
        self.send_command("DEACTIVATE_AUTO")
        logger.info("Auto deactivation command sent")

    def send_set_mode(self, mode: str, auto_params: Dict = None) -> None:
        """
        Send command to set trading mode (non-blocking)
        
        Args:
            mode: "AUTO" or "MANUAL"
            auto_params: Parameters if switching to AUTO mode
        """
        params = {"mode": mode}
        if mode == "AUTO" and auto_params:
            params.update(auto_params)
            
        self.send_command("SET_MODE", params)
        logger.info(f"Mode change command sent: {mode}")

    def send_emergency_stop(self) -> None:
        """Send emergency stop command (non-blocking)"""
        self.send_command("EMERGENCY_STOP")
        logger.warning("Emergency stop command sent")

    def send_set_ul_index(self, ul_index: str) -> int:
        """
        Send command to set underlying index (non-blocking)
        
        Args:
            ul_index: Underlying index to set (e.g., "NIFTY", "BANKNIFTY")
            
        Returns:
            int: Request ID for this command
        """
        params = {"ul_index": ul_index}
        request_id = self.send_command("SET_UL_INDEX", params)
        logger.info(f"Set ul_index command sent: {ul_index}")
        return request_id

    def send_market_action(self, action: str, trade_price: float = None, ui_qty: int = 1) -> int:
        """
        Send market action command (Buy/Short) (non-blocking)
        
        Args:
            action: "Buy" or "Short"
            trade_price: Optional trade price
            ui_qty: Quantity to trade
            
        Returns:
            int: Request ID for this command
        """
        params = {
            "action": action,
            "trade_price": trade_price,
            "ui_qty": ui_qty
        }
        request_id = self.send_command("MARKET_ACTION", params)
        logger.info(f"Market action command sent: {action} qty={ui_qty} price={trade_price}")
        return request_id

    def send_square_off(self, mode: str = "ALL", per: float = 100.0, ul_index: str = None, 
                       exch: str = None, inst_type: str = "ALL", partial_exit: bool = False) -> int:
        """
        Send square-off command (non-blocking)
        
        Args:
            mode: Square-off mode ("ALL" or "SELECT")
            per: Percentage to square-off (0-100)
            ul_index: Underlying index
            exch: Exchange
            inst_type: Instrument type
            partial_exit: Whether this is partial exit
            
        Returns:
            int: Request ID for this command
        """
        params = {
            "mode": mode,
            "per": per,
            "ul_index": ul_index,
            "exch": exch,
            "inst_type": inst_type,
            "partial_exit": partial_exit
        }
        request_id = self.send_command("SQUARE_OFF", params)
        logger.info(f"Square-off command sent: {mode} {per}%")
        return request_id

    def send_enhanced_square_off(self) -> int:
        """Send enhanced square-off command (non-blocking)
        
        Returns:
            int: Request ID for this command
        """
        request_id = self.send_command("ENHANCED_SQUARE_OFF")
        logger.info("Enhanced square-off command sent")
        return request_id

    def send_simple_square_off(self) -> int:
        """Send simple square-off command (non-blocking)
        
        Returns:
            int: Request ID for this command
        """
        request_id = self.send_command("SIMPLE_SQUARE_OFF")
        logger.info("Simple square-off command sent")
        return request_id

    def send_cancel_waiting_order(self, data) -> int:
        """
        Send cancel waiting order command (non-blocking)
        
        Args:
            data: Order data to cancel
            
        Returns:
            int: Request ID for this command
        """
        params = {"data": data}
        request_id = self.send_command("CANCEL_WAITING_ORDER", params)
        logger.info(f"Cancel waiting order command sent: {data}")
        return request_id

    def send_show_records(self) -> int:
        """Send show records command (non-blocking)
        
        Returns:
            int: Request ID for this command
        """
        request_id = self.send_command("SHOW_RECORDS")
        logger.info("Show records command sent")
        return request_id

    def send_get_latest_tick(self) -> None:
        """Send get latest tick command (non-blocking)"""
        self.send_command("GET_LATEST_TICK")
        logger.debug("Get latest tick command sent")

    def send_data_feed_connect(self) -> None:
        """Send data feed connect command (non-blocking)"""
        self.send_command("DATA_FEED_CONNECT")
        logger.info("Data feed connect command sent")

    def send_data_feed_disconnect(self) -> None:
        """Send data feed disconnect command (non-blocking)"""
        self.send_command("DATA_FEED_DISCONNECT")
        logger.info("Data feed disconnect command sent")
    
    def process_responses(self) -> Dict[str, Any]:
        """
        Process all available responses from backend with request ID correlation
        Should be called periodically by UI update loop
        
        Returns:
            dict: Summary of responses processed
        """
        all_messages = self.fetch_responses()

        # Separate notifications from actual responses
        notifications = []
        responses = []

        for message in all_messages:
            if "notification_id" in message:
                notifications.append(message)
            else:
                responses.append(message)

        # Log proactive notifications appropriately
        if len(notifications) > 0:
            logger.info(f"[Instance {self.instance_id}] Received {len(notifications)} proactive notifications from backend")

        # Enhanced diagnostics logging for actual responses only
        pending_count = self._get_pending_requests_count()
        if len(responses) > 0:
            logger.debug(f"[Instance {self.instance_id}] Processing {len(responses)} responses with {pending_count} pending requests")
            if pending_count > 0:
                with self._pending_requests_lock:
                    pending_ids = list(self._pending_requests.keys())
                    logger.debug(f"[Instance {self.instance_id}] Current pending request IDs: {pending_ids[:5]}{'...' if len(pending_ids) > 5 else ''}")
            elif len(responses) > 0:
                logger.warning(f"[Instance {self.instance_id}] Received {len(responses)} responses but have 0 pending requests - this may indicate a correlation issue")
        
        response_summary = {
            "count": len(responses) + len(notifications),
            "responses_count": len(responses),
            "notifications_count": len(notifications),
            "commands_processed": [],
            "errors": [],
            "mode_changes": [],
            "unmatched_responses": []
        }

        # Process proactive notifications first
        for notification in notifications:
            try:
                if "notification_id" in notification:
                    # Handle structured notifications (new system)
                    self._handle_structured_notification(notification)
                    notification_name = notification.get('notification_name', f"ID_{notification.get('notification_id')}")
                    response_summary["commands_processed"].append({
                        "command": f"NOTIFICATION_{notification_name}",
                        "request_id": None,
                        "success": True,
                        "message": f"Proactive notification processed: {notification_name}"
                    })
            except Exception as e:
                logger.error(f"Error processing notification: {e}")
                response_summary["errors"].append({
                    "command": "notification_processing",
                    "error": str(e)
                })

        # Process actual responses to requests
        for response in responses:
            try:
                # Extract request ID from response with type safety
                raw_request_id = response.get("request_id")
                command = response.get("command", "unknown")
                
                # Convert request_id to integer if it's a string (handle serialization issues)
                request_id = None
                if raw_request_id is not None:
                    try:
                        request_id = int(raw_request_id) if isinstance(raw_request_id, str) else raw_request_id
                    except (ValueError, TypeError) as e:
                        logger.error(f"Invalid request_id format: {raw_request_id} (type: {type(raw_request_id)}) - {e}")
                        continue
                
                logger.debug(f"Processing response: command={command}, request_id={request_id} (raw: {raw_request_id}), success={response.get('success', 'unknown')}")
                
                # Check for duplicate response processing AFTER checking pending requests
                if request_id:
                    with self._processed_responses_lock:
                        if request_id in self._processed_responses:
                            logger.warning(f"[Instance {self.instance_id}][UI] Duplicate response detected for request ID: {request_id}, command: {command} - skipping")
                            continue
                
                # Check if we have a matching pending request (with thread safety)
                pending_request = None
                with self._pending_requests_lock:
                    if request_id and request_id in self._pending_requests:
                        pending_request = self._pending_requests[request_id]
                        # Only mark as processed if we have a valid pending request
                        with self._processed_responses_lock:
                            self._processed_responses.add(request_id)
                
                if pending_request:
                    # Correlate with sent command
                    sent_request = pending_request
                    response_time = time.time() - sent_request["sent_at"]
                    
                    command_name = response.get("command", sent_request["command"])
                    success = response.get("success", False)
                    
                    # Log successful correlation
                    logger.info(f"[Instance {self.instance_id}][UI] Response for {command_name} (ID: {request_id}) - {'Success' if success else 'Failed'} in {response_time:.3f}s")
                    
                    response_summary["commands_processed"].append({
                        "command": command_name,
                        "request_id": request_id,
                        "success": success,
                        "message": response.get("message", ""),
                        "response_time": response_time
                    })
                    
                    # Track mode changes from command results
                    if command_name in ["ACTIVATE_AUTO", "DEACTIVATE_AUTO", "SET_MODE"]:
                        self._auto_mode_active = response.get("auto_active", self._auto_mode_active)
                        response_summary["mode_changes"].append({
                            "command": command_name,
                            "request_id": request_id,
                            "auto_active": self._auto_mode_active
                        })
                    
                    # Remove from pending requests with thread safety
                    with self._pending_requests_lock:
                        if request_id in self._pending_requests:  # Double-check still exists
                            del self._pending_requests[request_id]
                            logger.debug(f"Successfully correlated and removed request ID: {request_id} from pending ({len(self._pending_requests)} total pending)")
                        else:
                            logger.warning(f"Request ID {request_id} was removed from pending requests between checks")
                    
                elif request_id:
                    # Response with ID but no matching request - provide detailed debugging
                    with self._pending_requests_lock:
                        pending_count = len(self._pending_requests)
                        pending_ids = list(self._pending_requests.keys())
                    
                    logger.warning(f"[Instance {self.instance_id}][UI] Received response for unknown request ID: {request_id} (type: {type(request_id)}) command: {response.get('command', 'unknown')} success: {response.get('success', 'unknown')}")
                    logger.warning(f"[Instance {self.instance_id}][UI] Current pending requests ({pending_count}): {pending_ids[:10]}{'...' if len(pending_ids) > 10 else ''}")
                    
                    # Check if this was a duplicate
                    with self._processed_responses_lock:
                        was_duplicate = request_id in self._processed_responses
                    
                    response_summary["unmatched_responses"].append({
                        "request_id": request_id,
                        "command": response.get("command", "unknown"),
                        "reason": "duplicate_response" if was_duplicate else "no_matching_request",
                        "pending_count": pending_count
                    })
                else:
                    # Legacy response without request ID or error response
                    if response.get("type") == "error":
                        error_info = response.get("data", response)
                        response_summary["errors"].append({
                            "error": error_info.get("error", "Unknown error"),
                            "details": error_info.get("details", ""),
                            "request_id": None
                        })
                        logger.error(f"[UI] Backend error (no ID): {error_info.get('error')}")
                    elif response.get("type") == "SYSTEM_SQUARE_OFF_COMPLETE":
                        # Handle system square-off completion notification (no request ID expected)
                        self._handle_system_sqoff_notification(response)
                        response_summary["commands_processed"].append({
                            "command": "SYSTEM_SQUARE_OFF_COMPLETE",
                            "request_id": None,
                            "success": True,
                            "message": "System square-off completion processed"
                        })
                    elif response.get("type") == "SYSTEM_SQUARE_OFF_ERROR":
                        # Handle legacy system square-off error notification (no request ID expected)
                        self._handle_system_sqoff_error_notification(response)
                        response_summary["commands_processed"].append({
                            "command": "SYSTEM_SQUARE_OFF_ERROR",
                            "request_id": None,
                            "success": True,
                            "message": "System square-off error processed"
                        })
                    elif response.get("type") == "autotrailer_event":
                        # Handle legacy AutoTrailer event notifications (no request ID expected)
                        self._handle_autotrailer_event_notification(response)
                        response_summary["commands_processed"].append({
                            "command": "autotrailer_event",
                            "request_id": None,
                            "success": True,
                            "message": f"AutoTrailer event processed: {response.get('event', 'unknown')}"
                        })
                    # NOTE: Structured notifications now processed separately above
                    else:
                        logger.warning(f"[Instance {self.instance_id}][UI] Received unexpected response without request_id: command={response.get('command', 'unknown')} type={response.get('type', 'unknown')} success={response.get('success', 'unknown')} response={response}")
                        response_summary["unmatched_responses"].append({
                            "request_id": None,
                            "command": response.get("command", "unknown"),
                            "reason": "missing_request_id"
                        })
                    
            except Exception as e:
                logger.error(f"Error processing response: {e}")
                response_summary["errors"].append({
                    "error": str(e), 
                    "details": "Response processing error",
                    "request_id": response.get("request_id")
                })
        
        # Check for old pending requests (timeout detection) with thread safety
        current_time = time.time()
        timed_out_requests = []
        with self._pending_requests_lock:
            for req_id, req_info in list(self._pending_requests.items()):
                age = current_time - req_info["sent_at"]
                if age > 5.0:  # 5 second timeout
                    timed_out_requests.append((req_id, req_info["command"], age))
        
        if timed_out_requests:
            logger.warning(f"Found {len(timed_out_requests)} timed out requests:")
            for req_id, command, age in timed_out_requests:
                logger.warning(f"  - {command} (ID: {req_id}) aged {age:.1f}s")
        
        # Clean up very old processed response IDs (prevent memory leak)
        self._cleanup_old_processed_responses()
        
        return response_summary
    
    def process_data_updates(self) -> Dict[str, Any]:
        """
        Process all available data from backend (non-blocking)
        Should be called periodically by UI update loop
        
        Returns:
            dict: Latest data state for UI display
        """
        all_data = self.fetch_all_data()
        
        # Reset change counters at start of processing cycle
        self._pnl_change_count = 0
        self._tick_change_count = 0
        
        data_summary = {
            "has_update": len(all_data) > 0,
            "packets_processed": len(all_data),
            "pnl": self._last_pnl,
            "ltp": self._last_ltp,
            "auto_active": self._auto_mode_active,
            "timestamp": time.time(),
            "pnl_updates_count": 0,  # Will be set to actual change count
            "tick_updates_count": 0  # Will be set to actual change count
        }
        
        # Process all data packets - consume everything in the queue
        for packet in all_data:
            try:
                # Handle structured packet data from port coordinator
                packet_type = packet.get("type", "")
                packet_data = packet.get("data", {})
                
                if packet_type == DataPacketType.TICK_UPDATE.value:
                    self._handle_tick_update_packet(packet_data)
                    data_summary["has_tick_update"] = True
                    # tick_updates_count will be set later based on actual changes
                    
                elif packet_type == DataPacketType.PNL_UPDATE.value:
                    self._handle_pnl_update_packet(packet_data)
                    data_summary["has_pnl_update"] = True
                    # pnl_updates_count will be set later based on actual changes
                    
                elif packet_type == DataPacketType.STATUS_UPDATE.value:
                    self._handle_status_update_packet(packet_data)
                    data_summary["has_status_update"] = True
                    
                elif packet_type == DataPacketType.AUTO_TRAILER_UPDATE.value:
                    self._handle_auto_trailer_update_packet(packet_data)
                    data_summary["has_auto_trailer_update"] = True
                else:
                    logger.debug(f"Unknown packet type: {packet_type}")
                    
            except Exception as e:
                logger.error(f"Error processing data packet: {e}")
                data_summary["error"] = str(e)
        
        # Always update data summary with current cached values after processing all packets
        data_summary.update({
            "pnl": self._last_pnl,
            "ltp": self._last_ltp,
            "auto_active": self._auto_mode_active,
            "pnl_updates_count": self._pnl_change_count,
            "tick_updates_count": self._tick_change_count
        })
        
        if len(all_data) > 0:
            # Only log when there are meaningful changes (not just packet receipts)
            if self._pnl_change_count > 0 or self._tick_change_count > 0:
                logger.debug(f"Consumed {len(all_data)} packets: P&L Changes={self._pnl_change_count}, Tick Changes={self._tick_change_count} - Final: PnL={self._last_pnl:.2f}, LTP={self._last_ltp}")
            else:
                # Periodic health check every 50 packets to avoid complete silence
                if len(all_data) >= 50:
                    logger.debug(f"Processed {len(all_data)} packets (no changes): P&L={self._last_pnl:.2f}, LTP={self._last_ltp}")
        
        return data_summary
    
    def _handle_tick_update_packet(self, packet_data: Dict[str, Any]) -> None:
        """Handle tick update packet data"""
        try:
            old_ltp = self._last_ltp
            self._last_ltp = packet_data.get("ltp", self._last_ltp)
            
            # Only count and log tick updates when LTP value changes
            if old_ltp != self._last_ltp:
                self._tick_change_count += 1  # Count actual changes
                logger.debug(f"Processed tick update: LTP={old_ltp} -> {self._last_ltp}")
        except Exception as e:
            logger.error(f"Error handling tick update packet: {e}")
    
    def _handle_pnl_update_packet(self, packet_data: Dict[str, Any]) -> None:
        """Handle P&L update packet data - consume and process every update"""
        try:
            old_pnl = self._last_pnl
            self._last_pnl = packet_data.get("pnl", self._last_pnl)
            self._auto_mode_active = packet_data.get("auto_active", self._auto_mode_active)
            
            # Store additional P&L related flags for UI access
            self._sl_hit = packet_data.get("sl_hit", False)
            self._target_hit = packet_data.get("target_hit", False)
            self._sq_off_done = packet_data.get("sq_off_done", False)
            self._move_to_cost_active = packet_data.get("move_to_cost_active", False)
            self._trail_sl_active = packet_data.get("trail_sl_active", False)
            
            # Only count and log P&L updates when values actually change
            if old_pnl != self._last_pnl:
                self._pnl_change_count += 1  # Count actual changes
                change = self._last_pnl - old_pnl
                logger.debug(f"P&L update consumed: {old_pnl:.2f} -> {self._last_pnl:.2f} (Change: {change:+.2f})")
                
        except Exception as e:
            logger.error(f"Error handling P&L update packet: {e}")
    
    def _handle_status_update_packet(self, packet_data: Dict[str, Any]) -> None:
        """Handle status update packet data"""
        try:
            # Store system status information
            self._system_status = packet_data.get("status", "unknown")
            self._system_health = packet_data.get("health", "unknown")
            self._data_feed_connected = packet_data.get("data_feed_connected", False)
            
            logger.debug(f"Processed status update: {self._system_status}")
        except Exception as e:
            logger.error(f"Error handling status update packet: {e}")
    
    def _handle_auto_trailer_update_packet(self, packet_data: Dict[str, Any]) -> None:
        """Handle auto-trailer update packet data"""
        try:
            # Store auto-trailer specific data
            self._auto_trailer_state = packet_data.get("current_state", "INACTIVE")
            self._sl_level = packet_data.get("sl_level")
            self._target_level = packet_data.get("target_level")
            self._trail_sl_level = packet_data.get("trail_sl_level")
            
            logger.debug(f"Processed auto-trailer update: {self._auto_trailer_state}")
        except Exception as e:
            logger.error(f"Error handling auto-trailer update packet: {e}")
    
    def get_current_state(self) -> Dict[str, Any]:
        """
        Get current UI state summary (non-blocking)
        
        Returns:
            dict: Current state information
        """
        return {
            "auto_mode_active": self._auto_mode_active,
            "last_pnl": self._last_pnl,
            "last_ltp": self._last_ltp,
            "command_queue_size": self.command_port.get_queue_sizes()[1],  # cmd_queue_size
            "response_queue_size": self.response_port.get_queue_sizes()[0],  # data_queue_size
            "data_queue_size": self.data_port.get_queue_sizes()[0],  # data_queue_size
            "pending_requests": self._get_pending_requests_count()
        }
    
    def get_pending_requests_info(self) -> Dict[str, Any]:
        """
        Get detailed information about pending requests for debugging
        
        Returns:
            dict: Pending requests information
        """
        current_time = time.time()
        pending_info = {
            "total_pending": 0,
            "requests": []
        }
        
        with self._pending_requests_lock:
            pending_info["total_pending"] = len(self._pending_requests)
            for req_id, req_data in self._pending_requests.items():
                age = current_time - req_data["sent_at"]
                pending_info["requests"].append({
                    "request_id": req_id,
                    "command": req_data["command"],
                    "age_seconds": round(age, 3),
                    "sent_at": req_data["sent_at"]
                })
        
        return pending_info
    
    def get_latest_tick(self) -> float:
        """
        Get the latest tick/LTP data (non-blocking)
        
        Returns:
            float: Latest LTP value
        """
        return self._last_ltp
    
    def flush_all_ports(self) -> Dict[str, tuple]:
        """
        Flush all port queues (useful for cleanup/reset)
        
        Returns:
            dict: Flush statistics per port
        """
        return {
            "command": self.command_port.flush(),
            "response": self.response_port.flush(),
            "data": self.data_port.flush()
        }
    
    def _handle_system_sqoff_notification(self, notification_data: Dict[str, Any]) -> None:
        """
        Handle SYSTEM_SQUARE_OFF_COMPLETE notification from backend
        This handles ALL square-off completions (USER, TIMER, AutoTrailer) after execution
        
        Args:
            notification_data: The notification response from backend with trigger context
        """
        try:
            # Extract notification data
            all_positions_closed = notification_data["all_positions_closed"]
            total_positions = notification_data["total_positions"]
            trigger_source = notification_data["trigger_source"]
            trigger_reason = notification_data["trigger_reason"]
            pnl_at_trigger = notification_data["pnl_at_trigger"]
            
            # Log notification details
            logger.info(f"System square-off completed: {trigger_reason} (Source: {trigger_source})")
            logger.info(f"Result: positions_closed={all_positions_closed}, qty={total_positions}, pnl={pnl_at_trigger}")
            
            # Call the global callback function if all positions are closed
            if all_positions_closed:
                # Import here to avoid circular imports
                import tez_main
                if hasattr(tez_main, 'g_pnl_window') and tez_main.g_pnl_window:
                    logger.info("Triggering Trade Manager UI update for system square-off completion")
                    tez_main.g_pnl_window.ui_update_sys_sq_off()
                else:
                    logger.warning("Trade Manager window not available for system square-off update")
            else:
                logger.debug(f"System square-off notification: positions still remain ({total_positions}), no UI update needed")
                
        except Exception as e:
            logger.error(f"Error handling system square-off notification: {e}")
            logger.error(f"Notification data: {notification_data}")
    
    def _handle_system_sqoff_error_notification(self, notification_data: Dict[str, Any]) -> None:
        """
        Handle SYSTEM_SQUARE_OFF_ERROR notification from backend
        This handles square-off execution errors and shows appropriate UI messages
        
        Args:
            notification_data: The error notification response from backend
        """
        try:
            # Extract notification data
            positions_remain = notification_data.get("positions_remain", True)
            total_positions = notification_data.get("total_positions", "unknown")
            trigger_source = notification_data.get("trigger_source", "UNKNOWN")
            error_message = notification_data.get("error_message", "Square-off execution failed")
            pnl_at_trigger = notification_data.get("pnl_at_trigger", 0.0)
            
            # Log error details
            logger.error(f"System square-off error: {error_message} (Source: {trigger_source})")
            logger.error(f"Result: positions_remain={positions_remain}, qty={total_positions}, pnl={pnl_at_trigger}")
            
            # Always switch radio button to Manual and show error message
            # Import here to avoid circular imports
            import tez_main
            if hasattr(tez_main, 'g_pnl_window') and tez_main.g_pnl_window:
                logger.info("Triggering Trade Manager UI update for system square-off error")
                # Switch to manual mode
                tez_main.g_pnl_window.ui_update_sys_sq_off()
                
                # Show error message box
                import tkinter as tk
                from tkinter import messagebox
                
                if trigger_source == "AUTOTRAILER":
                    message_title = "AutoTrailer Error"
                    message_text = f"AutoTrailer failed to execute square-off.\n\n{error_message}\n\nPositions may still be open. Please take manual control."
                else:
                    message_title = "Square-off Error"
                    message_text = f"System square-off failed.\n\n{error_message}\n\nPlease check positions and take manual action."
                
                # Show message box in a thread-safe manner
                def show_error_message():
                    try:
                        messagebox.showerror(message_title, message_text)
                    except Exception as msg_error:
                        logger.error(f"Error showing error message box: {msg_error}")
                
                # Schedule message box to run in main thread
                if hasattr(tez_main, 'g_root') and tez_main.g_root:
                    tez_main.g_root.after(0, show_error_message)
                else:
                    logger.warning("Main window not available for error message display")
            else:
                logger.warning("Trade Manager window not available for error handling")
                
        except Exception as e:
            logger.error(f"Error handling system square-off error notification: {e}")
            logger.error(f"Error notification data: {notification_data}")
    
    def _handle_autotrailer_event_notification(self, notification_data: Dict[str, Any]) -> None:
        """
        Handle AutoTrailer event notifications from backend
        This handles all AutoTrailer state change events (activation, deactivation, etc.)
        
        Args:
            notification_data: The AutoTrailer event notification from backend
        """
        try:
            # Extract notification data
            event_type = notification_data.get("event", "unknown")
            event_data = notification_data.get("data", {})
            timestamp = notification_data.get("timestamp", time.time())
            
            # Log the event for debugging
            logger.debug(f"AutoTrailer event received: {event_type}")
            
            # Handle different event types
            if event_type == "autotrailer_activated":
                params = event_data.get("params", {})
                current_pnl = event_data.get("current_pnl", 0.0)
                logger.info(f"AutoTrailer activated with SL: {params.get('sl')}, Target: {params.get('target')}, Current P&L: {current_pnl}")
                
            elif event_type == "autotrailer_deactivated":
                final_pnl = event_data.get("final_pnl", 0.0)
                logger.info(f"AutoTrailer deactivated - Final P&L: {final_pnl}")
                
            elif event_type == "square_off_executed":
                reason = event_data.get("reason", "unknown")
                pnl = event_data.get("pnl", 0.0)
                logger.info(f"AutoTrailer square-off executed: {reason} at P&L {pnl}")
                
            elif event_type == "square_off_failed":
                reason = event_data.get("reason", "unknown")
                pnl = event_data.get("pnl", 0.0)
                logger.warning(f"AutoTrailer square-off failed: {reason} at P&L {pnl}")
                
            elif event_type == "square_off_error":
                reason = event_data.get("reason", "unknown")
                error = event_data.get("error", "unknown error")
                pnl = event_data.get("pnl", 0.0)
                logger.error(f"AutoTrailer square-off error: {reason} - {error} at P&L {pnl}")
                
            else:
                logger.debug(f"AutoTrailer event handled: {event_type} with data: {event_data}")
                
        except Exception as e:
            logger.error(f"Error handling AutoTrailer event notification: {e}")
            logger.error(f"Event notification data: {notification_data}")
    
    def _handle_structured_notification(self, notification_data: Dict[str, Any]) -> None:
        """
        Handle structured notifications using the new notification system
        
        Args:
            notification_data: Structured notification dictionary from backend
        """
        try:
            # Convert dictionary to structured notification object
            notification = Notification.from_dict(notification_data)
            
            # Log the structured notification
            self._notification_logger.log_notification(notification, "received")
            
            # Route to appropriate handler based on notification ID
            notification_id = notification.id
            
            if notification_id == NotificationID.SQUARE_OFF_SUCCESS:
                self._handle_square_off_success_notification(notification)
                
            elif notification_id == NotificationID.SQUARE_OFF_ERROR:
                self._handle_square_off_error_notification(notification)
                
            elif notification_id == NotificationID.AUTOTRAILER_ACTIVATED:
                self._handle_autotrailer_activated_notification(notification)
                
            elif notification_id == NotificationID.AUTOTRAILER_DEACTIVATED:
                self._handle_autotrailer_deactivated_notification(notification)
                
            elif notification_id == NotificationID.AUTOTRAILER_ERROR:
                self._handle_autotrailer_error_notification(notification)
                
            elif notification_id == NotificationID.UI_RADIO_BUTTON_UPDATE:
                self._handle_ui_radio_button_update_notification(notification)
                
            elif notification_id == NotificationID.UI_SHOW_MESSAGE:
                self._handle_ui_show_message_notification(notification)

            elif notification_id == NotificationID.NETWORK_CONNECTED:
                self._handle_network_connected_notification(notification)

            elif notification_id == NotificationID.NETWORK_DISCONNECTED:
                self._handle_network_disconnected_notification(notification)

            elif notification_id == NotificationID.NETWORK_RECONNECTING:
                self._handle_network_reconnecting_notification(notification)

            else:
                # Log unhandled notification types for future implementation
                logger.warning(f"Unhandled structured notification: {notification_id.name}")
                logger.debug(f"Notification data: {notification.data}")
                
        except Exception as e:
            logger.error(f"Error handling structured notification: {e}")
            # Log error through notification logger
            self._notification_logger.log_notification_error(e, "handle_structured_notification")
    
    def _handle_square_off_success_notification(self, notification: Notification) -> None:
        """Handle structured square-off success notification"""
        data = notification.data
        trigger_source = data.get('trigger_source', 'Unknown')
        pnl = data.get('pnl', 0.0)
        symbol = data.get('symbol', 'Unknown')
        
        logger.info(f"Square-off completed successfully: {trigger_source} for {symbol}, P&L: {pnl:.2f}")
        
        # If triggered by AutoTrailer, handle radio button switch
        if trigger_source.upper() == 'AUTOTRAILER':
            logger.info("AutoTrailer square-off completed - Radio button should switch to Manual")
    
    def _handle_square_off_error_notification(self, notification: Notification) -> None:
        """Handle structured square-off error notification"""
        data = notification.data
        error_message = data.get('error_message', 'Unknown error')
        trigger_source = data.get('trigger_source', 'Unknown')
        symbol = data.get('symbol', 'Unknown')
        
        logger.error(f"Square-off failed: {trigger_source} for {symbol} - {error_message}")
        
        if notification.is_critical():
            logger.critical("CRITICAL: Manual intervention required for square-off failure")
    
    def _handle_autotrailer_activated_notification(self, notification: Notification) -> None:
        """Handle structured AutoTrailer activation notification"""
        data = notification.data
        symbol = data.get('symbol', 'Unknown')
        sl_price = data.get('sl_price', 0.0)
        target_price = data.get('target_price', 0.0)
        
        logger.info(f"AutoTrailer activated for {symbol}: SL={sl_price}, Target={target_price}")
    
    def _handle_autotrailer_deactivated_notification(self, notification: Notification) -> None:
        """Handle structured AutoTrailer deactivation notification"""
        data = notification.data
        symbol = data.get('symbol', 'Unknown')
        reason = data.get('reason', 'Unknown')
        
        logger.info(f"AutoTrailer deactivated for {symbol}: {reason}")
    
    def _handle_autotrailer_error_notification(self, notification: Notification) -> None:
        """Handle structured AutoTrailer error notification"""
        data = notification.data
        error_details = data.get('error_details', 'Unknown error')
        symbol = data.get('symbol', 'Unknown')
        
        logger.error(f"AutoTrailer error for {symbol}: {error_details}")
        
        if notification.is_critical():
            logger.critical("CRITICAL: AutoTrailer error requires manual intervention")
    
    def _handle_ui_radio_button_update_notification(self, notification: Notification) -> None:
        """Handle UI radio button update notification"""
        data = notification.data
        from_mode = data.get('from_mode', 'Unknown')
        to_mode = data.get('to_mode', 'Unknown')
        reason = data.get('reason', 'Unknown')
        
        logger.info(f"UI radio button update: {from_mode} -> {to_mode} (Reason: {reason})")
    
    def _handle_ui_show_message_notification(self, notification: Notification) -> None:
        """Handle UI message display notification"""
        data = notification.data
        message_type = data.get('message_type', 'info')
        title = data.get('title', 'Notification')
        content = data.get('content', 'No content')
        
        log_level = notification.get_log_level()
        logger.log(log_level, f"UI Message [{message_type.upper()}]: {title} - {content}")

    def _handle_network_connected_notification(self, notification: Notification) -> None:
        """Handle network connected notification - update StatusLED to green"""
        logger.info("Network connected")

        if self.frontend and hasattr(self.frontend, 'status_led_manager') and self.frontend.status_led_manager:
            try:
                from app_mods.infra_error_handler import ConnectionStatus
                self.frontend.status_led_manager.led.update_status(ConnectionStatus.CONNECTED)
            except Exception as e:
                logger.error(f"Failed to update StatusLED for network connected: {e}")

    def _handle_network_disconnected_notification(self, notification: Notification) -> None:
        """Handle network disconnected notification - update StatusLED to red"""
        data = notification.data
        logger.warning("Network connection lost")

        if self.frontend and hasattr(self.frontend, 'status_led_manager') and self.frontend.status_led_manager:
            try:
                from app_mods.infra_error_handler import ConnectionStatus
                self.frontend.status_led_manager.led.update_status(ConnectionStatus.DISCONNECTED)
            except Exception as e:
                logger.error(f"Failed to update StatusLED for network disconnected: {e}")

    def _handle_network_reconnecting_notification(self, notification: Notification) -> None:
        """Handle network reconnecting notification - update StatusLED to yellow"""
        logger.info("Network reconnection in progress")

        if self.frontend and hasattr(self.frontend, 'status_led_manager') and self.frontend.status_led_manager:
            try:
                from app_mods.infra_error_handler import ConnectionStatus
                self.frontend.status_led_manager.led.update_status(ConnectionStatus.RECONNECTING)
            except Exception as e:
                logger.error(f"Failed to update StatusLED for network reconnecting: {e}")

    def _get_pending_requests_count(self) -> int:
        """Get count of pending requests with thread safety"""
        with self._pending_requests_lock:
            return len(self._pending_requests)
    
    def _cleanup_old_processed_responses(self) -> None:
        """Clean up old processed response IDs to prevent memory leak"""
        # Only clean up if we have too many processed responses
        with self._processed_responses_lock:
            if len(self._processed_responses) > 1000:
                # Keep only the most recent 500
                old_count = len(self._processed_responses)
                self._processed_responses = set(list(self._processed_responses)[-500:])
                new_count = len(self._processed_responses)
                logger.debug(f"Cleaned up processed responses: {old_count} -> {new_count}")

class UIWidgetPortHelper:
    """
    Helper class for UI widgets to extract parameters and handle common operations
    """
    
    @staticmethod
    def get_auto_params_from_widgets(widgets: Dict[str, Any]) -> Dict[str, float]:
        """
        Helper to extract parameters from UI widgets
        
        Args:
            widgets: Dictionary of widget references (e.g., {"sl_entry": entry_widget})
        
        Returns:
            Dictionary with auto-trading parameters
        """
        try:
            return {
                "sl": float(widgets.get("sl_entry", {}).get() or "-50.0"),
                "target": float(widgets.get("target_entry", {}).get() or "100.0"),
                "mvto_cost": float(widgets.get("mvto_cost_entry", {}).get() or "25.0"),
                "trail_after": float(widgets.get("trail_after_entry", {}).get() or "50.0"),
                "trail_by": float(widgets.get("trail_by_entry", {}).get() or "10.0"),
                "ui_reset": widgets.get("ui_reset", False)
            }
        except (ValueError, AttributeError) as e:
            logger.error(f"Error extracting auto params from widgets: {e}")
            # Return safe defaults
            return {
                "sl": -50.0,
                "target": 100.0,
                "mvto_cost": 25.0,
                "trail_after": 50.0,
                "trail_by": 10.0,
                "ui_reset": False
            }
    
    @staticmethod
    def update_widgets_from_data(widgets: Dict[str, Any], data: Dict[str, Any]) -> None:
        """
        Update UI widgets with data from backend
        
        Args:
            widgets: Dictionary of widget references
            data: Data dictionary from backend
        """
        try:
            # Update PnL display
            if "pnl_label" in widgets and "pnl" in data:
                widgets["pnl_label"].config(text=f"P&L: {data['pnl']:.2f}")
            
            # Update mode radio buttons
            if data.get("auto_active", False):
                if "radio_auto" in widgets:
                    widgets["radio_auto"].select()
            else:
                if "radio_manual" in widgets:
                    widgets["radio_manual"].select()
            
            # Update status indicators
            if "status_label" in widgets:
                status = "AUTO" if data.get("auto_active", False) else "MANUAL"
                widgets["status_label"].config(text=f"Mode: {status}")
            
            # Handle square-off completion
            if data.get("sq_off_done", False):
                if "radio_manual" in widgets:
                    widgets["radio_manual"].select()
                logger.info("Square-off completed - switched to MANUAL mode")
                
        except Exception as e:
            logger.error(f"Error updating widgets from data: {e}")

class PortUITester:
    """
    Simple tester class for port-based UI integration
    Used for testing the 3-port system without full UI
    """
    
    def __init__(self, port_manager):
        """
        Initialize with port manager
        
        Args:
            port_manager: PortManager instance
        """
        self.ports = port_manager.get_all_ports()
        self.ui_manager = SimpleUIPortManager(self.ports)
        logger.info("Port UI Tester initialized")
    
    def test_command_flow(self):
        """Test basic command flow through ports"""
        logger.info("Testing command flow...")
        
        # Send test commands
        self.ui_manager.send_activate_auto({
            "sl": -25.0,
            "target": 50.0,
            "mvto_cost": 15.0,
            "trail_after": 30.0,
            "trail_by": 5.0
        })
        
        # Wait briefly
        time.sleep(0.1)
        
        # Process responses
        responses = self.ui_manager.process_responses()
        logger.info(f"Command test responses: {responses}")
        
        return responses
    
    def test_data_flow(self):
        """Test data flow through ports"""
        logger.info("Testing data flow...")
        
        # Process data updates
        data = self.ui_manager.process_data_updates()
        logger.info(f"Data test results: {data}")
        
        return data
    
    def get_system_status(self):
        """Get overall system status"""
        state = self.ui_manager.get_current_state()
        logger.info(f"System status: {state}")
        return state