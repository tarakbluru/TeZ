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
__version__ = "0.1"

import sys
import traceback

import app_utils as utils

logger = utils.get_logger(__name__)

try:
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

            exp_date = app_mods.get_system_info("TIU", "EXPIRY_DATE")
            symbol = app_mods.get_system_info("TIU", "INSTRUMENT")
            exch = app_mods.get_system_info("TIU", "EXCHANGE")

            if symbol != '':
                if exch == 'NSE':
                    tiu.create_sym_token_tsym_q_access([symbol])
                elif exch == 'NFO':
                    tiu.compact_search_file(symbol, exp_date)

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
            return diu

        def create_bku():
            bku_file = app_mods.get_system_info("TIU", "TRADES_RECORD_FILE")
            bku = app_mods.BookKeeperUnit(bku_file, reset=False)
            return bku

        self.tiu = create_tiu()
        self.diu = create_diu()
        self.bku = create_bku()

    def market_action(self, action):
        def get_tsym_token(tiu, diu, action):
            def get_ltp_strike(diu):
                ul_ltp = diu.get_latest_tick()
                strike = round(ul_ltp / 50 + 0.5) * 50
                logger.debug(f'ul_ltp:{ul_ltp} strike:{strike}')
                return ul_ltp, strike

            sym = app_mods.get_system_info("TIU", "INSTRUMENT")
            exch = app_mods.get_system_info("TIU", "EXCHANGE")
            qty = app_mods.get_system_info("TIU", "QUANTITY")
            ltp = None
            ltp, strike = get_ltp_strike(diu)

            if exch == 'NFO':
                c_or_p = 'C' if action == 'Buy' else 'P'

                if c_or_p == 'C':
                    strike_offset = app_mods.get_system_info("TIU", "CE_STRIKE_OFFSET")
                else:
                    strike_offset = app_mods.get_system_info("TIU", "PE_STRIKE_OFFSET")
                strike += strike_offset * 50
                exp = app_mods.get_system_info("TIU", "EXPIRY_DATE")
                searchtext = f'{sym}{exp}{c_or_p}{strike}'
            elif exch == 'NSE':
                searchtext = sym
                strike = ''
                logger.debug(f'ltp:{ltp} strike:{strike}')
            else:
                ...
            token, tsym = tiu.search_scrip(exchange=exch, symbol=searchtext)
            ltp, ti = tiu.fetch_ltp(exch, token)

            logger.info(f'strike: {strike}, sym: {sym}, tsym: {tsym}, token: {token}, qty:{qty}, ltp: {ltp}, ti:{ti}')
            return strike, sym, tsym, token, qty, ltp, ti

        strike, sym, tsym, token, qty, ltp, ti = get_tsym_token(self.tiu, self.diu, action=action)
        oco_order = np.NaN
        os = app_mods.shared_classes.OrderStatus()
        status = app_mods.Tiu_OrderStatus.HARD_FAILURE

        if app_mods.get_system_info("TIU", "TRADE_MODE") == 'PAPER':
            # tiu place order
            order_id = '1'
            oco_order = f'{order_id}_gtt_order_id_1'
        else:
            logger.info(f'sym:{sym} tsym:{tsym} ltp: {ltp}')
            if sym == 'NIFTYBEES' and ltp is not None:

                pp = app_mods.get_system_info("TIU", "PROFIT_PER") / 100.0
                bp = utils.round_stock_prec(ltp * pp, base=ti)

                sl_p = app_mods.get_system_info("TIU", "STOPLOSS_PER") / 100.0
                bl = utils.round_stock_prec(ltp * sl_p, base=ti)
                logger.debug(f'ltp:{ltp} pp:{pp} bp:{bp} sl_p:{sl_p} bl:{bl}')
                if action == 'Buy':
                    order = app_mods.BO_B_MKT_Order(tradingsymbol=tsym,
                                                    quantity=qty, bookloss_price=bl,
                                                    bookprofit_price=bp, remarks='tiny_tez_')
                else:
                    order = app_mods.BO_S_MKT_Order(tradingsymbol=tsym,
                                                    quantity=qty, bookloss_price=bl,
                                                    bookprofit_price=bp, remarks='tiny_tez_')
                status, os = self.tiu.place_and_confirm_tiny_tez_order(order=order)
            else:
                ...

        symbol = tsym + '_' + str(token)
        order_time = os.fill_timestamp
        status = status.name
        order_id = os.order_id
        qty = os.fillshares
        self.bku.save_order(order_id, symbol, qty, order_time, status, oco_order)
        self.bku.show()

    def square_off_position(self):
        order_list = self.bku.fetch_order_id()
        self.tiu.square_off_position(order_details=order_list)
        print("Square off Position - Complete.")

    def data_feed_connect(self):
        self.diu.connect_to_data_feed_servers()

    def data_feed_disconnect(self):
        self.diu.disconnect_data_feed_servers()

    def get_latest_tick(self):
        return self.diu.get_latest_tick()
