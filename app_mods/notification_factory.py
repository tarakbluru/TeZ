"""
File: notification_factory.py
Author: [Tarakeshwar NC] / Claude Code
Date: September 11, 2025
Description: Factory methods for creating standardized notifications across TeZ trading platform components
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


import uuid
import time
from typing import Optional, Dict, Any

from .notification_system import Notification
from .notification_types import NotificationID, NotificationCategory, NotificationPriority


class NotificationFactory:
    """Factory for creating standardized notifications"""
    
    @staticmethod
    def _generate_correlation_id() -> str:
        """Generate short correlation ID for tracking"""
        return str(uuid.uuid4())[:8]
    
    # =============================================================================
    # AUTOTRAILER NOTIFICATIONS
    # =============================================================================
    
    @staticmethod
    def autotrailer_square_off_complete(
        trigger_reason: str, 
        pnl: float, 
        symbol: str,
        correlation_id: Optional[str] = None
    ) -> Notification:
        """Create AutoTrailer square-off completion notification"""
        return Notification(
            id=NotificationID.SQUARE_OFF_SUCCESS,
            category=NotificationCategory.AUTOTRAILER,
            priority=NotificationPriority.HIGH,
            message=f"AutoTrailer square-off completed for {symbol}",
            data={
                'trigger_reason': trigger_reason,
                'pnl': pnl,
                'symbol': symbol,
                'action_required': 'switch_to_manual',
                'ui_actions': ['radio_button_to_manual', 'show_success_message']
            },
            source="AutoTrailer",
            target="TradeManagerUI",
            correlation_id=correlation_id or NotificationFactory._generate_correlation_id()
        )
    
    @staticmethod
    def autotrailer_square_off_error(
        error_msg: str, 
        symbol: str,
        correlation_id: Optional[str] = None
    ) -> Notification:
        """Create AutoTrailer square-off error notification"""
        return Notification(
            id=NotificationID.AUTOTRAILER_ERROR,
            category=NotificationCategory.ERROR,
            priority=NotificationPriority.CRITICAL,
            message=f"AutoTrailer square-off failed for {symbol} - Manual intervention required",
            data={
                'error_details': error_msg,
                'symbol': symbol,
                'action_required': 'manual_intervention',
                'ui_actions': ['radio_button_to_manual', 'show_error_dialog']
            },
            source="AutoTrailer",
            target="TradeManagerUI", 
            correlation_id=correlation_id or NotificationFactory._generate_correlation_id()
        )
    
    @staticmethod
    def autotrailer_activated(
        symbol: str,
        sl_price: float,
        target_price: float
    ) -> Notification:
        """Create AutoTrailer activation notification"""
        return Notification(
            id=NotificationID.AUTOTRAILER_ACTIVATED,
            category=NotificationCategory.AUTOTRAILER,
            priority=NotificationPriority.NORMAL,
            message=f"AutoTrailer activated for {symbol}",
            data={
                'symbol': symbol,
                'sl_price': sl_price,
                'target_price': target_price,
                'activated_at': time.time()
            },
            source="AutoTrailer",
            target="TradeManagerUI"
        )
    
    @staticmethod
    def autotrailer_deactivated(
        symbol: str,
        reason: str = "Manual deactivation"
    ) -> Notification:
        """Create AutoTrailer deactivation notification"""
        return Notification(
            id=NotificationID.AUTOTRAILER_DEACTIVATED,
            category=NotificationCategory.AUTOTRAILER,
            priority=NotificationPriority.NORMAL,
            message=f"AutoTrailer deactivated for {symbol}",
            data={
                'symbol': symbol,
                'reason': reason,
                'deactivated_at': time.time()
            },
            source="AutoTrailer",
            target="TradeManagerUI"
        )
    
    @staticmethod
    def autotrailer_sl_hit(
        symbol: str,
        sl_price: float,
        current_price: float
    ) -> Notification:
        """Create AutoTrailer stop-loss hit notification"""
        return Notification(
            id=NotificationID.AUTOTRAILER_SL_HIT,
            category=NotificationCategory.AUTOTRAILER,
            priority=NotificationPriority.HIGH,
            message=f"AutoTrailer SL hit for {symbol} at {current_price}",
            data={
                'symbol': symbol,
                'sl_price': sl_price,
                'current_price': current_price,
                'trigger_type': 'stop_loss'
            },
            source="AutoTrailer"
        )
    
    @staticmethod
    def autotrailer_target_hit(
        symbol: str,
        target_price: float,
        current_price: float
    ) -> Notification:
        """Create AutoTrailer target hit notification"""
        return Notification(
            id=NotificationID.AUTOTRAILER_TARGET_HIT,
            category=NotificationCategory.AUTOTRAILER,
            priority=NotificationPriority.HIGH,
            message=f"AutoTrailer target hit for {symbol} at {current_price}",
            data={
                'symbol': symbol,
                'target_price': target_price,
                'current_price': current_price,
                'trigger_type': 'target'
            },
            source="AutoTrailer"
        )
    
    # =============================================================================
    # SYSTEM NOTIFICATIONS
    # =============================================================================
    
    @staticmethod
    def system_error(
        component: str,
        error_msg: str,
        error_code: Optional[str] = None
    ) -> Notification:
        """Create system error notification"""
        return Notification(
            id=NotificationID.SYSTEM_ERROR,
            category=NotificationCategory.ERROR,
            priority=NotificationPriority.CRITICAL,
            message=f"System error in {component}",
            data={
                'component': component,
                'error_message': error_msg,
                'error_code': error_code,
                'requires_restart': False
            },
            source=component
        )
    
    @staticmethod
    def system_startup(component: str) -> Notification:
        """Create system startup notification"""
        return Notification(
            id=NotificationID.SYSTEM_STARTUP,
            category=NotificationCategory.SYSTEM,
            priority=NotificationPriority.NORMAL,
            message=f"{component} started successfully",
            data={
                'component': component,
                'startup_time': time.time()
            },
            source=component
        )
    
    @staticmethod
    def system_shutdown(component: str, reason: str = "Normal shutdown") -> Notification:
        """Create system shutdown notification"""
        return Notification(
            id=NotificationID.SYSTEM_SHUTDOWN,
            category=NotificationCategory.SYSTEM,
            priority=NotificationPriority.HIGH,
            message=f"{component} shutting down",
            data={
                'component': component,
                'reason': reason,
                'shutdown_time': time.time()
            },
            source=component
        )
    
    # =============================================================================
    # TRADING NOTIFICATIONS
    # =============================================================================
    
    @staticmethod
    def position_opened(
        symbol: str,
        quantity: int,
        price: float,
        action: str
    ) -> Notification:
        """Create position opened notification"""
        return Notification(
            id=NotificationID.POSITION_OPENED,
            category=NotificationCategory.TRADING,
            priority=NotificationPriority.NORMAL,
            message=f"Position opened: {action} {quantity} {symbol} @ {price}",
            data={
                'symbol': symbol,
                'quantity': quantity,
                'price': price,
                'action': action,
                'timestamp': time.time()
            },
            source="PFMU"
        )
    
    @staticmethod
    def position_closed(
        symbol: str,
        quantity: int,
        exit_price: float,
        pnl: float
    ) -> Notification:
        """Create position closed notification"""
        return Notification(
            id=NotificationID.POSITION_CLOSED,
            category=NotificationCategory.TRADING,
            priority=NotificationPriority.NORMAL,
            message=f"Position closed: {symbol} P&L: {pnl:.2f}",
            data={
                'symbol': symbol,
                'quantity': quantity,
                'exit_price': exit_price,
                'pnl': pnl,
                'timestamp': time.time()
            },
            source="PFMU"
        )
    
    @staticmethod
    def square_off_success(
        mode: str,
        trigger_source: str,
        pnl: float,
        symbol: Optional[str] = None
    ) -> Notification:
        """Create square-off success notification"""
        return Notification(
            id=NotificationID.SQUARE_OFF_SUCCESS,
            category=NotificationCategory.TRADING,
            priority=NotificationPriority.HIGH,
            message=f"Square-off successful: {mode} mode",
            data={
                'mode': mode,
                'trigger_source': trigger_source,
                'pnl': pnl,
                'symbol': symbol,
                'timestamp': time.time()
            },
            source="PFMU"
        )
    
    @staticmethod
    def square_off_error(
        mode: str,
        error_msg: str,
        trigger_source: str,
        symbol: Optional[str] = None
    ) -> Notification:
        """Create square-off error notification"""
        return Notification(
            id=NotificationID.SQUARE_OFF_ERROR,
            category=NotificationCategory.ERROR,
            priority=NotificationPriority.CRITICAL,
            message=f"Square-off failed: {mode} mode",
            data={
                'mode': mode,
                'error_message': error_msg,
                'trigger_source': trigger_source,
                'symbol': symbol,
                'timestamp': time.time(),
                'action_required': 'manual_intervention'
            },
            source="PFMU"
        )
    
    # =============================================================================
    # UI NOTIFICATIONS
    # =============================================================================
    
    @staticmethod
    def ui_radio_button_update(
        from_mode: str, 
        to_mode: str,
        reason: str
    ) -> Notification:
        """Create UI radio button update notification"""
        return Notification(
            id=NotificationID.UI_RADIO_BUTTON_UPDATE,
            category=NotificationCategory.UI,
            priority=NotificationPriority.NORMAL,
            message=f"Radio button switched: {from_mode} -> {to_mode}",
            data={
                'from_mode': from_mode,
                'to_mode': to_mode,
                'reason': reason,
                'timestamp': time.time()
            },
            source="TradeManagerUI",
            target="Portfolio"
        )
    
    @staticmethod
    def ui_show_message(
        message_type: str,
        title: str,
        content: str,
        priority: NotificationPriority = NotificationPriority.NORMAL
    ) -> Notification:
        """Create UI message display notification"""
        return Notification(
            id=NotificationID.UI_SHOW_MESSAGE,
            category=NotificationCategory.UI,
            priority=priority,
            message=f"UI message: {title}",
            data={
                'message_type': message_type,  # 'info', 'warning', 'error', 'success'
                'title': title,
                'content': content
            },
            target="TradeManagerUI"
        )
    
    # =============================================================================
    # MARKET DATA NOTIFICATIONS
    # =============================================================================
    
    @staticmethod
    def tick_update(
        symbol: str, 
        price: float, 
        tick_timestamp: float
    ) -> Notification:
        """Create tick update notification"""
        return Notification(
            id=NotificationID.TICK_UPDATE,
            category=NotificationCategory.MARKET_DATA,
            priority=NotificationPriority.LOW,
            message=f"Tick update: {symbol} @ {price}",
            data={
                'symbol': symbol,
                'price': price,
                'tick_timestamp': tick_timestamp
            },
            source="MarketData"
        )
    
    @staticmethod
    def market_data_connected(connection_info: Dict[str, Any]) -> Notification:
        """Create market data connection notification"""
        return Notification(
            id=NotificationID.MARKET_DATA_CONNECTED,
            category=NotificationCategory.MARKET_DATA,
            priority=NotificationPriority.NORMAL,
            message="Market data connected",
            data=connection_info,
            source="MarketData"
        )
    
    @staticmethod
    def market_data_disconnected(reason: str) -> Notification:
        """Create market data disconnection notification"""
        return Notification(
            id=NotificationID.MARKET_DATA_DISCONNECTED,
            category=NotificationCategory.MARKET_DATA,
            priority=NotificationPriority.HIGH,
            message="Market data disconnected",
            data={
                'reason': reason,
                'disconnected_at': time.time()
            },
            source="MarketData"
        )
    
    @staticmethod
    def feed_timeout(symbol: str, timeout_duration: float) -> Notification:
        """Create market data feed timeout notification"""
        return Notification(
            id=NotificationID.FEED_TIMEOUT,
            category=NotificationCategory.MARKET_DATA,
            priority=NotificationPriority.HIGH,
            message=f"Feed timeout for {symbol}",
            data={
                'symbol': symbol,
                'timeout_duration': timeout_duration,
                'detected_at': time.time()
            },
            source="MarketData"
        )


class NotificationFactoryValidator:
    """Validator for factory-created notifications"""
    
    @staticmethod
    def validate_autotrailer_data(symbol: str, price: float) -> bool:
        """Validate AutoTrailer notification data"""
        return bool(symbol and symbol.strip() and price > 0)
    
    @staticmethod
    def validate_trading_data(symbol: str, quantity: int, price: float) -> bool:
        """Validate trading notification data"""
        return bool(symbol and symbol.strip() and quantity > 0 and price > 0)
    
    @staticmethod
    def validate_system_data(component: str) -> bool:
        """Validate system notification data"""
        return bool(component and component.strip())