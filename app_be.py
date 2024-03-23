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
    import time
    from datetime import datetime
    from threading import Event, Timer
    from typing import NamedTuple

    import app_mods
    import numpy as np
    import yaml

except Exception as e:
    logger.debug(traceback.format_exc())
    logger.error(("Import Error " + str(e)))
    sys.exit(1)


class TeZ_App_BE_CreateConfig(NamedTuple):
    limit_order_cfg:bool

class TeZ_App_BE:
    name = "APBE"
    __count = 0
    __componentType = app_mods.shared_classes.Component_Type.ACTIVE 

    def __init__(self, cc_cfg:TeZ_App_BE_CreateConfig):
        self.cc_cfg = cc_cfg
        def create_tiu():
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
                                            dl_filepath=dl_filepath,
                                            notifier=None,
                                            save_tokenfile_cfg=tiu_save_token_file_cfg,
                                            save_token_file=tiu_save_token_file, 
                                            test_env=virtual_env)
            
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

        def create_diu(live_data_output_port:app_mods.SimpleDataPort):
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
                virtual_env = True

            dcc = app_mods.Diu_CreateConfig(inst_prefix='diu', cred_file=diu_cred_file,  
                                            susertoken=None,
                                            token_file=diu_token_file, 
                                            use_pool=False, 
                                            dl_filepath=None, 
                                            notifier=None, 
                                            save_tokenfile_cfg=diu_save_token_file_cfg,
                                            save_token_file=diu_save_token_file, 
                                            out_port=live_data_output_port, 
                                            test_env=virtual_env)
            logger.debug(f'dcc:{str(dcc)}')
            try:
                diu = app_mods.Diu(dcc=dcc)
            except ValueError:
                ...
                raise
            except Exception:
                logger.error (f'diu not created ')
                raise

            diu.ul_symbol = app_mods.get_system_info("GUI_CONFIG", "RADIOBUTTON_DEF_VALUE")

            return diu

        def create_pfmu(tiu):
            pfmu_file = app_mods.get_system_info("BKU", "TRADES_RECORD_FILE")
            pfmu_cc = app_mods.PFMU_CreateConfig(tiu=tiu, rec_file=pfmu_file)
            pfmu = app_mods.PFMU(pfmu_cc)
            return pfmu

        logger.debug ('APBE initialization ...')

        self.data_q = utils.ExtSimpleQueue()
        self.evt = Event()
        self.diu_op_port = app_mods.SimpleDataPort(data_q=self.data_q, evt=self.evt)

        self.tiu = create_tiu()
        self.diu = create_diu(live_data_output_port=self.diu_op_port)
        self.pfmu = create_pfmu(tiu=self.tiu)

        pmu_cc = app_mods.PMU_cc(inp_dataPort=self.diu_op_port)
        self.pmu = app_mods.PriceMonitoringUnit(pmu_cc=pmu_cc)

        ocpu_cc = app_mods.Ocpu_CreateConfig(tiu=self.tiu,diu=self.diu, pfmu=self.pfmu, pmu=self.pmu, lmt_order=self.cc_cfg.limit_order_cfg)
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

        self.pmu.start_monitoring()
        time.sleep(0.1)
        self.diu.live_df_ctrl = app_mods.Ctrl.ON

        self.__count += 1
        logger.debug (f"APBE initialization ...done Inst: {TeZ_App_BE.name} {TeZ_App_BE.__count} {TeZ_App_BE.__componentType}")
        return

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
        self.diu.live_df_ctrl = app_mods.Ctrl.OFF
        logger.debug ('Cancelling all waiting orders')
        self.ocpu.cancel_all_waiting_orders ()
        self.pmu.hard_exit()

    @staticmethod
    def get_instrument_info(exchange, ul_inst):
        instruments = app_mods.get_system_info("TRADE_DETAILS", "INSTRUMENT_INFO")
        instrument_info = None
        for inst_id, info in instruments.items():
            logger.debug(f"Instrument: {inst_id}")
            if info['EXCHANGE'] == exchange and info['UL_INSTRUMENT'] == ul_inst:
                instrument_info = info
                break
        return instrument_info  # symbol, exp_date, ce_offset, pe_offset

    def gen_action(self, action, data):
        if action=='cancel_waiting_order':
            if '-' in data:
                try:
                    start, end = map(int, data.split('-'))
                    if start <= end:
                        row_id = range(start, end + 1)
                    else:
                        row_id = range(end, start + 1)                    
                except ValueError:
                    print("Invalid range format")
                    return None
            else:
                try:
                    row_id = [int(data)]
                except ValueError:
                    print("Invalid row ID format")
                    return None
            logger.info (f'row_id {row_id}')
            for rn in row_id:
                self.ocpu.cancel_waiting_order (id=rn-1)

    def show_records (self):
        self.ocpu.wo_table_show ()
        self.pfmu.show()

    def market_action(self, action, trade_price=None):

        nlegs = app_mods.get_system_info("TRADE_DETAILS", "N_LEGS")

        ul_sym = self.diu.ul_symbol
        exch = app_mods.get_system_info("TRADE_DETAILS", "EXCHANGE")

        inst_info_dict = TeZ_App_BE.get_instrument_info(exch, ul_sym)
        inst_info = {key.lower(): value for key, value in inst_info_dict.items()}


        qty = round(app_mods.get_system_info("TRADE_DETAILS", "QUANTITY"), 0)
        use_gtt_oco = True if app_mods.get_system_info("TRADE_DETAILS", "USE_GTT_OCO").upper() == 'YES' else False

        inst_info = app_mods.OcpuInstrumentInfo(**inst_info, 
                                                use_gtt_oco=use_gtt_oco,
                                                qty=qty, 
                                                n_legs=nlegs 
                                                )
        try:
            self.ocpu.create_and_place_order(action, inst_info=inst_info, trade_price=trade_price)
        except RuntimeError:
            ...

    def square_off_position(self, mode='SELECT'):
        exch = app_mods.get_system_info("TRADE_DETAILS", "EXCHANGE")
        if mode == 'SELECT':
            ul_sym = self.diu.ul_symbol
            inst_info = TeZ_App_BE.get_instrument_info(exch, ul_sym)
            sq_off_ul_symbol = inst_info['SYMBOL']
            logger.info(f'Sq_off_symbol:{sq_off_ul_symbol}')
        else:
            sq_off_ul_symbol = None

        # IMPORTANT : Incase of Partial Exits, ensure ul_sym is taken from the TM gui 

        self.pfmu.square_off_position (mode=mode, ul_symbol=sq_off_ul_symbol)

    def data_feed_connect(self):
        self.diu.connect_to_data_feed_servers()

    def data_feed_disconnect(self):
        self.diu.disconnect_data_feed_servers()

    def get_latest_tick(self):
        return self.diu.get_latest_tick()
