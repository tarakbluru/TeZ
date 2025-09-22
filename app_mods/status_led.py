"""
StatusLED Widget Module

Visual LED indicator for network connectivity status in TeZ trading platform.
Shows connection status through color-coded circular indicator.

Author: Claude Code
Created: Network Disconnection Notification System v2
"""

import tkinter as tk
from typing import Optional
import logging

from .infra_error_handler import ConnectionStatus

logger = logging.getLogger(__name__)


class StatusLED:
    """
    Network status LED indicator widget

    Visual indicator that shows network connectivity status through colors:
    - Green: Connected
    - Red: Disconnected
    - Yellow: Reconnecting
    """

    def __init__(self, parent_widget: tk.Widget):
        """
        Initialize StatusLED widget

        Args:
            parent_widget: Parent tkinter widget to contain the LED
        """
        self.parent = parent_widget

        # Create canvas for LED circle
        self.canvas = tk.Canvas(
            parent_widget,
            width=12,
            height=12,
            highlightthickness=0,
            bg=parent_widget.cget('bg') if hasattr(parent_widget, 'cget') else 'white'
        )

        # LED visual elements
        self.led_circle = None
        self.current_status = ConnectionStatus.DISCONNECTED

        # Status color mapping
        self.color_map = {
            ConnectionStatus.CONNECTED: "#00FF00",      # Bright green
            ConnectionStatus.DISCONNECTED: "#FF0000",   # Bright red
            ConnectionStatus.RECONNECTING: "#FFFF00"    # Bright yellow
        }

        # Create the LED visual
        self._create_led_visual()

        # Optional tooltip setup
        self._setup_tooltip()

        logger.info("StatusLED widget initialized")

    def _create_led_visual(self):
        """Create the circular LED indicator"""
        # Create circular LED with slight border for visibility
        self.led_circle = self.canvas.create_oval(
            1, 1, 11, 11,  # 10x10 circle with 1px margin
            fill=self.color_map[self.current_status],
            outline="#808080",  # Gray border
            width=1
        )

        logger.debug("LED visual created")

    def _setup_tooltip(self):
        """Setup hover tooltip for detailed status"""
        def on_enter(event):
            """Show tooltip on mouse enter"""
            self._show_tooltip()

        def on_leave(event):
            """Hide tooltip on mouse leave"""
            self._hide_tooltip()

        self.canvas.bind("<Enter>", on_enter)
        self.canvas.bind("<Leave>", on_leave)

        # Tooltip window (initially None)
        self.tooltip_window = None

    def _show_tooltip(self):
        """Display status tooltip"""
        if self.tooltip_window:
            return

        # Status text mapping
        status_text = {
            ConnectionStatus.CONNECTED: "Network: Connected",
            ConnectionStatus.DISCONNECTED: "Network: Disconnected",
            ConnectionStatus.RECONNECTING: "Network: Reconnecting"
        }

        # Create tooltip window
        x = self.canvas.winfo_rootx() + 15
        y = self.canvas.winfo_rooty() - 25

        self.tooltip_window = tk.Toplevel(self.canvas)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")

        # Tooltip label
        label = tk.Label(
            self.tooltip_window,
            text=status_text.get(self.current_status, "Network: Unknown"),
            background="#FFFFE0",  # Light yellow background
            relief="solid",
            borderwidth=1,
            font=("Arial", 8)
        )
        label.pack()

    def _hide_tooltip(self):
        """Hide status tooltip"""
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

    def update_status(self, status: ConnectionStatus):
        """
        Update LED status and color

        Args:
            status: New connection status
        """
        if status == self.current_status:
            return  # No change needed

        # Update internal status
        old_status = self.current_status
        self.current_status = status

        # Update LED color
        new_color = self.color_map.get(status, "#808080")  # Gray for unknown
        if self.led_circle:
            self.canvas.itemconfig(self.led_circle, fill=new_color)

        logger.info(f"StatusLED updated: {old_status.value} -> {status.value}")

    def place(self, **kwargs):
        """Place the LED widget using tkinter place geometry manager"""
        self.canvas.place(**kwargs)

    def pack(self, **kwargs):
        """Pack the LED widget using tkinter pack geometry manager"""
        self.canvas.pack(**kwargs)

    def grid(self, **kwargs):
        """Grid the LED widget using tkinter grid geometry manager"""
        self.canvas.grid(**kwargs)

    def get_current_status(self) -> ConnectionStatus:
        """Get current LED status"""
        return self.current_status

    def destroy(self):
        """Clean up LED widget"""
        if self.tooltip_window:
            self.tooltip_window.destroy()
        self.canvas.destroy()
        logger.debug("StatusLED widget destroyed")


class StatusLEDManager:
    """
    Manager for StatusLED widget integration with notification system

    Handles the connection between network status notifications and LED updates
    """

    def __init__(self, parent_widget: tk.Widget):
        """
        Initialize StatusLED manager

        Args:
            parent_widget: Parent widget for LED placement
        """
        self.led = StatusLED(parent_widget)
        logger.info("StatusLEDManager initialized")

    def handle_network_notification(self, notification_data: dict):
        """
        Handle network status notification from InfraErrorHandler

        Args:
            notification_data: Notification dictionary from error handler
        """
        try:
            # Extract status from notification
            status_value = notification_data.get('data', {}).get('status')
            if not status_value:
                logger.warning("No status found in network notification")
                return

            # Convert to ConnectionStatus enum
            status = ConnectionStatus(status_value)

            # Update LED
            self.led.update_status(status)

            logger.debug(f"LED updated from notification: {status.value}")

        except (ValueError, KeyError) as e:
            logger.error(f"Error processing network notification: {e}")

    def get_led_widget(self) -> StatusLED:
        """Get the StatusLED widget for direct manipulation"""
        return self.led