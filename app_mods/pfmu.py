"""
File: pfmu.py
Author: [Tarakeshwar NC]
Date: January 15, 2024
Description: This script provides portfolic management functionality
"""
# Copyright (c) [2024] [Tarakeshwar N.C]
# This file is part of the Tez project.
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
    import json
    import os
    import re
    from dataclasses import dataclass
    from datetime import datetime, time
    from threading import Lock, Thread

    import numpy as np
    import pandas as pd
    from rich.console import Console
    from rich.table import Table

    from .bku import BookKeeperUnit, BookKeeperUnitCreateConfig
    from .ocpu import OCPU, Ocpu_CreateConfig, Ocpu_RetObject
    from .pmu import PMU_CreateConfig, PriceMonitoringUnit
    from .shared_classes import (Component_Type, ExtSimpleQueue, I_B_MKT_Order,
                                 I_S_MKT_Order, InstrumentInfo)
    from .tiu import Diu, OrderExecutionException, Tiu

except Exception as e:
    logger.debug(traceback.format_exc())
    logger.error(("Import Error " + str(e)))
    sys.exit(1)


@dataclass
class Portfolio_CreateConfig:
    store_file: str
    mo: str


class Portfolio:
    def __init__(self, pf_cc: Portfolio_CreateConfig):
        self.store_file = pf_cc.store_file
        pf_cc.mo = pf_cc.mo

        file_path = pf_cc.store_file
        # Get the modification time of the file if it exists
        if os.path.exists(file_path):
            modification_time = os.path.getmtime(file_path)
        else:
            modification_time = 0

        # Convert modification time to a datetime object
        modification_datetime = datetime.fromtimestamp(modification_time)

        # Define the cutoff time (9:15 am)
        cutoff_time = datetime.strptime(pf_cc.mo, "%H:%M")

        # Get the current time
        current_datetime = datetime.now()
        cutoff_datetime = datetime.combine(current_datetime.date(), cutoff_time.time())
        cutoff_datetime = cutoff_datetime.replace(second=0)
        cutoff_datetime = cutoff_datetime.replace(microsecond=0)

        # Check if the file is absent or modification time is more than the cutoff time
        if not os.path.exists(file_path) or modification_datetime <= cutoff_datetime:
            # Create an empty DataFrame with specified columns
            self.stock_data = pd.DataFrame(columns=["tsym_token", "ul_index", "available_qty", "max_qty"])
            logger.debug("File is absent or modification time is more than cutoff time. Empty DataFrame created.")
            self.stock_data.to_csv(self.store_file, index=False)

        # Read the CSV file into a DataFrame
        self.stock_data = pd.read_csv(file_path)
        logger.debug("File was modified after 9:15 am today. DataFrame created successfully.")

        self.stock_data.set_index("tsym_token", inplace=True)

    def update_position_taken(self, tsym_token, ul_index, qty):
        if tsym_token not in self.stock_data.index:
            self.stock_data.loc[tsym_token] = ["", 0, 0]
        self.stock_data.loc[tsym_token, "ul_index"] = ul_index  # Assign value to "ul_index" column
        self.stock_data.loc[tsym_token, "available_qty"] += qty
        if qty > 0:
            self.stock_data.loc[tsym_token, "max_qty"] = max(self.stock_data.loc[tsym_token, "max_qty"],
                                                             self.stock_data.loc[tsym_token, "available_qty"])
        else:
            self.stock_data.loc[tsym_token, "max_qty"] = min(self.stock_data.loc[tsym_token, "max_qty"],
                                                             self.stock_data.loc[tsym_token, "available_qty"])
        logger.debug(f'\n{self.stock_data}')
        self.stock_data.to_csv(self.store_file, index=True)

    def update_position_closed(self, tsym_token, qty):
        if tsym_token in self.stock_data.index:
            self.stock_data.loc[tsym_token, "available_qty"] -= qty
            if self.stock_data.loc[tsym_token, "available_qty"] == 0:
                self.stock_data.loc[tsym_token, "max_qty"] = 0
            self.stock_data.to_csv(self.store_file, index=True)

        logger.debug(f'\n{self.stock_data}')

    def max_qty(self, tsym_token=None, ul_index=None):
        if tsym_token and tsym_token in self.stock_data.index:
            return self.stock_data.loc[tsym_token, "max_qty"]
        if ul_index is not None:
            ul_data = self.stock_data[self.stock_data['ul_index'] == ul_index]
            if not ul_data.empty:
                return ul_data['max_qty'].sum()
        return 0

    def available_qty(self, tsym_token=None, ul_index=None):
        if tsym_token and tsym_token in self.stock_data.index:
            return self.stock_data.loc[tsym_token, "available_qty"]
        if ul_index is not None:
            ul_data = self.stock_data[self.stock_data['ul_index'] == ul_index]
            if not ul_data.empty:
                return ul_data['available_qty'].sum()
        return 0

    def verify_reset(self, ul_index=None):
        df = self.stock_data
        if len(df):
            if ul_index:
                not_zero_available_qty = df.loc[(df['ul_index'] == ul_index) & (df['available_qty'] != 0), 'available_qty']
                if not_zero_available_qty.any():
                    logger.info("available_qty is not already 0 and is being set to 0. Verify on Broker Terminal")
                    df.loc[(df['ul_index'] == ul_index), 'available_qty'] = 0
                
                # Check if max_qty is not already 0, and if so, set it to 0
                not_zero_max_qty = df.loc[(df['ul_index'] == ul_index) & (df['max_qty'] != 0), 'max_qty']
                if not_zero_max_qty.any():
                    logger.info("max_qty is not already 0 and is being set to 0. Verify on Broker Terminal")
                    df.loc[(df['ul_index'] == ul_index), 'max_qty'] = 0
            else:
            # For all rows, irrespective of ul_index
                # Check if available_qty is not already 0, and if so, set it to 0
                not_zero_available_qty = df[df['available_qty'] != 0]
                if not_zero_available_qty.shape[0] > 0:  # Check if there are non-zero elements
                    for index, row in not_zero_available_qty.iterrows():
                        logger.info(f"Available_qty is not already 0 for ul_index {row['ul_index']} and is forced to 0.")
                        logger.info(f"Please check the broker's terminal")
                    df.loc[not_zero_available_qty.index, 'available_qty'] = 0

                # Check if max_qty is not already 0, and if so, set it to 0
                not_zero_max_qty = df[df['max_qty'] != 0]
                if not_zero_max_qty.shape[0] > 0:  # Check if there are non-zero elements
                    for index, row in not_zero_max_qty.iterrows():
                        logger.info(f"max_qty is not already 0 for ul_index {row['ul_index']} and is forced to 0.")
                        logger.info(f"Please check the broker's terminal")
                    df.loc[not_zero_max_qty.index, 'max_qty'] = 0

            self.stock_data.to_csv(self.store_file, index=True)

    def update_portfolio_from_position(self, posn_df):
        pf_df = self.stock_data
        for tsym_token, row in pf_df.iterrows():
            _, token = tsym_token.split('_')
            rec_qty = row['available_qty']
            matching_row = posn_df.loc[posn_df['token'] == token]
            posn_qty = matching_row['netqty'].iloc[0] if not matching_row.empty else 0
            if posn_qty > 0:
                net_qty = min(posn_qty, rec_qty)
            else:
                net_qty = max(posn_qty, rec_qty)
            pf_df.loc[tsym_token, 'available_qty'] = net_qty
        self.stock_data.to_csv(self.store_file, index=True)
        logger.info(f'\n{pf_df}')

    def fetch_all_available_qty(self, ul_index):
        logger.info(f'ul_index: {ul_index}')
        return (self.stock_data[self.stock_data["ul_index"] == ul_index].copy())

    def show (self):
        df = self.stock_data
        console = Console()
        table = Table(title='Portfolio-Records')
        table.add_column("#", justify="center")

        # Add header row
        for column in df.columns:
            table.add_column(column, justify="center")

        # Add data rows
        for i, (_, row) in enumerate(df.iterrows(), start=1):
            table.add_row(str(i), *[str(value) for value in row.tolist()])

        console.print(table)


