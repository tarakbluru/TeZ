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
    import locale
    import os
    import re
    import time
    from dataclasses import dataclass
    from time import sleep
    from datetime import datetime
    from threading import Lock, Thread, Event
    from typing import Callable

    import numpy as np
    import pandas as pd
    from rich.console import Console
    from rich.table import Table

    from .bku import BookKeeperUnit, BookKeeperUnitCreateConfig
    from .ocpu import OCPU, Ocpu_CreateConfig, Ocpu_RetObject
    from .pmu import PMU_CreateConfig, PriceMonitoringUnit, WaitConditionData
    from .shared_classes import (Component_Type, ExtSimpleQueue, I_B_MKT_Order,
                                 I_S_MKT_Order, InstrumentInfo)
    from .tiu import Diu, OrderExecutionException, Tiu
    from .notification_factory import NotificationFactory
    from .notification_system import NotificationLogger
    from .infra_error_handler import InfraErrorHandler, ConnectionStatus

except Exception as e:
    logger.debug(traceback.format_exc())
    logger.error(("Import Error " + str(e)))
    sys.exit(1)


locale.setlocale(locale.LC_ALL, '')

@dataclass
class Portfolio_CreateConfig:
    store_file: str
    mo: str

#g_count = 0

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
            logger.debug(f"File :{self.store_file} is absent or modification time is more than cutoff time. Empty DataFrame created.")
            self.stock_data.to_csv(self.store_file, index=False)
        else:
            # Read the CSV file into a DataFrame
            self.stock_data = pd.read_csv(file_path)
            logger.debug(f"File: {file_path} was modified after 9:15 am today. DataFrame created successfully.")

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
        if tsym_token:
            if tsym_token in self.stock_data.index:
                return self.stock_data.loc[tsym_token, "available_qty"]
            else:
                return None

        if ul_index is not None:
            ul_data = self.stock_data[self.stock_data['ul_index'] == ul_index]
            if ul_data.empty:
                return None
            else:
                return ul_data['available_qty'].sum()
        else :
            try:
                qty = self.stock_data['available_qty'].sum()
            except Exception as e:
                return None
            else:
                return qty

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
        logger.debug(f'\n{pf_df}')

    def fetch_all_available_qty(self, ul_index):
        logger.info(f'ul_index: {ul_index}')
        return (self.stock_data[self.stock_data["ul_index"] == ul_index].copy())

    def show (self):
        logger.debug(f"[PORTFOLIO_TABLE_DEBUG] Starting portfolio show, stock_data shape: {self.stock_data.shape}")
        logger.debug(f"[PORTFOLIO_TABLE_DEBUG] stock_data columns: {list(self.stock_data.columns)}")
        logger.debug(f"[PORTFOLIO_TABLE_DEBUG] stock_data content: {self.stock_data.to_string()}")

        df = self.stock_data
        console = Console()
        table = Table(title='Portfolio-Records')
        table.add_column("#", justify="center")

        # Add index column
        table.add_column("tsym_token", justify="center")

        # Add header row
        for column in df.columns:
            table.add_column(column, justify="center")

        # Add data rows
        for i, (index, row) in enumerate(df.iterrows(), start=1):
            table.add_row(str(i), index, *[str(value) for value in row.tolist()])

        logger.debug(f"[PORTFOLIO_TABLE_DEBUG] About to print table with {len(df)} rows")
        console.print(table)
        logger.debug(f"[PORTFOLIO_TABLE_DEBUG] Table printed successfully")


@dataclass
class PFMU_CreateConfig:
    tiu: Tiu
    diu: Diu
    rec_file: str
    mo: str
    pf_file: str
    port: ExtSimpleQueue
    response_port: object = None  # Port for sending notifications to UI
    limit_order_cfg: bool = False
    reset: bool = False
    disable_price_entry_cb: Callable = None
    error_handler: InfraErrorHandler = None

