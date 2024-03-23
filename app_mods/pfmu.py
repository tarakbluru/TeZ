"""
File: pfmu.py
Author: [Tarakeshwar NC]
Date: January 15, 2024
Description: This script provides portfolic management functionality
"""
# Copyright (c) [2024] [Tarakeshwar N.C]
# This file is part of the Tiny_TeZ project.
# It is subject to the terms and conditions of the MIT License.
# See the file LICENSE in the top-level directory of this distribution
# for the full text of the license.

__author__ = "Tarakeshwar N.C"
__copyright__ = "2024"
__date__ = "2024/3/22"
__deprecated__ = False
__email__ = "tarakesh.nc_at_google_mail_dot_com"
__license__ = "MIT"
__maintainer__ = "Tarak"
__status__ = "Development"


import sys
import traceback

from app_utils import app_logger

logger = app_logger.get_logger(__name__)

try:
    import threading
    import pandas as pd

    from .bku import BookKeeperUnit, BookKeeperUnitCreateConfig
    from .tiu import Tiu
    from typing import NamedTuple
    from dataclasses import dataclass

except Exception as e:
    logger.debug(traceback.format_exc())
    logger.error(("Import Error " + str(e)))
    sys.exit(1)

class Portfolio:
    def __init__(self):
        self.lock = threading.Lock()
        self.stock_data = pd.DataFrame(columns=["tsym_token", "ul", "available_qty", "max_qty"])
        self.stock_data.set_index("tsym_token", inplace=True)

    def update_stock_bought(self, tsym_token, ul, qty):
        with self.lock:
            if tsym_token not in self.stock_data.index:
                self.stock_data.loc[tsym_token] = ["", 0, 0]
            self.stock_data.loc[tsym_token, "ul"] = ul  # Assign value to "ul" column
            self.stock_data.loc[tsym_token, "available_qty"] += qty
            self.stock_data.loc[tsym_token, "max_qty"] = max(self.stock_data.loc[tsym_token, "max_qty"],
                                                            self.stock_data.loc[tsym_token, "available_qty"])

    def update_stock_sold(self, tsym_token, qty):
        with self.lock:
            if tsym_token in self.stock_data.index:
                self.stock_data.loc[tsym_token, "available_qty"] -= qty

    def max_qty(self, tsym_token=None, ul=None):
        with self.lock:
            if tsym_token and tsym_token in self.stock_data.index:
                return self.stock_data.loc[tsym_token, "max_qty"]
            if ul is not None:
                ul_data = self.stock_data[self.stock_data['ul'] == ul]
                if not ul_data.empty:
                    return ul_data['max_qty'].sum()
        return 0

    def available_qty(self, tsym_token=None, ul=None):
        with self.lock:
            if tsym_token and tsym_token in self.stock_data.index:
                return self.stock_data.loc[tsym_token, "available_qty"]
            if ul is not None:
                ul_data = self.stock_data[self.stock_data['ul'] == ul]
                if not ul_data.empty:
                    return ul_data['available_qty'].sum()
        return 0


@dataclass
class PFMU_CreateConfig:
    tiu:Tiu
    rec_file:str
    reset:bool=False

class PFMU:
    def __init__ (self, pfmu_cc:PFMU_CreateConfig):
        self.portfolio = Portfolio()
        self.tiu = pfmu_cc.tiu
        bku_cc = BookKeeperUnitCreateConfig(pfmu_cc.rec_file, pfmu_cc.reset)
        self.bku = BookKeeperUnit(bku_cc=bku_cc)

    def square_off_position (self, mode, ul_symbol:str=None, per:float=100):
        def reduce_qty_for_ul(ul, reduce_per):
            nonlocal self
            with self.portfolio.lock:
                ul_rows = self.portfolio.stock_data[self.portfolio.stock_data["ul"] == ul]
                for index, row in ul_rows.iterrows():
                    new_available_qty = int(row["max_qty"] * (reduce_per / 100))
                    logger.info (f'new_available_qty = {new_available_qty}')
                    if self.portfolio.stock_data.loc[index, "available_qty"] > new_available_qty:
                        reduce_qty = min(row["max_qty"] - new_available_qty, row["available_qty"] - new_available_qty)

                        # Sell Here
                        # How to ensure this is a multiple of lot size
                        #TODO:
                        # After successful completion of the order, port folio needs to be updated.

                        if self.portfolio.stock_data.loc[index, "available_qty"] > reduce_qty:
                            self.portfolio.stock_data.loc[index, "available_qty"] -= reduce_qty
                        else :
                            self.portfolio.stock_data.loc[index, "available_qty"] = 0

        df = self.bku.fetch_order_id()
        if mode == 'ALL':
            self.tiu.square_off_position(df=df)
            self.bku.show_records()
        else:
            self.tiu.square_off_position(df=df, symbol=ul_symbol)

        #TODO:
        # After successful completion of the order, port folio needs to be updated.
        
        logger.info("Square off Position - Complete.")

    def save_order_details(self,order_id, tsym_token, qty, order_time, status, oco_order):
        self.bku.save_order(order_id, tsym_token, qty, order_time, status, oco_order)

    def portfolio_add(self, ul_symbol:str, tsym_token:str, qty:int):
        self.portfolio.update_stock_bought(tsym_token=tsym_token, ul=ul_symbol, qty=qty)

    def show(self):
        self.bku.show()
