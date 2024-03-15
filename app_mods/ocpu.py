"""
File: shared_classes.py
Author: [Tarakeshwar NC]
Date: January 15, 2024
Description: This script provides all shared classes in the system.
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
    from datetime import datetime
    from typing import NamedTuple
    import numpy as np
    import app_utils as utils

    from . import BookKeeperUnit, Diu, Tiu, Tiu_OrderStatus, shared_classes

except Exception as e:
    logger.debug(traceback.format_exc())
    logger.error(("Import Error " + str(e)))
    sys.exit(1)


class Ocpu_CreateConfig(NamedTuple):
    tiu: Tiu
    bku: BookKeeperUnit
    diu: Diu


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
                                                       ('use_gtt_oco', str),
                                                       ('qty', int),
                                                       ("n_legs", int),
                                                       ])


class OCPU(object):
    def __init__(self, ocpu_cc: Ocpu_CreateConfig):
        self.tiu = ocpu_cc.tiu
        self.bku = ocpu_cc.bku
        self.diu = ocpu_cc.diu

    def crete_and_place_order(self, action: str, inst_info: OcpuInstrumentInfo):
        def get_tsym_token(tiu: Tiu, diu: Diu, action: str):
            sym = inst_info.symbol
            expiry_date = inst_info.expiry_date
            ce_offset = inst_info.ce_strike_offset
            pe_offset = inst_info.pe_strike_offset
            qty = inst_info.qty
            exch = inst_info.exchange
            ltp = diu.get_latest_tick()
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

            logger.info(f'exch: {exch} searchtext: {searchtext}')
            token, tsym = tiu.search_scrip(exchange=exch, symbol=searchtext)
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

            logger.info(f'''strike: {strike}, sym: {sym}, tsym: {tsym}, token: {token},
                        qty:{qty}, ltp: {ltp}, ti:{ti} ls:{ls} frz_qty: {frz_qty} lot-size: {ls}''')

            return strike, sym, tsym, token, qty, ltp, ti, frz_qty, ls

        strike, sym, tsym, token, qty, ltp, ti, frz_qty, ls = get_tsym_token(self.tiu, self.diu, action=action)
        oco_order = np.NaN
        os = shared_classes.OrderStatus()
        status = Tiu_OrderStatus.HARD_FAILURE

        given_nlegs = inst_info.n_legs

        if qty and given_nlegs:
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
            logger.debug(f"res_qty1: {res_qty1}")

            min_legs = (nearest_lcm_qty//(frz_qty-1))
            logger.debug(f"min_legs: {min_legs}")
            max_legs = (nearest_lcm_qty//ls)
            logger.debug(f"max_legs:{max_legs}")

            if given_nlegs < min_legs:
                nlegs = min_legs
            elif given_nlegs > max_legs:
                nlegs = max_legs
            else:
                nlegs = given_nlegs

            logger.debug (f'n_given_legs: {given_nlegs}, nlegs: {nlegs}')
            per_leg_qty = ((nearest_lcm_qty/nlegs)//ls)*ls
            logger.debug (f'per_leg_qty:{per_leg_qty}')

            res_qty2 = nearest_lcm_qty - (per_leg_qty*nlegs)

            logger.debug(f'Verification: qty: {qty} final_qty: {((per_leg_qty*nlegs) + res_qty1 + res_qty2)}: {qty == ((per_leg_qty*nlegs) + res_qty1 + res_qty2)}')

            rem_qty = res_qty1 + res_qty2
            logger.debug (f'per_leg_qty: {per_leg_qty}, res_qty1:{res_qty1} res_qty2:{res_qty2}')
        else:
            logger.info(f'qty: {qty} given_nlegs: {given_nlegs} is not allowed')
            return

        logger.info(f'sym:{sym} tsym:{tsym} ltp: {ltp}')
        use_gtt_oco = True if inst_info.use_gtt_oco == 'YES' else False
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

            resp_exception, resp_ok, os_tuple_list = self.tiu.place_and_confirm_tez_order(orders=orders, use_gtt_oco=use_gtt_oco)
            if resp_exception:
                logger.info('Exception had occured while placing order: ')
            if resp_ok:
                logger.debug(f'respok: {resp_ok}')

        symbol = tsym + '_' + str(token)

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
            self.bku.save_order(order_id, symbol, qty, order_time, status, oco_order)

        logger.info(f'Total Qty taken : {total_qty}')
        self.bku.show()

        return
