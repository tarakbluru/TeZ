"""
File: app_be.py
Author: [Tarakeshwar NC]
Date: January 15, 2024
Description: This is the backend service provider for the gui.
"""
# Copyright (c) [2024] [Tarakeshwar N.C]
# This file is part of the TeZ project.
# It is subject to the terms and conditions of the MIT License.
# See the file LICENSE in the top-level directory of this distribution
# for the full text of the license.

__app_name__ = 'TeZ'
__author__ = "Tarakeshwar N.C"
__copyright__ = "2024"
__date__ = "2024/1/14"
__deprecated__ = False
__email__ = "tarakesh.nc_at_google_mail_dot_com"
__license__ = "MIT"
__maintainer__ = "Tarak"
__status__ = "Development"

import sys
import traceback

import app_utils as utils

logger = utils.get_logger(__name__)

try:
    import copy
    import json
    import math
    from datetime import datetime
    from threading import Timer

    import app_mods
    import numpy as np
    import yaml

except Exception as e:
    logger.debug(traceback.format_exc())
    logger.error(("Import Error " + str(e)))
    sys.exit(1)


class TeZ_App_BE:
    def __init__(self):
        def create_tiu():
            cred_file = app_mods.get_system_info("TIU", "CRED_FILE")
            logger.info(f'credfile{cred_file}')

            with open(cred_file) as f:
                cred = yaml.load(f, Loader=yaml.FullLoader)

            session_id = None

            if app_mods.get_system_info("TIU", "USE_GSHEET_TOKEN") == 'YES':
                gsheet_info = app_mods.get_system_info("TIU", "GOOGLE_SHEET")
                print(gsheet_info)
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

            dl_filepath = app_mods.get_system_info("SYSTEM", "DL_FOLDER")
            logger.info(f'dl_filepath: {dl_filepath}')

            tiu_token_file = app_mods.get_system_info("TIU", "TOKEN_FILE")
            logger.info(f'token_file: {tiu_token_file}')

            tiu_cred_file = app_mods.get_system_info("TIU", "CRED_FILE")

            tiu_save_token_file_cfg = app_mods.get_system_info("TIU", "SAVE_TOKEN_FILE_CFG")
            tiu_save_token_file = app_mods.get_system_info("TIU", "SAVE_TOKEN_FILE_NAME")

            tcc = app_mods.Tiu_CreateConfig(tiu_cred_file,
                                            session_id,
                                            tiu_token_file,
                                            False,
                                            dl_filepath,
                                            None,
                                            tiu_save_token_file_cfg,
                                            tiu_save_token_file)
            logger.debug(f'tcc:{str(tcc)}')
            tiu = app_mods.Tiu(tcc=tcc)

            logger.info('Creating dataframe for quick access')
            instruments = app_mods.get_system_info("TIU", "INSTRUMENT_INFO")

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

        def create_diu():
            diu_cred_file = app_mods.get_system_info("DIU", "CRED_FILE")
            diu_token_file = app_mods.get_system_info("DIU", "TOKEN_FILE")
            logger.info(f'token_file: {diu_token_file}')
            diu_save_token_file_cfg = app_mods.get_system_info("DIU", "SAVE_TOKEN_FILE_CFG")
            diu_save_token_file = app_mods.get_system_info("DIU", "SAVE_TOKEN_FILE_NAME")

            dcc = app_mods.Diu_CreateConfig(diu_cred_file, None, diu_token_file, False, None, None, diu_save_token_file_cfg, diu_save_token_file)
            logger.debug(f'dcc:{str(dcc)}')
            diu = app_mods.Diu(dcc=dcc)

            diu.ul_symbol = app_mods.get_system_info("GUI_CONFIG", "RADIOBUTTON_DEF_VALUE")

            return diu

        def create_bku():
            bku_file = app_mods.get_system_info("TIU", "TRADES_RECORD_FILE")
            bku = app_mods.BookKeeperUnit(bku_file, reset=False)
            return bku

        self.tiu = create_tiu()
        self.diu = create_diu()
        self.bku = create_bku()

        ocpu_cc = app_mods.Ocpu_CreateConfig(tiu=self.tiu,diu=self.diu, bku=self.bku)
        self.ocpu = app_mods.OCPU(ocpu_cc=ocpu_cc)

        self._sqoff_time = None
        self.sqoff_timer = None

        auto_sq_off_time_str = app_mods.get_system_info("SYSTEM", "SQ_OFF_TIMING")
        current_time = datetime.now().time()
        logger.info(f'auto_sq_off_time:{auto_sq_off_time_str} current_time:  {current_time}')
        hr = datetime.strptime(auto_sq_off_time_str, '%H:%M').hour
        minute = datetime.strptime(auto_sq_off_time_str, '%H:%M').minute
        self._sq_off_time = datetime.now().replace(hour=hr, minute=minute, second=0, microsecond=0)

        rm_durn = utils.calcRemainingDuration(self._sq_off_time.hour, self._sq_off_time.minute)
        if (rm_durn > 0):
            self.sqoff_timer = Timer(rm_durn, self.__square_off_position_timer__)
        if self.sqoff_timer is not None:
            self.sqoff_timer.name = "SQ_OFF_TIMER"
            self.sqoff_timer.daemon = True
            self.sqoff_timer.start()
        else:
            logger.debug("Square off Timer Is not Created.. as Time has elapsed ")

    def __square_off_position_timer__(self):
        logger.info(f'{datetime.now().time()} !! Auto Square Off Time !!')
        self.square_off_position(mode='ALL')

    @property
    def ul_symbol(self):
        return self.diu.ul_symbol

    @ul_symbol.setter
    def ul_symbol(self, ul_symbol):
        self.diu.ul_symbol = ul_symbol

    def exit_app_be(self):
        if self.sqoff_timer is not None:
            if self.sqoff_timer.is_alive():
                self.sqoff_timer.cancel()

    @staticmethod
    def get_instrument_info(exchange, ul_inst):
        instruments = app_mods.get_system_info("TIU", "INSTRUMENT_INFO")
        instrument_info = None
        for inst_id, info in instruments.items():
            logger.debug(f"Instrument: {inst_id}")
            if info['EXCHANGE'] == exchange and info['UL_INSTRUMENT'] == ul_inst:
                instrument_info = info
                break
        return instrument_info  # symbol, exp_date, ce_offset, pe_offset

    def market_action(self, action):

        ul_sym = self.diu.ul_symbol
        exch = app_mods.get_system_info("TIU", "EXCHANGE")

        inst_info_dict = TeZ_App_BE.get_instrument_info(exch, ul_sym)
        inst_info = {key.lower(): value for key, value in inst_info_dict.items()}

        nlegs = app_mods.get_system_info("TIU", "N_LEGS")
        if not nlegs:
            nlegs = 1

        qty = round(app_mods.get_system_info("TIU", "QUANTITY"), 0)
        use_gtt_oco = True if app_mods.get_system_info("TIU", "USE_GTT_OCO").upper() == 'YES' else False

        inst_info = app_mods.OcpuInstrumentInfo(**inst_info, 
                                                use_gtt_oco=use_gtt_oco,
                                                qty=qty, 
                                                n_legs=nlegs 
                                                )

        self.ocpu.crete_and_place_order(action, inst_info=inst_info)

    def square_off_position(self, mode='SELECT'):
        df = self.bku.fetch_order_id()
        if mode == 'ALL':
            self.tiu.square_off_position(df=df)
        else:
            exch = app_mods.get_system_info("TIU", "EXCHANGE")
            ul_sym = self.diu.ul_symbol
            inst_info = TeZ_App_BE.get_instrument_info(exch, ul_sym)
            sq_off_symbol = inst_info['SYMBOL']
            logger.info(f'Sq_off_symbol:{sq_off_symbol}')
            self.tiu.square_off_position(df=df, symbol=sq_off_symbol)

        print("Square off Position - Complete.")

    def data_feed_connect(self):
        self.diu.connect_to_data_feed_servers()

    def data_feed_disconnect(self):
        self.diu.disconnect_data_feed_servers()

    def get_latest_tick(self):
        return self.diu.get_latest_tick()
