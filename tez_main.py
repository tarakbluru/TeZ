"""
File: tez_main_v2.py
Author: [Tarakeshwar NC] / Claude Code  
Date: September 7, 2025
Description: Simplified main launcher for TeZ trading platform using app_fe.py.
This is the refactored version with clean separation of concerns between
frontend (app_fe.py) and backend (app_be.py) via port-based communication.
"""
# Copyright (c) [2024] [Tarakeshwar N.C]
# This file is part of the TeZ project.
# It is subject to the terms and conditions of the MIT License.
# See the file LICENSE in the top-level directory of this distribution
# for the full text of the license.

__app_name__ = 'TeZ'
__author__ = "Tarakeshwar N.C"
__copyright__ = "2024"
__date__ = "2025/09/07"
__deprecated__ = False
__email__ = "tarakesh.nc_at_google_mail_dot_com"
__license__ = "MIT"
__maintainer__ = "Tarak"
__status__ = "Development"
__version__ = "1.0.0_TC3"

import sys
import traceback
import json
import threading
import time
from datetime import datetime
from multiprocessing import active_children

import app_utils as utils
from app_utils import FAILURE, SUCCESS
from app_utils.gen_utils import (
    check_expiry_dates, 
    update_system_config
)
import app_mods
from app_be import TeZ_App_BE, TeZ_App_BE_CreateConfig
from app_fe import AppFE

logger = utils.get_logger(__name__)

