"""
File: bku.py
Author: [Tarakeshwar NC]
Date: January 15, 2024
Description: This script provides book keeper of the orders.
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
    import os
    import shutil
    from dataclasses import dataclass
    from datetime import datetime
    from threading import Lock

    import pandas as pd
    from rich.console import Console
    from rich.table import Table

except Exception as e:
    logger.debug(traceback.format_exc())
    logger.error(("Import Error " + str(e)))
    sys.exit(1)

@dataclass
class BookKeeperUnitCreateConfig():
    rec_file:str
    reset:bool=False

class BookKeeperUnit:
    def __init__(self, bku_cc:BookKeeperUnitCreateConfig):
        self.lock = Lock()
        self.rec_file = bku_cc.rec_file
        self.orders_df = self.load_orders(self.rec_file, reset=bku_cc.reset)

    def __check_and_update_backup_file(self, rec_file, reset):
        # Check if the file was modified today

        try:
            modified_date = datetime.fromtimestamp(os.path.getmtime(rec_file)).strftime('%Y-%m-%d')
        except Exception:
            ...
        else:
            today_date = datetime.now().strftime('%Y-%m-%d')
            if modified_date != today_date or reset:
                # If not, create the new file path in the same directory
                backup_directory = os.path.dirname(rec_file)
                # If not, rename the file with the modified date
                new_file_path = os.path.join(backup_directory, f'orders_backup_{modified_date}.csv')

                shutil.move(rec_file, new_file_path)
                print(f'Renamed backup file to: {new_file_path}')

    def save_order(self, order_id, tsym_token, qty, order_time, status, oco_order_id):
        new_order = pd.DataFrame({
            'Order_ID': [order_id],
            'TradingSymbol_Token': [tsym_token],
            'Qty': [qty],
            'Order_Time': [order_time],
            'Status': [status],
            'OCO_Alert_ID': [oco_order_id]
        })

        new_order['Order_ID'] = new_order['Order_ID'].astype(object)

        # Append the new order to the existing dataframe
        with self.lock:
            if self.orders_df.empty:
                # If it's empty, set self.orders_df to the new_order DataFrame
                self.orders_df = new_order
            else:
                self.orders_df = pd.concat([self.orders_df, new_order], ignore_index=True)

            # Save the dataframe to a CSV file
            self.orders_df.to_csv(self.rec_file, index=False)

    def load_orders(self, rec_file, reset):
        self.__check_and_update_backup_file(rec_file=rec_file, reset=reset)
        try:
            # Try to load the CSV file
            orders_df = pd.read_csv(rec_file, dtype={'Order_ID': object, 'OCO_Alert_ID': object})
        except FileNotFoundError:
            # If the file is not found, create an empty dataframe
            orders_df = pd.DataFrame(columns=['Order_ID', 'TradingSymbol_Token', 'Qty', 'Order_Time', 'Status', 'OCO_Alert_ID'])
        return orders_df

    def show(self):
        df = self.orders_df
        console = Console()
        table = Table(title='Position Order - Records')
        table.add_column("#", justify="center")

        # Add header row
        for column in df.columns:
            table.add_column(column, justify="center")

        # Add data rows
        for i, (_, row) in enumerate(df.iterrows(), start=1):
            table.add_row(str(i), *[str(value) for value in row.tolist()])

        console.print(table)

    def fetch_order_id(self):
        if len(self.orders_df):
            # return self.orders_df.to_dict(orient='records')
            return self.orders_df
        else:
            return None
