"""
File: notification_types.py
Author: [Tarakeshwar NC] / Claude Code
Date: September 11, 2025
Description: Notification system enums and types for structured communication across TeZ trading platform components
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


from enum import IntEnum, Enum


class NotificationID(IntEnum):
    """Unique numeric identifiers for all notifications"""
    
    # System notifications (1000-1099)
    SYSTEM_STARTUP = 1001
    SYSTEM_SHUTDOWN = 1002  
    SYSTEM_ERROR = 1003
    SYSTEM_READY = 1004
    SYSTEM_MAINTENANCE = 1005
    
    # Trading notifications (1100-1199)
    POSITION_OPENED = 1101
    POSITION_CLOSED = 1102
    POSITION_UPDATED = 1103
    SQUARE_OFF_SUCCESS = 1104
    SQUARE_OFF_ERROR = 1105
    ORDER_PLACED = 1106
    ORDER_FILLED = 1107
    ORDER_REJECTED = 1108
    ORDER_CANCELLED = 1109
    
    # AutoTrailer notifications (1200-1299)
    AUTOTRAILER_ACTIVATED = 1201
    AUTOTRAILER_DEACTIVATED = 1202
    AUTOTRAILER_SL_HIT = 1203
    AUTOTRAILER_TARGET_HIT = 1204
    AUTOTRAILER_ERROR = 1205
    AUTOTRAILER_STATUS_UPDATE = 1206
    AUTOTRAILER_SQUARE_OFF_TRIGGERED = 1207
    
    # Market data notifications (1300-1399)
    MARKET_DATA_CONNECTED = 1301
    MARKET_DATA_DISCONNECTED = 1302
    TICK_UPDATE = 1303
    MARKET_DATA_ERROR = 1304
    FEED_TIMEOUT = 1305
    NETWORK_CONNECTED = 1306
    NETWORK_DISCONNECTED = 1307
    NETWORK_RECONNECTING = 1308
    
    # UI notifications (1400-1499)
    UI_REFRESH_PORTFOLIO = 1401
    UI_REFRESH_ORDERS = 1402
    UI_SHOW_MESSAGE = 1403
    UI_RADIO_BUTTON_UPDATE = 1404
    UI_ENABLE_CONTROLS = 1405
    UI_DISABLE_CONTROLS = 1406
    
    # Port system notifications (1500-1599)
    PORT_DATA_RECEIVED = 1501
    PORT_CONNECTION_ERROR = 1502
    PORT_BUFFER_OVERFLOW = 1503


class NotificationCategory(Enum):
    """Notification categories for filtering and routing"""
    SYSTEM = "system"
    TRADING = "trading"
    AUTOTRAILER = "autotrailer"  
    MARKET_DATA = "market_data"
    UI = "ui"
    PORT_SYSTEM = "port_system"
    ERROR = "error"


class NotificationPriority(IntEnum):
    """Priority levels for notification handling"""
    LOW = 1        # Informational updates
    NORMAL = 2     # Standard operations
    HIGH = 3       # Important events requiring attention
    CRITICAL = 4   # Errors requiring immediate action
    EMERGENCY = 5  # System-threatening issues