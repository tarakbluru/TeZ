"""
File: ocpu.py
Author: [Tarakeshwar NC]
Date: January 15, 2024
Description: This script provides order creation and place functionality
"""
# Copyright (c) [2024] [Tarakeshwar N.C]
# This file is part of the Tiny_TeZ project.
# It is subject to the terms and conditions of the MIT License.
# See the file LICENSE in the top-level directory of this distribution
# for the full text of the license.

__author__ = "Tarakeshwar N.C"
__copyright__ = "2024"
__date__ = "2024/3/14"
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
    import copy
    import json
    import math
    import threading
    import numpy as np
    import pandas as pd
    from datetime import datetime
    from typing import NamedTuple
    import numpy as np
    from rich.console import Console
    from rich.table import Table

    import app_utils as utils

    from . import shared_classes, PFMU, Diu, Tiu, Tiu_OrderStatus, PriceMonitoringUnit 

except Exception as e:
    logger.debug(traceback.format_exc())
    logger.error(("Import Error " + str(e)))
    sys.exit(1)


class Ocpu_CreateConfig(NamedTuple):
    tiu: Tiu
    pfmu: PFMU
    diu: Diu
    pmu: PriceMonitoringUnit
    lmt_order:bool


OcpuInstrumentInfo = NamedTuple('OcpuInstrumentInfo', [('symbol', str),
                                                       ('ul_instrument', str),
                                                       ('exchange', str),
                                                       ('expiry_date', str),
                                                       ('strike_diff', int),
                                                       ('ce_strike_offset', str),
                                                       ('pe_strike_offset', str),
                                                       ('profit_per', float),
                                                       ('stoploss_per', float),
                                                       ('profit_points', float),
                                                       ('stoploss_points', float),
                                                       ('use_gtt_oco', bool),
                                                       ('qty', int),
                                                       ("n_legs", int),
                                                       ])

