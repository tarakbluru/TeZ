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
    from datetime import datetime
    from threading import Lock
    from typing import NamedTuple

    import app_utils as utils
    import numpy as np

    from . import Diu, Tiu, Tiu_OrderStatus, shared_classes

except Exception as e:
    logger.debug(traceback.format_exc())
    logger.error(("Import Error " + str(e)))
    sys.exit(1)


class Ocpu_CreateConfig(NamedTuple):
    tiu: Tiu
    diu: Diu


class Ocpu_RetObject(NamedTuple):
    orders_list: list
    tsym_token: str
    ul_ltp: float


class OCPU(object):
    def __init__(self, ocpu_cc: Ocpu_CreateConfig):
        self.lock = Lock()
        self.tiu = ocpu_cc.tiu
        self.diu = ocpu_cc.diu

    def create_order(self, action: str, inst_info: shared_classes.InstrumentInfo, trade_price: float = None):
        def get_tsym_token(tiu: Tiu, diu: Diu, action: str, trade_price: float = None):
            sym = inst_info.symbol
            expiry_date = inst_info.expiry_date
            ce_offset = inst_info.ce_strike_offset
            pe_offset = inst_info.pe_strike_offset
            qty = inst_info.quantity
            exch = inst_info.exchange
            ul_ltp = diu.get_latest_tick()
            if trade_price is None:
                use_u_ltp = ul_ltp
            else:
                use_u_ltp = trade_price
            if exch == 'NFO':
                # find the nearest strike price
                strike_diff = inst_info.strike_diff
                strike1 = int(math.floor(use_u_ltp / strike_diff) * strike_diff)
                strike2 = int(math.ceil(use_u_ltp / strike_diff) * strike_diff)
                strike = strike1 if abs(use_u_ltp - strike1) < abs(use_u_ltp - strike2) else strike2
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
                logger.debug(f'ul_ltp:{ul_ltp} strike:{strike}')
            else:
                ...

            logger.debug(f'exch: {exch} searchtext: {searchtext}')
            token, tsym = tiu.search_scrip(exchange=exch, symbol=searchtext)

            if not token and not tsym:
                logger.error('Major error: Check Expiry date')
                raise RuntimeError

            ltp, ti, ls = tiu.fetch_ltp(exch, token)

            if ls is None or ti is None or ltp is None:
                ltp, ti, ls = diu.fetch_ltp(exch, token)
                if ls is None or ti is None or ltp is None:
                    logger.error(f'Major Issue..Exit and Take manual control {token}')
                    raise RuntimeError

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

        ul_ltp = tsym_token = orders = None
        try:
            strike, sym, tsym, token, qty, ul_ltp, ltp, ti, frz_qty, ls = get_tsym_token(self.tiu, self.diu, action=action, trade_price=trade_price)
        except RuntimeError:
            raise
        except Exception as e:
            logger.error(f'Exception occured {e}')
            raise
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
                    nearest_lcm_qty = find_nearest_lcm(ls, (frz_qty - 1), qty)

                logger.debug(f"qty:{qty} Nearest LCM qty:{nearest_lcm_qty}")

                res_qty1 = qty - nearest_lcm_qty
                min_legs = (nearest_lcm_qty // (frz_qty - 1))  # Lower boundary
                max_legs = (nearest_lcm_qty // ls)           # Upper boundary

                logger.debug(f"res_qty1: {res_qty1} min_legs: {min_legs} max_legs:{max_legs}")

                # Below compact code is same as :
                # if given_nlegs < min_legs:
                #     nlegs = min_legs
                # elif given_nlegs > max_legs:
                #     nlegs = max_legs
                # else:
                #     nlegs = given_nlegs

                nlegs = max(min(given_nlegs, max_legs), min_legs)
                per_leg_qty = ((nearest_lcm_qty / nlegs) // ls) * ls
                logger.debug(f'n_given_legs: {given_nlegs}, nlegs: {nlegs} per_leg_qty:{per_leg_qty}')

                res_qty2 = nearest_lcm_qty - (per_leg_qty * nlegs)
                logger.debug(f'Verification: qty: {qty} final_qty: {((per_leg_qty*nlegs) + res_qty1 + res_qty2)}: {qty == ((per_leg_qty*nlegs) + res_qty1 + res_qty2)}')

                rem_qty = res_qty1 + res_qty2
                logger.debug(f'per_leg_qty: {per_leg_qty}, res_qty1:{res_qty1} res_qty2:{res_qty2}')
            else:
                logger.info(f'qty: {qty} given_nlegs: {given_nlegs} is not allowed')
                return

            logger.debug(f'sym:{sym} tsym:{tsym} ltp: {ltp}')

            use_gtt_oco = True if inst_info.order_prod_type == 'O' else False
            remarks = None

            orders = []
            if (sym == 'NIFTYBEES' or sym == 'BANKBEES') and ltp is not None:
                if inst_info.order_prod_type == 'I':
                    if per_leg_qty:
                        if action == 'Buy':
                            order = shared_classes.I_B_MKT_Order(tradingsymbol=tsym, quantity=per_leg_qty)
                        else:
                            order = shared_classes.I_S_MKT_Order(tradingsymbol=tsym, quantity=per_leg_qty)
                        orders = [copy.deepcopy(order) for _ in range(nlegs)]
                    if rem_qty:
                        if action == 'Buy':
                            order = shared_classes.I_B_MKT_Order(tradingsymbol=tsym, quantity=rem_qty)
                        else:
                            order = shared_classes.I_S_MKT_Order(tradingsymbol=tsym, quantity=rem_qty)
                        orders.append(order)

                elif inst_info.order_prod_type == 'B':  # Bracket Order
                    pp = inst_info.profit_per / 100.0
                    sl_p = inst_info.stoploss_per / 100.0
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

                elif inst_info.order_prod_type == 'O':  # OCO - Order
                    pp = inst_info.profit_per / 100.0
                    sl_p = inst_info.stoploss_per / 100.0

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
                    ...

                if not use_gtt_oco:
                    ...
                    # bp = utils.round_stock_prec(ltp * pp, base=ti)
                    # bl = utils.round_stock_prec(ltp * sl_p, base=ti)
                    # logger.debug(f'ltp:{ltp} pp:{pp} bp:{bp} sl_p:{sl_p} bl:{bl}')

                    # if per_leg_qty:
                    #     if action == 'Buy':
                    #         order = shared_classes.BO_B_MKT_Order(tradingsymbol=tsym,
                    #                                             quantity=per_leg_qty, book_loss_price=bl,
                    #                                             book_profit_price=bp, bo_remarks=remarks)
                    #     else:
                    #         order = shared_classes.BO_S_MKT_Order(tradingsymbol=tsym,
                    #                                             quantity=per_leg_qty, book_loss_price=bl,
                    #                                             book_profit_price=bp, bo_remarks=remarks)
                    #     orders = [copy.deepcopy(order) for _ in range(nlegs)]

                    # if rem_qty:
                    #     if action == 'Buy':
                    #         order = shared_classes.BO_B_MKT_Order(tradingsymbol=tsym,
                    #                                             quantity=rem_qty, book_loss_price=bl,
                    #                                             book_profit_price=bp, bo_remarks=remarks)
                    #     else:
                    #         order = shared_classes.BO_S_MKT_Order(tradingsymbol=tsym,
                    #                                             quantity=rem_qty, book_loss_price=bl,
                    #                                             book_profit_price=bp, bo_remarks=remarks)
                    #     orders.append(order)
                else:
                    ...
                    # bp1 = utils.round_stock_prec(ltp + pp * ltp, base=ti)
                    # bp2 = utils.round_stock_prec(ltp - pp * ltp, base=ti)
                    # bp = bp1 if action == 'Buy' else bp2

                    # bl1 = utils.round_stock_prec(ltp - sl_p * ltp, base=ti)
                    # bl2 = utils.round_stock_prec(ltp + sl_p * ltp, base=ti)

                    # bl = bl1 if action == 'Buy' else bl2
                    # logger.debug(f'ltp:{ltp} pp:{pp} bp:{bp} sl_p:{sl_p} bl:{bl}')

                    # if per_leg_qty:
                    #     if action == 'Buy':
                    #         order = shared_classes.Combi_Primary_B_MKT_And_OCO_S_MKT_I_Order_NSE(tradingsymbol=tsym, quantity=per_leg_qty,
                    #                                                                             bl_alert_p=bl, bp_alert_p=bp,
                    #                                                                             remarks=remarks)
                    #     else:
                    #         order = shared_classes.Combi_Primary_S_MKT_And_OCO_B_MKT_I_Order_NSE(tradingsymbol=tsym, quantity=per_leg_qty,
                    #                                                                             bl_alert_p=bl, bp_alert_p=bp,
                    #                                                                             remarks=remarks)
                    #     # deep copy is not required as object contain same info and are not
                    #     # modified
                    #     orders = [copy.deepcopy(order) for _ in range(nlegs)]

                    # if rem_qty:
                    #     if action == 'Buy':
                    #         order = shared_classes.Combi_Primary_B_MKT_And_OCO_S_MKT_I_Order_NSE(tradingsymbol=tsym, quantity=rem_qty,
                    #                                                                             bl_alert_p=bl, bp_alert_p=bp,
                    #                                                                             remarks=remarks)
                    #     else:
                    #         order = shared_classes.Combi_Primary_S_MKT_And_OCO_B_MKT_I_Order_NSE(tradingsymbol=tsym, quantity=rem_qty,
                    #                                                                             bl_alert_p=bl, bp_alert_p=bp,
                    #                                                                             remarks=remarks)
                    #     orders.append(order)
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
                        if isinstance(order, shared_classes.BO_B_MKT_Order) or isinstance(order, shared_classes.BO_S_MKT_Order) \
                                or isinstance(order, shared_classes.I_B_MKT_Order) or isinstance(order, shared_classes.I_S_MKT_Order):
                            remarks = f'TeZ_{i+1}_Qty_{order.quantity:.0f}_of_{qty:.0f}'
                        else:
                            remarks = f'TeZ_{i+1}_Qty_{order.primary_order_quantity:.0f}_of_{qty:.0f}'
                        # logger.info(remarks)
                        order.remarks = remarks
                        # logger.info(f'order: {i} -> {order}')
                    except Exception:
                        logger.error(traceback.format_exc())
                        raise

                tsym_token = tsym + '_' + str(token)
                logger.debug(f'Record Symbol: {tsym_token}')
                if str(token) == '26000' or str(token) == '26009':
                    logger.error(f'Major issue: token belongs to Index {str(token)}')
                    tsym_token = None

        r = Ocpu_RetObject(orders_list=orders, tsym_token=tsym_token, ul_ltp=ul_ltp)
        return r