class PFMU:
    __count = 0
    __componentType = Component_Type.ACTIVE

    def __init__(self, pfmu_cc: PFMU_CreateConfig):
        logger.info(f'{PFMU.__count}: Creating PFMU Object..')
        self.inst_id = f'{self.__class__.__name__}:{PFMU.__count}'
        PFMU.__count += 1

        self.pf_lock = Lock()
        self.cancellation_flag = False  # Flag to prevent race conditions during waiting order cancellation

        self.tiu = pfmu_cc.tiu
        self.diu = pfmu_cc.diu

        # Validate required error_handler
        if pfmu_cc.error_handler is None:
            raise ValueError("error_handler is required in PFMU_CreateConfig")
        self.error_handler = pfmu_cc.error_handler

        self.disable_price_entry_cb:Callable = pfmu_cc.disable_price_entry_cb

        def force_reconnect ():
            nonlocal self
            logger.debug ('Disabling Price entry ..')
            if self.disable_price_entry_cb is not None:
                r = self.disable_price_entry_cb ()
                if r :
                    logger.debug ('Cancelling all waiting Orders ..')
                    self.cancel_all_waiting_orders(exit_flag=False, show_table=True)
                    logger.debug ('Forcing the diu to reconnect ..')
                    self.diu.force_reconnect = True
                return r
            return True

        pmu_cc = PMU_CreateConfig(pfmu_cc.port, data_delay_callback_function=force_reconnect)

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
                    "click_time",
                    "click_price",
                    "tsym_token",
                    "ul_index",
                    "use_gtt_oco",
                    "trade",
                    "wait_price_lvl",
                    "prev_tick_lvl",
                    "n_orders",
                    "order_list",
                    "status"],
            )

        bku_cc = BookKeeperUnitCreateConfig(pfmu_cc.rec_file, pfmu_cc.reset)
        self.bku = BookKeeperUnit(bku_cc=bku_cc)

        pf_cc = Portfolio_CreateConfig(store_file=pfmu_cc.pf_file, mo=pfmu_cc.mo)
        self.portfolio = Portfolio(pf_cc=pf_cc)

        self._response_port = pfmu_cc.response_port
        self._notification_logger = NotificationLogger(f"{self.inst_id}.notifications")
        #
        # TODO: In case of a restart of app, portfolio should get updated based on the
        # platform quantity. If there is any difference ( due to manual exit and not manual entry...)
        # it should be taken into the portfolio.
        #
        
        # Pure PFMU service - AutoTrailer functionality moved to AutoTrailerManager
        # No AutoTrailer initialization or thread management in pure service

        logger.info(f'Creating PFMU Object.. Done')

        # Report successful initialization to error handler
        self.error_handler.report_connection_status(ConnectionStatus.CONNECTED, "PFMU")

    def start_monitoring(self):
        self.pmu.start_monitoring()







    # Pure PFMU Service - Timer functionality moved to SquareOffTimeManager
    
    def _send_system_sqoff_notification(self, trigger_source: str, trigger_reason: str, 
                                       pnl_at_trigger: float, additional_data: dict = None):
        """
        Send system square-off completion notification via response port using structured notifications
        
        Args:
            trigger_source: Source of square-off (USER, TIMER, SL_HIT, TARGET_HIT, TRAILING_SL)
            trigger_reason: Human-readable reason for square-off
            pnl_at_trigger: P&L value when square-off was triggered
            additional_data: Optional additional context data
        """
        if self._response_port is None:
            logger.warning("Response port not available for system square-off notification")
            return
            
        try:
            # Get current position status
            total_qty = self.portfolio.available_qty(ul_index=None)
            all_positions_closed = total_qty is None or total_qty == 0
            
            # Get symbol from additional data if available
            symbol = (additional_data or {}).get('symbol', 'Unknown')
            
            # Create structured notification using factory
            notification = NotificationFactory.square_off_success(
                mode="ALL",
                trigger_source=trigger_source,
                pnl=pnl_at_trigger,
                symbol=symbol
            )
            
            # Add additional PFMU-specific data
            notification.data.update({
                'total_positions': total_qty,
                'all_positions_closed': all_positions_closed,
                'trigger_reason': trigger_reason
            })
            
            # Add any additional data provided
            if additional_data:
                notification.data.update(additional_data)
            
            # Log the notification
            self._notification_logger.log_notification(notification, "sending")
            
            # Send via response port as structured notification
            self._response_port.send_data(notification.to_dict())
            
            logger.info(f"System square-off notification sent: source={trigger_source}, reason='{trigger_reason}', "
                       f"positions_closed={all_positions_closed}, qty={total_qty}, pnl={pnl_at_trigger:.2f}")
            
        except Exception as e:
            logger.error(f"Error sending system square-off notification: {e}")
            # Log the error through notification logger
            self._notification_logger.log_notification_error(e, "send_system_sqoff_notification")
    
    def _send_system_sqoff_error_notification(self, trigger_source: str, error_message: str, 
                                           pnl_at_trigger: float, additional_data: dict = None):
        """
        Send system square-off error notification via response port using structured notifications
        
        Args:
            trigger_source: Source of square-off (USER, AUTOTRAILER, TIMER)
            error_message: Human-readable error message
            pnl_at_trigger: P&L value when error occurred
            additional_data: Optional additional context data
        """
        if self._response_port is None:
            logger.warning("Response port not available for system square-off error notification")
            return
            
        try:
            # Get current position status
            total_qty = self.portfolio.available_qty(ul_index=None)
            positions_remain = total_qty is not None and total_qty > 0
            
            # Get symbol from additional data if available
            symbol = (additional_data or {}).get('symbol', 'Unknown')
            
            # Create structured error notification using factory
            notification = NotificationFactory.square_off_error(
                mode="ALL",
                error_msg=error_message,
                trigger_source=trigger_source,
                symbol=symbol
            )
            
            # Add additional PFMU-specific data
            notification.data.update({
                'total_positions': total_qty,
                'positions_remain': positions_remain,
                'pnl_at_trigger': pnl_at_trigger,
                'requires_manual_action': True
            })
            
            # Add any additional data provided
            if additional_data:
                notification.data.update(additional_data)
            
            # Log the notification
            self._notification_logger.log_notification(notification, "sending")
            
            # Send via response port as structured notification
            self._response_port.send_data(notification.to_dict())
            
            logger.error(f"System square-off error notification sent: source={trigger_source}, error='{error_message}', "
                       f"positions_remain={positions_remain}, qty={total_qty}, pnl={pnl_at_trigger:.2f}")
            
        except Exception as e:
            logger.error(f"Error sending system square-off error notification: {e}")
            # Log the error through notification logger
            self._notification_logger.log_notification_error(e, "send_system_sqoff_error_notification")

    def wo_table_show(self):
        if self.limit_order_cfg:
            logger.debug(f"[WO_TABLE_DEBUG] Starting wo_table_show, wo_df shape: {self.wo_df.shape}")
            logger.debug(f"[WO_TABLE_DEBUG] wo_df columns: {list(self.wo_df.columns)}")
            logger.debug(f"[WO_TABLE_DEBUG] wo_df content: {self.wo_df.to_string()}")

            df = self.wo_df[["click_time","click_price", "wait_price_lvl", "tsym_token", "trade", "n_orders", "use_gtt_oco", "status"]]
            logger.debug(f"[WO_TABLE_DEBUG] Filtered df shape: {df.shape}")

            console = Console()
            table = Table(title='Waiting-Order-Records')
            table.add_column("#", justify="center")

            # Add header row
            for column in df.columns:
                table.add_column(column, justify="center")

            # Add data rows
            for i, (_, row) in enumerate(df.iterrows(), start=1):
                table.add_row(str(i), *[str(value) for value in row.tolist()])

            logger.debug(f"[WO_TABLE_DEBUG] About to print table with {len(df)} rows")
            console.print(table)
            logger.debug(f"[WO_TABLE_DEBUG] Table printed successfully")
        else:
            logger.debug(f"[WO_TABLE_DEBUG] limit_order_cfg is disabled, skipping table display")

    def show(self):
        logger.debug("PFMU: Starting show method - displaying BKU, waiting orders, and portfolio")
        self.bku.show()
        self.wo_table_show()
        self.portfolio.show()
        logger.debug("PFMU: Completed show method")

    def _add_order(
            self,
            ul_token: str,
            ul_index: str,
            tsym_token: str,
            use_gtt_oco: bool,
            click_price: float,
            wait_price: float,
            order_list: list, action:str):
        # Find the index where it would lie in OrderBank

        index = len(self.wo_df)
        key_name = f"{ul_token}_{index}"

        wait_price_lvl = round(wait_price * self.prec_factor)

        # Create a new row with initial values

        now = datetime.now().strftime("%H:%M:%S")

        new_order = {
            "click_time" : now,
            "click_price": click_price,
            "tsym_token": tsym_token,
            "ul_index": ul_index,
            "use_gtt_oco": use_gtt_oco,
            "trade": action,
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
        ...
    #     r = False
    #     order_info = self.wo_df.loc[key_name]
    #     ltp_level = round(ltp * self.prec_factor)
    #     wait_price_lvl = order_info.wait_price_lvl

    #     if order_info.prev_tick_lvl:
    #         if order_info.cond:
    #             if order_info.prev_tick_lvl < wait_price_lvl and ltp_level >= wait_price_lvl:
    #                 logger.debug (f'order_info.prev_tick_lvl: {order_info.prev_tick_lvl} wait_price_lvl: {wait_price_lvl} Triggered')
    #                 r = True
    #         else:
    #             if order_info.prev_tick_lvl > wait_price_lvl and ltp_level <= wait_price_lvl:
    #                 logger.debug (f'order_info.prev_tick_lvl: {order_info.prev_tick_lvl} wait_price_lvl: {wait_price_lvl} Triggered')
    #                 r = True
    #     if r:
    #         self._order_placement_th (key_name=key_name)
    #     else:
    #         with self.ord_lock:
    #             self.wo_df.loc[key_name, "prev_tick_lvl"] = ltp_level

    #     return r

    def order_placement(self, key_name: str):
        logger.debug(f"Callback triggered for ID: {key_name}")
        with self.ord_lock:
            # Check cancellation flag to prevent orders from being triggered during cancellation
            if self.cancellation_flag:
                logger.debug(f"Order placement blocked for {key_name} due to cancellation in progress")
                return
            
            order_info = self.wo_df.loc[key_name]
            
            # Check if order was cancelled while waiting to be processed
            if order_info.status == 'Cancelled':
                logger.debug(f"Order {key_name} was cancelled, skipping execution")
                return
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

            self.wo_table_show()

    def _order_placement_th(self, key_name: str, ft:str):
        logger.debug (f'Creating Thread: key_name:{key_name}')
        
        # Check cancellation flag before creating thread to prevent orders from being triggered during cancellation
        if self.cancellation_flag:
            logger.debug(f"Order placement thread creation blocked for {key_name} due to cancellation in progress")
            return
            
        with self.ord_lock:
            self.wo_df.loc[key_name, "status"] = f"Trig @ {ft}"
        Thread(name=f'PMU Order Placement Thread {key_name}', target=self.order_placement, args=(key_name,), daemon=True).start()
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

    def __cancel_all_waiting_orders_com__(self, ul_token, detailed_logging=False):
        if detailed_logging:
            logger.info("=== WAITING ORDER CANCELLATION START ===")
        
        cancelled_count = 0
        failed_count = 0
        failed_orders = []
        
        # Get list of orders to cancel
        orders_to_cancel = []
        for index, row in self.wo_df.iterrows():
            key_name = index
            ul_token_from_key_name = index.split('_')[0]

            if ul_token:
                if ul_token != ul_token_from_key_name:
                    continue

            status = row["status"]
            if status == 'Waiting':
                orders_to_cancel.append((key_name, ul_token_from_key_name, row))
        
        if detailed_logging:
            logger.info(f"Found {len(orders_to_cancel)} waiting orders to cancel")
        
        # Cancel each order with retry logic
        for idx, (key_name, ul_token_from_key_name, row) in enumerate(orders_to_cancel):
            if detailed_logging:
                logger.info(f"Cancelling order {idx+1}/{len(orders_to_cancel)}: {key_name} ({row['tsym_token']} {row['trade']})")
            
            # Use lock-free retry logic for cancellation (we already hold ord_lock)
            cancel_result = self._cancel_waiting_order_with_retry_unlocked(
                key_name, ul_token_from_key_name, 
                max_retries=2, 
                detailed_logging=detailed_logging
            )
            
            if cancel_result["success"]:
                cancelled_count += 1
                if detailed_logging and cancel_result["attempts"] > 1:
                    logger.info(f"Order {key_name} cancelled after {cancel_result['attempts']} attempts")
            else:
                failed_count += 1
                failed_orders.append({
                    "key_name": key_name,
                    "error": cancel_result.get("error", "Unknown error"),
                    "attempts": cancel_result.get("attempts", 1)
                })
                if detailed_logging:
                    logger.error(f"[X] Order {key_name} cancellation failed after {cancel_result['attempts']} attempts: {cancel_result.get('error', 'Unknown error')}")
        
        if detailed_logging:
            logger.info(f"Cancellation summary: {cancelled_count} succeeded, {failed_count} failed")
            if failed_orders:
                logger.error(f"Failed orders details:")
                for failed_order in failed_orders:
                    logger.error(f"  - {failed_order['key_name']}: {failed_order['error']} (attempts: {failed_order['attempts']})")
            logger.info("=== WAITING ORDER CANCELLATION END ===")
        
        return {
            "success": failed_count == 0,
            "cancelled": cancelled_count,
            "failed": failed_count,
            "failed_orders": failed_orders
        }

    def cancel_all_waiting_orders(self, ul_token=None, exit_flag=False, show_table=True, detailed_logging=False):
        result = {"success": True, "cancelled": 0, "failed": 0, "failed_orders": []}
        
        if self.limit_order_cfg:
            with self.ord_lock:
                # Check if cancellation is already in progress
                if self.cancellation_flag:
                    if detailed_logging:
                        logger.warning("Cancellation already in progress, skipping duplicate request")
                    return {"success": False, "error": "Cancellation already in progress", "cancelled": 0, "failed": 0, "failed_orders": []}
                
                # Set cancellation flag to prevent race conditions
                self.cancellation_flag = True
                
                try:
                    result = self.__cancel_all_waiting_orders_com__(ul_token=ul_token, detailed_logging=detailed_logging)
                finally:
                    # Always reset the flag when done
                    self.cancellation_flag = False
        elif detailed_logging:
            logger.info("Limit order feature not enabled - no waiting orders to cancel")

        if exit_flag:
            self.pmu.hard_exit()
        if show_table:
            self.wo_table_show()
            
        return result

    def cancel_all_waiting_orders_from_pf_context(self, ul_token=None, exit_flag=False, show_table=True, detailed_logging=False):
        """Cancel all waiting orders when called from within pf_lock context
        This avoids the pf_lock -> ord_lock deadlock by acquiring ord_lock separately"""
        result = {"success": True, "cancelled": 0, "failed": 0, "failed_orders": []}
        
        if self.limit_order_cfg:
            # We need to acquire ord_lock, but we're coming from pf_lock context
            # This is safe because we're going pf_lock -> ord_lock consistently
            with self.ord_lock:
                # Check if cancellation is already in progress
                if self.cancellation_flag:
                    if detailed_logging:
                        logger.warning("Cancellation already in progress, skipping duplicate request")
                    return {"success": False, "error": "Cancellation already in progress", "cancelled": 0, "failed": 0, "failed_orders": []}
                
                # Set cancellation flag to prevent race conditions
                self.cancellation_flag = True
                
                try:
                    result = self.__cancel_all_waiting_orders_com__(ul_token=ul_token, detailed_logging=detailed_logging)
                finally:
                    # Always reset the flag when done
                    self.cancellation_flag = False
        elif detailed_logging:
            logger.info("Limit order feature not enabled - no waiting orders to cancel")

        if exit_flag:
            self.pmu.hard_exit()
        if show_table:
            self.wo_table_show()
            
        return result

    def _cancel_waiting_order_with_retry_unlocked(self, key_name, ul_token_from_key_name, max_retries=2, detailed_logging=False):
        """Internal lock-free version - Cancel a waiting order with retry logic
        MUST be called with ord_lock already held"""
        
        for attempt in range(max_retries + 1):
            try:
                # Attempt to cancel the order
                self.pmu.unregister_callback(ul_token_from_key_name, callback_id=key_name)
                self.wo_df.at[key_name, "status"] = "Cancelled"
                
                if detailed_logging:
                    if attempt > 0:
                        logger.info(f"[OK] Order {key_name} cancelled successfully on retry {attempt}")
                    else:
                        logger.info(f"[OK] Order {key_name} cancelled successfully")
                
                return {"success": True, "attempts": attempt + 1}
                
            except Exception as e:
                if attempt < max_retries:
                    if detailed_logging:
                        logger.warning(f"Retry {attempt + 1} failed for order {key_name}: {str(e)}")
                    time.sleep(0.1)  # Small delay before retry
                else:
                    if detailed_logging:
                        logger.error(f"Final retry failed for order {key_name}: {str(e)}")
                    return {"success": False, "error": str(e), "attempts": attempt + 1}
    
        return {"success": False, "error": "Max retries exceeded", "attempts": max_retries + 1}

    def cancel_waiting_order_with_retry(self, key_name, ul_token_from_key_name, max_retries=2, detailed_logging=False):
        """Cancel a waiting order with retry logic"""
        with self.ord_lock:
            return self._cancel_waiting_order_with_retry_unlocked(key_name, ul_token_from_key_name, max_retries, detailed_logging)

    def _get_waiting_orders_count_unlocked(self, ul_token=None):
        """Internal lock-free version - Get count of active waiting orders
        MUST be called with ord_lock already held"""
        if not self.limit_order_cfg:
            return 0
            
        if ul_token:
            waiting_orders = self.wo_df[
                (self.wo_df.index.str.startswith(f"{ul_token}_")) & 
                (self.wo_df['status'] == 'Waiting')
            ]
        else:
            waiting_orders = self.wo_df[self.wo_df['status'] == 'Waiting']
        return len(waiting_orders)

    def get_waiting_orders_count(self, ul_token=None):
        """Get count of active waiting orders"""
        if not self.limit_order_cfg:
            return 0
            
        with self.ord_lock:
            return self._get_waiting_orders_count_unlocked(ul_token)

    def _get_waiting_orders_list_unlocked(self, ul_token=None):
        """Internal lock-free version - Get list of active waiting orders
        MUST be called with ord_lock already held"""
        if not self.limit_order_cfg:
            return []
            
        if ul_token:
            waiting_orders = self.wo_df[
                (self.wo_df.index.str.startswith(f"{ul_token}_")) & 
                (self.wo_df['status'] == 'Waiting')
            ]
        else:
            waiting_orders = self.wo_df[self.wo_df['status'] == 'Waiting']
        
        order_list = []
        for index, row in waiting_orders.iterrows():
            order_list.append({
                'key_name': index,
                'ul_token': index.split('_')[0],
                'tsym_token': row['tsym_token'],
                'trade': row['trade'],
                'wait_price_lvl': row['wait_price_lvl'],
                'click_time': row['click_time'],
                'status': row['status']
            })
        return order_list

    def get_waiting_orders_list(self, ul_token=None):
        """Get list of active waiting orders with details"""
        if not self.limit_order_cfg:
            return []
            
        with self.ord_lock:
            return self._get_waiting_orders_list_unlocked(ul_token)

    def take_position(self, action: str, inst_info: InstrumentInfo, trade_price: float|None):

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
                        logger.debug(f'Position Taken {inst_info} total_qty: {total_qty}')
                        self.portfolio.update_position_taken(tsym_token=r.tsym_token, ul_index=inst_info.ul_index, qty=total_qty)
                self.show()
            else:
                ul_token = self.diu.ul_token
                use_gtt_oco = True if inst_info.order_prod_type == 'O' else False
                key_name = self._add_order(ul_token=ul_token, ul_index=inst_info.ul_index, tsym_token=r.tsym_token,
                                           use_gtt_oco=use_gtt_oco,
                                           click_price=r.ul_ltp,
                                           wait_price=trade_price, order_list=r.orders_list, action=action)

                order_info = self.wo_df.loc[key_name]
                cond_obj = WaitConditionData(condition_fn=self._price_condition,
                                             callback_function=self._order_placement_th,
                                             cb_id=key_name,
                                             wait_price_lvl=order_info.wait_price_lvl,
                                             prec_factor=self.prec_factor)

                self.pmu.register_callback(token=ul_token, cond_obj=cond_obj)
                self.wo_table_show()
                # global g_count
                # g_count += 1

                # if g_count == 5:
                #     # self.pmu.simulate(ultoken=ul_token, trade_price=trade_price, cross='down')
                logger.debug(f'Registered Call back with PMU {key_name} {cond_obj}')

            return total_qty

    def _update_portfolio_based_platform(self):
        r = self.error_handler.handle_api_call(
            api_function=lambda: self.tiu.get_positions(),
            component_id="PFMU"
        )
        if r is not None and isinstance(r, list):
            posn_df = pd.DataFrame(r)
            posn_df.loc[posn_df['prd'] == 'I', 'netqty'] = posn_df.loc[posn_df['prd'] == 'I', 'netqty'].apply(lambda x: int(x))
            posn_df = posn_df.loc[(posn_df['prd'] == 'I')]
            if not posn_df.empty:
                self.portfolio.update_portfolio_from_position(posn_df=posn_df)
        else:
            logger.info(f'Not able to fetch the positions. Check manually')

    def square_off_position(self, mode, ul_index: str = None, ul_symbol:str=None,
                            per: float = 100, inst_type: str = None, partial_exit: bool = False, exit_flag=True, trigger_source: str = "USER"):
        logger.debug(f'[SQUARE_OFF_DEBUG] Starting square_off_position: mode={mode}, ul_index={ul_index}, ul_symbol={ul_symbol}, per={per}, inst_type={inst_type}, partial_exit={partial_exit}, exit_flag={exit_flag}, trigger_source={trigger_source}')

        # Enforce exit_flag rules: Only TIMER can shut down PMU during trading hours
        original_exit_flag = exit_flag
        if trigger_source == "TIMER":
            # End of day - always shut down PMU
            exit_flag = True
        else:
            # During trading hours (AUTOTRAILER, USER, etc.) - keep PMU running
            exit_flag = False

        if original_exit_flag != exit_flag:
            logger.info(f'[SQUARE_OFF_DEBUG] exit_flag overridden: {original_exit_flag} -> {exit_flag} (trigger_source={trigger_source})')

        def place_sq_off_order(tsym: str, b_or_s: str, exit_qty: int, ls: int, frz_qty: int, exchange='NSE'):
            nonlocal self
            failure_cnt = 0
            order = None
            closed_qty = 0

            # find nearest qty to lotsize multiple

            exit_qty = int(exit_qty/ls)*ls

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
                logger.debug (f'order:{str(order)}')

                try:
                    r = self.tiu.get_order_margin(buy_or_sell=b_or_s, exchange=exchange,
                                                product_type='I', tradingsymbol=tsym,
                                                quantity=per_leg_exit_qty, price_type='MKT', price=0.0)
                except Exception as e:
                    logger.error (f'Exception occured {repr(e)}')
                    return None
                else:
                    logger.debug (f"qty: {per_leg_exit_qty} {json.dumps(r, indent=2)}")
                    if r and r['stat'] == 'Ok':
                        if (r['remarks'] == 'Squareoff Order'):
                            logger.debug (f'square_off_qty: {per_leg_exit_qty}')
                        else :
                            logger.error (f'Qty to square off > in Position: Take Manual Control: {per_leg_exit_qty} {r["remarks"]} ')
                            break
                    else :
                        logger.debug (f'Trying to Square off without checking Order Margin')

                r = self.tiu.place_order(order)
                if r is None:
                    logger.debug(f'Exit order Failed: Check Manually')
                    break

                if r['stat'] == 'Not_Ok':
                    logger.debug(f'Exit order Failed:  {r["emsg"]}')
                    failure_cnt += 1
                else:
                    logger.debug(f'Exit Order Attempt success:: order id  : {r["norenordno"]}')
                    order_id = r["norenordno"]
                    r_os_list = self.tiu.single_order_history(order_id)

                    # Shoonya gives a list for all status of order, we are interested in first one
                    r_os_dict = r_os_list[0]
                    if r_os_dict["status"].lower() == "complete":
                        closed_qty += order.quantity
                        logger.debug(f'Exit order Complete: order_id: {order_id}')
                    else:
                        logger.debug(f'Exit order InComplete: order_id: {order_id} Check Manually')
                    exit_qty -= per_leg_exit_qty

            if failure_cnt > 2 or exit_qty:
                logger.debug(f'Exit order InComplete: Check Manually')
                raise OrderExecutionException

            logger.debug(f'tsym_token:{tsym} qty: {closed_qty} squared off..')

            return closed_qty

        def reduce_qty_for_ul(ul_index, ul_ltp, reduce_per, inst_type):
            nonlocal self
            with self.pf_lock:
                self._update_portfolio_based_platform()
                df = self.portfolio.fetch_all_available_qty(ul_index=ul_index)
                logger.debug(f'\n {df}')
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

                    logger.debug(f'\n{ul_rows}')
                # if available quantity of ul_index, CE/PE is not there, then also it should return
                if ul_rows.empty:
                    return
                else:
                    total_reduce_qty = 0
                    new_available_qty = None
                    if inst_type == 'CE' or inst_type == 'PE':
                        pattern = r'([CP])(\d+)'
                        # Function to extract option type ('C' or 'P') and strike price

                        def extract_option_info(option_symbol):
                            # Split the string at the underscore
                            parts = option_symbol.split('_')
                            
                            # The first part contains the strike price information
                            strike_info = parts[0]
                            
                            # Initialize an empty string to collect digits
                            strike_price = ''
                            
                            opt_type = None
                            # Scan from the right side of the string until a non-digit character is found
                            found = False
                            for char in reversed(strike_info):
                                if char.isdigit():
                                    strike_price = char + strike_price  # Prepend to maintain order
                                else:
                                    opt_type = char
                                    found = True
                                    break  # Stop when we hit a non-digit character
                            
                            if found and (opt_type == 'C' or opt_type == 'P'):
                                # Convert to integer and return
                                return opt_type, int(strike_price)
                            else:
                                return None, None

                        def extract_option_info_delete(index):
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
                            logger.debug(f'{ce_df_sorted}')

                            if not ce_df_sorted.empty:
                                max_qty = ce_df_sorted['max_qty'].sum()
                                total_reduce_qty = int(max_qty * (reduce_per / 100))
                                new_available_qty = max_qty - total_reduce_qty
                                logger.debug(f'CE: new_available_qty {new_available_qty} total_reduce_qty_ce: {total_reduce_qty}')
                            sq_df = ce_df_sorted
                        else:
                            pe_df = ul_rows[ul_rows['option_type'] == 'P'].copy()
                            # Calculate the absolute difference between each strike price and ul_ltp
                            pe_df['distance_from_ul_ltp'] = pe_df['strike_price'] - ul_ltp
                            # Sort PE DataFrame based on the distance from ul_ltp in ascending order
                            pe_df_sorted = pe_df.sort_values(by='distance_from_ul_ltp', ascending=False)
                            logger.debug(f'{pe_df_sorted}')
                            if not pe_df_sorted.empty:
                                max_qty = pe_df_sorted['max_qty'].sum()
                                total_reduce_qty = int(max_qty * (reduce_per / 100))
                                new_available_qty = max_qty - total_reduce_qty
                                logger.debug(f'PE: new_available_qty {new_available_qty} total_reduce_qty_pe: {total_reduce_qty}')
                            sq_df = pe_df_sorted
                            total_available_qty = sq_df['available_qty'].sum()
                    else:
                        max_qty = ul_rows['max_qty'].sum()
                        total_reduce_qty = int(max_qty * (reduce_per / 100))
                        new_available_qty = max_qty - total_reduce_qty
                        logger.debug(f'BEES: new_available_qty {new_available_qty} total_reduce_qty: {total_reduce_qty}')
                        sq_df = ul_rows

                    total_available_qty = sq_df['available_qty'].sum() if len(sq_df) else 0

                    logger.debug(f'Total Available : {total_available_qty} New_Available: {new_available_qty} ')

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

                                logger.debug(f'Reducing tsym_token: {tsym_token} {tsym} {token} reduce_qty: {act_sq_off_qty} of {diff_qty}')
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

                                logger.debug(f'Reducing tsym_token: {tsym_token} {tsym} {token} reduce_qty: updated: {act_sq_off_qty} of {diff_qty}')

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

        def __square_off_position(df: pd.DataFrame, symbol=None, wait_flag=False):
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

            if wait_flag:
                sleep(0.4)
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
                    logger.debug(f'[SQUARE_OFF_DEBUG] Processing position: {tsym_token}, recorded_qty: {rec_qty}')
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
                    logger.debug(f'[SQUARE_OFF_DEBUG] Position data: tsym={tsym}, token={token}, posn_qty={posn_qty}, net_qty={net_qty}')

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

                    logger.debug(f'[SQUARE_OFF_DEBUG] Exit decision: net_qty={net_qty}, rec_qty={rec_qty}, condition net_qty > 0: {net_qty > 0}')
                    if net_qty > 0:
                        # exit the position
                        # CRITICAL FIX (2025-01-19): NIFTYBEES Square-off Issue Resolution
                        # Problem: Buy → Square-off → Short → Square-off sequence failed on second square-off
                        # Root Cause: orders.csv sums offsetting orders: +1 (Buy) + (-1) (Short) = 0 (rec_qty)
                        #             But broker still shows position: -1 (posn_qty), net_qty = 1
                        # Old Formula: exit_qty = min(abs(rec_qty), net_qty) = min(abs(0), 1) = 0 ❌ FAILED
                        # New Formula: exit_qty = abs(min(rec_qty, posn_qty)) = abs(min(0, -1)) = 1 ✅ WORKS
                        # Maintains min(system_responsibility, broker_reality) principle while handling tracking gaps
                        exit_qty = abs(min(rec_qty, posn_qty))
                        logger.debug(f'[SQUARE_OFF_DEBUG] Entering exit logic: exit_qty={exit_qty}, abs(rec_qty)={abs(rec_qty)}, net_qty={net_qty}')
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

                            logger.debug(f'[SQUARE_OFF_DEBUG] Order loop: exit_qty={exit_qty}, per_leg_exit_qty={per_leg_exit_qty}, failure_cnt={failure_cnt}')
                            if order and order.quantity == per_leg_exit_qty:
                                logger.debug(f'[SQUARE_OFF_DEBUG] Reusing existing order with same quantity')
                            else:
                                logger.debug(f'[SQUARE_OFF_DEBUG] Creating new order: rec_qty={rec_qty}, rec_qty > 0: {rec_qty > 0}')
                                if rec_qty > 0:
                                    order = I_S_MKT_Order(tradingsymbol=tsym, quantity=per_leg_exit_qty, exchange=exch)
                                    logger.debug(f'[SQUARE_OFF_DEBUG] Created SELL order: {tsym}, qty={per_leg_exit_qty}, exch={exch}')
                                else:
                                    order = I_B_MKT_Order(tradingsymbol=tsym, quantity=per_leg_exit_qty, exchange=exch)
                                    logger.debug(f'[SQUARE_OFF_DEBUG] Created BUY order: {tsym}, qty={per_leg_exit_qty}, exch={exch}')

                            # r = self.fv.place_order(buy_or_sell, product_type='I', exchange=exch, tradingsymbol=tsym,
                            #                         quantity=per_leg_exit_qty, price_type='MKT', discloseqty=0.0)

                            logger.debug(f'[SQUARE_OFF_DEBUG] Placing order: {order.__class__.__name__} for {tsym}')
                            r = self.tiu.place_order(order)
                            logger.debug(f'[SQUARE_OFF_DEBUG] Order placement result: {r}')

                            if r is None or r['stat'] == 'Not_Ok':
                                logger.info(f'[SQUARE_OFF_DEBUG] Exit order Failed:  {r["emsg"] if r else "None response"}')
                                failure_cnt += 1
                            else:
                                logger.info(f'[SQUARE_OFF_DEBUG] Exit Order Attempt success:: order id  : {r["norenordno"]}')
                                order_id = r["norenordno"]
                                r_os_list = self.tiu.single_order_history(order_id)
                                # Shoonya gives a list for all status of order, we are interested in first one
                                r_os_dict = r_os_list[0]
                                logger.debug(f'[SQUARE_OFF_DEBUG] Order status check: {r_os_dict["status"]}')
                                if r_os_dict["status"].lower() == "complete":
                                    closed_qty += order.quantity
                                    logger.info(f'[SQUARE_OFF_DEBUG] Exit order Complete: order_id: {order_id}, closed_qty: {closed_qty}')
                                else:
                                    logger.info(f'[SQUARE_OFF_DEBUG] Exit order InComplete: order_id: {order_id} Status: {r_os_dict["status"]} Check Manually')
                                exit_qty -= per_leg_exit_qty

                        if failure_cnt > 2 or exit_qty:
                            logger.info(f'Exit order InComplete: order_id: {order_id} Check Manually')
                            raise OrderExecutionException
                        elif closed_qty:
                            logger.info(f'[SQUARE_OFF_DEBUG] tsym_token:{tsym_token} qty: {closed_qty} squared off..')
                            logger.debug(f'[SQUARE_OFF_DEBUG] Position update: rec_qty={rec_qty}, closed_qty={closed_qty}, updating with qty={-closed_qty if rec_qty < 0 else closed_qty}')
                            if rec_qty < 0:
                                self.portfolio.update_position_closed(tsym_token=tsym_token, qty=-closed_qty)
                            else:
                                self.portfolio.update_position_closed(tsym_token=tsym_token, qty=closed_qty)
                    else:
                        logger.debug(f'[SQUARE_OFF_DEBUG] Skipping position {tsym_token}: net_qty={net_qty} <= 0, no square-off needed')

        df = self.bku.fetch_orders_df()

        if mode == 'ALL':
            # System Square off - At square off time
            with self.pf_lock:
                wait_flag = False
                avl = self.portfolio.available_qty(ul_index=None)
                if avl is not None and not avl:
                    logger.info (f'No Recoreded Positions to Square Off')
                    wait_flag = True
                    # If there are any open orders, that also need to be cancelled
                try:
                    if self.limit_order_cfg:
                        self.cancel_all_waiting_orders_from_pf_context(exit_flag=exit_flag, show_table=False)
                    __square_off_position(df=df, wait_flag=wait_flag)
                    time.sleep(2)  # Allow settlement time for orders to complete
                    if self._verify_all_positions_closed_on_broker():
                        with self.pf_lock:
                            self.portfolio.verify_reset()
                        logger.info("Positions verified closed on broker - reset completed")
                    else:
                        logger.warning("Some positions still open on broker - skipping reset")

                    # Send system square-off notification via port instead of callback
                    current_pnl = self.intra_day_pnl()
                    self._send_system_sqoff_notification(trigger_source, "Square-off position completed", current_pnl)

                except OrderExecutionException:
                    logger.error('Major Exception Happened: Take Manual control..')
                    # Send error notification instead of complete notification
                    current_pnl = self.intra_day_pnl()
                    self._send_system_sqoff_error_notification(trigger_source, "Order execution failed - Take manual control", current_pnl)

        else:
            if partial_exit:
                ul_ltp = self.diu.get_latest_tick(ul_index=ul_index)
                # ul_ltp is required for find the deep in the money strikes
                reduce_qty_for_ul(ul_index=ul_index, ul_ltp=ul_ltp, reduce_per=per, inst_type=inst_type)

                # Add check for any remaining positions after partial exit
                remaining_qty = self.portfolio.available_qty(ul_index=None)
                if remaining_qty is not None and remaining_qty == 0:
                    # No positions left, send system square-off notification
                    current_pnl = self.intra_day_pnl()
                    self._send_system_sqoff_notification(trigger_source, "Partial exit completed all positions", current_pnl)

            else:
                with self.pf_lock:
                    wait_flag = False
                    avl = self.portfolio.available_qty(ul_index=None)
                    if avl is not None and not avl:
                        logger.info (f'No quantity to Square Off')
                        wait_flag = True
                    try:
                        ul_token = self.diu.ul_token
                        if self.limit_order_cfg:
                            self.cancel_all_waiting_orders_from_pf_context(ul_token=ul_token, show_table=False)

                        __square_off_position(df=df, symbol=ul_symbol, wait_flag=wait_flag)
                        time.sleep(2)  # Allow settlement time for orders to complete
                        if self._verify_positions_closed_for_index(ul_index):
                            self.portfolio.verify_reset(ul_index=ul_index)
                            logger.info(f"Positions for {ul_index} verified closed on broker - reset completed")
                        else:
                            logger.warning(f"Positions for {ul_index} still open on broker - skipping reset")
                    except OrderExecutionException:
                        logger.error('Major Exception Happened: Take Manual control..')
                        return False  # Return False for actual failures

        logger.info("[SQUARE_OFF_DEBUG] Square off Position - Complete.")
        return True  # Return True for successful completion (even if no positions to square off)

    def _verify_all_positions_closed_on_broker(self):
        """
        Verify that all positions are actually closed on the broker platform.
        Returns True if all positions are closed, False otherwise.
        """
        try:
            positions = self.tiu.get_positions()
            if positions is None:
                logger.warning("Unable to fetch positions from broker - assuming not closed")
                return False

            if isinstance(positions, list):
                posn_df = pd.DataFrame(positions)
                # Filter for MIS positions only and convert netqty to int
                mis_positions = posn_df.loc[posn_df['prd'] == 'I'].copy()
                if not mis_positions.empty:
                    mis_positions['netqty'] = mis_positions['netqty'].apply(lambda x: int(x))
                    open_positions = mis_positions[mis_positions['netqty'] != 0]
                    if not open_positions.empty:
                        logger.debug(f"Found {len(open_positions)} open MIS positions on broker")
                        return False

                logger.debug("All MIS positions confirmed closed on broker")
                return True
            else:
                logger.warning("Unexpected positions format from broker")
                return False

        except Exception as e:
            logger.error(f"Error verifying broker positions: {e}")
            return False

    def _verify_positions_closed_for_index(self, ul_index):
        """
        Verify that positions for a specific ul_index are closed on the broker platform.
        Returns True if positions for this index are closed, False otherwise.
        """
        try:
            positions = self.tiu.get_positions()
            if positions is None:
                logger.warning(f"Unable to fetch positions from broker for {ul_index} - assuming not closed")
                return False

            if isinstance(positions, list):
                posn_df = pd.DataFrame(positions)
                # Filter for MIS positions only and convert netqty to int
                mis_positions = posn_df.loc[posn_df['prd'] == 'I'].copy()
                if mis_positions.empty:
                    logger.debug(f"No MIS positions found on broker for {ul_index}")
                    return True

                mis_positions['netqty'] = mis_positions['netqty'].apply(lambda x: int(x))

                # Get all tsym_tokens for this ul_index from our portfolio
                df = self.portfolio.stock_data
                index_tokens = df[df['ul_index'] == ul_index].index.tolist()

                # Check if any broker positions match our tracked positions
                for index, row in mis_positions.iterrows():
                    pos_token = row.get('token', '')
                    pos_tsym = row.get('tsym', '')
                    pos_netqty = row.get('netqty', 0)

                    # Create tsym_token format to match our tracking
                    tsym_token = f"{pos_tsym}_{pos_token}"

                    if tsym_token in index_tokens and pos_netqty != 0:
                        logger.debug(f"Position still open for {ul_index}: {tsym_token} qty={pos_netqty}")
                        return False

                logger.debug(f"All positions for {ul_index} confirmed closed on broker")
                return True
            else:
                logger.warning("Unexpected positions format from broker")
                return False

        except Exception as e:
            logger.error(f"Error verifying broker positions for {ul_index}: {e}")
            return False

    def intra_day_pnl (self):
        mtm = 0.0
        df = self.bku.fetch_orders_df()
        if df is None or df.empty:
            return mtm
        try:
            # Some times partial orders are filled. In such cases also, it should be tracked.
            df_filtered = df[(df['Qty'] != 0) & ((df['Status'] == 'SUCCESS')| (df['Status'] == 'SOFT_FAILURE_QTY'))].copy()
            df_filtered['token'] = df_filtered['TradingSymbol_Token'].str.split('_').str[-1]
            unique_tokens_df = df_filtered[['token']].drop_duplicates()
        except Exception:
            # logger.info('No position to Square off')
            return
        else:
            r = self.error_handler.handle_api_call(
                api_function=lambda: self.tiu.get_positions(),
                component_id="PFMU"
            )
            if r is not None and isinstance(r, list):
                try:
                    posn_df = pd.DataFrame(r)
                    posn_df = posn_df.loc[(posn_df['prd'] == 'I')]

                    merged_df = posn_df.merge(unique_tokens_df[['token']], on='token', how='inner')
                    merged_df.loc[merged_df['prd'] == 'I', 'urmtom'] = merged_df.loc[merged_df['prd'] == 'I', 'urmtom'].apply(lambda x: locale.atof(x))

                    # Use .loc to filter rows and update the 'rpnl' column
                    merged_df.loc[merged_df['prd'] == 'I', 'rpnl'] = merged_df.loc[merged_df['prd'] == 'I', 'rpnl'].apply(lambda x: locale.atof(x))

                    # Filter the DataFrame for 'prd' == 'I' again to calculate the sums
                    mtm_df = merged_df.loc[merged_df['prd'] == 'I']

                    urmtom = mtm_df['urmtom'].sum()
                    pnl = mtm_df['rpnl'].sum()
                    mtm = round(urmtom + pnl, 2)
                except Exception as e:
                    logger.debug (f'Exception occured {str(e)}')
                else :
                    ...
        
        # Pure P&L calculation - AutoTrailer event handling moved to AutoTrailerManager
            
        return mtm


    def hard_exit(self):
        """
        Comprehensive cleanup and shutdown of PFMU components with thread management
        """
        logger.info("=== PFMU Hard Exit Started ===")
        cleanup_start_time = time.time()
        
        # Track cleanup operations
        cleanup_operations = []
        
        try:
            # STEP 1: Shutdown PMU (Price Monitoring Unit with data processing thread)
            if self.pmu:
                logger.info("Shutting down PMU component...")
                cleanup_operations.append("PMU")
                self.pmu.hard_exit()
            else:
                logger.debug("PMU not present or already shutdown")
            
            # STEP 2: Clean up any additional spawned threads (order placement threads, etc.)
            import threading
            active_threads = threading.enumerate()
            pfmu_threads = [t for t in active_threads if 'PMU Order Placement Thread' in t.name]
            
            if pfmu_threads:
                logger.info(f"Found {len(pfmu_threads)} PMU order placement threads still active")
                cleanup_operations.append(f"OrderThreads({len(pfmu_threads)})")
                # Note: These are daemon threads, they should stop when main threads stop
            
            # STEP 3: Final validation
            cleanup_time = time.time() - cleanup_start_time
            logger.info(f"PFMU components shutdown: {', '.join(cleanup_operations) if cleanup_operations else 'None'}")
            logger.info(f"=== PFMU Hard Exit Completed ({cleanup_time:.2f}s) ===")
            
        except Exception as e:
            logger.error(f"Error during PFMU hard_exit: {e}")
            logger.error(traceback.format_exc())
            logger.error("PFMU shutdown may be incomplete - check for zombie threads")
