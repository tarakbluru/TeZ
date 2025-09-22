"""
File: man_pfmu.py
Author: [Tarakeshwar NC]
Date: January 15, 2024
Description: Manual Trading Manager - Coordination service for user-initiated trading operations
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
from typing import Dict, List, Any, Optional

from app_utils import app_logger
logger = app_logger.get_logger(__name__)

try:
    from .shared_classes import InstrumentInfo
    from .pfmu import PFMU
except Exception as e:
    logger.debug(traceback.format_exc())
    logger.error(("Import Error " + str(e)))
    sys.exit(1)


class ManualTradingManager:
    """
    Manual trading operations coordinator
    Manages order operations, display functions, and system lifecycle
    
    Responsibilities:
    - Manual trading operation coordination
    - Order management interfaces  
    - System lifecycle operations (excluding timer operations)
    - Market data access abstraction
    - Display operations coordination
    
    Note: All operations are delegated to the injected PFMU service.
    This manager provides enhanced error handling and context.
    """
    
    def __init__(self, pfmu_service: PFMU):
        """
        Initialize Manual Trading Manager with service injection
        
        Args:
            pfmu_service: Injected PFMU service for all trading operations
        """
        logger.info("Creating Manual Trading Manager with PFMU service injection...")
        
        # Service injection - no ownership
        self.pfmu = pfmu_service
        
        logger.info("Manual Trading Manager initialized with PFMU service injection")

    # =============================================================================
    # POSITION OPERATIONS - Direct delegation with context
    # =============================================================================

    def take_position(self, action: str, inst_info: InstrumentInfo, trade_price: float) -> int:
        """
        Execute position taking - direct delegation to PFMU service
        
        Args:
            action: Trading action ('B' for buy, 'S' for sell)  
            inst_info: Instrument information
            trade_price: Price for position taking
            
        Returns:
            int: Quantity taken
            
        Before: app_be.pfmu.take_position(...)
        After:  app_be.manual_trader.take_position(...)
        """
        try:
            result = self.pfmu.take_position(action, inst_info, trade_price)
            logger.info(f"Manual position taking completed: {action} {inst_info.symbol} @ {trade_price}, qty={result}")
            return result
        except Exception as e:
            logger.error(f"Manual position taking failed: {action} {inst_info.symbol} @ {trade_price} - {e}")
            self._handle_operation_error("take_position", e, action=action, symbol=inst_info.symbol, price=trade_price)
            raise

    def square_off_position(self, mode: str = "ALL", **kwargs) -> bool:
        """
        Execute manual square-off - direct delegation with context
        
        Args:
            mode: Square-off mode (typically "ALL")
            **kwargs: Additional parameters for square-off
            
        Returns:
            bool: True if square-off successful
            
        Before: app_be.pfmu.square_off_position(...)  
        After:  app_be.manual_trader.square_off_position(...)
        """
        try:
            # Store manual trading context for logging
            sq_off_triggered_by = kwargs.get('sq_off_triggered_by', 'manual_trader')
            trigger_reason = kwargs.get('trigger_reason', 'Manual square-off request')
            
            # Extract valid PFMU parameters only
            valid_pfmu_params = {
                'ul_index': kwargs.get('ul_index'),
                'ul_symbol': kwargs.get('ul_symbol'),
                'per': kwargs.get('per', 100),
                'inst_type': kwargs.get('inst_type'),
                'partial_exit': kwargs.get('partial_exit', False),
                'exit_flag': kwargs.get('exit_flag', True)
            }
            
            # Remove None values
            valid_pfmu_params = {k: v for k, v in valid_pfmu_params.items() if v is not None}
            
            result = self.pfmu.square_off_position(mode, **valid_pfmu_params)
            
            if result:
                logger.info(f"Manual square-off completed successfully: mode={mode}, triggered_by={sq_off_triggered_by}, reason={trigger_reason}")
            else:
                logger.error(f"Manual square-off failed with error: mode={mode}, triggered_by={sq_off_triggered_by}, reason={trigger_reason}")
                
            return result
        except Exception as e:
            logger.error(f"Manual square-off failed: mode={mode} - {e}")
            self._handle_operation_error("square_off_position", e, mode=mode, kwargs=kwargs)
            raise

    # =============================================================================
    # ORDER MANAGEMENT OPERATIONS - Direct delegation
    # =============================================================================

    def get_waiting_orders_count(self, ul_token: str = None) -> int:
        """Get count of active waiting orders"""
        try:
            return self.pfmu.get_waiting_orders_count(ul_token)
        except Exception as e:
            logger.error(f"Error getting waiting orders count: {e}")
            return 0

    def get_waiting_orders_list(self, ul_token: str = None) -> List[Dict]:
        """Get list of active waiting orders"""
        try:
            return self.pfmu.get_waiting_orders_list(ul_token)
        except Exception as e:
            logger.error(f"Error getting waiting orders list: {e}")
            return []

    def cancel_waiting_order(self, **kwargs) -> bool:
        """Cancel specific waiting order"""
        try:
            result = self.pfmu.cancel_waiting_order(**kwargs)
            logger.info(f"Manual order cancellation: {'successful' if result else 'failed'}")
            return result
        except Exception as e:
            logger.error(f"Manual order cancellation failed: {e}")
            self._handle_operation_error("cancel_waiting_order", e, kwargs=kwargs)
            return False

    def cancel_all_waiting_orders(self, **kwargs) -> Dict[str, Any]:
        """Cancel all waiting orders with detailed results"""
        try:
            # Add manual trading context for detailed logging
            kwargs['detailed_logging'] = kwargs.get('detailed_logging', True)
            
            result = self.pfmu.cancel_all_waiting_orders(**kwargs)
            
            success = result.get('success', False)
            cancelled_count = result.get('cancelled_count', 0)
            
            logger.info(f"Manual bulk order cancellation: {'successful' if success else 'failed'}, cancelled={cancelled_count}")
            
            return result
        except Exception as e:
            logger.error(f"Manual bulk order cancellation failed: {e}")
            self._handle_operation_error("cancel_all_waiting_orders", e, kwargs=kwargs)
            return {"success": False, "error": str(e), "cancelled_count": 0}

    # =============================================================================
    # DISPLAY OPERATIONS - Enhanced delegation
    # =============================================================================

    def show_portfolio(self) -> None:
        """Display current portfolio state"""
        try:
            self.pfmu.show()  # Delegate to PFMU portfolio display
            logger.info("Portfolio display completed via Manual Trading Manager")
        except Exception as e:
            logger.error(f"Portfolio display failed: {e}")
            self._handle_operation_error("show_portfolio", e)

    def show_waiting_orders(self) -> None:
        """Display waiting orders table"""
        try:
            self.pfmu.wo_table_show()  # Delegate to PFMU waiting orders display
            logger.info("Waiting orders display completed via Manual Trading Manager")
        except Exception as e:
            logger.error(f"Waiting orders display failed: {e}")
            self._handle_operation_error("show_waiting_orders", e)

    # =============================================================================
    # SYSTEM LIFECYCLE OPERATIONS - Coordination
    # =============================================================================

    def start_monitoring(self) -> None:
        """Start system monitoring - coordinate startup sequence"""
        try:
            self.pfmu.start_monitoring()  # Delegate to PFMU
            logger.info("System monitoring started via Manual Trading Manager")
        except Exception as e:
            logger.error(f"System monitoring startup failed: {e}")
            self._handle_operation_error("start_monitoring", e)
            raise

    def shutdown(self) -> None:
        """Shutdown system - coordinate cleanup sequence"""
        try:
            self.pfmu.hard_exit()  # Delegate to PFMU comprehensive cleanup
            logger.info("System shutdown completed via Manual Trading Manager")
        except Exception as e:
            logger.error(f"System shutdown error: {e}")
            self._handle_operation_error("shutdown", e)
            raise

    # =============================================================================
    # MARKET DATA ACCESS - Abstraction layer
    # =============================================================================

    def get_market_data(self) -> Dict[str, Any]:
        """Get current market data - abstracted access"""
        try:
            return {
                'ul_symbol': getattr(self.pfmu.diu, 'ul_symbol', 'UNKNOWN'),
                'token_info': getattr(self.pfmu.diu, '_ul_symbol', {}),
                'ltp': self.pfmu.diu.get_latest_tick() if self.pfmu.diu else None,
                'connection_status': getattr(self.pfmu.diu, 'is_connected', lambda: False)()
            }
        except Exception as e:
            logger.error(f"Market data access failed: {e}")
            self._handle_operation_error("get_market_data", e)
            return {
                'ul_symbol': 'ERROR',
                'token_info': {},
                'ltp': None,
                'connection_status': False
            }

    # =============================================================================
    # ERROR HANDLING AND VALIDATION
    # =============================================================================

    def _handle_operation_error(self, operation: str, error: Exception, **context) -> None:
        """Enhanced error handling with manual trading context"""
        error_details = {
            'operation': operation,
            'error': str(error),
            'error_type': type(error).__name__,
            'context': context,
            'timestamp': time.time()
        }
        
        logger.error(f"Manual Trading Manager - {operation} failed: {error}")
        logger.debug(f"Error details: {error_details}")
        
        # Could be extended to send error notifications via port system
        # self.notification_port.send_data({"type": "manual_trading_error", "data": error_details})

    def _validate_pfmu_service(self) -> bool:
        """Validate PFMU service availability before operations"""
        if not self.pfmu:
            logger.error("PFMU service not available for manual trading operations")
            return False
        return True

    def _execute_with_validation(self, operation_name: str, operation_func, *args, **kwargs):
        """Execute operation with service validation and error handling"""
        if not self._validate_pfmu_service():
            raise RuntimeError(f"PFMU service unavailable for {operation_name}")
        
        try:
            return operation_func(*args, **kwargs)
        except Exception as e:
            self._handle_operation_error(operation_name, e, args=args, kwargs=kwargs)
            raise

    # =============================================================================
    # ADDITIONAL UTILITY METHODS
    # =============================================================================

    def get_service_status(self) -> Dict[str, Any]:
        """Get status of underlying PFMU service and components"""
        try:
            return {
                'pfmu_available': self.pfmu is not None,
                'tiu_available': self.pfmu.tiu is not None if self.pfmu else False,
                'diu_available': self.pfmu.diu is not None if self.pfmu else False,
                'pmu_available': self.pfmu.pmu is not None if self.pfmu else False,
                'portfolio_available': self.pfmu.portfolio is not None if self.pfmu else False,
                'limit_orders_enabled': getattr(self.pfmu, 'limit_order_cfg', False) if self.pfmu else False,
                'timestamp': time.time()
            }
        except Exception as e:
            logger.error(f"Error getting service status: {e}")
            return {
                'pfmu_available': False,
                'error': str(e),
                'timestamp': time.time()
            }

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get portfolio summary information"""
        try:
            if not self.pfmu or not self.pfmu.portfolio:
                return {'available': False, 'error': 'Portfolio not available'}
                
            return {
                'available': True,
                'positions_count': len(self.pfmu.portfolio.stock_data),
                'waiting_orders_count': self.get_waiting_orders_count(),
                'current_pnl': self.pfmu.intra_day_pnl(),
                'timestamp': time.time()
            }
        except Exception as e:
            logger.error(f"Error getting portfolio summary: {e}")
            return {
                'available': False,
                'error': str(e),
                'timestamp': time.time()
            }