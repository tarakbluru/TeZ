"""
File: gen_utils.py
Author: [Tarakeshwar NC]
Date: January 15, 2024
Description: This script provides general utilities required for the system.
References:
...
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

from . import app_logger

logger = app_logger.get_logger(__name__)

try:
    import concurrent.futures
    import os
    import time
    from datetime import datetime

    import pandas as pd
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
# # Usage
# custom_sleep('09:15:05', 8)  # Sleep until 09:15:05, divided into 8 chunks