class OCPU(object):
    def __init__(self, ocpu_cc: Ocpu_CreateConfig):
        self.lock = threading.Lock()
        self.tiu = ocpu_cc.tiu
        self.pfmu = ocpu_cc.pfmu
        self.diu = ocpu_cc.diu
        self.pmu = ocpu_cc.pmu
        self.limit_order = ocpu_cc.lmt_order
        self.prec_factor = 100
        self.wo_df = pd.DataFrame(columns=["price_at_click", "tsym_token", "ul_symbol", "use_gtt_oco", "cond", "wait_price_lvl", "prev_tick_lvl", "n_orders", "order_list", "status"])
        
    def wo_table_show (self):
        if self.limit_order:
            df = self.wo_df [["price_at_click", "wait_price_lvl", "tsym_token","cond", "n_orders","use_gtt_oco", "status"]]
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

    def _add_order(self, ul_token:str, ul_symbol:str, tsym_token:str, use_gtt_oco:bool, price_at_click:float, wait_price:float, order_list: list):
        # Find the index where it would lie in OrderBank
        index = len(self.wo_df)
        # Create a key name "26000_<index>" using an f-string
        key_name = f"{ul_token}_{index}"
        if wait_price >= price_at_click:
            cond = 1
        elif wait_price < price_at_click:
            cond = 0
        
        wait_price_lvl = round (wait_price * self.prec_factor)
        # Create a new row with initial values

        new_order = {
            "price_at_click": price_at_click,
            "tsym_token":tsym_token,
            "ul_symbol":ul_symbol,
            "use_gtt_oco":use_gtt_oco,
            "cond": cond,
            "wait_price_lvl": int(wait_price_lvl),
            "prev_tick_lvl": np.nan,
            "n_orders": len(order_list),
            "order_list": order_list,
            "status":'Waiting'
        }
        # Append the new row to OrderBank DataFrame
        self.wo_df.loc[key_name] = new_order
        # Return the key name for easy access
        return key_name

    def _price_condition(self, ltp:float, key_name:str):
        order_info = self.wo_df.loc[key_name]
        ltp_level = round (ltp *self.prec_factor)
        wait_price_lvl = order_info.wait_price_lvl
        if order_info.prev_tick_lvl:
            if order_info.cond:
                if order_info.prev_tick_lvl < wait_price_lvl and ltp_level>=wait_price_lvl:
                    return True
            if not order_info.cond:
                if order_info.prev_tick_lvl > wait_price_lvl and ltp_level<=wait_price_lvl:
                    return True
        self.wo_df.loc[key_name, "prev_tick_lvl"] = ltp_level

    def order_placement(self, key_name:str):
        logger.debug(f"Callback triggered for ID: {key_name}")
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
            self.pfmu.save_order_details(order_id, order_info.tsym_token, qty, order_time, status, oco_order)

        logger.debug(f'Total Qty taken : {total_qty}')
        if total_qty:
            self.pfmu.portfolio_add (ul_symbol=order_info.ul_symbol, tsym_token=order_info.tsym_token, qty=total_qty)
        self.pfmu.show()

        self.wo_df.loc[key_name, "status"] = "Completed"
        self.wo_table_show()

    def _order_placement_th(self, key_name:str):
        threading.Thread(name='PMU Order Placement Thread',target=self.order_placement, args=(key_name,), daemon=True).start()


    # def disable_waiting_order(self, id, ul_token=None):
    # def enable_waiting_order(self, id, ul_token=None):
    # Enable and disable of orders:  Not done by desgin. Scoped out of this small project
    # To keep it simple, once order is waiting, it can be cancelled. 
    # if user wishes to re-enter he will have type in the detail and place the waiting order again.
    # 

    def cancel_waiting_order(self, id, ul_token=None):
        if ul_token:
            key_name = f"{ul_token}_{id}"
            if key_name in self.wo_df.index:
                status = self.wo_df.loc[key_name, "status"]
                if status == 'Waiting':
                    self.pmu.unregister_callback(ul_token, callback_id=key_name)
                    self.wo_df.loc[key_name, "status"] = "Cancelled"
        else :
            if id < len(self.wo_df):  # Check if id is within the DataFrame's range
                status = self.wo_df.iloc[id, self.wo_df.columns.get_loc("status")]
                if status == 'Waiting':
                    key_name = self.wo_df.index[id]
                    ul_token = key_name.split ('_')[0]
                    logger.info (f'unregistering: {key_name} ul_token: {ul_token}')
                    # Unregister callback and update status
                    self.pmu.unregister_callback( ul_token, callback_id=key_name)
                    self.wo_df.iloc[id, self.wo_df.columns.get_loc("status")] = "Cancelled"

        self.wo_table_show()

    def cancel_all_waiting_orders(self, ul_token=None):
        for index, row in self.wo_df.iterrows():
            if ul_token:
                key_name = f"{ul_token}_{index}"
            else:
                key_name = index
                ul_token = index.split ('_')[0]
            if key_name in self.wo_df.index:  # Check if the key name exists in the index
                status = row["status"]
                if status == 'Waiting':
                    self.pmu.unregister_callback(ul_token, callback_id=key_name)
                    self.wo_df.at[key_name, "status"] = "Cancelled"  # Use at[] for setting single values
        self.wo_table_show()

    def create_and_place_order(self, action: str, inst_info: OcpuInstrumentInfo, trade_price:float=None):
        def get_tsym_token(tiu: Tiu, diu: Diu, action: str):
            sym = inst_info.symbol
            expiry_date = inst_info.expiry_date
            ce_offset = inst_info.ce_strike_offset
            pe_offset = inst_info.pe_strike_offset
            qty = inst_info.qty
            exch = inst_info.exchange
            ul_ltp=ltp= diu.get_latest_tick()
            if exch == 'NFO':
                # find the nearest strike price
                strike_diff = inst_info.strike_diff
                strike1 = int(math.floor(ltp / strike_diff) * strike_diff)
                strike2 = int(math.ceil(ltp / strike_diff) * strike_diff)
                strike = strike1 if abs(ltp - strike1) < abs(ltp - strike2) else strike2
                logger.debug(f'strike1: {strike1} strike2: {strike2} strike: {strike}')
                c_or_p = 'C' if action == 'Buy' else 'P'

                if c_or_p == 'C':
                    strike_offset = ce_offset
                else:
                    strike_offset = pe_offset

                strike += int(strike_offset * strike_diff)
                # expiry_date = app_mods.get_system_info("TIU", "EXPIRY_DATE")
                parsed_date = datetime.strptime(expiry_date, '%d-%b-%Y')
                exp_date = parsed_date.strftime('%d%b%y')
                searchtext = f'{sym}{exp_date}{c_or_p}{strike:.0f}'
            elif exch == 'NSE':
                searchtext = sym
                strike = None
                logger.debug(f'ltp:{ltp} strike:{strike}')
            else:
                ...

            logger.debug(f'exch: {exch} searchtext: {searchtext}')
            token, tsym = tiu.search_scrip(exchange=exch, symbol=searchtext)

            if not token and not tsym:
                logger.error ('Major error: Check Expiry date')
                raise RuntimeError

            ltp, ti, ls = tiu.fetch_ltp(exch, token)

            qty = qty * ls

            r = tiu.get_security_info(exchange=exch, symbol=tsym, token=token)
            logger.debug(f'{json.dumps(r, indent=2)}')
            frz_qty = None
            if isinstance(r, dict) and 'frzqty' in r:
                frz_qty = int(r['frzqty'])
            else:
                frz_qty = qty + 1

            # Ideally, for breakout orders need to use the margin available
            # For option buying it is cash availablity.
            # To keep it simple, using available cash for both.
            margin = self.tiu.avlble_margin
            if margin < (ltp * 1.1 * qty):
                old_qty = qty
                qty = math.floor(margin / (1.1 * ltp))  # 10% buffer
                qty = int(qty / ls) * ls  # Important as above value will not be a multiple of lot
                logger.info(f'Available Margin: {self.tiu.avlble_margin:.2f} Required Amount: {ltp * old_qty} Updating qty: {old_qty} --> {qty} ')

            logger.debug(f'''strike: {strike}, sym: {sym}, tsym: {tsym}, token: {token},
                        qty:{qty}, ul_ltp:{ul_ltp}, ltp: {ltp}, ti:{ti} ls:{ls} frz_qty: {frz_qty}''')

            return strike, sym, tsym, token, qty, ul_ltp, ltp, ti, frz_qty, ls

        try:
            strike, sym, tsym, token, qty, ul_ltp, ltp, ti, frz_qty, ls = get_tsym_token(self.tiu, self.diu, action=action)
        except RuntimeError:
            raise
        except Exception as e:
            logger.error (f'Exception occured {e}')
        else:
            oco_order = np.nan
            os = shared_classes.OrderStatus()
            status = Tiu_OrderStatus.HARD_FAILURE

            given_nlegs = inst_info.n_legs

            if qty and given_nlegs:
                # Note: Following piece of Neat code has been developed after many Trials.
                # in case you are re-using the code, please do not forget to give a 
                # star on github.

                # +++++++++++++++++++++++++++++++++++++++++++++++++++++
                # Generic and mathematical solution for order Slicing:
                # +++++++++++++++++++++++++++++++++++++++++++++++++++++
                # Problem statement: required_nlegs, lot size, frz qty and trade_qty are given
                # Find no. of nlegs, per_leg_qty and residual qty.
                # 

                def lcm(x, y):
                    """Compute the least common multiple of x and y."""
                    return x * y // math.gcd(x, y)

                def find_nearest_lcm(lotsize, freezeqty, qty):
                    """Find the nearest LCM of lotsize and freezeqty that is less than qty."""
                    # Calculate the LCM of lotsize and freezeqty
                    lcm_value = lcm(lotsize, freezeqty)
                    
                    # Determine the nearest multiple of lcm_value less than qty
                    nearest_multiple = (qty // lcm_value) * lcm_value
                    
                    return nearest_multiple

                # Important: frz_qty is 1801 for nifty fno and not 1800 in finvasia api
                if (qty / given_nlegs) < frz_qty:
                    nearest_lcm_qty = qty
                    logger.debug(f'making nearest_lcm :{qty}')
                else:
                    nearest_lcm_qty = find_nearest_lcm(ls, (frz_qty-1), qty)

                logger.debug(f"qty:{qty} Nearest LCM qty:{nearest_lcm_qty}")
                
                res_qty1 = qty - nearest_lcm_qty
                min_legs = (nearest_lcm_qty//(frz_qty-1))  # Lower boundary
                max_legs = (nearest_lcm_qty//ls)           # Upper boundary

                logger.debug(f"res_qty1: {res_qty1} min_legs: {min_legs} max_legs:{max_legs}")

                # Below compact code is same as :
                # if given_nlegs < min_legs:
                #     nlegs = min_legs
                # elif given_nlegs > max_legs:
                #     nlegs = max_legs
                # else:
                #     nlegs = given_nlegs
                                    
                nlegs = max(min(given_nlegs, max_legs), min_legs)
                per_leg_qty = ((nearest_lcm_qty/nlegs)//ls)*ls
                logger.debug (f'n_given_legs: {given_nlegs}, nlegs: {nlegs} per_leg_qty:{per_leg_qty}')

                res_qty2 = nearest_lcm_qty - (per_leg_qty*nlegs)
                logger.debug(f'Verification: qty: {qty} final_qty: {((per_leg_qty*nlegs) + res_qty1 + res_qty2)}: {qty == ((per_leg_qty*nlegs) + res_qty1 + res_qty2)}')

                rem_qty = res_qty1 + res_qty2
                logger.debug (f'per_leg_qty: {per_leg_qty}, res_qty1:{res_qty1} res_qty2:{res_qty2}')
            else:
                logger.info(f'qty: {qty} given_nlegs: {given_nlegs} is not allowed')
                return

            logger.debug(f'sym:{sym} tsym:{tsym} ltp: {ltp}')

            use_gtt_oco = inst_info.use_gtt_oco
            remarks = None

            orders = []
            if (sym == 'NIFTYBEES' or sym == 'BANKBEES') and ltp is not None:
                pp = inst_info.profit_per / 100.0
                sl_p = inst_info.stoploss_per / 100.0
                if not use_gtt_oco:
                    bp = utils.round_stock_prec(ltp * pp, base=ti)
                    bl = utils.round_stock_prec(ltp * sl_p, base=ti)
                    logger.debug(f'ltp:{ltp} pp:{pp} bp:{bp} sl_p:{sl_p} bl:{bl}')

                    if per_leg_qty:
                        if action == 'Buy':
                            order = shared_classes.BO_B_MKT_Order(tradingsymbol=tsym,
                                                                quantity=per_leg_qty, book_loss_price=bl,
                                                                book_profit_price=bp, bo_remarks=remarks)
                        else:
                            order = shared_classes.BO_S_MKT_Order(tradingsymbol=tsym,
                                                                quantity=per_leg_qty, book_loss_price=bl,
                                                                book_profit_price=bp, bo_remarks=remarks)
                        orders = [copy.deepcopy(order) for _ in range(nlegs)]

                    if rem_qty:
                        if action == 'Buy':
                            order = shared_classes.BO_B_MKT_Order(tradingsymbol=tsym,
                                                                quantity=rem_qty, book_loss_price=bl,
                                                                book_profit_price=bp, bo_remarks=remarks)
                        else:
                            order = shared_classes.BO_S_MKT_Order(tradingsymbol=tsym,
                                                                quantity=rem_qty, book_loss_price=bl,
                                                                book_profit_price=bp, bo_remarks=remarks)
                        orders.append(order)
                else:
                    bp1 = utils.round_stock_prec(ltp + pp * ltp, base=ti)
                    bp2 = utils.round_stock_prec(ltp - pp * ltp, base=ti)
                    bp = bp1 if action == 'Buy' else bp2

                    bl1 = utils.round_stock_prec(ltp - sl_p * ltp, base=ti)
                    bl2 = utils.round_stock_prec(ltp + sl_p * ltp, base=ti)

                    bl = bl1 if action == 'Buy' else bl2
                    logger.debug(f'ltp:{ltp} pp:{pp} bp:{bp} sl_p:{sl_p} bl:{bl}')

                    if per_leg_qty:
                        if action == 'Buy':
                            order = shared_classes.Combi_Primary_B_MKT_And_OCO_S_MKT_I_Order_NSE(tradingsymbol=tsym, quantity=per_leg_qty,
                                                                                                bl_alert_p=bl, bp_alert_p=bp,
                                                                                                remarks=remarks)
                        else:
                            order = shared_classes.Combi_Primary_S_MKT_And_OCO_B_MKT_I_Order_NSE(tradingsymbol=tsym, quantity=per_leg_qty,
                                                                                                bl_alert_p=bl, bp_alert_p=bp,
                                                                                                remarks=remarks)
                        # deep copy is not required as object contain same info and are not
                        # modified
                        orders = [copy.deepcopy(order) for _ in range(nlegs)]

                    if rem_qty:
                        if action == 'Buy':
                            order = shared_classes.Combi_Primary_B_MKT_And_OCO_S_MKT_I_Order_NSE(tradingsymbol=tsym, quantity=rem_qty,
                                                                                                bl_alert_p=bl, bp_alert_p=bp,
                                                                                                remarks=remarks)
                        else:
                            order = shared_classes.Combi_Primary_S_MKT_And_OCO_B_MKT_I_Order_NSE(tradingsymbol=tsym, quantity=rem_qty,
                                                                                                bl_alert_p=bl, bp_alert_p=bp,
                                                                                                remarks=remarks)
                        orders.append(order)
            else:
                if use_gtt_oco:
                    pp = inst_info.profit_points
                    bp = utils.round_stock_prec(ltp + pp, base=ti)

                    sl_p = inst_info.stoploss_points
                    bl = utils.round_stock_prec(ltp - sl_p, base=ti)
                    logger.debug(f'ltp:{ltp} pp:{pp} bp:{bp} sl_p:{sl_p} bl:{bl}')
                else:
                    bp = bl = None

                if per_leg_qty:
                    order = shared_classes.Combi_Primary_B_MKT_And_OCO_S_MKT_I_Order_NFO(tradingsymbol=tsym, quantity=per_leg_qty,
                                                                                        bl_alert_p=bl, bp_alert_p=bp,
                                                                                        remarks=remarks)
                    orders = [copy.deepcopy(order) for _ in range(nlegs)]

                if rem_qty:
                    order = shared_classes.Combi_Primary_B_MKT_And_OCO_S_MKT_I_Order_NFO(tradingsymbol=tsym, quantity=rem_qty,
                                                                                        bl_alert_p=bl, bp_alert_p=bp,
                                                                                        remarks=remarks)
                    orders.append(order)

            if len(orders):
                for i, order in enumerate(orders):
                    try:
                        if isinstance(order, shared_classes.BO_B_MKT_Order) or isinstance(order, shared_classes.BO_S_MKT_Order):
                            remarks = f'TeZ_{i+1}_Qty_{order.quantity:.0f}_of_{qty:.0f}'
                        else:
                            remarks = f'TeZ_{i+1}_Qty_{order.primary_order_quantity:.0f}_of_{qty:.0f}'
                        # logger.info(remarks)
                        order.remarks = remarks
                        # logger.info(f'order: {i} -> {order}')
                    except Exception:
                        logger.error(traceback.format_exc())

                tsym_token = tsym + '_' + str(token)
                logger.debug (f'Record Symbol: {tsym_token}')
                if str(token) == '26000' or str(token) == '26009':
                    logger.error (f'Major issue: token belongs to Index {str(token)}')
                    return

                if trade_price is None:
                    resp_exception, resp_ok, os_tuple_list = self.tiu.place_and_confirm_tez_order(orders=orders, use_gtt_oco=use_gtt_oco)
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
                        self.pfmu.save_order_details(order_id, tsym_token, qty, order_time, status, oco_order)
                    logger.info(f'Total Qty taken : {total_qty}')
                    if total_qty:
                        self.pfmu.portfolio_add (ul_symbol=inst_info.ul_instrument, tsym_token=tsym_token, qty=total_qty)
                    self.pfmu.show()
                else:
                    with self.lock:
                        ul_token=self.diu.ul_token
                        key_name = self._add_order(ul_token=ul_token, ul_symbol=inst_info.ul_instrument, tsym_token=tsym_token, 
                                                   use_gtt_oco=use_gtt_oco, 
                                                   price_at_click=ul_ltp, 
                                                   wait_price=trade_price, order_list=orders)
                        cond_ds = {'condition_fn': self._price_condition, 
                                   'callback_function': self._order_placement_th, 
                                   'cb_id': key_name}
                        self.pmu.register_callback(token=ul_token, cond_ds=cond_ds)
                        self.wo_table_show()
                    
                        # self.pmu.simulate(trade_price)

                    logger.debug (f'Registered Call back with PMU {key_name}')
        return

