"""
File: app_be.py
Author: [Tarakeshwar NC] / Claude Code
Date: September 11, 2025
Description: Backend coordinator for TeZ trading platform with 3-port architecture and service management
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


import threading
from typing import NamedTuple, Dict, Any
import yaml
import time
from datetime import datetime

import app_mods
from app_utils import app_logger, SUCCESS, FAILURE
from app_mods.infra_error_handler import InfraErrorHandler
from app_mods.port_system import PortManager
from app_mods.base_processing_unit import ProcessingUnit
from app_mods.at_pfmu import AutoTrailerManager
from app_mods.man_pfmu import ManualTradingManager
from app_mods.sqofftime_pfmu import SquareOffTimeManager
from app_mods.shared_types import (
    SquareOff_Mode, SquareOff_InstType, SquareOff_Type, SquareOff_Info,
    MarketAction, MarketActionParams, UICommand, UICommandResponse, CommandStatus
)

logger = app_logger.get_logger(__name__)

class TeZ_App_BE_CreateConfig(NamedTuple):
    """Configuration for TeZ_App_BE"""
    ul_index: str
    instrument_info: str

class TeZ_App_BE(ProcessingUnit):
    """
    Active TeZ Application Backend with 3-Port Architecture and Command Processing
    
    Inherits from ProcessingUnit to handle UI commands directly,
    eliminating the need for complex port coordinator routing.
    """
    
    name = "APBE_3Port"
    __count = 0
    __componentType = app_mods.shared_classes.Component_Type.ACTIVE

    def __init__(self, cc_cfg: TeZ_App_BE_CreateConfig):
        """Initialize TeZ backend with 3-port architecture"""
        self.cc_cfg = cc_cfg
        TeZ_App_BE.__count += 1
        
        logger.info(f"Initializing Clean TeZ_App_BE with 3-port architecture...")
        
        # Initialize 3-port system FIRST (needed by PFMU)
        self.port_manager = PortManager()
        
        # Initialize core components (TIU, DIU, PFMU) and service managers
        self._initialize_core_components()
        
        # Initialize ProcessingUnit with command and response ports
        super().__init__(
            unit_id=f"TeZ_App_BE_{TeZ_App_BE.__count}",
            command_port=self.port_manager.command_port,
            response_port=self.port_manager.response_port
        )
        
        # Set up command handler
        self.set_cmd_handler(self._handle_ui_command)
        
        # Initialize data publishing and health monitoring
        self._data_thread = None
        self._health_thread = None
        self._last_pnl = 0.0
        self._last_ui_state = None
        self._data_updates_sent = 0
        self._start_time = time.time()
        
        # Prevent infinite ul_index feedback loop
        self._current_ul_index = None
        self._updating_ul_index = False
        
        # Track data feed connection state to prevent duplicate disconnects
        self._data_feed_connected = False

        # Network connectivity monitoring
        self._network_connected = True  # Assume connected initially
        self._last_network_check = 0.0  # Track last network check time

        # Load network monitoring configuration
        self._network_check_interval = app_mods.get_system_info("SYSTEM", "NETWORK_CHECK_INTERVAL")
        self._network_check_enabled = app_mods.get_system_info("SYSTEM", "NETWORK_CHECK_ENABLED") == "YES"

        # Setup auto square-off timing
        self._setup_auto_squareoff()
        
        # Start system monitoring via manual trader
        self.manual_trader.start_monitoring()
        time.sleep(0.1)
        self.diu.live_df_ctrl = app_mods.Ctrl.ON
        
        # Initialize with default underlying index (will be set by UI through ports)
        default_ul_index = cc_cfg.ul_index or app_mods.get_system_info("GUI_CONFIG", "RADIOBUTTON_DEF_VALUE")
        self._current_ul_index = default_ul_index  # Track current state
        logger.info(f"Default underlying index: {default_ul_index}")
        # NOTE: UI will set the actual index through SET_UL_INDEX command via ports
        
        # Start ProcessingUnit command processing FIRST
        self.start()
        
        # THEN start data publishing and health monitoring threads (after is_running = True)
        self._start_background_threads()
        
        TeZ_App_BE.__count += 1
        logger.info(f"Clean TeZ_App_BE initialization completed. Inst: {TeZ_App_BE.name} {TeZ_App_BE.__count} {TeZ_App_BE.__componentType}")
    
    def _initialize_core_components(self):
        """Initialize TIU, DIU, PFMU service, and service managers"""
        logger.info("Initializing core components (TIU, DIU, PFMU) and service managers...")

        # Create error handler service first
        self.infra_error_handler = self._create_infra_error_handler()

        # Create TIU
        self.tiu = self._create_tiu()

        # Create DIU
        master_file = self.tiu.scripmaster_file
        self.diu = self._create_diu(master_file)

        # Create PFMU service (hidden from app_be)
        pfmu_service = self._create_pfmu_service()

        # Create service managers with dependency injection
        self.manual_trader = ManualTradingManager(pfmu_service)
        self.autotrailer = AutoTrailerManager(pfmu_service, self.port_manager.response_port)
        self.timer_manager = SquareOffTimeManager(pfmu_service, self.port_manager.response_port)

        # No direct PFMU access - all operations through service managers
        logger.info("Service-oriented architecture initialized successfully")

        # Check if all components are successfully initialized and send initial GREEN notification
        from app_mods.infra_error_handler import ConnectionStatus
        if self.infra_error_handler.get_current_status() == ConnectionStatus.CONNECTED:
            self.infra_error_handler.send_initial_success_notification()
            logger.info("Initial system readiness notification sent")

    def _create_infra_error_handler(self):
        """Create infrastructure error handler service"""
        logger.info("Creating InfraErrorHandler service with response port")
        return InfraErrorHandler(
            notification_port=self.port_manager.response_port
        )

    def _create_tiu(self):
        """Create Trading Interface Unit"""
        dl_filepath = app_mods.get_system_info("SYSTEM", "DL_FOLDER")
        logger.info(f'dl_filepath: {dl_filepath}')

        session_id = None
        if app_mods.get_system_info("SYSTEM","VIRTUAL_ENV") == 'NO':
            tiu_cred_file = app_mods.get_system_info("TIU", "CRED_FILE")
            tiu_token_file = app_mods.get_system_info("TIU", "TOKEN_FILE")
            logger.info(f'token_file: {tiu_token_file}')

            tiu_save_token_file_cfg = app_mods.get_system_info("TIU", "SAVE_TOKEN_FILE_CFG")
            tiu_save_token_file = app_mods.get_system_info("TIU", "SAVE_TOKEN_FILE_NAME")
            virtual_env = False
            if app_mods.get_system_info("TIU", "USE_GSHEET_TOKEN") == 'YES':
                # Reading the Cred file to get the info. about the range where
                # session ID is available
                with open(tiu_cred_file) as f:
                    cred = yaml.load(f, Loader=yaml.FullLoader)

                gsheet_info = app_mods.get_system_info("TIU", "GOOGLE_SHEET")
                logger.debug(gsheet_info)
                gsheet_client_json = gsheet_info['CLIENT_SECRET']
                url = gsheet_info['URL']
                sheet_name = gsheet_info['NAME']
                if gsheet_client_json != '' and url != '' and sheet_name != '':
                    session_id = app_mods.get_session_id_from_gsheet(
                                            cred,
                                            gsheet_client_json=gsheet_client_json,
                                            url=url,
                                            sheet_name=sheet_name
                                        )
        else:
            tiu_token_file = None
            tiu_cred_file = app_mods.get_system_info("TIU", "VIRTUAL_ENV_CRED_FILE")
            tiu_save_token_file_cfg = app_mods.get_system_info("TIU", "VIRTUAL_ENV_SAVE_TOKEN_FILE_CFG")
            tiu_save_token_file = app_mods.get_system_info("TIU", "VIRTUAL_ENV_SAVE_TOKEN_FILE_NAME")
            virtual_env = True

        tcc = app_mods.Tiu_CreateConfig(inst_prefix='tiu', cred_file=tiu_cred_file,
                                        susertoken=session_id,
                                        token_file=tiu_token_file,
                                        use_pool=False,
                                        master_file=None,
                                        dl_filepath=dl_filepath,
                                        notifier=None,
                                        save_tokenfile_cfg=tiu_save_token_file_cfg,
                                        save_token_file=tiu_save_token_file,
                                        test_env=virtual_env,
                                        error_handler=self.infra_error_handler)

        logger.debug(f'tcc:{str(tcc)}')
        tiu = app_mods.Tiu(tcc=tcc)

        logger.info('Creating dataframe for quick access')
        instruments = app_mods.get_system_info("TRADE_DETAILS", "INSTRUMENT_INFO")

        symbol_exp_date_pairs = []
        for symbol, info in instruments.items():
            logger.debug(f"Instrument: {symbol}")
            if info['EXCHANGE'] == 'NFO':
                symbol = info['SYMBOL']
                exp_date = info['EXPIRY_DATE']
                symbol_exp_date_pairs.append((symbol, exp_date))

        if len(symbol_exp_date_pairs):
            tiu.compact_search_file(symbol_exp_date_pairs)

        tiu.create_sym_token_tsym_q_access(symbol_list=None, instruments=instruments)

        return tiu
    
    def _create_diu(self, master_file):
        """Create Data Interface Unit"""
        # Create simple data port for DIU output
        from app_mods.shared_classes import ExtSimpleQueue, SimpleDataPort
        from threading import Event
        
        data_q = ExtSimpleQueue()
        evt = Event()
        diu_output_port = SimpleDataPort(data_q=data_q, evt=evt)
        
        if app_mods.get_system_info("SYSTEM","VIRTUAL_ENV") == 'NO':
            diu_cred_file = app_mods.get_system_info("DIU", "CRED_FILE")
            diu_token_file = app_mods.get_system_info("DIU", "TOKEN_FILE")
            logger.info(f'token_file: {diu_token_file}')
            diu_save_token_file_cfg = app_mods.get_system_info("DIU", "SAVE_TOKEN_FILE_CFG")
            diu_save_token_file = app_mods.get_system_info("DIU", "SAVE_TOKEN_FILE_NAME")
            virtual_env = False
            logger.info (f'Real Environment')
        else:
            logger.info (f'Virtual Environment')
            diu_cred_file = app_mods.get_system_info("DIU", "VIRTUAL_ENV_CRED_FILE")
            diu_token_file = app_mods.get_system_info("DIU", "VIRTUAL_ENV_TOKEN_FILE")
            logger.info(f'token_file: {diu_token_file}')
            diu_save_token_file_cfg = False
            diu_save_token_file = None
            virtual_env = False

        tr_folder = app_mods.get_system_info("SYSTEM", "TR_FOLDER")
        tr = True if app_mods.get_system_info("SYSTEM", "TR").upper() == 'YES' else False

        dcc = app_mods.Diu_CreateConfig(inst_prefix='diu', cred_file=diu_cred_file,
                                        susertoken=None,
                                        token_file=diu_token_file,
                                        use_pool=False,
                                        master_file=master_file,
                                        dl_filepath=None,
                                        notifier=None,
                                        save_tokenfile_cfg=diu_save_token_file_cfg,
                                        save_token_file=diu_save_token_file,
                                        out_port=diu_output_port,
                                        tr_folder=tr_folder,
                                        tr_flag=tr,
                                        test_env=virtual_env,
                                        error_handler=self.infra_error_handler)

        logger.debug(f'dcc:{str(dcc)}')
        try:
            diu = app_mods.Diu(dcc=dcc)
        except ValueError:
            raise
        except Exception:
            logger.error (f'diu not created ')
            raise

        diu.ul_symbol = app_mods.get_system_info("GUI_CONFIG", "RADIOBUTTON_DEF_VALUE")
        
        # Store output port for PFMU
        diu.live_data_output_port = diu_output_port
        
        return diu
    
    def _create_pfmu_service(self):
        """Create PFMU service - hidden from application layer"""
        pfmu_ord_file = app_mods.get_system_info("BKU", "TRADES_RECORD_FILE")
        pf_file = app_mods.get_system_info("PFMU", "PF_RECORD_FILE")
        mo = app_mods.get_system_info("MARKET_TIMING", "OPEN")
        
        pfmu_cc = app_mods.PFMU_CreateConfig(
            tiu=self.tiu,
            diu=self.diu,
            rec_file=pfmu_ord_file,
            mo=mo,
            pf_file=pf_file,
            reset=False,
            port=self.diu.live_data_output_port,
            response_port=self.port_manager.response_port,  # For sending system sqoff notifications
            limit_order_cfg=getattr(self.cc_cfg, 'limit_order_cfg', True),
            disable_price_entry_cb=getattr(self.cc_cfg, 'disable_price_entry_cb', lambda: True),
            error_handler=self.infra_error_handler
        )
        
        return app_mods.PFMU(pfmu_cc=pfmu_cc)
    
    def _setup_auto_squareoff(self):
        """Setup automatic square-off timing"""
        auto_sq_off_time_str = app_mods.get_system_info("SYSTEM", "SQ_OFF_TIMING")
        current_time = datetime.now().time()
        logger.info(f'auto_sq_off_time: {auto_sq_off_time_str}, Current time: {current_time}')
        
        hr = datetime.strptime(auto_sq_off_time_str, '%H:%M').hour
        minute = datetime.strptime(auto_sq_off_time_str, '%H:%M').minute
        self._sq_off_time = datetime.now().replace(hour=hr, minute=minute, second=0, microsecond=0)
        
        from threading import Timer
        import app_utils as utils
        
        rm_durn = utils.calcRemainingDuration(self._sq_off_time.hour, self._sq_off_time.minute) + 1.0  # Add 1 sec buffer for timer precision
        if (rm_durn > 1.0):  # Ensure we have more than just the buffer time
            self.sqoff_timer = Timer(rm_durn, self._square_off_position_timer)
        else:
            self.sqoff_timer = None
            
        if self.sqoff_timer is not None:
            self.sqoff_timer.name = "SQ_OFF_TIMER"
            self.sqoff_timer.daemon = True
            self.sqoff_timer.start()
        else:
            logger.debug("Square off Timer Is not Created.. as Time has elapsed ")
    
    def _square_off_position_timer(self):
        """Timer callback for automatic square-off"""
        current_time_display = datetime.now().strftime("%H:%M:%S")  # Show seconds for accurate timing display
        current_time_timer = datetime.now().strftime("%H:%M")  # Timer manager expects HH:MM format
        logger.info(f'{current_time_display} !! Auto Square Off Time !!')

        # Execute timer square-off via SquareOff Timer Manager - handles execution + push notifications
        try:
            if self.timer_manager:
                success = self.timer_manager.execute_timer_squareoff(current_time_timer)
                if success:
                    logger.info("Timer square-off completed successfully via SquareOff Timer Manager")
                else:
                    logger.warning("Timer square-off failed - positions may remain open")
            else:
                logger.error("SquareOff Timer Manager not available")
        except Exception as e:
            logger.error(f"Error during timer square-off execution: {e}")
    
    @property
    def ul_index(self):
        """Get current underlying index from DIU"""
        return getattr(self.diu, 'ul_symbol', None)

    def set_ul_index_via_port(self, ul_index: str):
        """
        Set underlying index via port system (recommended approach)
        This mimics what the UI should do - send command through port
        """
        if self.port_manager:
            # Send command through port system
            self.port_manager.command_port.send_command("SET_UL_INDEX", {"ul_index": ul_index})
            logger.info(f"ul_index change sent via port: {ul_index}")
        else:
            logger.warning("Port manager not available, falling back to direct access")
            self.diu.ul_symbol = ul_index
    
    def get_port_manager(self):
        """Get the port manager for UI integration"""
        return self.port_manager
    
    def data_feed_connect(self):
        """Connect to data feed"""
        try:
            if self._data_feed_connected:
                logger.debug("Data feed already connected, skipping")
                return SUCCESS
                
            result = self.diu.connect_to_data_feed_servers()
            if result:
                self._data_feed_connected = True
                # Note: PFMU monitoring already started during initialization
                logger.info("Data feed connected successfully")
                return SUCCESS
            else:
                logger.error("Data feed connection failed")
                return FAILURE
        except Exception as e:
            logger.error(f"Error connecting data feed: {e}")
            return FAILURE
    
    def data_feed_disconnect(self):
        """Disconnect from data feed with duplicate prevention"""
        try:
            if not self._data_feed_connected:
                logger.debug("Data feed already disconnected, skipping")
                return
                
            if self.diu:
                self.diu.disconnect_data_feed_servers()
                self._data_feed_connected = False
                logger.info("Data feed disconnected")
        except Exception as e:
            logger.error(f"Error disconnecting data feed: {e}")
    
    def get_latest_tick(self):
        """Get latest tick data"""
        try:
            # Get market data via manual trader (abstracted access)
            market_data = self.manual_trader.get_market_data()
            ul_index = market_data.get('ul_symbol', 'UNKNOWN')
            token_info = market_data.get('token_info', {})
            current_token = token_info.get('token', 'UNKNOWN')
            
            ltp = market_data.get('ltp')
            
            # logger.debug(f"get_latest_tick: ul_index={ul_index}, token={current_token}, ltp={ltp}")
            return ltp
        except Exception as e:
            logger.error(f"Error getting latest tick: {e}")
            return None
    
    @staticmethod
    def get_instrument_info(exchange, ul_inst):
        """Get instrument info for given exchange and underlying index - matches reference implementation"""
        instruments = app_mods.get_system_info("TRADE_DETAILS", "INSTRUMENT_INFO")
        instrument_info = None
        for inst_id, info in instruments.items():
            logger.debug(f"Instrument: {inst_id}")
            if info['EXCHANGE'] == exchange and info['UL_INDEX'] == ul_inst:
                instrument_info = info
                break
        return instrument_info
    
    def market_action(self, action: str, trade_price: float, ui_qty: int):
        """Execute market action (Buy/Short) - matches reference implementation"""
        try:
            # Get instrument info like reference implementation
            ul_index = getattr(self.diu, 'ul_symbol', 'NIFTY')
            exch = app_mods.get_system_info("TRADE_DETAILS", "EXCHANGE")
            
            # Check for high NIFTY price threshold like reference
            if ul_index == 'NIFTY' and trade_price is not None and trade_price >= 30000.0:
                logger.warning(f"NIFTY trade price {trade_price} seems too high - please verify")
            
            if ul_index == 'NIFTY BANK' and trade_price is not None and trade_price <= 30000.0:
                raise ValueError(f"Index: {ul_index}:{trade_price} Value seems to be for Nifty")
                
            # Use the reference implementation approach
            inst_info_dict = TeZ_App_BE.get_instrument_info(exch, ul_index)
            
            if not inst_info_dict:
                logger.error(f"No instrument configuration found for exchange={exch}, ul_index={ul_index}")
                return 0
            
            # Convert keys to lowercase like reference implementation
            inst_info = {key.lower(): value for key, value in inst_info_dict.items()}
            inst_info['use_gtt_oco'] = True if inst_info['order_prod_type'].lower() == 'o' else False
            
            # Set quantity if provided
            if ui_qty:
                inst_info['quantity'] = ui_qty
                
            # Convert to InstrumentInfo object
            inst_info = app_mods.shared_classes.InstrumentInfo(**inst_info)

            # Block orders if auto-trader target/SL already hit today
            # Note: Check state even if auto-trader is currently inactive - state persists after deactivation
            if self.autotrailer:
                at_state = self.autotrailer.get_autotrailer_ui_state()
                if at_state.target_hit or at_state.sl_hit or at_state.sq_off_done:
                    logger.warning(f"Order blocked: Auto-trader already hit target/SL today (target_hit={at_state.target_hit}, sl_hit={at_state.sl_hit}, sq_off_done={at_state.sq_off_done})")
                    logger.info(f"Market action {action} blocked: Auto-trader target/SL already hit today")
                    return 0  # Return 0 qty taken

            # Use manual trader for position taking
            qty_taken = self.manual_trader.take_position(action=action, inst_info=inst_info, trade_price=trade_price)
            
            logger.info(f"Market action {action} completed: qty_taken={qty_taken}")
            return qty_taken
            
        except Exception as e:
            logger.error(f"Error executing market action {action}: {e}")
            return 0
    
    def square_off_position(self, sq_off_info):
        """Execute square-off position"""
        try:
            # Handle both dict and SquareOff_Info object via manual trader
            if isinstance(sq_off_info, dict):
                self.manual_trader.square_off_position(
                    mode=sq_off_info.get('mode', 'ALL'),
                    ul_index=sq_off_info.get('ul_index'),
                    per=sq_off_info.get('per', 100),
                    inst_type=sq_off_info.get('inst_type', 'ALL'),
                    partial_exit=sq_off_info.get('partial_exit', False),
                    exit_flag=sq_off_info.get('exit_flag', False)
                )
            else:
                # SquareOff_Info object
                self.manual_trader.square_off_position(
                    mode=getattr(sq_off_info.mode, 'name', sq_off_info.mode),
                    ul_index=sq_off_info.ul_index,
                    per=sq_off_info.per,
                    inst_type=getattr(sq_off_info.inst_type, 'name', sq_off_info.inst_type),
                    partial_exit=(sq_off_info.type == SquareOff_Type.PARTIAL),
                    exit_flag=False
                )
            
            # Show console records after successful square-off execution
            try:
                logger.info("Displaying updated records after square-off...")
                self.manual_trader.show_portfolio()
            except Exception as display_error:
                logger.error(f"Error displaying records after square-off: {display_error}")
                
        except Exception as e:
            logger.error(f"Error in square-off position: {e}")
    
    def enhanced_square_off_with_cancellation(self):
        """Enhanced square-off with waiting order cancellation - matches reference implementation"""
        try:
            logger.info("Starting enhanced square-off with waiting order cancellation...")
            
            # Phase 1: Waiting order cancellation (if enabled)
            cancelled_orders = 0
            timing_seconds = 0.0
            
            if getattr(self.cc_cfg, 'limit_order_cfg', True):
                logger.info("Starting waiting order cancellation process...")
                
                # Get count before cancellation via manual trader
                waiting_count_before = self.manual_trader.get_waiting_orders_count()
                logger.info(f"Found {waiting_count_before} waiting orders to cancel")
                
                if waiting_count_before > 0:
                    import time
                    start_time = time.time()
                    
                    # Cancel orders with detailed logging via manual trader
                    cancellation_result = self.manual_trader.cancel_all_waiting_orders(
                        exit_flag=False, 
                        show_table=True,
                        detailed_logging=True
                    )
                    
                    end_time = time.time()
                    timing_seconds = end_time - start_time
                    logger.info(f"Cancellation process took {timing_seconds:.2f} seconds")
                    
                    # Verify cancellation via manual trader
                    waiting_count_after = self.manual_trader.get_waiting_orders_count()
                    logger.info(f"Verification: {waiting_count_after} waiting orders remain")
                    
                    if not cancellation_result.get('success', False):
                        failed_count = cancellation_result.get('failed', 0)
                        error_msg = f"Failed to cancel {failed_count} waiting orders. Aborting square-off for safety."
                        logger.error(error_msg)
                        return {"success": False, "error": error_msg, "cancelled_orders": 0}
                    
                    if waiting_count_after > 0:
                        error_msg = f"CRITICAL: {waiting_count_after} waiting orders still active after cancellation!"
                        logger.error(error_msg)
                        return {"success": False, "error": error_msg, "cancelled_orders": cancellation_result.get('cancelled', 0)}
                    
                    cancelled_orders = cancellation_result.get('cancelled', 0)
                    logger.info("Proceeding with square-off operation...")
                else:
                    logger.info("No waiting orders to cancel - proceeding directly with square-off")
            else:
                logger.info("Limit order configuration disabled - proceeding directly with square-off")
            
            # Phase 2: ALWAYS proceed with actual position square-off
            try:
                logger.info("Executing position square-off...")
                exch = app_mods.get_system_info("TRADE_DETAILS", "EXCHANGE")
                ul_index = getattr(self.diu, 'ul_symbol', 'NIFTY')
                
                sqoff_info = SquareOff_Info(
                    mode=SquareOff_Mode.SELECT, 
                    per=100.0, 
                    ul_index=ul_index, 
                    exch=exch,
                    inst_type=SquareOff_InstType.ALL,
                    type=SquareOff_Type.FULL
                )
                
                self.square_off_position(sqoff_info)
                
                logger.info("Enhanced square-off completed successfully")
                return {
                    "success": True, 
                    "message": "Enhanced square-off completed successfully",
                    "cancelled_orders": cancelled_orders,
                    "timing_seconds": timing_seconds
                }
                
            except Exception as e:
                logger.error(f"Error in square-off operation: {e}")
                return {
                    "success": False, 
                    "error": f"Square-off failed: {str(e)}", 
                    "cancelled_orders": cancelled_orders
                }
                
        except Exception as e:
            logger.error(f"Error in enhanced square-off: {e}")
            return {"success": False, "error": str(e)}
    
    def simple_square_off(self):
        """Simple square-off without cancellation"""
        try:
            logger.info("Executing simple square-off...")
            # Use the regular square_off_position method
            exch = app_mods.get_system_info("TRADE_DETAILS", "EXCHANGE")
            sqoff_info = SquareOff_Info(
                mode=SquareOff_Mode.ALL, 
                per=100.0, 
                ul_index=None, 
                exch=exch,
                inst_type=SquareOff_InstType.ALL,
                type=SquareOff_Type.FULL
            )
            self.square_off_position(sqoff_info)
            return {"success": True, "message": "Simple square-off completed"}
        except Exception as e:
            logger.error(f"Error in simple square-off: {e}")
            return {"success": False, "error": str(e)}
    
    def gen_action(self, action: str, data=None):
        """General action handler - matches reference implementation"""
        try:
            if action == 'cancel_waiting_order':
                # Parse row ID(s) from data - supports single ID or range
                if '-' in str(data):
                    try:
                        start, end = map(int, str(data).split('-'))
                        if start <= end:
                            row_id = range(start, end + 1)
                        else:
                            row_id = range(end, start + 1)
                    except ValueError:
                        logger.error("Invalid range format")
                        return None
                else:
                    try:
                        row_id = [int(data)]
                    except (ValueError, TypeError):
                        logger.error("Invalid row ID format")
                        return None
                
                logger.info(f'Cancelling row_id: {list(row_id)}')
                
                # Cancel each row (convert to 0-based index) via manual trader
                for rn in row_id:
                    self.manual_trader.cancel_waiting_order(id=rn-1)
                
                # Refresh waiting orders table after cancellation via manual trader
                self.manual_trader.show_waiting_orders()
                
            else:
                logger.warning(f"Unknown general action: {action}")
        except Exception as e:
            logger.error(f"Error in general action {action}: {e}")
    
    def show_records(self):
        """Display records"""
        try:
            self.manual_trader.show_portfolio()
        except Exception as e:
            logger.error(f"Error showing records: {e}")
    
    def exit_app_be(self):
        """Clean exit of application backend with proper shutdown sequence"""
        logger.info("Exiting TeZ_App_BE...")
        
        try:
            # PHASE 1: Stop data source FIRST to prevent new data from flowing
            logger.info("Phase 1: Disconnecting data feed to stop data source...")
            self.data_feed_disconnect()
            
            # PHASE 2: Stop service managers and data processing components  
            logger.info("Phase 2: Stopping service managers...")
            
            # Shutdown service managers in proper order
            if self.autotrailer:
                logger.info("Shutting down AutoTrailer Manager...")
                self.autotrailer.shutdown()
                
            if self.timer_manager:
                logger.info("Shutting down SquareOff Timer Manager...")
                self.timer_manager.shutdown()
                
            if self.manual_trader:
                logger.info("Shutting down Manual Trading Manager and PFMU service...")
                self.manual_trader.shutdown()  # This will call PFMU hard_exit()
            
            # PHASE 3: Stop command processing and background operations
            logger.info("Phase 3: Stopping ProcessingUnit command processing...")
            self.stop()
            
            # PHASE 4: Wait for background threads to finish cleanly
            logger.info("Phase 4: Waiting for background threads to complete...")
            if self._data_thread and self._data_thread.is_alive():
                logger.debug("Waiting for data publishing thread...")
                self._data_thread.join(timeout=2.0)
            if self._health_thread and self._health_thread.is_alive():
                logger.debug("Waiting for health monitoring thread...")
                self._health_thread.join(timeout=2.0)
            
            logger.info("TeZ_App_BE exit completed - all phases successful")
            
        except Exception as e:
            logger.error(f"Error during TeZ_App_BE exit: {e}")
    
    def get_health_status(self):
        """Get system health status"""
        try:
            return {
                "status": "running" if self.is_running else "stopped",
                "uptime": time.time() - self._start_time,
                "data_updates_sent": self._data_updates_sent,
                "last_pnl": self._last_pnl,
                "ul_index": getattr(self.diu, 'ul_symbol', 'UNKNOWN'),
                "threads": {
                    "processing_unit_running": self.is_running,
                    "data_thread_alive": self._data_thread.is_alive() if self._data_thread else False,
                    "health_thread_alive": self._health_thread.is_alive() if self._health_thread else False
                },
                "service_managers_active": self.manual_trader is not None,
                "diu_connected": self.diu and hasattr(self.diu, 'live_df_ctrl')
            }
        except Exception as e:
            logger.error(f"Error getting health status: {e}")
            return {"status": "error", "error": str(e)}
    
    def _handle_ui_command(self, command: str, data: Any, request_id: int) -> Dict[str, Any]:
        """Handle UI commands sent through ProcessingUnit ports"""
        try:
            logger.info(f"[BACKEND] Processing UI command: {command} (ID: {request_id}) with data: {data}")
            
            if command == "SET_UL_INDEX":
                ul_index = data.get("ul_index") if isinstance(data, dict) else data
                if ul_index:
                    # Prevent infinite feedback loop
                    if self._updating_ul_index or self._current_ul_index == ul_index:
                        logger.debug(f"Skipping ul_index update - already {ul_index} or updating in progress")
                        return {"success": True, "command": command, "request_id": request_id, "ul_index": ul_index, "skipped": True}
                    
                    try:
                        self._updating_ul_index = True
                        self._current_ul_index = ul_index
                        self.diu.ul_symbol = ul_index
                        logger.info(f"Updated underlying index to: {ul_index}")
                        return {"success": True, "command": command, "request_id": request_id, "ul_index": ul_index}
                    finally:
                        self._updating_ul_index = False
                else:
                    return {"success": False, "command": command, "request_id": request_id, "error": "Invalid ul_index"}
            
            elif command == "MARKET_ACTION":
                if isinstance(data, dict):
                    action = data.get("action")
                    trade_price = data.get("trade_price", 0.0)
                    ui_qty = data.get("ui_qty", 0)
                    logger.info(f"[BACKEND] MARKET_ACTION {action} started (ID: {request_id}) qty={ui_qty} price={trade_price}")
                    result = self.market_action(action, trade_price, ui_qty)
                    response = {"success": True, "command": command, "request_id": request_id, "result": result}
                    logger.info(f"[BACKEND] MARKET_ACTION {action} response ready (ID: {request_id}) success=True result={result}")
                    return response
                else:
                    return {"success": False, "command": command, "request_id": request_id, "error": "Invalid data format"}
            
            elif command == "SQUARE_OFF":
                result = self.square_off_position(data)
                return {"success": True, "command": command, "request_id": request_id, "result": "Square-off initiated"}
            
            elif command == "ENHANCED_SQUARE_OFF":
                result = self.enhanced_square_off_with_cancellation()
                return {"success": True, "command": command, "request_id": request_id, "result": result}
            
            elif command == "SIMPLE_SQUARE_OFF":
                result = self.simple_square_off()
                return {"success": True, "command": command, "request_id": request_id, "result": result}
            
            elif command == "GET_LATEST_TICK":
                ltp = self.get_latest_tick()
                return {"success": True, "command": command, "request_id": request_id, "ltp": ltp}
            
            elif command == "DATA_FEED_CONNECT":
                result = self.data_feed_connect()
                return {"success": result == SUCCESS, "command": command, "request_id": request_id, "result": result}
            
            elif command == "DATA_FEED_DISCONNECT":
                self.data_feed_disconnect()
                return {"success": True, "command": command, "request_id": request_id, "result": "Disconnected"}
            
            elif command == "GET_HEALTH_STATUS":
                status = self.get_health_status()
                return {"success": True, "command": command, "request_id": request_id, "status": status}
            
            elif command == "SHOW_RECORDS":
                self.show_records()
                return {"success": True, "command": command, "request_id": request_id, "result": "Records displayed"}
            
            elif command == "CANCEL_WAITING_ORDER":
                # Extract row ID from data dict
                row_data = data.get("data") if isinstance(data, dict) else data
                logger.info(f"CANCEL_WAITING_ORDER received - original data: {data}, extracted row_data: {row_data}")
                self.gen_action("cancel_waiting_order", row_data)
                return {"success": True, "command": command, "request_id": request_id, "result": "Cancel order initiated"}
            
            elif command == "ACTIVATE_AUTO":
                try:
                    if isinstance(data, dict):
                        # Extract auto trailer parameters
                        auto_data = app_mods.shared_classes.AutoTrailerData(
                            sl=data.get("sl", -50.0),
                            target=data.get("target", 100.0),
                            mvto_cost=data.get("mvto_cost", 25.0),
                            trail_after=data.get("trail_after", 50.0),
                            trail_by=data.get("trail_by", 10.0)
                        )
                        # Activate auto-trading via AutoTrailer Manager
                        result = self.autotrailer.activate_auto_trading(auto_data)
                        logger.info(f"Auto trading activation result: {result}")
                        return {"success": result, "command": command, "request_id": request_id, "result": {"status": "success" if result else "failed"}}
                    else:
                        return {"success": False, "command": command, "request_id": request_id, "error": "Invalid data format for auto activation"}
                except Exception as e:
                    logger.error(f"Error activating auto trading: {e}")
                    return {"success": False, "command": command, "request_id": request_id, "error": str(e)}
            
            elif command == "DEACTIVATE_AUTO":
                try:
                    # Deactivate auto-trading via AutoTrailer Manager
                    result = self.autotrailer.deactivate_auto_trading()
                    logger.info(f"Auto trading deactivated: {result}")
                    return {"success": result, "command": command, "request_id": request_id, "result": {"status": "success" if result else "failed"}}
                except Exception as e:
                    logger.error(f"Error deactivating auto trading: {e}")
                    return {"success": False, "command": command, "request_id": request_id, "error": str(e)}
            
            else:
                logger.warning(f"Unknown command: {command}")
                return {"success": False, "command": command, "request_id": request_id, "error": f"Unknown command: {command}"}
                
        except Exception as e:
            logger.error(f"Error handling command {command}: {e}")
            return {"success": False, "command": command, "request_id": request_id, "error": str(e)}
    
    def _start_background_threads(self):
        """Start data publishing and health monitoring threads"""
        logger.info("Starting background threads for data publishing and health monitoring...")
        
        # Start data publishing thread
        self._data_thread = threading.Thread(target=self._data_publishing_loop, daemon=True)
        self._data_thread.name = "TeZ_App_BE-DataPublisher"
        self._data_thread.start()
        
        # Start health monitoring thread
        self._health_thread = threading.Thread(target=self._health_monitoring_loop, daemon=True)
        self._health_thread.name = "TeZ_App_BE-HealthMonitor"
        self._health_thread.start()

        logger.info("Background threads started successfully")

    def _check_network_connectivity(self):
        """Check network connectivity using socket connection to Google DNS"""
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)  # 1 second timeout for faster network restoration detection
            result = sock.connect_ex(("8.8.8.8", 53))  # Google DNS, port 53
            sock.close()
            return result == 0  # 0 means success
        except Exception as e:
            logger.debug(f"Network connectivity check failed: {e}")
            return False

    def _check_and_report_network_status(self):
        """Check network connectivity and report changes (separate from broker status)"""
        try:
            current_network_connected = self._check_network_connectivity()

            # Only report if state changed
            if current_network_connected != self._network_connected:
                if current_network_connected:
                    logger.debug("Network connectivity restored - sending network notification")
                    self.infra_error_handler.send_network_status_notification(True)
                else:
                    logger.debug("Network connectivity lost - sending network notification")
                    self.infra_error_handler.send_network_status_notification(False)

                # Update stored state
                self._network_connected = current_network_connected

        except Exception as e:
            logger.error(f"Error in network status reporting: {e}")

    def _data_publishing_loop(self):
        """Background thread that publishes PFMU P&L data to UI"""
        logger.info("Data publishing loop started")
        
        data_publishing_interval = 0.5  # 500ms
        pnl_update_counter = 0
        PNL_UPDATE_EVERY = 2  # Every 1000ms
        health_check_counter = 0
        HEALTH_CHECK_EVERY = 1000  # Log health every 500 seconds (1000 * 0.5s)
        
        while self.is_running:
            try:
                pnl_update_counter += 1
                health_check_counter += 1
                
                # Publish P&L data continuously - NO CONDITIONS SHOULD STOP THIS
                if pnl_update_counter >= PNL_UPDATE_EVERY:
                    self._publish_pnl_data()
                    pnl_update_counter = 0
                
                # Periodic health logging to track publishing status
                if health_check_counter >= HEALTH_CHECK_EVERY:
                    # Get position status via service managers
                    portfolio_summary = self.manual_trader.get_portfolio_summary() if self.manual_trader else {}
                    remaining_positions = portfolio_summary.get('current_qty', 0)
                    logger.debug(f"P&L Publishing Active: updates_sent={self._data_updates_sent}, "
                               f"last_pnl={self._last_pnl:.2f}, positions={remaining_positions}")
                    health_check_counter = 0
                
                time.sleep(data_publishing_interval)
                
            except Exception as e:
                logger.error(f"Error in data publishing loop: {e}")
                logger.error(f"is_running={self.is_running}, continuing loop...")
                time.sleep(1.0)
        
        logger.info("Data publishing loop ended - shutdown signal received")
    
    def _publish_pnl_data(self):
        """Publish P&L data to UI via data port - continues regardless of position status"""
        try:
            # Get current P&L via AutoTrailer manager (P&L coordination)
            if not self.autotrailer:
                logger.warning("AutoTrailer Manager not available for P&L calculation")
                return
                
            current_pnl = self.autotrailer.update_pnl_and_process()
            
            # Publish P&L data at every tick for real-time updates
            if not self.port_manager:
                logger.warning("Port manager not available for P&L publishing")
                return
                
            data_port = self.port_manager.data_port
            
            # Create P&L update packet
            pnl_packet = {
                "type": "pnl_update",
                "data": {
                    "pnl": current_pnl,
                    "auto_active": self.autotrailer.is_auto_trading_active() if self.autotrailer else False,
                    "ul_index": getattr(self.diu, 'ul_symbol', 'UNKNOWN')
                },
                "timestamp": time.time()
            }
            
            data_port.send_data(pnl_packet)
            
            # Track publishing statistics
            self._data_updates_sent += 1
            
            # Reduce log frequency - only log significant P&L changes or periodically
            if current_pnl != self._last_pnl:
                change = current_pnl - self._last_pnl
                # Only log every 10th P&L change or if change is significant (>= 50)
                if self._data_updates_sent % 10 == 0 or abs(change) >= 50:
                    logger.debug(f"Published P&L update: {self._last_pnl:.2f} -> {current_pnl:.2f} (Change: {change:+.2f}, total sent: {self._data_updates_sent})")
            elif self._data_updates_sent % 100 == 0:
                logger.debug(f"P&L health check: {current_pnl:.2f} (total sent: {self._data_updates_sent})")
            
            self._last_pnl = current_pnl
                    
        except Exception as e:
            logger.error(f"Error publishing P&L data: {e}")
            logger.debug(f"AutoTrailer Manager available: {self.autotrailer is not None}, Port manager available: {self.port_manager is not None}")
            # Don't let publishing errors stop the loop - continue publishing
    
    def _health_monitoring_loop(self):
        """Background thread that monitors system health and network connectivity"""
        logger.info("Health monitoring loop started")

        # Check and report actual network status during initialization (separate from broker status)
        initial_network_connected = self._check_network_connectivity()
        self.infra_error_handler.send_network_status_notification(initial_network_connected)
        self._network_connected = initial_network_connected  # Update stored state
        logger.debug(f"Network monitor reported initial status: {'connected' if initial_network_connected else 'disconnected'}")

        health_check_interval = 5.0  # 5 seconds total
        sleep_chunk = 0.5  # Check is_running every 500ms for responsive shutdown

        while self.is_running:
            try:
                current_time = time.time()

                # Check network connectivity (if enabled and interval reached)
                # Use adaptive intervals: normal speed when up, half-time when down for faster recovery
                adaptive_interval = self._network_check_interval if self._network_connected else self._network_check_interval / 2

                if (self._network_check_enabled and
                    current_time - self._last_network_check >= adaptive_interval):

                    self._check_and_report_network_status()
                    self._last_network_check = current_time

                # Check P&L health via AutoTrailer Manager (P&L coordination)
                try:
                    pnl = self.autotrailer.update_pnl_and_process()
                    self._last_pnl = pnl
                except Exception as e:
                    logger.error(f"P&L health check failed: {e}")

                    # Send error to UI via data_port (not response_port to avoid ID collision)
                    try:
                        data_port = self.port_manager.data_port
                        data_port.send_data({
                            "type": "error_event",
                            "error_type": "PFMU_ERROR",
                            "error_message": str(e),
                            "timestamp": time.time()
                        })
                        logger.warning(f"[BACKEND] Sent PFMU error via data_port to avoid request_id collision: {str(e)}")
                    except Exception:
                        # Ignore port errors during shutdown
                        pass

                # Log periodic stats
                if self._data_updates_sent > 0 and self._data_updates_sent % 2000 == 0:
                    logger.info(f"Health check: {self._data_updates_sent} data updates sent")
                
                # Sleep in small chunks to be responsive to shutdown
                elapsed = 0.0
                while elapsed < health_check_interval and self.is_running:
                    time.sleep(sleep_chunk)
                    elapsed += sleep_chunk
                
            except Exception as e:
                logger.error(f"Error in health monitoring: {e}")
                # Sleep in chunks here too for responsive shutdown
                elapsed = 0.0
                while elapsed < 5.0 and self.is_running:
                    time.sleep(sleep_chunk)
                    elapsed += sleep_chunk
        
        logger.info("Health monitoring loop ended")