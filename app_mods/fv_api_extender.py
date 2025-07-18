"""
File: fv_api_extender.py
Author: [Tarakeshwar NC]
Date: January 15, 2024
Description:  This script provides wrapper to the shoonya apis.
"""
# Copyright (c) [2024] [Tarakeshwar N.C]
# This file is part of the Tez project.
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

import app_utils as utils

logger = utils.get_logger(__name__)

try:
    import io
    import json
    import os
    import time
    import urllib
    import re
    import zipfile
    from dataclasses import dataclass
    from datetime import datetime
    from difflib import SequenceMatcher
    from app_utils import FAILURE, SUCCESS
    from threading import Event, Thread, Lock

    import pandas as pd
    import requests
    from NorenRestApiPy.NorenApi import NorenApi

    from .shared_classes import Market_Timing

except Exception as e:
    logger.debug(traceback.format_exc())
    logger.error(("Import Error " + str(e)))
    sys.exit(1)


class FeedBaseObj(object):
    DATAFEED_TIMEOUT = float(3)
    FORCE_RECONNECT_COUNT_THRESHOLD = 10

    def __init__(self, ws_monitor_cfg: bool = True):
        self.lock = Lock ()
        self.ws_connected = False

        self.ws_monitor_flag = ws_monitor_cfg
        self.ws_v2_th = None
        self.ws_v2_data_flow_evt = Event()
        self.ws_v2_exit_evt = Event()

        self.app_cb_on_open = None
        self.app_cb_on_disconnect = None
        self.app_cb_on_error = None
        self.app_cb_subscribe = None
        self.app_cb_order_update = None
        self._force_reconnect = False
        self.force_reconnect_ts = None
        self.force_reconnect_count = 0
        return

    def get_force_reconnect (self):
        return self._force_reconnect

    def set_force_reconnect (self, reconnect:bool):
        logger.debug (f"{self._force_reconnect} --> {reconnect}")
        with self.lock:
            self._force_reconnect = reconnect

    force_reconnect = property (get_force_reconnect, set_force_reconnect)

@dataclass
class ShoonyaApiPy_CreateConfig (object):
    inst_prefix:str
    dl_file: bool = True
    use_file: bool = True
    master_file: str = None
    dl_filepath: str = None
    market_hours: Market_Timing = None
    ws_monitor_cfg: bool = True
    test_env:bool = False


