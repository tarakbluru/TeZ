"""
Infrastructure Error Handler Module

Centralized network error handling service that provides:
- Network exception handling without tracebacks
- Component status tracking (TIU, DIU, PFMU)
- LED status notification via port system
- Anti-bombardment filtering for notifications
- Background connectivity monitoring

Author: Claude Code
Created: Network Disconnection Notification System v2
"""

import threading
import time
import socket
import requests
from enum import Enum
from typing import Callable, Any, Dict, Optional
import logging

try:
    import websocket
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False

from .notification_types import NotificationID, NotificationCategory, NotificationPriority
from .notification_system import Notification

logger = logging.getLogger(__name__)


class ConnectionStatus(Enum):
    """Network connection status enumeration"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"


class InfraErrorHandler:
    """
    Centralized infrastructure error handler service

    Handles all broker API call exceptions, tracks connection status,
    and sends filtered notifications via existing port infrastructure.
    """

    def __init__(self, notification_port):
        """
        Initialize error handler service

        Args:
            notification_port: Port for sending status notifications
        """
        self.notification_port = notification_port

        # Component status tracking
        self.component_status = {
            "TIU": ConnectionStatus.DISCONNECTED,
            "DIU": ConnectionStatus.DISCONNECTED,
            "PFMU": ConnectionStatus.DISCONNECTED
        }

        # Component call tracking - skip notifications for first call from each component
        # Note: HEALTH_MONITOR removed - network status is separate from broker status
        self.component_call_count = {
            "TIU": 0,
            "DIU": 0,
            "PFMU": 0
        }

        # Anti-bombardment tracking
        self.last_notification_time = {}
        self.recent_errors = {}
        self.last_global_notification = 0
        self._last_overall_status = ConnectionStatus.DISCONNECTED

        # Thread safety
        self._status_lock = threading.Lock()
        self._notification_lock = threading.Lock()

        # No background monitoring needed - this is a simple wrapper service

        logger.info("InfraErrorHandler initialized")

    def handle_api_call(self, api_function: Callable, component_id: str) -> Any:
        """
        Central method for all broker API calls with error handling

        Args:
            api_function: Function to execute (lambda containing API call)
            component_id: Component identifier ("TIU", "DIU", "PFMU")

        Returns:
            API result on success, error dict on network failure
        """
        try:
            result = api_function()

            # Success - update status if previously failed
            with self._status_lock:
                if self.component_status.get(component_id) != ConnectionStatus.CONNECTED:
                    self.component_status[component_id] = ConnectionStatus.CONNECTED
                    self.report_connection_status(ConnectionStatus.CONNECTED, component_id)

            return result

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout,
                requests.exceptions.HTTPError, ConnectionError, TimeoutError,
                socket.gaierror, OSError) as e:
            # Network-related errors that cause tracebacks

            # Log error only if not recently logged (deduplication)
            if self._should_log_error("network_error", component_id):
                logger.error(f"Network error in {component_id}: {str(e)}")

            # Update status and send filtered notification
            with self._status_lock:
                self.component_status[component_id] = ConnectionStatus.DISCONNECTED
                self.report_connection_status(ConnectionStatus.DISCONNECTED, component_id)

            # Return clean error indicator - NO EXCEPTION PROPAGATION
            return {"error": "network_failure"}

        except Exception as e:
            # Check for WebSocket exceptions (if websocket library is available)
            if WEBSOCKET_AVAILABLE and hasattr(websocket, '_exceptions'):
                websocket_exceptions = (
                    websocket._exceptions.WebSocketException,
                    websocket._exceptions.WebSocketConnectionClosedException,
                    websocket._exceptions.WebSocketTimeoutException,
                    websocket._exceptions.WebSocketBadStatusException
                )
                if isinstance(e, websocket_exceptions):
                    # WebSocket network errors - treat as network failure
                    if self._should_log_error("websocket_error", component_id):
                        logger.error(f"WebSocket error in {component_id}: {str(e)}")

                    # Update status and send filtered notification
                    with self._status_lock:
                        self.component_status[component_id] = ConnectionStatus.DISCONNECTED
                        self.report_connection_status(ConnectionStatus.DISCONNECTED, component_id)

                    # Return clean error indicator - NO EXCEPTION PROPAGATION
                    return {"error": "websocket_failure"}

            # Non-network errors (API errors, broker errors) - pass through
            if self._should_log_error("api_error", component_id):
                logger.warning(f"Non-network error in {component_id}: {e}")
            raise  # Re-raise non-network exceptions

    def report_connection_status(self, status: ConnectionStatus, component_id: str):
        """
        Update component status and send filtered notifications

        Args:
            status: New connection status
            component_id: Component that reported the status
        """
        with self._status_lock:
            # Increment call counter for this component
            self.component_call_count[component_id] = self.component_call_count.get(component_id, 0) + 1

            # Skip notification for first call from each component (startup sequence)
            if self.component_call_count[component_id] == 1:
                old_status = self.component_status.get(component_id, "unknown")
                self.component_status[component_id] = status
                logger.debug(f"Component {component_id}: {old_status} -> {status.value} (first call - notification skipped)")
                return

            old_status = self.component_status.get(component_id, "unknown")
            self.component_status[component_id] = status
            overall_status = self._calculate_overall_status()
            logger.debug(f"Component {component_id}: {old_status} -> {status.value}, Overall: {overall_status.value}")

        # Only send notification if overall status changed or sufficient time passed
        if self._should_send_notification(overall_status):
            # Map ConnectionStatus to NotificationID
            status_to_notification_id = {
                ConnectionStatus.CONNECTED: NotificationID.NETWORK_CONNECTED,
                ConnectionStatus.DISCONNECTED: NotificationID.NETWORK_DISCONNECTED,
                ConnectionStatus.RECONNECTING: NotificationID.NETWORK_RECONNECTING
            }

            notification = Notification(
                id=status_to_notification_id[overall_status],
                category=NotificationCategory.MARKET_DATA,
                priority=NotificationPriority.HIGH,
                message=f"Network status: {overall_status.value}",
                data={"status": overall_status.value},
                source="InfraErrorHandler",
                target="UI"
            )

            with self._notification_lock:
                self.notification_port.send_data(notification.to_dict())
                self.last_global_notification = time.time()

            logger.info(f"Network status notification sent: {overall_status.value} (component: {component_id}, trigger: operational)")

    def get_current_status(self) -> ConnectionStatus:
        """Get current overall system connection status"""
        with self._status_lock:
            return self._calculate_overall_status()

    # No monitoring methods needed - this is a simple wrapper service

    def _calculate_overall_status(self) -> ConnectionStatus:
        """Calculate system-wide status from individual component statuses"""
        if not self.component_status:
            return ConnectionStatus.CONNECTED

        status_values = list(self.component_status.values())

        # If any component is reconnecting, overall status is reconnecting
        if ConnectionStatus.RECONNECTING in status_values:
            return ConnectionStatus.RECONNECTING

        # If any component is disconnected, overall status is disconnected
        if ConnectionStatus.DISCONNECTED in status_values:
            return ConnectionStatus.DISCONNECTED

        # All components connected
        return ConnectionStatus.CONNECTED

    def _should_send_notification(self, overall_status: ConnectionStatus) -> bool:
        """Determine if UI notification should be sent based on filtering rules"""
        current_time = time.time()

        # Rule 1: Always send if overall status changed
        if self._last_overall_status != overall_status:
            self._last_overall_status = overall_status
            return True

        # Rule 2: Rate limiting - minimum 5 seconds between identical status notifications
        if current_time - self.last_global_notification < 5.0:
            return False

        # Rule 3: Send periodic heartbeat for extended outages (every 60 seconds)
        if overall_status == ConnectionStatus.DISCONNECTED:
            if current_time - self.last_global_notification > 60.0:
                return True

        return False

    def _should_log_error(self, error_type: str, component_id: str) -> bool:
        """Error deduplication logic to prevent log flooding"""
        current_time = time.time()
        error_key = f"{error_type}_{component_id}"

        # Get last log time for this error type and component
        last_log_time = self.recent_errors.get(error_key, 0)

        # Log if more than 30 seconds since last identical error
        if current_time - last_log_time > 30.0:
            self.recent_errors[error_key] = current_time
            return True

        return False

    def send_initial_success_notification(self):
        """
        Send initial GREEN LED notification when system is ready.
        Called by app_be after successful component initialization.
        """
        if self.get_current_status() == ConnectionStatus.CONNECTED:
            # Map ConnectionStatus to NotificationID
            notification = Notification(
                id=NotificationID.NETWORK_CONNECTED,
                category=NotificationCategory.MARKET_DATA,
                priority=NotificationPriority.HIGH,
                message="Network status: connected",
                data={"status": "connected"},
                source="InfraErrorHandler",
                target="UI"
            )

            with self._notification_lock:
                self.notification_port.send_data(notification.to_dict())
                self.last_global_notification = time.time()

            logger.info("Network status notification sent: connected (trigger: initial_success)")

    def send_network_status_notification(self, network_connected: bool):
        """
        Send network connectivity notification directly (separate from broker status)

        Args:
            network_connected: True if network is connected, False if disconnected
        """
        status = ConnectionStatus.CONNECTED if network_connected else ConnectionStatus.DISCONNECTED

        # Map ConnectionStatus to NotificationID
        status_to_notification_id = {
            ConnectionStatus.CONNECTED: NotificationID.NETWORK_CONNECTED,
            ConnectionStatus.DISCONNECTED: NotificationID.NETWORK_DISCONNECTED
        }

        notification = Notification(
            id=status_to_notification_id[status],
            category=NotificationCategory.MARKET_DATA,
            priority=NotificationPriority.HIGH,
            message=f"Network status: {status.value}",
            data={"status": status.value},
            source="NetworkMonitor",
            target="UI"
        )

        with self._notification_lock:
            self.notification_port.send_data(notification.to_dict())

        logger.info(f"Network status notification sent: {status.value} (source: NetworkMonitor)")

    # No monitoring loops needed - components report failures through API call exceptions