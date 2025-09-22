"""
File: shared_types.py
Author: [Tarakeshwar NC] / Claude Code
Date: September 11, 2025
Description: Shared enums and data structures for TeZ trading platform component communication
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


from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, Any
import time

class SquareOff_Mode(Enum):
    ALL = 0
    SELECT = 1

class SquareOff_InstType(Enum):
    BEES = 0
    CE = 1
    PE = 2
    ALL = 3

class SquareOff_Type(Enum):
    FULL = auto()
    PARTIAL = auto()

class MarketAction(Enum):
    BUY = "Buy"
    SHORT = "Short"

class UICommand(Enum):
    """All UI commands that can be sent through ports"""
    ACTIVATE_AUTO = "ACTIVATE_AUTO"
    DEACTIVATE_AUTO = "DEACTIVATE_AUTO"
    SET_MODE = "SET_MODE"
    SET_UL_INDEX = "SET_UL_INDEX"
    MARKET_ACTION = "MARKET_ACTION"
    SQUARE_OFF = "SQUARE_OFF"
    ENHANCED_SQUARE_OFF = "ENHANCED_SQUARE_OFF"
    SIMPLE_SQUARE_OFF = "SIMPLE_SQUARE_OFF"
    CANCEL_WAITING_ORDER = "CANCEL_WAITING_ORDER"
    SHOW_RECORDS = "SHOW_RECORDS"
    GET_LATEST_TICK = "GET_LATEST_TICK"
    DATA_FEED_CONNECT = "DATA_FEED_CONNECT"
    DATA_FEED_DISCONNECT = "DATA_FEED_DISCONNECT"
    GET_SYSTEM_STATUS = "GET_SYSTEM_STATUS"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    REFRESH_POSITIONS = "REFRESH_POSITIONS"

@dataclass
class SquareOff_Info:
    """Square-off information structure"""
    mode: SquareOff_Mode
    per: float
    ul_index: str
    exch: str
    inst_type: SquareOff_InstType = SquareOff_InstType.ALL
    type: SquareOff_Type = SquareOff_Type.FULL

@dataclass
class MarketActionParams:
    """Parameters for market actions (Buy/Short)"""
    action: MarketAction
    trade_price: Optional[float] = None
    ui_qty: int = 1

@dataclass
class UICommandResponse:
    """Standard response structure for UI commands"""
    success: bool
    message: str
    command: str
    request_id: int
    data: Optional[Any] = None
    timestamp: Optional[float] = field(default_factory=time.time)

class CommandStatus(Enum):
    """Status of command execution"""
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    PENDING = "PENDING"
    ERROR = "ERROR"

# =============================================================================
# DATA PACKET CLASSES FOR PORT COMMUNICATION
# =============================================================================

@dataclass
class PnLUpdatePacket:
    """Data packet for P&L related updates"""
    type: str = "pnl_update"
    pnl: float = 0.0
    auto_active: bool = False
    sl_hit: bool = False
    target_hit: bool = False
    sq_off_done: bool = False
    move_to_cost_active: bool = False
    trail_sl_active: bool = False
    timestamp: float = field(default_factory=time.time)

@dataclass
class TickUpdatePacket:
    """Data packet for tick/LTP data updates"""
    type: str = "tick_update"
    ltp: float = 0.0
    ul_index: str = "NIFTY"
    token: str = ""
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume: Optional[int] = None
    timestamp: float = field(default_factory=time.time)

@dataclass
class StatusUpdatePacket:
    """Data packet for system status updates"""
    type: str = "status_update"
    status: str = "unknown"
    health: str = "unknown" 
    message: str = ""
    component: str = "system"
    data_feed_connected: bool = False
    auto_mode_active: bool = False
    timestamp: float = field(default_factory=time.time)

@dataclass
class AutoTrailerStatusPacket:
    """Data packet for auto-trailer specific updates"""
    type: str = "auto_trailer_update"
    current_state: str = "INACTIVE"
    sl_level: Optional[float] = None
    target_level: Optional[float] = None
    trail_sl_level: Optional[float] = None
    move_to_cost_level: Optional[float] = None
    trail_after: Optional[float] = None
    trail_by: Optional[float] = None
    pnl_at_activation: Optional[float] = None
    timestamp: float = field(default_factory=time.time)

class DataPacketType(Enum):
    """Enum for data packet types"""
    PNL_UPDATE = "pnl_update"
    TICK_UPDATE = "tick_update" 
    STATUS_UPDATE = "status_update"
    AUTO_TRAILER_UPDATE = "auto_trailer_update"