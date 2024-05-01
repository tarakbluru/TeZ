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
    from dataclasses import dataclass
    from datetime import datetime
    from enum import Enum
    from threading import Event, Timer
    from typing import NamedTuple, Callable

    import app_mods
    import numpy as np
    import yaml

except Exception as e:
    logger.debug(traceback.format_exc())
    logger.error(("Import Error " + str(e)))
    sys.exit(1)


class TeZ_App_BE_CreateConfig(NamedTuple):
    limit_order_cfg:bool
    system_sqoff_cb:Callable


class SquareOff_Mode(Enum):
    ALL = 0
    SELECT = 1

class SquareOff_InstType(Enum):
    BEES = 0
    CE = 1
    PE = 2
    ALL = 3

@dataclass
class SquareOff_Info:
    mode:SquareOff_Mode
    per: float
    ul_index: str
    exch:str
    inst_type:SquareOff_InstType=SquareOff_InstType.ALL
    partial_exit:bool = False

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
                                            master_file=None,
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

        def create_diu(live_data_output_port:app_mods.SimpleDataPort, master_file):
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
                                            out_port=live_data_output_port, 
                                            tr_folder=tr_folder,
                                            tr_flag=tr,
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

        def create_pfmu(tiu, diu, port):
            pfmu_ord_file = app_mods.get_system_info("BKU", "TRADES_RECORD_FILE")
            pf_file = app_mods.get_system_info("PFMU", "PF_RECORD_FILE")
            mo = app_mods.get_system_info("MARKET_TIMING", "OPEN")
            pfmu_cc = app_mods.PFMU_CreateConfig(tiu=tiu, diu=diu, rec_file=pfmu_ord_file, 
                                                 mo=mo, pf_file=pf_file, 
                                                 reset=False, port=port, 
                                                 limit_order_cfg=self.cc_cfg.limit_order_cfg,
                                                 system_sqoff_cb=self.cc_cfg.system_sqoff_cb)
            pfmu = app_mods.PFMU(pfmu_cc)
            return pfmu

        logger.info ('APBE initialization ...')

        self.data_q = utils.ExtSimpleQueue()
        self.evt = Event()
        self.diu_op_port = app_mods.SimpleDataPort(data_q=self.data_q, evt=self.evt)

        self.tiu = create_tiu()
        master_file = self.tiu.scripmaster_file
        self.diu = create_diu(live_data_output_port=self.diu_op_port, master_file=master_file)
        self.pfmu = create_pfmu(tiu=self.tiu, diu=self.diu, port=self.diu_op_port)

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

        self.pfmu.start_monitoring()
        time.sleep(0.1)
        self.diu.live_df_ctrl = app_mods.Ctrl.ON

        self.__count += 1
        logger.info (f"APBE initialization ...done Inst: {TeZ_App_BE.name} {TeZ_App_BE.__count} {TeZ_App_BE.__componentType}")
        return

    def __square_off_position_timer__(self):
        logger.info(f'{datetime.now().time()} !! Auto Square Off Time !!')
        exch = app_mods.get_system_info("TRADE_DETAILS", "EXCHANGE")
        sqoff_info = SquareOff_Info(mode=SquareOff_Mode.ALL, per=100.0, ul_index=None, exch=exch)
        self.square_off_position(sq_off_info=sqoff_info)

    @property
    def ul_index(self):
        return self.diu.ul_symbol

    @ul_index.setter
    def ul_index(self, ul_index):
        self.diu.ul_symbol = ul_index

    def exit_app_be(self):
        if self.sqoff_timer is not None:
            if self.sqoff_timer.is_alive():
                self.sqoff_timer.cancel()
        self.diu.live_df_ctrl = app_mods.Ctrl.OFF
        logger.debug ('Cancelling all waiting orders')
        self.pfmu.cancel_all_waiting_orders (exit_flag=True, show_table=False)
        self.pfmu.show()

    @staticmethod
    def get_instrument_info(exchange, ul_inst):
        instruments = app_mods.get_system_info("TRADE_DETAILS", "INSTRUMENT_INFO")
        instrument_info = None
        for inst_id, info in instruments.items():
            logger.debug(f"Instrument: {inst_id}")
            if info['EXCHANGE'] == exchange and info['UL_INDEX'] == ul_inst:
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
                self.pfmu.cancel_waiting_order (id=rn-1)
            
            self.pfmu.wo_table_show()

    def show_records (self) -> None:
        self.pfmu.show()

    def market_action(self, action:str, trade_price:float=None, ui_qty:int=None):

        ul_index = self.diu.ul_symbol
        exch = app_mods.get_system_info("TRADE_DETAILS", "EXCHANGE")

        inst_info_dict = TeZ_App_BE.get_instrument_info(exch, ul_index)
        inst_info = {key.lower(): value for key, value in inst_info_dict.items()}
        inst_info['use_gtt_oco'] = True if inst_info['order_prod_type'].lower() == 'o' else False
        if ui_qty:
            inst_info['quantity'] = ui_qty
        inst_info = app_mods.shared_classes.InstrumentInfo(**inst_info)

        try:
            qty_taken = self.pfmu.take_position(action, inst_info=inst_info, trade_price=trade_price)
        except RuntimeError:
            raise
        else :
            return qty_taken

    def square_off_position(self, sq_off_info:SquareOff_Info):
        logger.info (repr(sq_off_info))
        exch = sq_off_info.exch
        if sq_off_info.mode == SquareOff_Mode.SELECT:
            ul_index = sq_off_info.ul_index
            if sq_off_info.inst_type == SquareOff_InstType.ALL:
                inst_info = TeZ_App_BE.get_instrument_info(exch, ul_index)
                sq_off_ul_symbol = inst_info['SYMBOL']
                logger.info(f'Sq_off_symbol:{sq_off_ul_symbol}')
            else:
                sq_off_ul_symbol = ul_index
            inst_type = sq_off_info.inst_type.name
        else:
            sq_off_ul_symbol = None
            inst_type = 'ALL'

        partial_exit = sq_off_info.partial_exit
        logger.info (f'sq_off_ul_symbol: {sq_off_ul_symbol} mode: {sq_off_info.mode.name} inst_type: {inst_type}')
        per = sq_off_info.per
        self.pfmu.square_off_position (mode=sq_off_info.mode.name, ul_index=sq_off_ul_symbol, per=per, inst_type=inst_type, partial_exit=partial_exit)
        if inst_type == 'ALL':
            self.pfmu.show()

    def data_feed_connect(self):
        return (self.diu.connect_to_data_feed_servers())

    def data_feed_disconnect(self):
        self.diu.disconnect_data_feed_servers()

    def get_latest_tick(self):
        return self.diu.get_latest_tick()

    def auto_trailer(self, auto_trailer_data: app_mods.AutoTrailerData|None=None):
        return (self.pfmu.auto_trailer (auto_trailer_data))