@dataclass
class PFMU_CreateConfig:
    tiu: Tiu
    diu: Diu
    rec_file: str
    mo: str
    pf_file: str
    port: ExtSimpleQueue
    limit_order_cfg: bool = False
    reset: bool = False


class PFMU:
    __count = 0
    __componentType = Component_Type.ACTIVE

    def __init__(self, pfmu_cc: PFMU_CreateConfig):
        logger.info(f'{PFMU.__count}: Creating PFMU Object..')
        self.inst_id = f'{self.__class__.__name__}:{PFMU.__count}'
        PFMU.__count += 1
        
        self.pf_lock = Lock()

        self.tiu = pfmu_cc.tiu
        self.diu = pfmu_cc.diu

        pmu_cc = PMU_CreateConfig(pfmu_cc.port)
        self.pmu = PriceMonitoringUnit(pmu_cc=pmu_cc)
        ocpu_cc = Ocpu_CreateConfig(tiu=self.tiu, diu=self.diu)
        self.ocpu = OCPU(ocpu_cc=ocpu_cc)

        self.limit_order_cfg = pfmu_cc.limit_order_cfg
        self.prec_factor = 100

        self.wo_df = None
        self.ord_lock = None
        if pfmu_cc.limit_order_cfg:
            self.ord_lock = Lock()
            self.wo_df = pd.DataFrame(
                columns=[
                    "price_at_click",
                    "tsym_token",
                    "ul_index",
                    "use_gtt_oco",
                    "cond",
                    "wait_price_lvl",
                    "prev_tick_lvl",
                    "n_orders",
                    "order_list",
                    "status"])

        bku_cc = BookKeeperUnitCreateConfig(pfmu_cc.rec_file, pfmu_cc.reset)
        self.bku = BookKeeperUnit(bku_cc=bku_cc)

        pf_cc = Portfolio_CreateConfig(store_file=pfmu_cc.pf_file, mo=pfmu_cc.mo)
        self.portfolio = Portfolio(pf_cc=pf_cc)

        #
        # TODO: In case of a restart of app, portfolio should get updated based on the
        # platform quantity. If there is any difference ( due to manual exit and not manual entry...)
        # it should be taken into the portfolio.
        #

        logger.info(f'Creating PFMU Object.. Done')

    def start_monitoring(self):
        self.pmu.start_monitoring()

    def wo_table_show(self):
        if self.limit_order_cfg:
            df = self.wo_df[["price_at_click", "wait_price_lvl", "tsym_token", "cond", "n_orders", "use_gtt_oco", "status"]]
            console = Console()
            table = Table(title='Waiting-Order-Records')
            table.add_column("#", justify="center")

            # Add header row
            for column in df.columns:
                table.add_column(column, justify="center")

            # Add data rows
            for i, (_, row) in enumerate(df.iterrows(), start=1):
                table.add_row(str(i), *[str(value) for value in row.tolist()])

            console.print(table)

    def show(self):
        self.bku.show()
        self.wo_table_show()
        self.portfolio.show()

    def _add_order(
            self,
            ul_token: str,
            ul_index: str,
            tsym_token: str,
            use_gtt_oco: bool,
            price_at_click: float,
            wait_price: float,
            order_list: list):
        # Find the index where it would lie in OrderBank
        index = len(self.wo_df)
        # Create a key name "26000_<index>" using an f-string
        key_name = f"{ul_token}_{index}"
        if wait_price >= price_at_click:
            cond = 1
        elif wait_price < price_at_click:
            cond = 0

        wait_price_lvl = round(wait_price * self.prec_factor)
        # Create a new row with initial values

        new_order = {
            "price_at_click": price_at_click,
            "tsym_token": tsym_token,
            "ul_index": ul_index,
            "use_gtt_oco": use_gtt_oco,
            "cond": cond,
            "wait_price_lvl": int(wait_price_lvl),
            "prev_tick_lvl": np.nan,
            "n_orders": len(order_list),
            "order_list": order_list,
            "status": 'Waiting'
        }
        with self.ord_lock:
            # Append the new row to OrderBank DataFrame
            self.wo_df.loc[key_name] = new_order
            # Return the key name for easy access
        return key_name

    def _price_condition(self, ltp: float, key_name: str):
        order_info = self.wo_df.loc[key_name]
        ltp_level = round(ltp * self.prec_factor)
        wait_price_lvl = order_info.wait_price_lvl
        if order_info.prev_tick_lvl:
            if order_info.cond:
                if order_info.prev_tick_lvl < wait_price_lvl and ltp_level >= wait_price_lvl:
                    return True
            if not order_info.cond:
                if order_info.prev_tick_lvl > wait_price_lvl and ltp_level <= wait_price_lvl:
                    return True
        with self.ord_lock:
            self.wo_df.loc[key_name, "prev_tick_lvl"] = ltp_level

    def order_placement(self, key_name: str):
        logger.debug(f"Callback triggered for ID: {key_name}")
        with self.ord_lock:
            order_info = self.wo_df.loc[key_name]
            orders = order_info.order_list
            resp_exception, resp_ok, os_tuple_list = self.tiu.place_and_confirm_tez_order(orders=orders, use_gtt_oco=order_info.use_gtt_oco)
            if resp_exception:
                logger.info('Exception had occured while placing order: ')
            if resp_ok:
                logger.debug(f'respok: {resp_ok}')

            total_qty = 0
            for stat, os in os_tuple_list:
                status = stat.name
                order_time = os.fill_timestamp
                order_id = os.order_id
                qty = os.fillshares
                total_qty += qty
                oco_order = None
                for order in orders:
                    if order_id == order.order_id:
                        oco_order = order.al_id
                        break
                self.bku.save_order(order_id, order_info.tsym_token, qty, order_time, status, oco_order)

            logger.debug(f'Total Qty taken : {total_qty}')
            if total_qty:
                with self.pf_lock:
                    self.portfolio.update_position_taken(tsym_token=order_info.tsym_token, ul_index=order_info.ul_index, qty=total_qty)
            self.show()

            self.wo_df.loc[key_name, "status"] = "Completed"
            self.wo_table_show()

    def _order_placement_th(self, key_name: str):
        Thread(name='PMU Order Placement Thread', target=self.order_placement, args=(key_name,), daemon=True).start()

    #
    # def disable_waiting_order(self, id, ul_token=None):
    # def enable_waiting_order(self, id, ul_token=None):
    # Enable and disable of orders:  Not done by desgin. Scoped out of this small project
    # To keep it simple, once order is waiting, it can only be cancelled.
    # if user wishes to re-enter he will have type in the detail and place the waiting order again.
    #

    def cancel_waiting_order(self, id=None, ul_token=None):
        with self.ord_lock:
            if ul_token:
                if id:
                    key_name = f"{ul_token}_{id}"
                    if key_name in self.wo_df.index:
                        status = self.wo_df.loc[key_name, "status"]
                        if status == 'Waiting':
                            self.pmu.unregister_callback(ul_token, callback_id=key_name)
                            self.wo_df.loc[key_name, "status"] = "Cancelled"
                else:
                    # search all orders under underlying token, and cancel
                    if len(self.wo_df):
                        self.__cancel_all_waiting_orders_com__(ul_token=ul_token)
            else:
                if id < len(self.wo_df):  # Check if id is within the DataFrame's range
                    status = self.wo_df.iloc[id, self.wo_df.columns.get_loc("status")]
                    if status == 'Waiting':
                        key_name = self.wo_df.index[id]
                        ul_token = key_name.split('_')[0]
                        logger.info(f'unregistering: {key_name} ul_token: {ul_token}')
                        # Unregister callback and update status
                        self.pmu.unregister_callback(ul_token, callback_id=key_name)
                        self.wo_df.iloc[id, self.wo_df.columns.get_loc("status")] = "Cancelled"

    def __cancel_all_waiting_orders_com__(self, ul_token):
        for index, row in self.wo_df.iterrows():
            key_name = index
            ul_token_from_key_name = index.split('_')[0]

            if ul_token:
                if ul_token != ul_token_from_key_name:
                    continue

            status = row["status"]
            if status == 'Waiting':
                self.pmu.unregister_callback(ul_token, callback_id=key_name)
                self.wo_df.at[key_name, "status"] = "Cancelled"  # Use at[] for setting single values

    def cancel_all_waiting_orders(self, ul_token=None, exit_flag=False, show_table=True):
        if self.limit_order_cfg:
            with self.ord_lock:
                self.__cancel_all_waiting_orders_com__(ul_token=ul_token)

        if exit_flag:
            self.pmu.hard_exit()
        if show_table:
            self.wo_table_show()

    def take_position(self, action: str, inst_info: InstrumentInfo, trade_price: float):
        
        r: Ocpu_RetObject = self.ocpu.create_order(action=action, inst_info=inst_info, trade_price=trade_price)
        
        total_qty = 0
        if r and r.orders_list and r.tsym_token:
            if trade_price is None:
                use_gtt_oco = True if inst_info.order_prod_type == 'O' else False
                resp_exception, resp_ok, os_tuple_list = self.tiu.place_and_confirm_tez_order(orders=r.orders_list, use_gtt_oco=use_gtt_oco)
                if resp_exception:
                    logger.info('Exception had occured while placing order: ')
                if resp_ok:
                    logger.debug(f'respok: {resp_ok}')

                for stat, os in os_tuple_list:
                    status = stat.name
                    order_time = os.fill_timestamp
                    order_id = os.order_id
                    qty = os.fillshares
                    total_qty += qty
                    oco_order = None
                    for order in r.orders_list:
                        if order_id == order.order_id:
                            oco_order = order.al_id
                            break
                    self.bku.save_order(order_id, r.tsym_token, qty, order_time, status, oco_order)
                logger.info(f'Total Qty taken : {total_qty}')
                if total_qty:
                    with self.pf_lock:
                        # if (inst_info.symbol == 'NIFTYBEES' or inst_info.symbol == 'BANKBEES') and action == 'Sell':
                        logger.info(f'Position Taken {inst_info} total_qty: {total_qty}')
                        self.portfolio.update_position_taken(tsym_token=r.tsym_token, ul_index=inst_info.ul_index, qty=total_qty)
                self.show()
            else:
                ul_token = self.diu.ul_token
                use_gtt_oco = True if inst_info.order_prod_type == 'O' else False
                key_name = self._add_order(ul_token=ul_token, ul_index=inst_info.ul_index, tsym_token=r.tsym_token,
                                           use_gtt_oco=use_gtt_oco,
                                           price_at_click=r.ul_ltp,
                                           wait_price=trade_price, order_list=r.orders_list)
                cond_ds = {'condition_fn': self._price_condition,
                           'callback_function': self._order_placement_th,
                           'cb_id': key_name}
                self.pmu.register_callback(token=ul_token, cond_ds=cond_ds)
                self.wo_table_show()
                # self.pmu.simulate(trade_price)
                logger.debug(f'Registered Call back with PMU {key_name}')

            return total_qty

    def _update_portfolio_based_platform(self):
        r = self.tiu.get_positions()
        if r is not None and isinstance(r, list):
            posn_df = pd.DataFrame(r)
            posn_df.loc[posn_df['prd'] == 'I', 'netqty'] = posn_df.loc[posn_df['prd'] == 'I', 'netqty'].apply(lambda x: int(x))
            posn_df = posn_df.loc[(posn_df['prd'] == 'I')]
            if not posn_df.empty:
                self.portfolio.update_portfolio_from_position(posn_df=posn_df)
        else:
            logger.info(f'Not able to fetch the positions. Check manually')

    def square_off_position(self, mode, ul_index: str = None, per: float = 100, inst_type: str = None, partial_exit: bool = False):

        def place_sq_off_order(tsym: str, b_or_s: str, exit_qty: int, ls: int, frz_qty: int, exchange='NSE'):
            nonlocal self
            failure_cnt = 0
            order = None
            closed_qty = 0
            while (exit_qty and failure_cnt <= Tiu.SQ_OFF_FAILURE_COUNT):
                per_leg_exit_qty = frz_qty if exit_qty > frz_qty else exit_qty
                per_leg_exit_qty = int(per_leg_exit_qty / ls) * ls

                if not per_leg_exit_qty:
                    break

                if order and order.quantity == per_leg_exit_qty:
                    ...
                else:
                    if b_or_s == 'S':
                        order = I_S_MKT_Order(tradingsymbol=tsym, quantity=per_leg_exit_qty, exchange=exchange)
                    if b_or_s == 'B':
                        order = I_B_MKT_Order(tradingsymbol=tsym, quantity=per_leg_exit_qty, exchange=exchange)

                logger.info (f'order:{str(order)}')

                r = self.tiu.place_order(order)
                if r is None:
                    logger.info(f'Exit order Failed: Check Manually')
                    break

                if r['stat'] == 'Not_Ok':
                    logger.info(f'Exit order Failed:  {r["emsg"]}')
                    failure_cnt += 1
                else:
                    logger.info(f'Exit Order Attempt success:: order id  : {r["norenordno"]}')
                    order_id = r["norenordno"]
                    r_os_list = self.tiu.single_order_history(order_id)
                    # Shoonya gives a list for all status of order, we are interested in first one
                    r_os_dict = r_os_list[0]
                    if r_os_dict["status"].lower() == "complete":
                        closed_qty += order.quantity
                        logger.info(f'Exit order Complete: order_id: {order_id}')
                    else:
                        logger.info(f'Exit order InComplete: order_id: {order_id} Check Manually')
                    exit_qty -= per_leg_exit_qty

            if failure_cnt > 2 or exit_qty:
                logger.info(f'Exit order InComplete: Check Manually')
                raise OrderExecutionException

            logger.info(f'tsym_token:{tsym} qty: {closed_qty} squared off..')

            return closed_qty

        def reduce_qty_for_ul(ul_index, ul_ltp, reduce_per, inst_type):
            nonlocal self
            with self.pf_lock:
                self._update_portfolio_based_platform()
                df = self.portfolio.fetch_all_available_qty(ul_index=ul_index)
                logger.info(f'\n {df}')
                if df.empty:
                    logger.debug(f'all available qty is 0')
                    return
                else:
                    if inst_type == 'CE' or inst_type == 'PE':
                        logger.debug(f'inst_type : {inst_type}')
                        ul_rows = df[~df.index.str.contains('NIFTYBEES|BANKBEES')]
                    if inst_type == 'BEES':
                        logger.debug(f'inst_type : {inst_type}')
                        ul_rows = df[df.index.str.contains('NIFTYBEES|BANKBEES')]

                    logger.info(f'\n{ul_rows}')
                # if available quantity of ul_index, CE/PE is not there, then also it should return
                if ul_rows.empty:
                    return
                else:
                    total_reduce_qty = 0
                    new_available_qty = None
                    if inst_type == 'CE' or inst_type == 'PE':
                        pattern = r'([CP])(\d+)'
                        # Function to extract option type ('C' or 'P') and strike price

                        def extract_option_info(index):
                            tsym = str(index).split('_')[0]  # Convert index to string before splitting
                            match = re.search(pattern, tsym)
                            if match:
                                option_type = match.group(1)  # Extract 'C' or 'P' from the first group
                                strike_price = int(match.group(2))  # Extract digits from the second group
                                return option_type, strike_price
                            else:
                                return None, None

                        # Apply the function to each row to extract option type and strike price
                        ul_rows[['option_type', 'strike_price']] = ul_rows.index.to_series().apply(extract_option_info).apply(pd.Series)

                        if inst_type == 'CE':
                            # Separate CE and PE strike prices into different DataFrames
                            ce_df = ul_rows[ul_rows['option_type'] == 'C'].copy()
                            # Calculate the absolute difference between each strike price and ul_ltp
                            ce_df['distance_from_ul_ltp'] = ce_df['strike_price'] - ul_ltp
                            # Sort CE DataFrame based on the distance from ul_ltp in ascending order
                            ce_df_sorted = ce_df.sort_values(by='distance_from_ul_ltp', ascending=True)
                            logger.info(f'{ce_df_sorted}')

                            if not ce_df_sorted.empty:
                                max_qty = ce_df_sorted['max_qty'].sum()
                                total_reduce_qty = int(max_qty * (reduce_per / 100))
                                new_available_qty = max_qty - total_reduce_qty
                                logger.info(f'CE: new_available_qty {new_available_qty} total_reduce_qty_ce: {total_reduce_qty}')
                            sq_df = ce_df_sorted
                        else:
                            pe_df = ul_rows[ul_rows['option_type'] == 'P'].copy()
                            # Calculate the absolute difference between each strike price and ul_ltp
                            pe_df['distance_from_ul_ltp'] = pe_df['strike_price'] - ul_ltp
                            # Sort PE DataFrame based on the distance from ul_ltp in ascending order
                            pe_df_sorted = pe_df.sort_values(by='distance_from_ul_ltp', ascending=False)
                            logger.info(f'{pe_df_sorted}')
                            if not pe_df_sorted.empty:
                                max_qty = pe_df_sorted['max_qty'].sum()
                                total_reduce_qty = int(max_qty * (reduce_per / 100))
                                new_available_qty = max_qty - total_reduce_qty
                                logger.info(f'PE: new_available_qty {new_available_qty} total_reduce_qty_pe: {total_reduce_qty}')
                            sq_df = pe_df_sorted
                            total_available_qty = sq_df['available_qty'].sum()
                    else:
                        max_qty = ul_rows['max_qty'].sum()
                        total_reduce_qty = int(max_qty * (reduce_per / 100))
                        new_available_qty = max_qty - total_reduce_qty
                        logger.info(f'BEES: new_available_qty {new_available_qty} total_reduce_qty: {total_reduce_qty}')
                        sq_df = ul_rows

                    total_available_qty = sq_df['available_qty'].sum() if len(sq_df) else 0

                    logger.info(f'Total Available : {total_available_qty} New_Available: {new_available_qty} ')

                    if new_available_qty is not None and abs(new_available_qty) < abs(total_available_qty):
                        diff_qty = abs(total_available_qty) - abs(new_available_qty)
                        if max_qty < 0:
                            diff_qty *= -1

                        act_sq_off_qty = diff_qty

                        if not act_sq_off_qty:
                            return

                        for index, row in sq_df.iterrows():
                            tsym_token = str(index)
                            tsym = tsym_token.split('_')[0] 
                            token = tsym_token.split('_')[1]
                            if abs(row["available_qty"]) > 0:
                                if max_qty > 0:
                                    b_or_s = 'S'
                                else:
                                    b_or_s = 'B'

                                logger.info(f'Reducing tsym_token: {tsym_token} {tsym} {token} reduce_qty: {act_sq_off_qty} of {diff_qty}')
                                exch = 'NSE' if '-EQ' in tsym else 'NFO'
                                r = self.tiu.get_security_info(exchange=exch, token=token)
                                logger.debug(f'{json.dumps(r, indent=2)}')
                                frz_qty = None
                                if isinstance(r, dict) and 'frzqty' in r:
                                    frz_qty = int(r['frzqty'])
                                else:
                                    frz_qty = abs(act_sq_off_qty) + 1
                                if isinstance(r, dict) and 'ls' in r:
                                    ls = int(r['ls'])  # lot size
                                else:
                                    ls = 1
                                
                                if not abs(diff_qty) // ls:
                                    break

                                try:
                                    closed_qty = place_sq_off_order(tsym=tsym, b_or_s=b_or_s, 
                                                                    exit_qty=abs(act_sq_off_qty), ls=ls, 
                                                                    frz_qty=frz_qty, exchange=exch)
                                except Exception as e:
                                    logger.error(f'Orders not going through.. Check manually {str(e)}')
                                    raise
                                if b_or_s == 'B':
                                    self.portfolio.update_position_closed(tsym_token=tsym_token, qty=-closed_qty)
                                    diff_qty += closed_qty
                                else:
                                    self.portfolio.update_position_closed(tsym_token=tsym_token, qty=closed_qty)
                                    diff_qty -= closed_qty

                                if diff_qty:
                                    continue
                                else:
                                    diff_qty = 0
                                    break

        def __square_off_position__(df: pd.DataFrame, symbol=None):
            nonlocal self
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

            r = self.tiu.get_order_book()
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
                            self.tiu.cancel_order(row['norenordno'])

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
                                r = self.tiu.exit_order(row['snonum'], 'B')
                                if r is None:
                                    logger.error("Exit order result is None. Check Manually")
                                if 'stat' in r and r['stat'] == 'Ok':
                                    logger.debug(f'child order of {row["norenordno"]} : {row["snonum"]}, status: {json.dumps (r, indent=2)}')
                                else:
                                    logger.error('Exit order Failed, Check Manually')
            else:
                logger.info('get_order_book Failed, Check Manually')
                return

            r = self.tiu.get_pending_gtt_order()
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
                                r = self.tiu.cancel_gtt_order(al_id=str(alert_id))
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

            r = self.tiu.get_positions()
            if r is not None and isinstance(r, list):
                posn_df = pd.DataFrame(r)
                posn_df.loc[posn_df['prd'] == 'I', 'netqty'] = posn_df.loc[posn_df['prd'] == 'I', 'netqty'].apply(lambda x: int(x))
                posn_df = posn_df.loc[(posn_df['prd'] == 'I')]

                for index, row in sum_qty_by_symbol.iterrows():
                    tsym_token = symbol = row['TradingSymbol_Token']
                    token = symbol.split('_')[1]
                    tsym = symbol.split('_')[0]
                    rec_qty = row['Qty']
                    if not posn_df.empty:
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
                        r = self.tiu.get_security_info(exchange=exch, token=token)
                        logger.debug(f'{json.dumps(r, indent=2)}')

                        frz_qty = None
                        if isinstance(r, dict) and 'frzqty' in r:
                            frz_qty = int(r['frzqty'])
                        else:
                            frz_qty = exit_qty + 1

                        if isinstance(r, dict) and 'ls' in r:
                            ls = int(r['ls'])  # lot size
                        else:
                            ls = 1

                        failure_cnt = 0
                        order = None
                        closed_qty = 0
                        while (exit_qty and failure_cnt <= Tiu.SQ_OFF_FAILURE_COUNT):
                            per_leg_exit_qty = frz_qty if exit_qty > frz_qty else exit_qty
                            per_leg_exit_qty = int(per_leg_exit_qty / ls) * ls

                            if order and order.quantity == per_leg_exit_qty:
                                ...
                            else:
                                if rec_qty > 0:
                                    order = I_S_MKT_Order(tradingsymbol=tsym, quantity=per_leg_exit_qty, exchange=exch)
                                else:
                                    order = I_B_MKT_Order(tradingsymbol=tsym, quantity=per_leg_exit_qty, exchange=exch)

                            # r = self.fv.place_order(buy_or_sell, product_type='I', exchange=exch, tradingsymbol=tsym,
                            #                         quantity=per_leg_exit_qty, price_type='MKT', discloseqty=0.0)

                            r = self.tiu.place_order(order)

                            if r is None or r['stat'] == 'Not_Ok':
                                logger.info(f'Exit order Failed:  {r["emsg"]}')
                                failure_cnt += 1
                            else:
                                logger.info(f'Exit Order Attempt success:: order id  : {r["norenordno"]}')
                                order_id = r["norenordno"]
                                r_os_list = self.tiu.single_order_history(order_id)
                                # Shoonya gives a list for all status of order, we are interested in first one
                                r_os_dict = r_os_list[0]
                                if r_os_dict["status"].lower() == "complete":
                                    closed_qty += order.quantity
                                    logger.info(f'Exit order Complete: order_id: {order_id}')
                                else:
                                    logger.info(f'Exit order InComplete: order_id: {order_id} Check Manually')
                                exit_qty -= per_leg_exit_qty

                        if failure_cnt > 2 or exit_qty:
                            logger.info(f'Exit order InComplete: order_id: {order_id} Check Manually')
                            raise OrderExecutionException
                        elif closed_qty:
                            logger.info(f'tsym_token:{tsym_token} qty: {closed_qty} squared off..')
                            if rec_qty < 0:
                                self.portfolio.update_position_closed(tsym_token=tsym_token, qty=-closed_qty)
                            else:
                                self.portfolio.update_position_closed(tsym_token=tsym_token, qty=closed_qty)

        df = self.bku.fetch_order_id()

        if mode == 'ALL':
            # System Square off - At square off time
            try:
                if self.limit_order_cfg:
                    self.cancel_all_waiting_orders(exit_flag=True, show_table=False)
                __square_off_position__(df=df)
                with self.pf_lock:
                    self.portfolio.verify_reset()
            except OrderExecutionException:
                logger.error('Major Exception Happened: Take Manual control..')

        else:
            if partial_exit:
                ul_ltp = self.diu.get_latest_tick(ul_index=ul_index)
                # ul_ltp is required for find the deep in the money strikes
                reduce_qty_for_ul(ul_index=ul_index, ul_ltp=ul_ltp, reduce_per=per, inst_type=inst_type)
            else:
                try:
                    ul_token = self.diu.ul_token
                    if self.limit_order_cfg:
                        self.cancel_all_waiting_orders(ul_token=ul_token)

                    __square_off_position__(df=df, symbol=ul_index)

                    with self.pf_lock:
                        self.portfolio.verify_reset(ul_index=ul_index)
                except OrderExecutionException:
                    logger.error('Major Exception Happened: Take Manual control..')

        logger.info("Square off Position - Complete.")
