"""
File: ws_wrap.py
Author: [Tarakeshwar NC]
Date: January 15, 2024
Description:  This script provides websocket wrapper to the finvasia websocket apis.
This sub-system also maintains a thread for monitoring the web socket.
References:
https://websocket-client.readthedocs.io/_/downloads/en/latest/pdf/
"""
# Copyright (c) [2024] [Tarakeshwar N.C]
# This file is part of the Tiny_TeZ project.
# It is subject to the terms and conditions of the MIT License.
# See the file LICENSE in the top-level directory of this distribution
# for the full text of the license.

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

import app_utils

logger = app_utils.get_logger(__name__)

try:
    import copy
    import json
    from datetime import datetime
    from sre_constants import FAILURE, SUCCESS
    from threading import Lock
    from time import mktime

    import pyotp
    import yaml

    from .fv_api_extender import ShoonyaApiPy, ShoonyaApiPy_CreateConfig
    from .shared_classes import (BaseInst, Component_Type, Ctrl, FVInstrument,
                                 LiveFeedStatus, SimpleDataPort, SysInst,
                                 TickData)

except Exception as e:
    logger.debug(traceback.format_exc())
    logger.error(("Import Error " + str(e)))
    sys.exit(1)


class WS_WrapU(object):
    name = ""
    __count = 0
    __componentType = Component_Type.ACTIVE
    NIFTY_TOKEN = None
    NIFTY_BANK_TOKEN = None
    DEBUG = False

    def __init__(self,
                 port_cfg: SimpleDataPort = None,
                 order_port_cfg: SimpleDataPort = None,
                 fv: ShoonyaApiPy = None,
                 at_stocks: list = None,
                 bm_stocks: list = None,
                 primary: str = 'FINVASIA',
                 sec: str = None,
                 mo: str = "09:15", mc: str = "15:30",
                 tr: None = None,
                 notifier=None):
        logger.debug("WebSocket Wrapper Unit initialization ...")

        self.lock = Lock()
        self._send_data = bool(False)
        self.__count += 1
        self.inst_id = self.__count
        self.df_status = LiveFeedStatus.OFF

        self._fv_connected = False

        self.port: SimpleDataPort = port_cfg
        self.order_port: SimpleDataPort = order_port_cfg

        mo_hr = datetime.strptime(mo, "%H:%M").hour
        mo_min = datetime.strptime(mo, "%H:%M").minute
        mc_hr = datetime.strptime(mc, "%H:%M").hour
        mc_min = datetime.strptime(mc, "%H:%M").minute

        mo_today = datetime.now().replace(hour=mo_hr, minute=mo_min, second=0, microsecond=0)
        mc_today = datetime.now().replace(hour=mc_hr, minute=mc_min, second=0, microsecond=0)

        mo_epoch = int(mktime(mo_today.timetuple()))
        mc_epoch = int(mktime(mc_today.timetuple()))

        self.mo_epoch = mo_epoch
        self.mc_epoch = mc_epoch

        self.primary = primary
        self.sec = sec

        self.feed_stocks = []

        if at_stocks:
            self.feed_stocks = [*at_stocks]
        if bm_stocks:
            self.feed_stocks = [*self.feed_stocks, *bm_stocks]

        if fv is None:
            cred_file: str = r'../../../Finvasia_login/cred/tarak_fv.yml'
            token_file: str = r'../../../Finvasia_login/temp/tarak_token.json'
            dl_filepath: str = r'../log'
            
            s_cc = ShoonyaApiPy_CreateConfig(dl_filepath=dl_filepath, ws_monitor_cfg=True)
            fv = ShoonyaApiPy(cc=s_cc)
            with open(cred_file) as f:
                cred = yaml.load(f, Loader=yaml.FullLoader)

            try:
                with open(token_file, 'r') as f:
                    susertoken = json.load(f)['susertoken']
                    logger.debug(f'susertoken: {susertoken}')
            except BaseException:
                totp = pyotp.TOTP(cred['token']).now()
                try:
                    r = fv.login(userid=cred['userId'], password=cred['pwd'],
                                 twoFA=totp, vendor_code=cred['vc'],
                                 api_secret=cred['app_key'], imei=cred['imei'])
                    logger.debug(f'finvasia login: {r}')
                except ValueError:
                    mesg = 'Finvasia log in error'
                    logger.error(mesg)
                    raise

                except TimeoutError:
                    mesg = 'Finvasia log in error'
                    logger.error(mesg)
                    raise RuntimeError

                except Exception:
                    mesg = 'Finvasia log in error'
                    logger.error(mesg)
                    raise
            else:
                logger.info(f'skipping login: setting the session!! : {susertoken}')
                ret = fv.set_session(userid=cred['userId'], password=cred['pwd'], usertoken=susertoken)
                logger.debug(f'ret: {ret} type: {type(ret)}')
            finally:
                ...

        self.fv: ShoonyaApiPy = fv
        self._fv_send_data = False

        if not len(self.feed_stocks):
            # create a NIFTY 50 as basic feed
            base = BaseInst('NSE', 'NIFTY', index=True)
            ret = fv.searchscrip(exchange=base.exch, searchtext='NIFTY INDEX')
            if ret is not None and ret['stat'] == 'Ok':
                token = ret['values'][0]['token']
                tsym = ret['values'][0]['tsym']
                logger.debug(f'tsym: {tsym} token: {token}')
                fv_inst = FVInstrument(exch=base.exch, token=str(token), tsym=tsym)
                if WS_WrapU.NIFTY_TOKEN is None:
                    WS_WrapU.NIFTY_TOKEN = token
            else:
                fv_inst = None

            sym1 = SysInst(base_inst=base, fv_inst=fv_inst)
            self.feed_stocks.append(sym1)

            base = BaseInst('NSE', 'NIFTY BANK', index=True)
            ret = fv.searchscrip(exchange=base.exch, searchtext='NIFTY BANK')
            if ret is not None and ret['stat'] == 'Ok':
                token = ret['values'][0]['token']
                tsym = ret['values'][0]['tsym']
                logger.debug(f'tsym: {tsym} token: {token}')
                fv_inst = FVInstrument(exch=base.exch, token=str(token), tsym=tsym)
                if WS_WrapU.NIFTY_BANK_TOKEN is None:
                    WS_WrapU.NIFTY_BANK_TOKEN = token
            else:
                fv_inst = None

            sym1 = SysInst(base_inst=base, fv_inst=fv_inst)
            self.feed_stocks.append(sym1)

        self.com_ohlc_data = list()
        self.fv_token_port_map: dict = dict()

        if fv is not None:
            self.fv_ws_tokens = list()
            self.fv_tokens = list()
            self.fv_dyn_ws_tokens = list()
            self.fv_dyn_tokens = list()

            for item in self.feed_stocks:
                at_stock: SysInst = item
                token = at_stock.fv_inst.token
                ws_token = at_stock.fv_inst.prefixed_ws_token()
                self.fv_tokens.append(token)
                self.fv_ws_tokens.append(ws_token)
                logger.debug(f'{ws_token}')

                live_data: TickData = TickData()
                live_data.tk = int(token)
                self.com_ohlc_data.append(live_data)
                self.fv_token_port_map[str(token)] = live_data

        if WS_WrapU.DEBUG:
            self.fv_ws_tokens = list()
            self.fv_ws_tokens.append('MCX|260606')

        self._prim_rec_tick_data: bool = False
        self._sec_rec_tick_data: bool = False

        self.tr = tr
        self.notifier = notifier
        
        self._fv_send_data = True

        return

    # getter
    def __get_send_data__(self):
        logger.debug("Getting Data Send")
        return self._send_data

    # only setter
    def __set_send_data__(self, new_value):
        if new_value:
            logger.debug("Enabling Data Send")
            self._send_data = True
        else:
            logger.debug("Disabling Data Send")
            self._send_data = False

    send_data = property(None, __set_send_data__)

    # only setter
    def set_fv_ctrl(self, new_value: Ctrl):
        if new_value == Ctrl.ON:
            logger.debug("Enabling fv Data Send")
            self._fv_send_data = True
        else:
            logger.debug("Disabling fv Data Send")
            self._fv_send_data = False

    fv_ctrl = property(None, set_fv_ctrl)

    def fv_create_connect_wsfeed(self):
        def app_open():  # Socket open callback function
            logger.debug("Connected")
            self.fv_socket_opened = True

        def app_close():  # Socket open callback function
            logger.debug("closing")
            self.fv_socket_opened = False

        def app_event_handler_quote_update(msg):
            # print (msg)
            tick_data = msg
            if 'lp' in tick_data and 'tk' in tick_data:
                fv_token = tick_data['tk']
                if WS_WrapU.DEBUG:
                    fv_token = '26000'
                ohlc_obj: TickData = self.fv_token_port_map[fv_token]
                c = float(tick_data['lp'])
                with self.lock:
                    if 'o' in tick_data:
                        logger.debug(f'msg: {msg}')
                        o = float(tick_data['o'])
                        ohlc_obj.o = o
                        ohlc_obj.h = o
                        ohlc_obj.l = o
                        ohlc_obj.c = o

                    if 'h' in tick_data:
                        h = float(tick_data['h'])
                        ohlc_obj.h = h
                    if 'l' in tick_data:
                        ohlc_obj.l = float(tick_data['l'])

                    ohlc_obj.c = c

                    if (c > ohlc_obj.h):
                        ohlc_obj.h = c
                    if (c < ohlc_obj.l):
                        ohlc_obj.l = c

                    if 'v' in tick_data:
                        ohlc_obj.v = int(tick_data["v"])

                    if 'oi' in tick_data:
                        ohlc_obj.oi = int(tick_data["oi"])

                    ohlc_obj.ft = tick_data['ft']

                    if self._send_data and self._fv_send_data:
                        new_obj = copy.copy(ohlc_obj)
                        self.port.send_data(new_obj)
            return

        def app_event_handler_order_update(msg):
            if self.order_port is not None:
                self.order_port.send_data(msg)
            return

        retval = self.fv.connect_to_datafeed_server(on_message=app_event_handler_quote_update,
                                                    on_order_update=app_event_handler_order_update,
                                                    on_open=app_open,
                                                    on_close=app_close)
        return retval

    def fv_disconnect_wsfeed(self):
        return (self.fv.disconnect_from_datafeed_server())

    def connect_to_data_feed_servers(self, primary: str = "FINVASIA", sec: str = ""):
        if (self._fv_connected):
            logger.error("data feed in connected  State")
        if self.fv is not None:
            logger.debug(f'setting the tokens {self.fv_ws_tokens}')
            self.fv.setstreamingdata(self.fv_ws_tokens)
            retval = self.fv_create_connect_wsfeed()
            if retval == SUCCESS:
                self._fv_connected = True
                logger.debug("Data feed connected")
            return retval

    def disconnect_data_feed_servers(self):
        if self.fv is not None and self._fv_connected:
            if (self.fv_disconnect_wsfeed() == FAILURE):
                logger.debug("Finvasia ws wrapper did not disconnect cleanly")
            else:
                logger.debug("Finvasia ws wrapper disconnected cleanly ")
            self._fv_connected = False

    def get_latest_tick(self, token=None):
        if token is None:
            token_str = str(WS_WrapU.NIFTY_TOKEN)
        if isinstance(token, int):
            token_str = str(token)
        else:
            token_str = token
        ohlc_obj: TickData = self.fv_token_port_map[token_str]
        return ohlc_obj
