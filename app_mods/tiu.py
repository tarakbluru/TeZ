"""
File: tiu.py
Author: [Tarakeshwar NC]
Date: January 15, 2024
Description:  This script provides Trading Interface Unit.
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
    import concurrent
    import datetime
    import json
    import locale
    import os
    import re
    import time
    import urllib.parse
    from enum import Enum
    from typing import List, NamedTuple, Union
    from dataclasses import dataclass

    import app_utils
    import pandas as pd
    import pyotp
    import requests
    import yaml

    from . import fv_api_extender, shared_classes, ws_wrap
except Exception as e:
    logger.debug(traceback.format_exc())
    logger.error(("Import Error " + str(e)))
    sys.exit(1)

locale.setlocale(locale.LC_ALL, '')


class Tiu_OrderStatus (Enum):
    HARD_FAILURE = 0
    SOFT_FAILURE_REJRMS = 1
    SOFT_FAILURE_QTY = 2
    SUCCESS = 3


class LoginFailureException(Exception):
    pass

class OrderExecutionException(Exception):
    pass

@dataclass
class Biu_CreateConfig(object):
    inst_prefix: str
    cred_file: str  # ='../../../Finvasia_login/cred/tarak_fv.yml'
    susertoken: str  # =''
    token_file: str  # ='../../../Finvasia_login/temp/tarak_token.json'
    use_pool: bool  # =True
    dl_filepath: str  # =f'../log'
    notifier: None  # =None
    save_tokenfile_cfg: bool  # =False
    save_token_file: str  # ='../../Finvasia_login/temp/tarak_token_new.json'
    test_env:bool=False
    
    def __str__(self):
        return f'''cred_file: {self.cred_file} susertoken: {self.susertoken} 
                  token_file:{self.token_file} use_pool:{self.use_pool} 
                  dl_filepath:{self.dl_filepath} notifier:{self.notifier} 
                  save_tokenfile_cfg: {self.save_tokenfile_cfg} 
                  save_token_file:{self.save_tokenfile_cfg} test_env:{self.test_env}'''

@dataclass
class Diu_CreateConfig(Biu_CreateConfig):
    out_port: shared_classes.SimpleDataPort=None

    def __str__(self):
        return f"{super().__str__()} out_port: {self.out_port}"

@dataclass
class Tiu_CreateConfig(Biu_CreateConfig):
    ...

class BaseIU (object):
    def __init__(self, bcc: Biu_CreateConfig):
        self.notifier = bcc.notifier
        self.cred_file = bcc.cred_file
        self.token_file = bcc.token_file
        self.holdings_df = None
        self.posn_df = None
        self._amount_in_ac = None
        self._used_margin = None
        self.use_pool = bcc.use_pool
        self.df = None
        usefile = True if bcc.dl_filepath else False
        dl_file = True if bcc.dl_filepath else False
        s_cc = fv_api_extender.ShoonyaApiPy_CreateConfig(inst_prefix=bcc.inst_prefix, dl_file=dl_file, use_file=usefile, dl_filepath=bcc.dl_filepath, test_env=bcc.test_env)

        self.fv = fv_api_extender.ShoonyaApiPy(cc=s_cc)
        fv = self.fv

        with open(bcc.cred_file) as f:
            cred = yaml.load(f, Loader=yaml.FullLoader)

        if bcc.susertoken is None:
            logger.debug(f'susertoken is None trying {bcc.token_file}')
            try:
                with open(bcc.token_file, 'r') as f:
                    susertoken = json.load(f)['susertoken']
                    logger.debug(f'susertoken: {susertoken}')
            except BaseException:
                if s_cc.test_env:
                    totp = cred['token']
                else:
                    totp = pyotp.TOTP(cred['token']).now()
                try:
                    r = fv.login(userid=cred['userId'], password=cred['pwd'],
                                 twoFA=totp, vendor_code=cred['vc'],
                                 api_secret=cred['app_key'], imei=cred['imei'])
                    logger.debug(f'finvasia login: {json.dumps(r, indent=2)}')
                    act_id = None
                    if r is not None and 'actid' in r:
                        act_id = r.get('actid')
                    dmsg = None
                    if r is not None and 'dmsg' in r:
                        dmsg = r.get('dmsg')
                    emsg = None
                    if r is not None and 'emsg' in r:
                        emsg = r.get('emsg')

                    logger.info(f'Acct: {act_id} dmsg:{dmsg} emsg:{emsg}')
                    if bcc.save_tokenfile_cfg and bcc.save_token_file is not None:
                        with open(bcc.save_token_file, "w") as outfile:
                            outfile.write(json.dumps(r, indent=2))

                except ValueError:
                    mesg = 'Finvasia log in error'
                    logger.error(mesg)
                    raise LoginFailureException

                except TimeoutError:
                    mesg = 'Finvasia log in error'
                    logger.error(mesg)
                    raise RuntimeError

                except Exception as e:
                    mesg = f'Finvasia log in error {e}'
                    logger.error(mesg)
                    raise
            else:
                logger.info(f'skipping login: setting the session!! : {susertoken}')
                ret = fv.set_session(userid=cred['userId'], password=cred['pwd'], usertoken=susertoken)
                logger.debug(f'ret: {ret} type: {type(ret)}')

                r = fv.get_user_details()
                logger.debug(f'ret: {json.dumps(r, indent=2)} type: {type(r)}')

                act_id = None
                if r is not None and 'actid' in r:
                    act_id = r.get('actid')

                dmsg = None
                if r is not None and 'dmsg' in r:
                    dmsg = r.get('dmsg')
                emsg = None
                if r is not None and 'emsg' in r:
                    emsg = r.get('emsg')

                if r is None or r ['stat'] == 'Not_Ok':
                    raise LoginFailureException

                logger.info(f'Acct: {act_id} dmsg:{dmsg} emsg:{emsg}')

            finally:
                ...
        else:
            logger.info(f'skipping login: setting the session!! : {bcc.susertoken}')
            ret = fv.set_session(userid=cred['userId'], password=cred['pwd'], usertoken=bcc.susertoken)
            logger.debug(f'ret: {ret}')

    def __search_sym_token_tsym__(self, symbol, exchange='NSE'):
        fv = self.fv

        if symbol == 'NIFTY':
            search_text = (symbol + ' INDEX')
            logger.info (f'Searching {search_text}')
        elif symbol == 'NIFTY BANK':
            search_text = symbol
            logger.info (f'Searching {search_text}')
        else:
            symbol = symbol.replace(" ", "")
            symbol = "".join(re.findall("[a-zA-Z0-9-_&]+", symbol)).upper()
            search_text = (symbol + '-EQ') if exchange == 'NSE' else symbol

        try:
            ret = fv.searchscrip(exchange=exchange, searchtext=search_text)
            token = tsym = None
            if ret is not None and ret['stat'] == 'Ok' and isinstance(ret['values'], list):
                token = ret['values'][0]['token']
                tsym = ret['values'][0]['tsym']
            else:
                logger.debug('Not found in -EQ, Trying in -BE')
                ret = fv.searchscrip(exchange=exchange, searchtext=(symbol + '-BE'))
                if ret is not None and isinstance(ret, list):
                    token = ret['values'][0]['token']
                    tsym = ret['values'][0]['tsym']
            if token is None or tsym is None:
                raise ValueError(f"token {token} or tsym {tsym} is None")
        except Exception:
            raise
        else :
            if token is None or tsym is None:
                logger.error (f'Major issue {token} {tsym}')
        
        return (str(token), tsym)


class Diu (BaseIU):
    def __init__(self, dcc: Diu_CreateConfig):
        super().__init__(dcc)

        token = None
        tsym = None
        logger.info (f'Setting the default Index: Symobl and token')
        try:
            token, tsym = self.__search_sym_token_tsym__(symbol='NIFTY')
        except Exception:
            logger.error (f'token: {token} tsym:{tsym}')
            raise 
        
        self._ul_symbol = {'symbol': 'NIFTY', 'token': token}
        logger.debug(f'{json.dumps(self._ul_symbol, indent=2)}')
        ws_wrap.WS_WrapU.DEBUG = False
        self.ws_wrap = ws_wrap.WS_WrapU(fv=self.fv, port_cfg=dcc.out_port)

        return

    def connect_to_data_feed_servers(self):
        self.ws_wrap.connect_to_data_feed_servers()

    @property
    def live_df_ctrl(self):
        return self.ws_wrap.send_data

    @live_df_ctrl.setter
    def live_df_ctrl(self, new_value:shared_classes.Ctrl):
        if new_value: 
            logger.debug ("Enabling Data Send")
        else :
            logger.debug ("Disabling Data Send")
        self.ws_wrap.send_data = new_value

    @property
    def ul_token(self):
        return self._ul_symbol['token']

    @property
    def ul_symbol(self):
        return self._ul_symbol['symbol']

    @ul_symbol.setter
    def ul_symbol(self, ul_symbol):
        self._ul_symbol['symbol'] = ul_symbol
        token, _ = self.__search_sym_token_tsym__(symbol=ul_symbol)
        self._ul_symbol['token'] = token
        logger.debug(f'{json.dumps(self._ul_symbol, indent=2)}')

    def get_latest_tick(self):
        return self.ws_wrap.get_latest_tick(self._ul_symbol['token']).c

    def disconnect_data_feed_servers(self):
        self.ws_wrap.disconnect_data_feed_servers()

    def fetch_data(self, symbol_list, output_directory, tf=3, ix=False):
        fv = self.fv

        for symbol in symbol_list:
            symbol_row = self.df[self.df['Symbol'] == symbol.upper()]
            fname = os.path.join(output_directory, f'{symbol.upper()}.csv')

            token = None
            use_alternate_server = False

            if not symbol_row.empty:
                # Accessing token based on the symbol
                token = symbol_row['Token'].values[0]
            if token is not None:
                lastBusDay = datetime.datetime.today()
                lastBusDay = lastBusDay.replace(hour=0, minute=0, second=0, microsecond=0)
                if datetime.date.weekday(lastBusDay) == 5:  # if it's Saturday
                    lastBusDay = lastBusDay - datetime.timedelta(days=1)  # then make it Friday
                elif datetime.date.weekday(lastBusDay) == 6:  # if it's Sunday
                    lastBusDay = lastBusDay - datetime.timedelta(days=2)  # then make it Friday
                # elif datetime.date.weekday(lastBusDay) == 0:      #if it's Monday
                #     lastBusDay = lastBusDay - datetime.timedelta(days = 3) #then make it Friday
                # elif datetime.date.weekday(lastBusDay) == 1:      #if it's Tuesday
                #     lastBusDay = lastBusDay - datetime.timedelta(days = 4) #then make it Friday
                # lastBusDay = lastBusDay - datetime.timedelta(days = 3)
                ret = fv.get_time_price_series(exchange='NSE', token=str(token), starttime=lastBusDay.timestamp(), interval=tf)
                if ret is not None and isinstance(ret, list):
                    df = pd.DataFrame.from_dict(ret)  # type: ignore
                    df = df.iloc[::-1]
                    df = df.drop(['stat', 'ssboe', 'intoi', 'oi', 'v'], axis=1)

                    column_mapping = {
                        'time': 'Time',
                        'into': 'Open',
                        'inth': 'High',
                        'intl': 'Low',
                        'intc': 'Close',
                        'intvwap': 'Vwap',
                        'intv': 'Volume',
                    }
                    # Use the rename method to rename the columns
                    df = df.rename(columns=column_mapping)

                    df = df[['Time', 'Open', 'High', 'Low', 'Close', 'Volume', 'Vwap']]
                    df.to_csv(fname, index=False)
                else:
                    use_alternate_server = True

            if use_alternate_server:
                def getIntraDayData(instrument):
                    instrument = urllib.parse.quote(instrument)
                    url = f'https://api.upstox.com/v2/historical-candle/intraday/{instrument}/1minute'
                    headers = {
                        'accept': 'application/json',
                        'Api-Version': '2.0',
                    }
                    response = requests.get(url, headers=headers)
                    return response.json()

                fileUrl = 'https://assets.upstox.com/market-quote/instruments/exchange/complete.csv.gz'
                symboldf = pd.read_csv(fileUrl)
                eqdf = symboldf[(symboldf.exchange == 'NSE_EQ') & (symboldf.instrument_type == 'EQUITY')]
                eqdf.reset_index(drop=True, inplace=True)
                instrument_key = eqdf.loc[eqdf['tradingsymbol'] == symbol, 'instrument_key'].values[0]

                candleRes = getIntraDayData(instrument_key)
                df = pd.DataFrame(candleRes['data']['candles'])

                if df is not None:
                    try:
                        df.rename(columns={
                            0: 'Time',
                            1: 'Open',
                            2: 'High',
                            3: 'Low',
                            4: 'Close',
                            5: 'Volume',
                            6: 'Other'  # Assuming the last column is labeled 'Other'
                        }, inplace=True)

                        # Drop the last column 'Other'
                        df.drop(columns=['Other'], inplace=True)

                        # Convert 'Time' column to the desired format
                        df['Time'] = pd.to_datetime(df['Time']).dt.strftime('%m-%d-%Y %H:%M:%S')
                        df['Time'] = pd.to_datetime(df['Time'])

                        df.set_index('Time', inplace=True)
                        # Reverse the DataFrame
                        data_frame_resampled = df.iloc[::-1]

                        # Resample to daily candles until 9:15:00
                        data_frame_resampled = data_frame_resampled.resample('3T').agg({
                            'Open': 'first',
                            'High': 'max',
                            'Low': 'min',
                            'Close': 'last',
                            'Volume': 'sum'
                        }).dropna()

                        # Reset the index
                        data_frame_resampled.reset_index(inplace=True)

                        data_frame_resampled['Time'] = data_frame_resampled['Time'].dt.strftime('%d-%m-%Y %H:%M:%S')

                        # Calculate VWAP
                        vwap = round(
                            (((data_frame_resampled['High'] + data_frame_resampled['Low'] + data_frame_resampled['Close']) / 3) *
                                data_frame_resampled['Volume']).cumsum() / data_frame_resampled['Volume'].cumsum(), 2
                        )
                        data_frame_resampled['Vwap'] = (vwap // 0.05) * 0.05
                        data_frame_resampled.to_csv(fname, index=False)
                    except Exception as e:
                        print(f'no data for sym:{symbol} exception: {e}')
                else:
                    print(f'no data for sym:{symbol}')

    def download_data_parallel(self, symbol_list, output_directory, tf):
        if self.use_pool:
            logger.info('Fetching data in parallel...')
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(self.fetch_data, [symbol], output_directory, tf) for symbol in symbol_list]
                # Wait for all tasks to complete
                concurrent.futures.wait(futures)
        else:
            for symbol in symbol_list:
                self.fetch_data([symbol], output_directory=output_directory, tf=tf)


class Tiu (BaseIU):
    CONFIRM_COUNT = 10
    CONFIRM_SLEEP_PERIOD = 0.3
    SQ_OFF_FAILURE_COUNT = 2

    def __init__(self, tcc: Tiu_CreateConfig):
        self.login = False
        try:
            super().__init__(tcc)
        except Exception:
            raise
        else:
            self.login = True

        self.__post_init__()

    def __post_init__(self):
        if self.login:
            try:
                self.fv_amount_in_ac = self.fv_ac_balance()
            except ValueError:
                logger.info('Exception occured: Login Faiulre')
                raise LoginFailureException

        mesg = f'Amount available in Finvasia A/c: INR {self.fv_amount_in_ac:n} /-'
        logger.info(mesg)
        self.update_holdings()
        self.update_positions()

    def compact_search_file(self, symbol_expdate_pairs):
        self.fv.compact_search_file(symbol_expdate_pairs)

    def get_security_info(self, exchange, symbol, token=None):

        if token is None:
            token, tsym = self.__search_sym_token_tsym__(exchange=exchange, symbol=symbol)

        if token:
            return self.fv.get_security_info(exchange=exchange, token=str(token))
        else:
            return None

    def get_broker_obj(self):
        return self.fv

    def fv_ac_balance(self):
        # {'request_time': '23:55:43 05-11-2022', 'stat': 'Ok', 'prfname': 'SHOONYA1', 'cash': '0.00', 'payin': '0.00', 'payout': '0.00',
        #   'brkcollamt': '0.00', 'unclearedcash': '0.00', 'aux_daycash': '0.00', 'aux_brkcollamt': '0.00', 'aux_unclearedcash': '0.00',
        #   'daycash': '0.00', 'turnoverlmt': '999999999999.00', 'pendordvallmt': '999999999999.00', 'blk_amt': '0.00'}
        # acct_limits = self.broker.get_balance()
        acct_limits = self.fv.get_limits()
        print(f'acct_limits: {json.dumps(acct_limits,indent=2)}')
        if isinstance(acct_limits, dict):
            if acct_limits['stat'] == "Not_Ok":
                mesg = "Unable to fetch the balance. Reason: " + acct_limits['emsg']
                logger.error(f'{mesg}')
                raise ValueError
        logger.debug(json.dumps(acct_limits, indent=2))

        self._amount_in_ac = locale.atof(acct_limits["cash"]) + locale.atof(acct_limits["payin"]) + locale.atof(acct_limits["unclearedcash"])
        try:
            self._used_margin = locale.atof(acct_limits['marginused'])
        except Exception:
            self._used_margin = float(0.0)

        return self._amount_in_ac

    def get_usable_margin(self):
        return (self._amount_in_ac - self._used_margin)

    avlble_margin = property(get_usable_margin, None, None)

    def get_strike_diff(self):
        return (self.fv.get_strike_diff())

    strike_diff = property(get_strike_diff, None, None)

    def update_holdings(self):
        ret = self.fv.get_holdings()
        if ret is not None and isinstance(ret, list):
            logger.info(f'No.of Holdings: {len(ret)}')
            for item in ret:
                try:
                    item['exch_tsym'].pop(1)
                except IndexError:
                    continue
            stocks = []
            for item in ret:
                stock = {}
                stock['exch'] = item['exch_tsym'][0]['exch']
                stock['tsym'] = item['exch_tsym'][0]['tsym']
                stock['upldprc'] = float(item['upldprc'])
                if 'holdqty' in item:
                    stock['sellableqty'] = int(item['holdqty'])
                if 'btstqty' in item:
                    stock['sellableqty'] += int(item['btstqty'])
                if 'unplgdqty' in item:
                    stock['sellableqty'] += int(item['unplgdqty'])
                if 'benqty' in item:
                    stock['sellableqty'] += int(item['benqty'])
                if 'dpqty' in item:
                    stock['sellableqty'] += int(item['dpqty'])
                if 'usedqty' in item:
                    stock['sellableqty'] -= int(item['usedqty'])

                stocks.append(stock)

            if len(stocks):
                df = self.holdings_df = pd.DataFrame(stocks)
                df.columns = df.columns.str.replace(" ", "")
                df.columns = df.columns.str.upper()
                df['TSYM'].str.strip()
                print("Holdings: ")
                print(df.to_string())
            else:
                logger.info('No holdings to update')

    def update_positions(self):
        ret = self.fv.get_positions()
        # List of dictionary
        # [{ "stat":"Ok",
        #    "uid":"",
        #  "actid":"",
        #   "exch":"NSE",
        #   "tsym":"MSUMI-EQ",
        #    "prd":"C",
        #  "token":"8596",
        # "frzqty":"1640231",
        #     "pp":"2",
        #     "ls":"1","ti":"0.05","mult":"1","prcftr":"1.000000",
        #  "daybuyqty":"80","daysellqty":"0","daybuyamt":"4976.00","daybuyavgprc":"62.20",
        # "daysellamt":"0.00","daysellavgprc":"0.00","cfbuyqty":"0","cfsellqty":"0",
        # "openbuyqty":"0","opensellqty":"0","openbuyamt":"0.00",
        # "openbuyavgprc":"0.00","opensellamt":"0.00","opensellavgprc":"0.00",
        # "dayavgprc":"62.20","netqty":"80","netavgprc":"62.20","upldprc":"0.00",
        # "netupldprc":"62.20","lp":"63.10","urmtom":"72.00","bep":"62.20","rpnl":"-0.00"}]
        #

        if ret is not None and isinstance(ret, list):
            stocks = []
            for item in ret:
                stock = {}
                qty = int(item['netqty'])
                prd = item["prd"]
                if prd == "C" and qty > 0:
                    stock['exch'] = item['exch']
                    stock['tsym'] = item['tsym']
                    stock['daybuyavgprc'] = float(item['daybuyavgprc'])
                    stock['sellableqty'] = qty
                    stocks.append(stock)

            if len(stocks):
                self.posn_df = pd.DataFrame(stocks)

                df = self.posn_df
                df.columns = df.columns.str.replace(" ", "")
                df.columns = df.columns.str.upper()
                df['TSYM'].str.strip()
                print("CNC Positions: ")
                print(self.posn_df.to_string())
                logger.info(f'No.of Positions: {len(stocks)}')
        else:
            logger.info('No positions ..')

    def order_status(self, order_id):
        r_os_list = self.fv.single_order_history(order_id)
        if r_os_list is not None:
            r_os_dict = r_os_list[0]
            return r_os_dict["status"].lower()
        else:
            return None

    def search_scrip(self, exchange, symbol):
        tsym = token = None

        if self.df is not None:
            try:
                stock_row = self.df[self.df['Symbol'] == symbol.upper()]
                if not stock_row.empty:
                    # Accessing token based on the symbol
                    token = stock_row['Token'].values[0]
                    tsym = stock_row['Tsym'].values[0]
            except Exception:
                ...
            else:
                ...
        if tsym is None and token is None:
            logger.debug(f'searching symbol in the file : {symbol} ')
            token, tsym = self.__search_sym_token_tsym__(symbol, exchange=exchange)
            logger.debug(f'token: {token} tsym: {tsym}')
            if (token is None or tsym is None) and exchange == 'NFO':
                logger.error (f'!!! Please check Expiry Date !!!')
                raise RuntimeError

        return (str(token), tsym)

    def create_sym_token_tsym_q_access(self, symbol_list=None, instruments=None):
        symbol_data = []
        tsym_data = []
        token_data = []

        if symbol_list:
            # Iterate through the symbol list and get tsym and token for each symbol
            for symbol in symbol_list:
                token, tsym = self.__search_sym_token_tsym__(symbol)
                tsym_data.append(tsym)
                token_data.append(str(token))
                symbol_data.append(symbol)

        if instruments:
            for symbol, info in instruments.items():
                logger.debug(f"Symbol: {symbol}")
                symbol = info['SYMBOL']
                if info['EXCHANGE'] == 'NSE':
                    token, tsym = self.__search_sym_token_tsym__(symbol)
                    tsym_data.append(tsym)
                    token_data.append(str(token))
                    symbol_data.append(symbol)

        data = {
            'Symbol': symbol_data,
            'Tsym': tsym_data,
            'Token': token_data
        }
        self.df = pd.DataFrame(data)
        logger.info(f'\n{self.df}')

    def fetch_ltp(self, exchange: str, token: str):
        fv = self.fv

        quote = fv.get_quotes(exchange=exchange, token=token)
        logger.debug(f'exchange:{exchange} token:{token} {json.dumps(quote,indent=2)}')
        if quote and 'c' in quote and 'ti' in quote and 'ls' in quote:
            return float(quote['lp']), float(quote['ti']), float(quote['ls'])
        else:
            return None, None, None

    def fetch_security_info(self, exchange, token):
        fv = self.fv
        r = fv.get_security_info(exchange=exchange, token=token)
        return r

    def get_enabled_gtts(self):
        return self.fv.get_enabled_gtts()

    def get_pending_gtt_order(self):
        return self.fv.get_pending_gtt_order()

    def place_and_confirm_tez_order(self, orders: List[Union[shared_classes.I_B_MKT_Order, shared_classes.I_S_MKT_Order,
                                                             shared_classes.BO_B_MKT_Order,
                                                             shared_classes.Combi_Primary_B_MKT_And_OCO_S_MKT_I_Order_NSE,
                                                             shared_classes.Combi_Primary_B_MKT_And_OCO_S_MKT_I_Order_NFO,
                                                             shared_classes.Combi_Primary_S_MKT_And_OCO_B_MKT_I_Order_NSE]],
                                    tag: str | None = None, use_gtt_oco=False):

        def process_result(order, r):
            nonlocal self
            status = Tiu_OrderStatus.HARD_FAILURE

            qty = order.quantity
            ord_status = shared_classes.OrderStatus()
            if r is not None:
                if r['stat'] == 'Not_Ok':
                    logger.info(f'place_order : Failure {r["emsg"]}')
                    ord_status.emsg = r['emsg']
                else:
                    logger.debug(f'Order Attempt success:: order id  : {r["norenordno"]}')
                    order_id = ord_status.order_id = r["norenordno"]
                    reason1 = "rms:blocked"  # TO BE TESTED
                    reason2 = "margin"
                    reason3 = 'RMS: Auto Square Off Block'.lower()  # TO BE TESTED
                    for check_cnt in range(0, Tiu.CONFIRM_COUNT):
                        r_os_list = self.fv.single_order_history(order_id)

                        # Shoonya gives a list for all status of order, we are interested in first one
                        r_os_dict = r_os_list[0]

                        # Different stages of the order
                        # PENDING
                        # CANCELED
                        # OPEN
                        # REJECTED
                        # COMPLETE
                        # TRIGGER_PENDING
                        # INVALID_STATUS_TYPE

                        # logger.debug(f'{tag}: order status: {r_os_dict["status"]} {json.dumps(r_os_dict,indent=2)}')
                        logger.debug(f'{tag}: order_id: {order_id} order status: {r_os_dict["status"]}')

                        if r_os_dict['status'].lower() == 'rejected':
                            rej_reason = r_os_dict['rejreason'].lower()
                            if rej_reason.find(reason1) != -1:
                                status = Tiu_OrderStatus.SOFT_FAILURE_REJRMS
                                break
                            elif rej_reason.find(reason2) != -1:
                                status = Tiu_OrderStatus.SOFT_FAILURE_REJRMS
                                break
                            elif rej_reason.find(reason3) != -1:
                                status = Tiu_OrderStatus.SOFT_FAILURE_REJRMS
                                break
                            else:
                                break
                        filled_qty = 0
                        if 'fillshares' in r_os_dict:
                            filled_qty = int(r_os_dict['fillshares'])
                            unfilled_qty = qty - filled_qty
                            if r_os_dict["status"].lower() == "complete":
                                avg_price = float(r_os_dict['avgprc'])
                                order_id = r_os_dict['norenordno']
                                fill_timestamp = r_os_dict['exch_tm']
                                if filled_qty == qty:
                                    ord_status.avg_price = avg_price
                                    ord_status.trantype = order.buy_or_sell
                                    if order.buy_or_sell == 'B':
                                        ord_status.fillshares = filled_qty
                                    else:
                                        ord_status.fillshares = -(filled_qty)
                                    ord_status.fill_timestamp = fill_timestamp
                                    # ord_resp = OrderResp(avg_price=avg_price, order_id=order_id, quantity=qty, ft=fill_timestamp)
                                    status = Tiu_OrderStatus.SUCCESS
                                    break
                                else:
                                    ...
                            elif unfilled_qty:
                                ...
                            else:
                                ...
                            logger.debug(f'{tag}: {check_cnt}: {unfilled_qty} Sleeping for {Tiu.CONFIRM_SLEEP_PERIOD} secs')
                        time.sleep(Tiu.CONFIRM_SLEEP_PERIOD)
                    else:  # This else is included with the FOR statement above
                        # Not filled even after few secs.
                        cancel_r_dict = self.fv.cancel_order(order_id)
                        if cancel_r_dict and cancel_r_dict["stat"] == "Ok":
                            r_os_list = self.fv.single_order_history(order_id)
                            # Shoonya gives a list for all status of order, we are interested in first one
                            r_os_dict = r_os_list[0]
                            filled_qty = 0
                            if 'fillshares' in r_os_dict:
                                filled_qty = int(r_os_dict['fillshares'])

                            if filled_qty:
                                fill_timestamp = r_os_dict['exch_tm']
                                avg_price = 0
                                if 'avgprc' in r_os_dict:
                                    avg_price = float(r_os_dict['avgprc'])

                                ord_status.avg_price = avg_price
                                if order.buy_or_sell == 'B':
                                    ord_status.fillshares = filled_qty
                                else:
                                    ord_status.fillshares = -(filled_qty)
                                ord_status.fill_timestamp = fill_timestamp
                                # ord_resp = OrderResp(avg_price=avg_price, order_id=order_id, quantity=filled_qty, ft=fill_timestamp)
                                status = Tiu_OrderStatus.SUCCESS if filled_qty == qty else Tiu_OrderStatus.SOFT_FAILURE_QTY
                            else:
                                status = Tiu_OrderStatus.HARD_FAILURE
                        else:
                            status = Tiu_OrderStatus.HARD_FAILURE

            if status == Tiu_OrderStatus.HARD_FAILURE:
                mesg = f'{tag}: Check manually, Quit the App, Orders not going Through'
                logger.error(mesg)
                if self.notifier is not None:
                    self.notifier.put_message(mesg)
            else:
                logger.debug(str(ord_status))

            # To debug following is used during off market hours
            # ord_status.avg_price = 1
            # if order.buy_or_sell == 'B':
            #     ord_status.fillshares = 1
            # else:
            #     logger.info('making qty = -1')
            #     ord_status.fillshares = -1
            # ord_status.fill_timestamp = 1
            # ord_status.order_id = str(12)
            # status = Tiu_OrderStatus.SUCCESS
            return (status, ord_status)

        def place_ind_order(com_order):
            nonlocal self

            order = com_order
            if isinstance(order, shared_classes.Combi_Primary_B_MKT_And_OCO_S_MKT_I_Order_NFO) or \
               isinstance(order, shared_classes.Combi_Primary_B_MKT_And_OCO_S_MKT_I_Order_NSE) or \
               isinstance(order, shared_classes.Combi_Primary_S_MKT_And_OCO_B_MKT_I_Order_NSE):
                order = order.primary_order

            logger.debug(f'placing {order.buy_or_sell} order {order}')
            r = self.fv.place_order(buy_or_sell=order.buy_or_sell,
                                    product_type=order.product_type,
                                    exchange=order.exchange,
                                    tradingsymbol=order.tradingsymbol,
                                    quantity=order.quantity, discloseqty=0,
                                    trigger_price=order.trigger_price,
                                    price=order.price,
                                    price_type=order.price_type,
                                    bookloss_price=order.book_loss_price,
                                    bookprofit_price=order.book_profit_price,
                                    trail_price=0.0,  # trail_price should be 0 for finvasia.
                                    retention=order.retention, remarks=order.remarks)

            r_tuple = process_result(order=order, r=r)
            return r_tuple

        def place_ind_oco_order(oco_tuple):
            nonlocal self
            order, r_tuple = oco_tuple
            primary_order_status, ord_status = r_tuple
            status = Tiu_OrderStatus.HARD_FAILURE

            if primary_order_status == Tiu_OrderStatus.SUCCESS:
                ord_status: shared_classes.OrderStatus = ord_status
                quantity = abs(ord_status.fillshares)
                f_order: shared_classes.OCO_FOLLOW_UP_MKT_I_Order = order.follow_up_order

                remarks = f_order.remarks + '_' + ord_status.order_id if f_order.remarks else ord_status.order_id

                # logger.info(f'placing {f_order.buy_or_sell} order: {order} f_order order {f_order}')

                r = self.fv.place_gtt_oco_order(buy_or_sell=f_order.buy_or_sell,
                                                product_type=f_order.product_type,
                                                exchange=f_order.exchange,
                                                tradingsymbol=f_order.tradingsymbol,
                                                book_loss_alert_price=f_order.book_loss_alert_price,
                                                book_loss_price=f_order.book_loss_price,
                                                book_loss_price_type=f_order.price_type,
                                                book_profit_alert_price=f_order.book_profit_alert_price,
                                                book_profit_price=f_order.book_profit_price,
                                                book_profit_price_type=f_order.price_type,
                                                quantity=quantity,
                                                remarks=remarks)
                ord_status = shared_classes.OrderStatus()
                if r is not None:
                    if r['stat'] == 'Not_Ok':
                        logger.info(f'OCO place_order : Failure {r["emsg"]}')
                        ord_status.emsg = r['emsg']
                    else:
                        if r['stat'] == 'OI created':
                            logger.info(f'Place order success:: al id  : {r["al_id"]}')
                            ord_status.al_id = r["al_id"]
                            order.al_id = r['al_id']
                            status = Tiu_OrderStatus.SUCCESS

                return status, ord_status

        resp_exception = 0
        resp_ok = 0
        result = []
        oco_tuple_list = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(place_ind_order, order): order for order in orders}

        for future in concurrent.futures.as_completed(futures):
            order = futures[future]
            try:
                r_tuple = future.result()
                result.append(r_tuple)
            except Exception as e:
                logger.error(f"Exception for item {order}: {e}")
                logger.error(traceback.format_exc())
                resp_exception = resp_exception + 1
            else:
                status, ord_status = r_tuple
                if status == Tiu_OrderStatus.SUCCESS:
                    resp_ok = resp_ok + 1
                    order.order_id = ord_status.order_id
                    oco_order = (order, r_tuple)
                    logger.debug(f'{ord_status}')
                    oco_tuple_list.append(oco_order)

        if use_gtt_oco:
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = {executor.submit(place_ind_oco_order, oco_tuple): oco_tuple for oco_tuple in oco_tuple_list}

            for future in concurrent.futures.as_completed(futures):
                oco_tuple = futures[future]
                try:
                    r_tuple = future.result()
                except Exception as e:
                    logger.error(f"Exception for item {oco_tuple}: {e}")
                    logger.error(traceback.format_exc())
                    resp_exception = resp_exception + 1
                else:
                    status, ord_status = r_tuple
                    if status == Tiu_OrderStatus.SUCCESS:
                        resp_ok = resp_ok + 1
                        order, r_tuple = oco_tuple
                        order.al_id = ord_status.al_id

        return resp_exception, resp_ok, result

    def square_off_position(self, df: pd.DataFrame, symbol=None):
        fv = self.fv

        try:
            df_filtered = df[(df['Qty'] != 0) & (df['Status'] == 'SUCCESS')]
        except Exception:
            logger.info('No position to Square off')
            return
        else:
            ...

        if symbol:
            try:
                df_filtered = df_filtered[df_filtered['TradingSymbol_Token'].str.startswith(symbol)]
            except Exception:
                logger.info('No position to Square off')
                return
            else:
                ...
        try:
            order_id_list = df_filtered['Order_ID'].tolist()
        except TypeError:
            logger.info('No order to square off')
            return

        r = fv.get_order_book()
        if r is not None and isinstance(r, list):
            order_book_df = pd.DataFrame(r)
            try:
                filtered_df = order_book_df[order_book_df['norenordno'].isin(order_id_list)]
                logger.debug(f'\n{filtered_df.to_string()}')
            except Exception as e:
                logger.debug(f'Exception : {e}')
            else:
                for index, row in filtered_df.iterrows():
                    status = row['status'].lower()
                    if status == 'open' or status == 'pending' or status == 'trigger_pending':
                        fv.cancel_order(row['norenordno'])

            # order_book_df remains intact even after filtered df, so can be reused.
            try:
                filtered_df = order_book_df[order_book_df['snonum'].isin(order_id_list)]
                logger.debug(f'\n{filtered_df.to_string()}')
            except Exception as e:
                logger.debug(f'Exception : {e}')
            else:
                for index, row in filtered_df.iterrows():
                    if '-EQ' in row['tsym']:
                        status = row['status'].lower()
                        if (status == 'open' or status == 'pending' or status == 'trigger_pending') and int(row['snoordt']) == 0:
                            r = fv.exit_order(row['snonum'], 'B')
                            if r is None:
                                logger.error("Exit order result is None. Check Manually")
                            if 'stat' in r and r['stat'] == 'Ok':
                                logger.debug(f'child order of {row["norenordno"]} : {row["snonum"]}, status: {json.dumps (r, indent=2)}')
                            else:
                                logger.error('Exit order Failed, Check Manually')
        else:
            logger.info('get_order_book Failed, Check Manually')
            return

        r = self.fv.get_pending_gtt_order()

        if r is not None and isinstance(r, list):
            gtt_p_df = pd.DataFrame(r)
            logger.debug(f'\n{gtt_p_df}')
            try:
                alert_id_list = df_filtered['OCO_Alert_ID'].tolist()
            except Exception as e:
                logger.debug(f'Exception : {e}')
            else:
                # Check oco order pending ..
                # if there are orders still open ..cancel the orders
                if gtt_p_df is not None and len(gtt_p_df):
                    for alert_id in alert_id_list:
                        if not pd.isna(alert_id) and alert_id in gtt_p_df['al_id'].values:
                            logger.debug(f'cancelling al_id : {alert_id}')
                            r = self.fv.cancel_gtt_order(al_id=str(alert_id))
                            if r is not None and isinstance(r, dict):
                                if 'emsg' in r:
                                    logger.debug(f'alert_id: {alert_id} : {r["emsg"]}')
                                if alert_id == r['al_id'] and r['stat'] == "OI deleted":
                                    logger.debug(f'alert id {alert_id} cancellation success')

        # Important
        # if the gtt orders are triggered, there will be pending orders
        # In this project, all OCO orders are triggered at market. So, there will not be any pending OCO triggered orders.
        # But, to ensure OCO orders are complete or have hit a terminal state, need to do some thing.
        # e.g, filter the orders that have remarks 'TEZ' parent order-id which is in the order_id_list, cancel those.

        try:
            sum_qty_by_symbol = df_filtered.groupby('TradingSymbol_Token')['Qty'].sum().reset_index()
        except Exception as e:
            logger.info(f'Not able to sum qty by symbol: {e}')
            return

        r = fv.get_positions()
        if r is not None and isinstance(r, list):
            posn_df = pd.DataFrame(r)
            posn_df.loc[posn_df['prd'] == 'I', 'netqty'] = posn_df.loc[posn_df['prd'] == 'I', 'netqty'].apply(lambda x: int(x))
            posn_df = posn_df.loc[(posn_df['prd'] == 'I')]

        for index, row in sum_qty_by_symbol.iterrows():
            symbol = row['TradingSymbol_Token']
            token = symbol.split('_')[1]
            tsym = symbol.split('_')[0]
            rec_qty = row['Qty']
            if len(posn_df):
                try:
                    posn_qty = posn_df.loc[posn_df['token'] == str(token), 'netqty'].values[0]
                except IndexError:
                    posn_qty = 0
                else:
                    ...
            else:
                posn_qty = 0
            net_qty = abs(posn_qty)

            # It is possible that manually, user could do following:
            # case 1: nothing
            #         System finds the net quantity is equal to the recorded qty and proceeds
            #         if rec_qty is +ve, it should sell else buy
            # case 2: square off partially
            #         Recorded qty > net_qty,   so, in this case square off remaining qty.
            #         rem_qty = min(abs(rec_qty), net_qty)
            #         example1 : rec_qty = 8,  net_qty = 6  exit_qty = 6
            #         example2 : rec_qty = -8,  net_qty = -6  exit_qty = 6
            # case 3: square off fully
            #         net_qty is 0, so nothing should be done.
            # case 4: Taken additional qty.
            #         Now, it is user's responsibility to manually exit the extra position.
            #         System would square off only those, which it has triggered.
            #         rem_qty = min(abs(rec_qty), net_qty)
            #         example1 : rec_qty = 8,  net_qty = 10   exit_qty = 8
            #         example2 : rec_qty = -8,  net_qty = -10  exit_qty = 8
            #         example3 : rec_qty = 8,   net_qty = -10, exit_qty = 8 sell
            #         example4 : rec_qty = -8,   net_qty = +10, exit_qty = 8 buy

            if net_qty > 0:
                # exit the position
                # important, rec_qty and net_qty should be both +ve values.
                exit_qty = min(abs(rec_qty), net_qty)
                logger.info(f'exit qty:{exit_qty}')
                exch = 'NSE' if '-EQ' in tsym else 'NFO'
                # Very Important:  Following should use frz_qty for breaking order into slices
                r = self.fv.get_security_info(exchange=exch, token=token)
                logger.debug(f'{json.dumps(r, indent=2)}')

                frz_qty = None
                if isinstance(r, dict) and 'frzqty' in r:
                    frz_qty = int(r['frzqty'])
                else:
                    frz_qty = exit_qty+1

                if isinstance(r, dict) and 'ls' in r:
                    ls = int(r['ls'])  # lot size
                else:
                    ls = 1

                failure_cnt = 0
                buy_or_sell = 'S' if rec_qty > 0 else 'B'
                while (exit_qty and failure_cnt <= Tiu.SQ_OFF_FAILURE_COUNT):
                    per_leg_exit_qty = frz_qty if exit_qty > frz_qty else exit_qty
                    per_leg_exit_qty = int(per_leg_exit_qty / ls) * ls
                    r = self.fv.place_order(buy_or_sell, product_type='I', exchange=exch, tradingsymbol=tsym,
                                            quantity=per_leg_exit_qty, price_type='MKT', discloseqty=0.0)

                    if r is None or r['stat'] == 'Not_Ok':
                        logger.info(f'Exit order Failed:  {r["emsg"]}')
                        failure_cnt += 1
                    else:
                        logger.info(f'Exit Order Attempt success:: order id  : {r["norenordno"]}')
                        order_id = r["norenordno"]
                        r_os_list = self.fv.single_order_history(order_id)
                        # Shoonya gives a list for all status of order, we are interested in first one
                        r_os_dict = r_os_list[0]
                        if r_os_dict["status"].lower() == "complete":
                            logger.info(f'Exit order Complete: order_id: {order_id}')
                        else:
                            logger.info(f'Exit order InComplete: order_id: {order_id} Check Manually')
                        exit_qty -= per_leg_exit_qty

                if failure_cnt > 2 or exit_qty:
                    logger.info(f'Exit order InComplete: order_id: {order_id} Check Manually')
                    raise OrderExecutionException
