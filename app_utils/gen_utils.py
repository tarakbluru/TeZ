"""
File: gen_utils.py
Author: [Tarakeshwar NC]
Date: January 15, 2024
Description: This script provides general utilities required for the system.
References:
...
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

from . import app_logger

logger = app_logger.get_logger(__name__)

try:
    import concurrent.futures
    import os
    import time
    from datetime import datetime

    import pandas as pd
    import requests
except Exception as e:
    logger.debug(traceback.format_exc())
    logger.error(("Import Error " + str(e)))
    sys.exit(1)


def convert_to_tv_symbol(symbol):
    symbol = symbol.replace('-', '_').replace('&', '_')
    return symbol


def round_stock_prec(x, prec=2, base=.05):
    return round(base * round(float(x)/base), prec)


def delete_files_in_folder(folder_path):
    # Check if the folder exists
    if not os.path.exists(folder_path):
        print(f"Folder '{folder_path}' does not exist.")
        return

    # List all files in the folder
    files = [os.path.join(folder_path, filename) for filename in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, filename))]

    # Use a ThreadPoolExecutor for concurrent file deletion
    if len(files):
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            # Create a list of submitted tasks for file deletion
            tasks = [executor.submit(os.remove, file) for file in files]

            # Wait for all tasks to complete
            concurrent.futures.wait(tasks)

            # Check for exceptions and handle them if needed
            for task in tasks:
                if task.exception():
                    print(f"Error deleting file: {task.exception()}")


def create_live_data_file(file, output_directory, nline):
    df = pd.read_csv(file)
    df = df.head(n=nline)
    csv_file_name = os.path.basename(file)
    op_file_name = os.path.join(output_directory, csv_file_name)
    df.to_csv(op_file_name, index=False)


def create_datafiles_parallel(file_list, output_directory, nline):
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        tasks = [executor.submit(create_live_data_file, file, output_directory, nline) for file in file_list]

        # Wait for all tasks to complete
        concurrent.futures.wait(tasks)

        # Check for exceptions and handle them if needed
        for task in tasks:
            if task.exception():
                print(f"Error deleting file: {task.exception()}")


def calcRemainingDuration(hour, minute, second=0):
    t = datetime.now()
    future = datetime(t.year, t.month, t.day, hour, minute, second=second)
    logger.debug(f'future: {future}')
    future.replace(microsecond=0)
    sl_duration = 0

    if t.timestamp() < future.timestamp():
        sl_duration = (future-t).total_seconds()

    return sl_duration


# # Usage
# custom_sleep('09:15:05', 8)  # Sleep until 09:15:05, divided into 8 chunks

def custom_sleep(fut_time, num_chunks=16):
    now = datetime.now()

    if isinstance(fut_time, str):
        l_time = datetime.strptime(fut_time.strip().upper(), "%H:%M:%S")
    else:
        l_time = fut_time

    fut_time = now.replace(hour=l_time.hour, minute=l_time.minute, second=l_time.second, microsecond=0)

    logger.debug(f'now : {now} fut_time:{fut_time}')
    start_time = datetime.now()
    if fut_time <= start_time:
        logger.debug(f"endtime:{fut_time} start_time:{start_time}")
        return
    for i in range(num_chunks):
        remaining_duration = (fut_time - datetime.now()).total_seconds()
        if remaining_duration <= 0.010:
            break
        else:
            chunk_duration = remaining_duration / 2
            logger.debug(f'sleeping for chunk_duration : {chunk_duration} secs')
            time.sleep(chunk_duration)

    logger.debug(f'now : {now} fut_time:{fut_time}')


# Market Data and Configuration Utilities
# Moved from tez_main_v2.py

def is_exp_date_lapsed(date_string):
    try:
        # Convert the date string to a datetime object
        date_object = datetime.strptime(date_string, "%d-%b-%Y")  # Adjust the format according to your date string
        # Get the current date and time
        current_date = datetime.now().date()
        # Compare the date with the current date
        if date_object.date() < current_date:
            return True  # Date has already lapsed
        else:
            return False  # Date is in the future
    except ValueError:
        return False  # Invalid date string format


def check_expiry_dates(data):

    for key, value in data.items():
        if isinstance(value, dict):
            # If the value is a dictionary, recursively check for expiry dates
            check_expiry_dates(value)
        elif key == 'EXPIRY_DATE':
            # If the key is 'expiry_date', check if the value has lapsed
            expiry_date = value
            if expiry_date and is_exp_date_lapsed(expiry_date):
                logger.info(f"Expiry date: {expiry_date} has already lapsed.")
                sys.exit (1)


def get_nth_nearest_expiry_date(symbol_prefix, n, url='EXPIRY_DATE_CALC_URL1'):
    import app_mods
    file_url = app_mods.get_system_info("TRADE_DETAILS", url)
    symboldf = pd.read_csv(file_url)
    symboldf = symboldf.rename(columns=str.lower)
    symboldf = symboldf.rename(columns=lambda x: x.strip())
    symboldf['expiry'] = pd.to_datetime(symboldf['expiry'], format='%d-%b-%Y')
    today = pd.Timestamp.now().floor('D').date()
    symboldf['days_until_expiry'] = (symboldf['expiry'] - pd.Timestamp(today)).dt.days

    if url == 'EXPIRY_DATE_CALC_URL2':
        nfodf = symboldf[(symboldf.last_price.notnull()) &
                        symboldf['tradingsymbol'].str.startswith(symbol_prefix) &
                        (symboldf.exchange == 'NSE_FO') &
                        (symboldf.tick_size == 0.05) &
                        (symboldf.instrument_type == 'OPTIDX')]
    else :
        nfodf = symboldf[((symboldf['symbol'] == symbol_prefix) & symboldf['tradingsymbol'].str.startswith(symbol_prefix)) &
                         (symboldf.exchange == 'NFO') &
                         (symboldf.ticksize == 0.05) &
                         (symboldf.instrument == 'OPTIDX')]

    # Get unique expiry dates and sort them
    unique_expiry_dates = sorted(nfodf['expiry'].unique())

    # Check if there are enough unique expiry dates
    if len(unique_expiry_dates) < n:
        return None  # Return None if there are not enough unique expiry dates

    # Get the nth unique expiry date
    nth_expiry_date = unique_expiry_dates[n - 1]

    return pd.Timestamp(nth_expiry_date).strftime('%d-%b-%Y').upper()


def update_expiry_date(symbol_prefix):
    import app_mods
    exp_date = get_nth_nearest_expiry_date (symbol_prefix, n=1)
    if exp_date:
        current_date = datetime.now().date()
        # Convert expir dates to datetime object
        exp_date_obj = datetime.strptime(exp_date, '%d-%b-%Y').date()
        opt_diff = (exp_date_obj - current_date).days
        if opt_diff <= 0:
            exp_date = get_nth_nearest_expiry_date (symbol_prefix, n=2)
        app_mods.replace_system_config ('SYMBOL', symbol_prefix, 'EXCHANGE', 'NFO', 'EXPIRY_DATE', exp_date)


def update_strike(symbol_prefix, ce_or_pe):
    import app_mods
    if symbol_prefix == 'NIFTY':
        inst_info = app_mods.get_system_info("INSTRUMENT_INFO", "INST_3")
    else:
        inst_info = app_mods.get_system_info("INSTRUMENT_INFO", "INST_4")

    exp_date = inst_info['EXPIRY_DATE']
    # Convert expiry dates to datetime object
    exp_date_obj = datetime.strptime(exp_date, '%d-%b-%Y').date()
    current_date = datetime.now().date()
    # Calculate the difference between expiry date and current date
    opt_diff = (exp_date_obj - current_date).days

    if ce_or_pe == 'CE':
        ce_or_pe_offset = 'CE_STRIKE_OFFSET'
        strike_key = 'CE_STRIKE'
        if opt_diff == 1:
            strike_offset = -1
        else:
            strike_offset = 0
    else:
        ce_or_pe_offset = 'PE_STRIKE_OFFSET'
        strike_key = 'PE_STRIKE'
        if opt_diff == 1:
            strike_offset = 1
        else:
            strike_offset = 0

    app_mods.replace_system_config ('SYMBOL', symbol_prefix, 'EXCHANGE', 'NFO', ce_or_pe_offset, strike_offset)
    app_mods.replace_system_config ('SYMBOL', symbol_prefix, 'EXCHANGE', 'NFO', strike_key, None)


def update_system_config ():
    import app_mods
    exch = app_mods.get_system_info("TRADE_DETAILS", "EXCHANGE")
    if exch == 'NFO':
        exp_date_cfg = app_mods.get_system_info("TRADE_DETAILS", "EXPIRY_DATE_CFG")
        if exp_date_cfg == 'AUTO':
            update_expiry_date('NIFTY')
            update_expiry_date('BANKNIFTY')

        offset_cfg = app_mods.get_system_info("TRADE_DETAILS", "CE_STRIKE_OFFSET_CFG")
        if offset_cfg == 'AUTO':
            update_strike('NIFTY','CE')
            update_strike('BANKNIFTY','CE')

        offset_cfg = app_mods.get_system_info("TRADE_DETAILS", "PE_STRIKE_OFFSET_CFG")
        if offset_cfg == 'AUTO':
            update_strike('NIFTY','PE')
            update_strike('BANKNIFTY','PE')