def main():
    """Main application entry point"""
    logger.info(f'{__app_name__}: {__version__}')
    
    # Verify System time with the External servers
    ct = utils.CustomTime()
    result = ct.compare_system_and_ntp_time()
    logger.info(f"System clock Verification: System time and NTP server time match: {result}")

    # Load system configuration
    r = app_mods.get_system_config()
    logger.info(f'System Config Read: {r}')

    logger.info(f'Updating System Config Expiry Date and Offsets: {r}')
    update_system_config()

    # Build comprehensive system configuration for AppFE
    system_feature_config = {}
    
    # Core feature flags
    system_feature_config['limit_order_cfg'] = True if app_mods.get_system_info("SYSTEM", "LMT_ORDER_FEATURE") == 'ENABLED' else False

    exch = app_mods.get_system_info("TRADE_DETAILS", "EXCHANGE")

    system_feature_config['tm'] = 'CE_PE' if exch == 'NFO' else None
    if not system_feature_config['tm']:
        system_feature_config['tm'] = 'BEES' if exch == 'NSE' else None
    
    # Add all GUI_CONFIG values that AppFE needs
    system_feature_config['gui'] = {
        'app_title': app_mods.get_system_info("GUI_CONFIG", "APP_TITLE"),
        'app_geometry': app_mods.get_system_info("GUI_CONFIG", "APP_GEOMETRY"),
        'long_button': app_mods.get_system_info("GUI_CONFIG", "LONG_BUTTON"),
        'short_button': app_mods.get_system_info("GUI_CONFIG", "SHORT_BUTTON"),
        'exit_button': app_mods.get_system_info("GUI_CONFIG", "EXIT_BUTTON"),
        'square_off_button': app_mods.get_system_info("GUI_CONFIG", "SQUARE_OFF_BUTTON"),
        'slider_font': app_mods.get_system_info("GUI_CONFIG", "SLIDER_FONT"),
        'slider_font_size': app_mods.get_system_info("GUI_CONFIG", "SLIDER_FONT_SIZE"),
        'slider_posn1_text': app_mods.get_system_info("GUI_CONFIG", "SLIDER_POSN1_TEXT"),
        'slider_posn2_text': app_mods.get_system_info("GUI_CONFIG", "SLIDER_POSN2_TEXT"),
        'radiobutton_def_value': app_mods.get_system_info("GUI_CONFIG", "RADIOBUTTON_DEF_VALUE"),
        'radiobutton_1_text': app_mods.get_system_info("GUI_CONFIG", "RADIOBUTTON_1_TEXT"),
        'radiobutton_1_value': app_mods.get_system_info("GUI_CONFIG", "RADIOBUTTON_1_VALUE"),
        'radiobutton_2_text': app_mods.get_system_info("GUI_CONFIG", "RADIOBUTTON_2_TEXT"),
        'radiobutton_2_value': app_mods.get_system_info("GUI_CONFIG", "RADIOBUTTON_2_VALUE"),
        'play_notify': app_mods.get_system_info("GUI_CONFIG", "PLAY_NOTIFY")
    }
    
    logger.info(f'{json.dumps(system_feature_config, indent=2)}')

    # Verification Step: Check expiry dates for NFO
    if exch == 'NFO':
        inst_info = app_mods.get_system_info("TRADE_DETAILS", "INSTRUMENT_INFO")
        check_expiry_dates(inst_info)
        logger.info(f'NIFTY OPTION: {json.dumps(app_mods.get_system_info("INSTRUMENT_INFO", "INST_3"), indent=2)}')
        logger.info(f'BANK NIFTY OPTION: {json.dumps(app_mods.get_system_info("INSTRUMENT_INFO", "INST_4"), indent=2)}')

    if exch == 'NSE':
        logger.info(f'NIFTYBEES: {json.dumps(app_mods.get_system_info("INSTRUMENT_INFO", "INST_1"), indent=2)}')
        logger.info(f'BANKBEES: {json.dumps(app_mods.get_system_info("INSTRUMENT_INFO", "INST_2"), indent=2)}')

    # Get default ul_index selection
    def_value = app_mods.get_system_info("GUI_CONFIG", "RADIOBUTTON_DEF_VALUE")
    ul_index = def_value
    instrument_info = "default"  # This will be updated later via ul_selection change
    
    # Create backend configuration
    app_be_cc_cfg = TeZ_App_BE_CreateConfig(
        ul_index=ul_index,
        instrument_info=instrument_info
    )
    
    # Initialize backend
    try:
        logger.info("Creating TeZ backend...")
        app_be = TeZ_App_BE(app_be_cc_cfg)
        logger.info("TeZ backend created successfully")
        
    except app_mods.tiu.LoginFailureException:
        logger.error('Login Failure')
        return
    except Exception as e:
        logger.error(traceback.format_exc())
        logger.error(f'Exception occurred during backend creation: {e}')
        return

    # Connect data feed
    try:
        logger.info("Connecting to data feed...")
        if app_be.data_feed_connect() == FAILURE:
            app_be.data_feed_disconnect()
            logger.error('Web socket Failure, exiting')
            sys.exit(1)
        logger.info("Data feed connected successfully")
        
    except KeyboardInterrupt:
        logger.info('CTRL+C interrupt..Exiting')
        sys.exit(2)
    except Exception as e:
        logger.error(f'Exception Occurred during data feed connection: {repr(e)}')
        sys.exit(3)

    # Create and start frontend
    try:
        logger.info("Creating TeZ frontend...")
        app_fe = AppFE(
            port_manager=app_be.get_port_manager(),
            system_feature_config=system_feature_config,
            app_be=app_be  # Pass backend reference for acceptable direct calls
        )
        logger.info("TeZ frontend created successfully")
        
        logger.info("Starting TeZ frontend UI...")
        app_fe.start()  # This blocks until UI is closed
        
    except KeyboardInterrupt:
        logger.info('UI interrupted by keyboard')
    except Exception as e:
        logger.error(f'Exception in frontend: {e}')
        logger.error(traceback.format_exc())

    # Cleanup
    logger.info("Shutting down TeZ application...")
    try:
        app_be.data_feed_disconnect()
        app_be.exit_app_be()
        time.sleep(1)
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
    
    logger.info(f'{__app_name__} Version: {__version__} -- Ends')

if __name__ == "__main__":
    logger.info(f'Python Version:{sys.version}: Exe: {sys.executable}')
    main()
    
    # Thread and process monitoring
    nthreads = threading.active_count()
    logger.info(f"nthreads in the system: {nthreads}")

    for count, t in enumerate(threading.enumerate()):
        logger.info(f"{count+1}. Thread name: {t.name} ")

    children = active_children()
    logger.info(f'Active Child Processes: {len(children)}')
    if len(children):
        logger.info(children)

    if nthreads == 1 and not len(children):
        logger.info('App Shuts down Cleanly..')
    else:
        logger.warning(f'App shutdown with {nthreads} threads and {len(children)} child processes remaining')