class ShoonyaApiPy(NorenApi, FeedBaseObj):
    __name = "FINVASIA_IF"
    DATAFEED_TIMEOUT: float = float(10.0)  # 5 secs time out
    INITIAL_TIMEOUT: float = float(5.0)
    __count = 0

    def __init__(self, cc: ShoonyaApiPy_CreateConfig):

        def download_unzip_symbols_file(url, folder, srcfile, dstfile):
            ret = FAILURE

            try:
                # Download the zip file
                response = urllib.request.urlopen(url, timeout=60)
            except requests.exceptions.Timeout:
                logger.debug(f'{self.inst_id} requests Timeout exception occured')
            except Exception as e:
                logger.debug(f'{self.inst_id} Exception occured: {str(e)}')
            else:
                data = response.read()

                # Extract the zip file
                with zipfile.ZipFile(io.BytesIO(data)) as zip_ref:
                    logger.debug(f'{self.inst_id} extracting the zip file')
                    zip_ref.extractall(folder)

                if os.path.exists(srcfile):
                    logger.debug(f'{self.inst_id} Renaming the file {srcfile} -> {dstfile}')
                    os.rename(srcfile, dstfile)
                    ret = SUCCESS

            return ret

        logger.info(f'{ShoonyaApiPy.__count}: Creating Shoonya Object..')
        self.inst_id = f'{ShoonyaApiPy.__count} {cc.inst_prefix} : '

        if cc.test_env:
            host = 'https://kwtest.shoonya.com/NorenWClientTP/'
            ws_host = 'wss://kwtest.shoonya.com/NorenWSTP/'
            logger.debug (f'setting the Test environment hosts {host} {ws_host}')
        else:
            host = 'https://api.shoonya.com/NorenWClientTP/'
            ws_host = 'wss://api.shoonya.com/NorenWSTP/'
            logger.debug (f'setting the Real environment hosts {host}  {ws_host}')

        NorenApi.__init__(self, host=host,websocket=ws_host)
        FeedBaseObj.__init__(self, ws_monitor_cfg=cc.ws_monitor_cfg)

        dl_file = cc.dl_file
        dl_filepath = cc.dl_filepath
        self.shoonya_api_host = host

        self.scripmaster_url: str = "https://api.shoonya.com/NSE_symbols.txt.zip"
        self.nfo_scripmaster_url: str = 'https://api.shoonya.com/NFO_symbols.txt.zip'
        self.scripmaster_folder: str = dl_filepath
        self._scripmaster_file: str = cc.master_file if cc.master_file and not dl_file else None
        self.use_file = cc.use_file

        self.shoonya_userid = None
        self.shoonya_accountid = None
        self.shoonya_susertoken = None

        if cc.market_hours is None:
            self.mh = Market_Timing()
        else:
            self.mh = cc.market_hours

        hr = datetime.strptime(self.mh.mo, "%H:%M").hour
        min = datetime.strptime(self.mh.mo, "%H:%M").minute
        self.m_open = datetime.now().replace(hour=hr, minute=min, second=0, microsecond=0)

        hr = datetime.strptime(self.mh.mc, "%H:%M").hour
        min = datetime.strptime(self.mh.mc, "%H:%M").minute
        self.m_close = datetime.now().replace(hour=hr, minute=min, second=0, microsecond=0)
        logger.debug(f'{self.inst_id} market open: {self.m_open} market close: {self.m_close}')

        self.streamingdata = None

        if dl_file and dl_filepath:
            url = self.scripmaster_url
            filename = os.path.basename(url)  # Get the filename from the URL
            filename = filename[:-4]  # Remove the .zip extension

            dstfilename = self._scripmaster_file = os.path.join(self.scripmaster_folder, f'FV_{filename}')
            srcfilename = os.path.join(self.scripmaster_folder, filename)

            logger.debug(f'{self.inst_id} srcfilename: {srcfilename} dstfilename:{dstfilename}')

            logger.info(f'{self.inst_id} scripmaster_file: {self._scripmaster_file}')
            new_file = False
            if os.path.exists(self._scripmaster_file):
                timestamp = os.path.getmtime(self._scripmaster_file)
                modification_datetime = datetime.fromtimestamp(timestamp)

                # modification time should be more than 8:30 am
                if modification_datetime >= datetime.now().replace(hour=8, minute=45, second=0, microsecond=0):
                    new_file = True
                if not new_file:
                    logger.debug(f'{self.inst_id} Removing the file: {self._scripmaster_file}')
                    os.remove(self._scripmaster_file)
            if not new_file:
                download_unzip_symbols_file(url=url, folder=self.scripmaster_folder, srcfile=srcfilename, dstfile=dstfilename)

            nfo_url = self.nfo_scripmaster_url
            nfo_filename = os.path.basename(nfo_url)  # Get the filename from the URL
            nfo_filename = nfo_filename[:-4]  # Remove the .zip extension

            nfo_dstfilename = self.nfo_scripmaster_file = os.path.join(self.scripmaster_folder, f'FV_{nfo_filename}')
            nfo_srcfilename = os.path.join(self.scripmaster_folder, nfo_filename)
            logger.debug(f'{self.inst_id} nfo_srcfilename: {nfo_srcfilename} nfo_dstfilename:{nfo_dstfilename}')

            logger.info(f'{self.inst_id} nfo_scripmaster_file: {self.nfo_scripmaster_file}')
            if os.path.exists(self.nfo_scripmaster_file):
                os.remove(self.nfo_scripmaster_file)
            download_unzip_symbols_file(url=nfo_url, folder=self.scripmaster_folder, srcfile=nfo_srcfilename, dstfile=nfo_dstfilename)

        self.symbol_dict = {}

        ShoonyaApiPy.__count += 1
        logger.info(f'{self.inst_id} Creating Shoonya Object..Done')

    @property
    def scripmaster_file(self):
        return self._scripmaster_file

    def login(self, userid, password, twoFA, vendor_code, api_secret, imei):
        self.shoonya_userid = userid
        self.shoonya_accountid = userid
        r = NorenApi.login(self, userid, password, twoFA, vendor_code, api_secret, imei)
        if r is not None and isinstance(r, dict):
            self.shoonya_susertoken = r['susertoken']
        return r

    def set_session(self, userid, password, usertoken):
        self.shoonya_userid = userid
        self.shoonya_accountid = userid
        self.shoonya_susertoken = usertoken
        return super().set_session(userid, password, usertoken)

    def compact_search_file(self, symbol_expdate_pairs):
        input_file_path = self.nfo_scripmaster_file
        output_file_path = os.path.splitext(input_file_path)[0] + '.csv'

        with open(input_file_path, 'r') as file:
            header = file.readline().strip()

        # Convert the first line to a list of columns
        # Extra comma at the end creates extra column in the dataframe. This is
        # elminated by the following way.
        columns = [col for col in header.split(',') if col]
        # Create an empty DataFrame to store the results
        results = pd.DataFrame(columns=columns)
        # Iterate over each symbol and expiry date combination
        for symbol, expdate in symbol_expdate_pairs:
            df = pd.read_csv(input_file_path, sep=',', usecols=columns)
            df = df[(df['Symbol'] == symbol) & (df['Expiry'] == expdate)]
            df = df.astype(object)
            results = pd.concat([results, df], ignore_index=True)
            self.symbol_dict[symbol] = df

        logger.debug (f'Saving file: {output_file_path}')
        results.to_csv(output_file_path, index=False)

    def get_strike_diff(self):
        input_file_path = self.nfo_scripmaster_file
        input_file_path = os.path.splitext(input_file_path)[0] + '.csv'
        data = pd.read_csv(input_file_path)

        # Filter data for Option Type PE
        pe_data = data[data['OptionType'] == 'PE']

        # Extract Strike Prices for PE options
        strike_prices = pe_data['StrikePrice'].tolist()

        # Sort the Strike Prices
        strike_prices.sort()

        # Calculate differences between consecutive Strike Prices
        differences = [strike_prices[i+1] - strike_prices[i] for i in range(len(strike_prices)-1)]

        # Find the minimum difference
        min_difference = min(differences)
        return min_difference

    def searchscrip(self, exchange, searchtext):
        # check if the symbol is available in the local txt file.
        # if not available then call the Parent search scrip

        def string_similarity(str1, str2):
            similarity = SequenceMatcher(None, str1, str2).ratio()
            return similarity

        def check_beginning_match(str1, str2, min_length=5):
            return str1[:min_length] == str2[:min_length]

        def check_similarity_and_beginning_match(str1, str2, min_length=5, threshold=0.95):
            is_beginning_match = check_beginning_match(str1, str2, min_length)
            similarity_percentage = string_similarity(str1, str2) * 100

            return is_beginning_match and (similarity_percentage >= threshold * 100)

        def read_symbol_info(filename, exchange, search_txt):
            # Open the symbol file for reading
            with open(filename, 'r') as f:
                # Read the file contents into a list of lines
                lines = f.readlines()

            # Create an empty dictionary to store the results
            resDict = {}
            values = []
            resDict['stat'] = 'Not_Ok'
            resDict["values"] = values

            # Iterate over each line in the file
            for line in lines:
                # Split the line into a list of values
                line_values = line.strip().split(',')
                # Extract the exchange, token, and trading symbol from the values list
                if exchange == 'NSE':
                    exch, token, _, symbol, tsym, _, _, _ = line_values
                elif exchange == 'NFO':
                    exch, token, lotsize, symbol, tsym, expiry, instrument, optiontype, strikeprice, tick_size, _ = line_values
                else:
                    ...

                # Check if the exchange and symbol match the desired criteria
                if exchange == 'NSE':
                    if (symbol == search_txt or tsym == search_txt):
                        logger.debug(f'{self.inst_id} {line_values}')
                        # Add the token and trading symbol to the result dictionary
                        # For NIFTY 50 symbol and trading symbols are interchanged in the NSE_symbols.txt
                        if symbol.upper() == 'NIFTY 50' or tsym.upper() == 'NIFTY INDEX':
                            tsym = 'Nifty 50'

                        sym_dict = {'exch': exchange, 'token': int(token.strip()), 'tsym': tsym.strip()}
                        values.append(sym_dict)
                        resDict['stat'] = 'Ok'
                        break

                elif exchange == 'NFO':
                    if check_similarity_and_beginning_match(tsym, search_txt):
                        logger.debug(f'{self.inst_id} {line_values}')
                        sym_dict = {'exch': exchange, 'token': int(token.strip()), 'tsym': tsym.strip()}
                        values.append(sym_dict)
                        resDict['stat'] = 'Ok'
                        break

            if resDict['stat'] != 'Ok':
                return None
            else:
                return resDict

        use_file = self.use_file

        found = False
        if exchange == 'NSE':
            scripmaster_file = self._scripmaster_file
        elif exchange == 'NFO':
            def extract_ul(searchtext):
                match = re.match(r'^[A-Z]+', searchtext)
                if match:
                    logger.debug (f'Able to extract UL: {searchtext} {match.group(0)}')
                    return match.group(0)
                return None

            ul_key = extract_ul(searchtext)
            if ul_key:
                # Check if the symbol is in the dictionary
                if ul_key in self.symbol_dict:
                    df = self.symbol_dict[ul_key]
                    # Check if searchtext is in the DataFrame
                    matching_rows = df.loc[df['TradingSymbol'] == searchtext]
                    if not matching_rows.empty:
                        # Access the first matching row
                        first_matching_row = matching_rows.iloc[0]

                        resDict = {}
                        values = []
                        resDict['stat'] = 'Not_Ok'
                        resDict["values"] = values

                        # Create the sym_dict
                        sym_dict = {
                            'exch': exchange,
                            'token': first_matching_row['Token'],
                            'tsym': first_matching_row['TradingSymbol']
                            }
                        values.append(sym_dict)
                        resDict['stat'] = 'Ok'
                        logger.debug (f'Found in local dataframe: {json.dumps(sym_dict, indent=2)}')
                        return resDict
                    else:
                        logger.debug(f"{searchtext} not found in {ul_key} DataFrame")

            scripmaster_file = self.nfo_scripmaster_file
            csv_file_path = os.path.splitext(scripmaster_file)[0] + '.csv'
            logger.info(f'{self.inst_id} Reading from {csv_file_path} ')
            if os.path.exists(csv_file_path):
                logger.debug(f'{self.inst_id} {csv_file_path} exists')
                df = pd.read_csv(csv_file_path)
                # Extract row where 'searchtext' is present in the 'tsym' column
                matching_rows = df.loc[df['TradingSymbol'] == searchtext]
                # Check if any rows were found
                if not matching_rows.empty:
                    # Access the first matching row
                    first_matching_row = matching_rows.iloc[0]

                    resDict = {}
                    values = []
                    resDict['stat'] = 'Not_Ok'
                    resDict["values"] = values

                    # Create the sym_dict
                    sym_dict = {
                        'exch': exchange,
                        'token': first_matching_row['Token'],
                        'tsym': first_matching_row['TradingSymbol']
                        }
                    values.append(sym_dict)
                    resDict['stat'] = 'Ok'
                    found = True
        else:
            ...

        if not found:
            logger.debug(f'{self.inst_id} scripmaster_file: {scripmaster_file} use_file: {use_file}')
            if os.path.exists(scripmaster_file) and use_file:
                logger.debug(f"{self.inst_id} Searching scrip in the {scripmaster_file} {exchange} {searchtext}")
                sym_info = read_symbol_info(scripmaster_file, exchange=exchange, search_txt=searchtext)
                if sym_info is None:
                    logger.debug(f"{self.inst_id} Searching scrip through api {exchange} {searchtext}")
                    sym_info = super(ShoonyaApiPy, self).searchscrip(exchange=exchange, searchtext=searchtext)
                    logger.debug(f"{self.inst_id} {searchtext} {sym_info}")
                    return sym_info
                else:
                    return sym_info
            else:
                logger.debug(f"{self.inst_id} Searching scrip through api {exchange} {searchtext}")
                return super(ShoonyaApiPy, self).searchscrip(exchange=exchange, searchtext=searchtext)
        else:
            return resDict

    def get_user_details(self):
        url = f'{self.shoonya_api_host}/UserDetails'
        # prepare the data
        values = {'ordersource': 'API'}
        values["uid"] = self.shoonya_userid

        payload = 'jData=' + json.dumps(values) + f'&jKey={self.shoonya_susertoken}'

        res = requests.post(url, data=payload)

        resDict = json.loads(res.text)
        if resDict['stat'] == 'Not_Ok':
            logger.debug(resDict['emsg'])
            return None

        return resDict

    def get_order_margin (self, buy_or_sell,
                          product_type, exchange, tradingsymbol,
                          quantity, price_type,
                          price=0.0, trigger_price=None):

        url = f'{self.shoonya_api_host}/GetOrderMargin'

        # prepare the data
        values = {'ordersource': 'API'}
        values["uid"] = self.shoonya_userid
        values["actid"] = self.shoonya_accountid
        values["trantype"] = buy_or_sell
        values["prd"] = product_type
        values["exch"] = exchange
        values["tsym"] = urllib.parse.quote_plus(tradingsymbol)
        values["qty"] = str(quantity)
        values["prctyp"] = price_type
        values["prc"] = str(price)
        values["rorgqty"] = "0"
        values["rorgprc"] = "0"

        if (price_type == "SL-LMT" or price_type == "SL_MKT"):
            values['trgprc'] = str(trigger_price)

        payload = 'jData=' + json.dumps(values) + f'&jKey={self.shoonya_susertoken}'

        res = requests.post(url, data=payload)

        resDict = json.loads(res.text)
        if resDict['stat'] == 'Not_Ok':
            logger.debug(resDict['emsg'])
            return None

        return resDict


    def place_gtt_order(self, buy_or_sell, alert_cond: str,
                        product_type, exchange, tradingsymbol, quantity,
                        discloseqty, alert_price, price_type, price=0.0,
                        trigger_price=None, retention='DAY', remarks=None):
        url = f'{self.shoonya_api_host}/PlaceGTTOrder'

        # prepare the data
        values = {'ordersource': 'API'}
        values["uid"] = self.shoonya_userid
        values["actid"] = self.shoonya_accountid
        values["trantype"] = buy_or_sell

        values["prd"] = product_type
        values["exch"] = exchange
        values["tsym"] = urllib.parse.quote_plus(tradingsymbol)
        values["qty"] = str(quantity)
        values["dscqty"] = str(discloseqty)
        values["prctyp"] = price_type
        values["prc"] = str(price)
        values["trgprc"] = str(trigger_price)
        values["ret"] = retention
        values["remarks"] = remarks

        if alert_cond == 'LTP_ABOVE_ALERT_PRICE':
            values["ai_t"] = "LTP_A_O"
        elif alert_cond == 'LTP_BELOW_ALERT_PRICE':
            values["ai_t"] = "LTP_B_O"
        else:
            ...
        values["validity"] = "GTT"
        values["d"] = str(alert_price)

        payload = 'jData=' + json.dumps(values) + f'&jKey={self.shoonya_susertoken}'

        res = requests.post(url, data=payload)

        resDict = json.loads(res.text)
        if resDict['stat'] == 'Not_Ok':
            logger.debug(resDict['emsg'])
            return None

        return resDict

    def modify_gtt_order(self, al_id: str, buy_or_sell, alert_cond: str,
                         product_type, exchange, tradingsymbol, quantity,
                         discloseqty, alert_price, price_type, price=0.0,
                         trigger_price=None, retention='DAY', remarks=None):

        url = f'{self.shoonya_api_host}/ModifyGTTOrder'

        # prepare the data
        values = {'ordersource': 'API'}
        values["uid"] = self.shoonya_userid
        values["actid"] = self.shoonya_accountid
        values["trantype"] = buy_or_sell

        values["prd"] = product_type
        values["exch"] = exchange
        values["tsym"] = urllib.parse.quote_plus(tradingsymbol)
        values["qty"] = str(quantity)
        values["dscqty"] = str(discloseqty)
        values["prctyp"] = price_type
        values["prc"] = str(price)
        values["trgprc"] = str(trigger_price)
        values["ret"] = "DAY"
        values["remarks"] = remarks

        if alert_cond == 'LTP_ABOVE_ALERT_PRICE':
            values["ai_t"] = "LTP_A_O"
        elif alert_cond == 'LTP_BELOW_ALERT_PRICE':
            values["ai_t"] = "LTP_B_O"
        else:
            ...

        values["validity"] = "GTT"
        values["d"] = str(alert_price)
        values["al_id"] = al_id

        payload = 'jData=' + json.dumps(values) + f'&jKey={self.shoonya_susertoken}'

        res = requests.post(url, data=payload)

        resDict = json.loads(res.text)
        if resDict['stat'] == 'Not_Ok':
            logger.debug(resDict['emsg'])
            return None

        return resDict

    def place_gtt_oco_order(self, buy_or_sell,
                            exchange, tradingsymbol, quantity, product_type: str,
                            book_loss_alert_price: float, book_loss_price: float,
                            book_loss_price_type: str,
                            book_profit_alert_price: float, book_profit_price: float,
                            book_profit_price_type: str,
                            remarks=None):
        """
        buy_or_sell = 'B' / 'S'
        exchange = 'NSE' or 'BSE'
        tradingsymbol = ex: 'INFY-EQ'
        quantity = int
        product_type = 'C'
        book_loss_alert_price <= price at which following order is placed by system
        book_loss_limit_price = float
        book_loss_price_type  = 'LMT' Or 'MKT'
        book_profit_alert_price >= price at which following order is placed by system
        book_profit_price = float
        book_profit_price_type  = 'LMT' Or 'MKT'
        al_id:str = if previous gtt order is to be updated
        remarks = order tag
        """
        """

        Example :
        jData={"uid":"FA****",
        "ai_t":"LMT_BOS_O","validity":"GTT","tsym":"NIFTYBEES-EQ","exch":"NSE",
        "oivariable":[{"d":"236","var_name":"x"},{"d":"235", "var_name":"y"}],
        "place_order_params":{"tsym":"NIFTYBEES-EQ", "exch":"NSE","trantype":"S","prctyp":"MKT","prd":"I",
        "ret":"DAY","actid":"FA*****","uid":"FA*****", "ordersource":"WEB","qty":"2", "prc":"0"},
        "place_order_params_leg2":{"tsym":"NIFTYBEES-EQ", "exch":"NSE", "trantype":"S", "prctyp":"MKT","prd":"I",
        "ret":"DAY","actid":"FA*****","uid":"FA*****", "ordersource":"WEB","qty":"2", "prc":"0"}}
        &jKey=c28e22b367d84fb32ecf6b96043ea1fc0766a7cabd9d564454912d94a2a53049

        """

        """
        response: {
            "request_time": "14:50:39 21-01-2024",
            "stat": "OI created",
            "al_id": "24012000003234"
        }
        """

        url = f'{self.shoonya_api_host}/PlaceOCOOrder'

        # prepare the data
        values = {'ordersource': 'API'}
        values["uid"] = self.shoonya_userid
        values["actid"] = self.shoonya_accountid
        values["tsym"] = urllib.parse.quote_plus(tradingsymbol)
        values["exch"] = exchange
        values["remarks"] = remarks if remarks is not None else ""
        values["ai_t"] = "LMT_BOS_O"
        values["validity"] = "GTT"
        values["oivariable"] = [{"d": str(book_profit_alert_price), "var_name": "x"}, {"d": str(book_loss_alert_price), "var_name": "y"}]

        if book_loss_price_type == "MKT":
            book_loss_price = float(0.0)

        if book_profit_price_type == "MKT":
            book_profit_price = float(0.0)

        values["place_order_params"] = {"tsym": values["tsym"],
                                        "exch": exchange,
                                        "trantype": buy_or_sell,
                                        "prctyp": book_profit_price_type,
                                        "prd": product_type,
                                        "ret": "DAY",
                                        "actid": self.shoonya_accountid,
                                        "uid": self.shoonya_userid,
                                        "ordersource": "API",
                                        "qty": str(quantity),
                                        "prc": str(book_profit_price)
                                        }

        values["place_order_params_leg2"] = {"tsym": values["tsym"],
                                             "exch": exchange,
                                             "trantype": buy_or_sell,
                                             "prctyp": book_loss_price_type,
                                             "prd": product_type,
                                             "ret": "DAY",
                                             "actid": self.shoonya_accountid,
                                             "uid": self.shoonya_userid,
                                             "ordersource": "API",
                                             "qty": str(quantity),
                                             "prc": str(book_loss_price)
                                             }
        payload = 'jData=' + json.dumps(values) + f'&jKey={self.shoonya_susertoken}'

        logger.debug(f'{self.inst_id} {payload}')
        res = requests.post(url, data=payload)

        resDict = json.loads(res.text)
        if resDict['stat'] == 'Not_Ok':
            logger.debug(f'{self.inst_id} {resDict["emsg"]}')
            return None

        return resDict

    def modify_gtt_oco_order(self, buy_or_sell,
                             exchange, tradingsymbol, quantity, product_type: str,
                             book_loss_alert_price: float, book_loss_price: float, book_loss_price_type: str,
                             book_profit_alert_price: float, book_profit_price: float,
                             book_profit_price_type: str,
                             al_id: str, remarks: str = None):
        """
        buy_or_sell = 'B' / 'S'
        exchange = 'NSE' or 'BSE'
        tradingsymbol = ex: 'INFY-EQ'
        quantity = int
        product_type = 'C'
        book_loss_alert_price <= price at which following order is placed by system
        book_loss_limit_price = float
        book_loss_price_type  = 'LMT' Or 'MKT'
        book_profit_alert_price >= price at which following order is placed by system
        book_profit_price = float
        book_profit_price_type  = 'LMT' Or 'MKT'
        al_id:str = previous gtt order alert id
        remarks = order tag
        """
        url = f'{self.shoonya_api_host}/ModifyOCOOrder'

        # prepare the data
        values = {'ordersource': 'API'}
        values["uid"] = self.shoonya_userid
        values["actid"] = self.shoonya_accountid
        values["tsym"] = urllib.parse.quote_plus(tradingsymbol)
        values["exch"] = exchange
        values["ai_t"] = "LMT_BOS_O"
        values["validity"] = "GTT"
        values["remarks"] = remarks if remarks is not None else ""

        values["al_id"] = al_id
        values["oivariable"] = [{"d": str(book_profit_alert_price), "var_name": "x"}, {"d": str(book_loss_alert_price), "var_name": "y"}]

        if book_loss_price_type == "MKT":
            book_loss_price = float(0.0)

        if book_profit_price_type == "MKT":
            book_profit_price = float(0.0)

        values["place_order_params"] = {"tsym": urllib.parse.quote_plus(tradingsymbol),
                                        "exch": exchange,
                                        "trantype": buy_or_sell,
                                        "prctyp": book_profit_price_type,
                                        "prd": product_type,
                                        "ret": "DAY",
                                        "actid": self.shoonya_accountid,
                                        "uid": self.shoonya_userid,
                                        # "ordersource":"API",
                                        "qty": str(quantity),
                                        "prc": str(book_profit_price),
                                        # "al_id": al_id
                                        }

        values["place_order_params_leg2"] = {"tsym": urllib.parse.quote_plus(tradingsymbol),
                                             "exch": exchange,
                                             "trantype": buy_or_sell,
                                             "prctyp": book_loss_price_type,
                                             "prd": product_type,
                                             "ret": "DAY",
                                             "actid": self.shoonya_accountid,
                                             "uid": self.shoonya_userid,
                                             #   "ordersource":"API",
                                             "qty": str(quantity),
                                             "prc": str(book_loss_price),
                                             #   "al_id": al_id
                                             }
        payload = 'jData=' + json.dumps(values) + f'&jKey={self.shoonya_susertoken}'

        logger.debug(f'{self.inst_id} {payload}')

        res = requests.post(url, data=payload)

        resDict = json.loads(res.text)
        if resDict['stat'] == 'Not_Ok':
            logger.debug(f'{self.inst_id} {resDict["emsg"]}')
            return None

        return resDict

    def cancel_gtt_order(self, al_id: str):
        url = f'{self.shoonya_api_host}/CancelGTTOrder'

        # example to modify the gtt oco order
        # jData={"uid":"","al_id":"22120600000475"}&jKey=09b19b2063a773234febc0efb96c913a24820a550552ce606006ac7a497dd4e0
        values = {'ordersource': 'API'}
        values["uid"] = self.shoonya_userid
        values["al_id"] = al_id
        payload = 'jData=' + json.dumps(values) + f'&jKey={self.shoonya_susertoken}'

        logger.debug(f'{self.inst_id} {payload}')

        res = requests.post(url, data=payload)

        resDict = json.loads(res.text)
        if resDict['stat'] == 'Not_Ok':
            logger.debug(f'{self.inst_id} resDict["emsg"]')
            return None

        return resDict


    def get_pending_gtt_order(self):
        url = f'{self.shoonya_api_host}/GetPendingGTTOrder'

        # example to modify the gtt oco order
        # jData={"uid":"","al_id":"22120600000475"}&jKey=09b19b2063a773234febc0efb96c913a24820a550552ce606006ac7a497dd4e0

        values = {'ordersource': 'API'}
        values["uid"] = self.shoonya_userid

        payload = 'jData=' + json.dumps(values) + f'&jKey={self.shoonya_susertoken}'

        logger.debug(f'{self.inst_id} {payload}')

        res = requests.post(url, data=payload)

        resDict = json.loads(res.text)
        if isinstance(resDict, dict) and resDict['stat'] == 'Not_Ok':
            # Following is the response from Finvasia when there are no pending gtt orders
            # {
            #     "stat": "Not_Ok",
            #     "request_time": "17:20:23 19-04-2024",
            #     "emsg": "Error Occurred : 5 \"no data\""
            # }
            # for this Fv extender returns None.
            logger.debug(f'{self.inst_id} {resDict["emsg"]}')
            return None

        return resDict

    def get_enabled_gtts(self):
        url = f'{self.shoonya_api_host}/GetEnabledGTTs'

        values = {'ordersource': 'API'}
        values["uid"] = self.shoonya_userid

        payload = 'jData=' + json.dumps(values) + f'&jKey={self.shoonya_susertoken}'

        logger.debug(f'{self.inst_id} self.shoonya_userid = {self.shoonya_userid} payload :{payload}')
        res = requests.post(url, data=payload)

        resDict = json.loads(res.text)
        if isinstance(resDict, dict) and resDict['stat'] == 'Not_Ok':
            logger.debug(f'{self.inst_id} {resDict["emsg"]}')
            return None

        return resDict

    def setstreamingdata(self, streamingdata: list):
        self.streamingdata = streamingdata.copy()
        logger.debug(f"{self.inst_id} {self.streamingdata}")

    def connect_to_datafeed_server(self, on_message=None,
                                   on_order_update=None,
                                   on_open=None,
                                   on_close=None,
                                   on_error=None):

        def open_callback():
            nonlocal self
            with self.lock:
                self.ws_connected = True
            if self.streamingdata is not None:
                logger.debug(f'{self.inst_id} Subscribing instruments..{str(self.streamingdata)}')
                self.subscribe(self.streamingdata)
            if self.app_cb_on_open is not None:
                self.app_cb_on_open()

        def subscribe_callback(mesg):
            nonlocal self
            self.ws_v2_data_flow_evt.set()
            if self.app_cb_subscribe is not None:
                self.app_cb_subscribe(mesg)
            return

        def order_update_callback(mesg):
            nonlocal self
            self.ws_v2_data_flow_evt.set()
            if self.app_cb_order_update is not None:
                self.app_cb_order_update(mesg)
            return

        def close_callback():
            nonlocal self
            with self.lock:
                self.ws_connected = False
            logger.info('Socket is Closed and Disconnected')
            return

        def error_callback(mesg):
            if isinstance(mesg, Exception):
                logger.info(f"WS Exception: {str(mesg)}")
                logger.error(traceback.format_exc())
            else:
                try:
                    logger.info (f'Web socket Error Call back: mesg:{json.dumps(mesg,indent=2)}')
                except Exception as e:
                    logger.error(traceback.format_exc())
                    logger.debug (f'Exception :{str(e)}')
            return


        def ws_v2_connect_and_monitor(self):
            import websocket
            websocket.enableTrace (False,level='DEBUG')
            # websocket.setdefaulttimeout(2.0)

            logger.debug(f'{self.inst_id} In finvasia ws_v2_connect_and_monitor..')
            data_flow_evt = self.ws_v2_data_flow_evt
            exit_evt = self.ws_v2_exit_evt
            re_connect_count = 0

            exit = False
            while not exit:
                logger.info (f're_connect_count: {re_connect_count} :: ws_connected:{self.ws_connected} ')
                if not self.ws_connected:
                    logger.info(f'{self.inst_id} Creating Websocket re_connect_count :: {re_connect_count} :')
                    try:
                        self.start_websocket(order_update_callback=order_update_callback,
                                            subscribe_callback=subscribe_callback,
                                            socket_open_callback=open_callback,
                                            socket_close_callback=close_callback,
                                            socket_error_callback=error_callback)
                    except Exception as e:
                        logger.error(f"WebSocket connection failed: {str(e)}")
                        logger.debug(traceback.format_exc())
                        # Don't re-raise, just continue to retry logic

                    time.sleep (1)
                else :
                    logger.info (f'ws_connected:{self.ws_connected}')
                re_connect = False
                to = (ShoonyaApiPy.INITIAL_TIMEOUT) if not re_connect_count else ShoonyaApiPy.DATAFEED_TIMEOUT
                re_connect_count += 1
                while not re_connect:
                    evt_flag = data_flow_evt.wait(timeout=to)
                    if evt_flag:
                        if exit_evt.is_set():
                            exit = True
                            exit_evt.clear()
                            break
                        else:
                            data_flow_evt.clear()
                            if self.force_reconnect:
                                if self.force_reconnect_ts is None:
                                    self.force_reconnect = False
                                    self.force_reconnect_ts = datetime.now ()
                                    if self.m_open <= datetime.now() < self.m_close:
                                        logger.debug(f"{self.inst_id} Market hours:: Needs to be Reconnected ..")
                                        re_connect = True
                                    break
                                else:
                                    self.force_reconnect = False
                                    self.force_reconnect_count += 1
                                    logger.debug (f'Getting multiple requests for reconnect...')
                                    if self.force_reconnect_count  == FeedBaseObj.FORCE_RECONNECT_COUNT_THRESHOLD:
                                        self.force_reconnect_count = 0
                                        self.force_reconnect_ts = None
                            else:
                                continue
                    else:
                        if exit_evt.is_set():
                            exit = True
                            break
                        else:
                            if self.m_open <= datetime.now() < self.m_close:
                                logger.debug(f"{self.inst_id} Market hours:: Needs to be Reconnected ..")
                                re_connect = True
                                break
                if not exit and re_connect:
                    logger.info(f"{self.inst_id} Making ready for re-connection..")
                    # self.unsubscribe(self.streamingdata)
                    logger.info(f"{self.inst_id} Unsubscribe..Done")
                    self.close_websocket()
                    logger.info(f"{self.inst_id} close socket..Done")

                    wait_count = 5
                    while self.ws_connected and wait_count:
                        time.sleep (2.0)
                        wait_count -= 1
                    with self.lock:
                        self.ws_connected = False
                    logger.info(f"{self.inst_id} Making ready for re-connection..Done")

            logger.debug(f"{self.inst_id} Exiting from Finvasia ws_v2_connect_and_monitor..")
            return

        self.app_cb_on_open = on_open
        self.app_cb_on_disconnect = on_close
        self.app_cb_on_error = on_error
        self.app_cb_subscribe = on_message
        self.app_cb_order_update = on_order_update

        if self.ws_monitor_flag:
            self.ws_v2_th = Thread(target=ws_v2_connect_and_monitor, args=(self,), name="ws_v2_connect_and_monitor")
            self.ws_v2_th.name = r'FV_ws_v2_connect_and_monitor'
            self.ws_v2_th.daemon = True

            self.ws_v2_th.start()

        try:
            time.sleep(2)
        except KeyboardInterrupt:
            logger.info (f'keyboard Interrupt.. Exiting..')
            raise
        else:
            ...

        cntr = 0
        while (not self.ws_connected):
            to = ShoonyaApiPy.INITIAL_TIMEOUT if not cntr else 2
            if to ==  ShoonyaApiPy.INITIAL_TIMEOUT:
                logger.info (f'time: c{datetime.now()} : FV Websocket issue: Waiting for Websocket connection..{to} sec. You can CTRL+C and re-run OR wait')
                try:
                    while to > 0:
                        try:
                            time.sleep (1)
                        except KeyboardInterrupt:
                            logger.info("Keyboard interrupt received. Exiting loop.")
                            break  # Exit the loop
                        else:
                            to -= 1
                            logger.info (f'Waiting for Websocket connection..{to} sec')
                except Exception as e:
                    logger.error(f"An error occurred: {e}")
                    raise
            else:
                try:
                    time.sleep(to)
                except KeyboardInterrupt:
                    raise
                else:
                    ...
            cntr += 1
            if (cntr >= 5):
                logger.info (f'Websocket failed.. Please restart the app..')
                break
        if (cntr >= 5):
            logger.error(f"{self.inst_id} Socket Not Opened")
            # self.ws_v2_exit_evt.set()
            # self.ws_v2_data_flow_evt.set()
            # self.ws_connected = False
            # self.unsubscribe(self.streamingdata)
            # self.close_websocket()
            return FAILURE
        else:
            logger.debug(f"{self.inst_id} Socket Opened")
            return SUCCESS

    def disconnect_from_datafeed_server(self):
        ret_val = None
        if self.ws_connected:
            logger.debug(f"{self.inst_id} unsubscribing..")
            self.unsubscribe(self.streamingdata)
            self.close_websocket()
            with self.lock:
                self.ws_connected = False
        if self.ws_v2_th:
            self.ws_v2_exit_evt.set()
            self.ws_v2_data_flow_evt.set()
            self.ws_v2_th.join(2.0)
            if self.ws_v2_th.is_alive():
                logger.error(f"{self.inst_id} {self.ws_v2_th.name} is still alive")

        return (ret_val)