"""
File: shared_classes.py
Author: [Tarakeshwar NC]
Date: January 15, 2024
Description: This script provides all shared classes in the system.
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

from app_utils import app_logger

logger = app_logger.get_logger(__name__)

try:
    import datetime
    import json
    import re
    from dataclasses import dataclass, field
    from enum import Enum, auto
    from threading import Event
    from typing import NamedTuple, Optional, Union

    from app_utils import ExtQueue, ExtSimpleQueue

except Exception as e:
    logger.debug(traceback.format_exc())
    logger.error(("Import Error " + str(e)))
    sys.exit(1)

class Status(Enum):
    FAILURE = 0
    SUCCESS = auto()

@dataclass(slots=True)
class TickData (object):
    tk: int = 0
    o: float = 0.0  # as given by the PF
    h: float = 0.0
    l: float = 0.0
    c: float = 0.0
    v: int = 0
    oi: int = 0
    ft: str = ""
    rx_ts:str = ""
    ap: float = 0.0
    poi: int =0

    def __str__(self):
        return (f"ft(str): {self.ft} rx_ts(str): {self.rx_ts} c: {self.c:.2f}  h: {self.h:.2f}  l: {self.l:.2f} tk(str): {self.tk} o: {self.o:.2f} v: {self.v} oi: {self.oi}")


class Ctrl(Enum):
    OFF = 0
    ON = 1


class UI_State(Enum):
    DISABLE = 0
    ENABLE = 1



@dataclass
class Order:
    seq_num: int
    buy_or_sell: str
    product_type: str  # C / M / I / B / H
    tradingsymbol: str
    quantity: int
    price_type: str  # LMT / MKT / SL-LMT / SL-MKT / DS / 2L / 3L
    price: float
    discloseqty: Optional[int] = None
    trigger_price: Optional[float] = None
    book_loss_price: Optional[float] = None
    book_profit_price: Optional[float] = None
    trail_price: Optional[float] = None
    parent_order_id: Optional[str] = None
    _remarks: Optional[str] = None
    order_id: Optional[str] = None
    al_id: Optional[str] = None
    exchange: str = 'NSE'
    retention: str = 'DAY'

    # Setter for the 'remarks' property
    @property
    def remarks(self):
        logger.debug(self._remarks)
        return self._remarks

    @remarks.setter
    def remarks(self, value):
        if not isinstance(value, str):
            raise ValueError("Name must be a string")
        self._remarks = re.sub("[-,&]+", "_", value)

    def __post_init__(self):
        if self._remarks and isinstance(self._remarks, str):
            self._remarks = re.sub("[-,&]+", "_", self._remarks)

    def __str__(self):
        data = {'seq_num': self.seq_num,
                'buy_or_sell': self.buy_or_sell,
                'product_type': self.product_type,
                'tradingsymbol': self.tradingsymbol,
                'quantity': f'{self.quantity:.0f}',
                'price_type': self.price_type,
                'price': self.price,
                'disclose_qty': self.discloseqty,
                'trigger_price': self.trigger_price,
                'book_loss_price': self.book_loss_price,
                'book_profit_price': self.book_profit_price,
                'trail_price': self.trail_price,
                'parent_order': self.parent_order_id,
                'remarks': self._remarks,
                'order_id': self.order_id,
                'al_id': self.al_id,
                'exchange': self.exchange,
                'retention': self.retention
                }
        return (json.dumps(data, indent=2))


@dataclass
class OCO_BaseOrder ():
    oco_seq_num: int
    oco_buy_or_sell: str
    oco_product_type: str  # C / M / I / B / H
    oco_quantity: int

    book_loss_alert_price: float
    book_loss_price: Optional[float]
    book_loss_price_type: str

    book_profit_alert_price: float
    book_profit_price: Optional[float]
    book_profit_price_type: str

    _oco_remarks: Optional[str] = None
    oco_retention: str = 'DAY'

    def __str__(self):
        data = {'oco_seq_num': self.oco_seq_num,
                'oco_buy_or_sell': self.oco_buy_or_sell,
                'oco_product_type': self.oco_product_type,
                'oco_quantity': f'{self.oco_quantity:.0f}',
                'book_loss_alert_price': f'{self.book_loss_alert_price:.2f}',
                'book_loss_price': f'{self.book_loss_price:.2f}',
                'book_loss_price_type': f'{self.book_loss_price_type}',
                'book_profit_alert_price': f'{self.book_profit_alert_price:.2f}',
                'book_profit_price': f'{self.book_profit_price:.2f}',
                'book_profit_price_type': f'{self.book_profit_price_type}',
                'oco_remarks': self._oco_remarks,
                'oco_retention': self.oco_retention,
                }
        return (json.dumps(data, indent=2))

    def __post_init__(self):
        if self._oco_remarks:
            self._oco_remarks = re.sub("[-,&]+", "_", self._oco_remarks)


@dataclass
class I_B_MKT_Order(Order):
    # Initialize default values using default_factory to avoid sharing mutable defaults
    seq_num: int = field(default=1, init=False)
    buy_or_sell: str = field(default='B', init=False)
    product_type: str = field(default='I', init=False)
    price_type: str = field(default='MKT', init=False)
    price: float = field(default=0.0, init=False)


@dataclass
class I_S_MKT_Order(Order):
    # Initialize default values using default_factory to avoid sharing mutable defaults
    seq_num: int = field(default=1, init=False)
    buy_or_sell: str = field(default='S', init=False)
    product_type: str = field(default='I', init=False)
    price_type: str = field(default='MKT', init=False)
    price: float = field(default=0.0, init=False)


@dataclass
class BO_B_SL_LMT_Order(Order):
    # Define only attributes that differ or need specific modification
    trigger_price: float
    book_loss_price: float
    book_profit_price: float

    # Initialize default values using default_factory to avoid sharing mutable defaults
    buy_or_sell: str = field(default='B', init=False)
    product_type: str = field(default='B', init=False)
    price_type: str = field(default='SL-LMT', init=False)

    def __post_init__(self):
        # Calculate discloseqty as 12% of the quantity
        if not self.discloseqty:
            self.discloseqty = int(self.quantity * 0.12)
        if self.trigger_price == self.price:
            self.price = self.trigger_price + 0.05


@dataclass
class BO_B_LMT_Order(Order):
    # Define only attributes that differ or need specific modification
    book_loss_price: float
    book_profit_price: float

    # Initialize default values using default_factory to avoid sharing mutable defaults
    buy_or_sell: str = field(default='B', init=False)
    product_type: str = field(default='B', init=False)
    price_type: str = field(default='LMT', init=False)

    def __post_init__(self):
        # Calculate discloseqty as 12% of the quantity
        if not self.discloseqty:
            self.discloseqty = int(self.quantity * 0.12)


@dataclass
class BO_B_MKT_Order(Order):
    # Define only attributes that differ or need specific modification
    book_loss_price: float
    book_profit_price: float

    # Initialize default values using default_factory to avoid sharing mutable defaults
    seq_num: int = field(default=1, init=False)
    buy_or_sell: str = field(default='B', init=False)
    product_type: str = field(default='B', init=False)
    price_type: str = field(default='MKT', init=False)
    price: float = field(default=0.0, init=False)
    bo_remarks: str = field(default='', init=True)

    def __post_init__(self):
        if self.bo_remarks and isinstance(self.bo_remarks, str):
            self._remarks = re.sub("[-,&]+", "_", self.bo_remarks)


@dataclass
class BO_S_MKT_Order(Order):
    # Define only attributes that differ or need specific modification
    book_loss_price: float
    book_profit_price: float

    # Initialize default values using default_factory to avoid sharing mutable defaults
    seq_num: int = field(default=1, init=False)
    buy_or_sell: str = field(default='S', init=False)
    product_type: str = field(default='B', init=False)
    price_type: str = field(default='MKT', init=False)
    price: float = field(default=0.0, init=False)
    bo_remarks: str = field(default='', init=True)

    def __post_init__(self):
        if self.bo_remarks and isinstance(self.bo_remarks, str):
            self._remarks = re.sub("[-,&]+", "_", self.bo_remarks)


@dataclass
class OCO_FOLLOW_UP_MKT_MIS_I_Order_V2(OCO_BaseOrder):
    book_loss_alert_price: float
    book_profit_alert_price: float

    book_loss_price = float(0.0)
    book_profit_price = float(0.0)

    oco_seq_num: int = field(default=2, init=False)
    buy_or_sell: str = field(default='S', init=False)
    oco_product_type: str = field(default='I', init=False)
    oco_price_type: str = field(default='MKT', init=False)
    price: float = field(default=0.0, init=False)


@dataclass
class OCO_FOLLOW_UP_MKT_I_Order(Order):
    # Define only attributes that differ or need specific modification
    book_loss_alert_price: float = 0.0
    book_profit_alert_price: float = 0.0

    # Initialize default values using default_factory to avoid sharing mutable defaults
    seq_num: int = field(default=2, init=False)
    product_type: str = field(default='I', init=False)
    price_type: str = field(default='MKT', init=False)
    price: float = field(default=0.0, init=False)
    book_loss_price = float(0.0)
    book_profit_price = float(0.0)

    def __str__(self):
        data = {'book_loss_alert_price': self.book_loss_alert_price,
                'book_profit_alert_price': self.book_profit_alert_price,
                }
        return (f'{super().__str__()}  {json.dumps(data, indent=2)}')


class Combi_Primary_B_MKT_And_OCO_S_MKT_I_Order_NSE:
    def __init__(self, tradingsymbol, quantity, bl_alert_p: float = None, bp_alert_p: float = None, remarks: str = None):
        if remarks:
            remarks = re.sub("[-,&]+", "_", remarks)
        self.primary_order = I_B_MKT_Order(tradingsymbol=tradingsymbol, quantity=quantity, _remarks=remarks)
        if bl_alert_p and bp_alert_p:
            logger.debug(f'bl_alert_p: {bl_alert_p} bp_alert_p: {bp_alert_p}')
            self.follow_up_order = OCO_FOLLOW_UP_MKT_I_Order(buy_or_sell='S',
                                                             tradingsymbol=tradingsymbol,
                                                             quantity=quantity,
                                                             book_loss_alert_price=bl_alert_p,
                                                             book_profit_alert_price=bp_alert_p, _remarks=remarks)
        else:
            self.follow_up_order = None

    # Setter for the 'prime_quantity' property
    @property
    def primary_order_quantity(self):
        return self.primary_order.quantity

    @primary_order_quantity.setter
    def primary_order_quantity(self, value):
        if not isinstance(value, int):
            raise ValueError("Quantity should be integer")
        logger.debug(value)
        self.primary_order.quantity = value

    # Setter for the 'prime_quantity' property
    @property
    def order_id(self):
        return self.primary_order.order_id

    @order_id.setter
    def order_id(self, value):
        if not isinstance(value, str):
            logger.debug(traceback.print_exc())
            raise ValueError("value should be a string")
        self.primary_order.order_id = value

    # Setter for the 'al_id' property
    @property
    def al_id(self):
        return self.primary_order.al_id

    @al_id.setter
    def al_id(self, value):
        if not isinstance(value, str):
            raise ValueError("value should be a string")
        self.primary_order.al_id = value

    # Setter for the 'remarks' property
    @property
    def remarks(self):
        logger.debug(self.primary_order.remarks)
        return self.primary_order.remarks

    @remarks.setter
    def remarks(self, value):
        if not isinstance(value, str):
            raise ValueError("Name must be a string")
        remarks = re.sub("[-,&]+", "_", value)
        logger.debug(remarks)
        self.primary_order.remarks = remarks

    def __str__(self):
        return (f'primary order: {str(self.primary_order)} follow_up_order: {str(self.follow_up_order)}')


class Combi_Primary_S_MKT_And_OCO_B_MKT_I_Order_NSE:
    def __init__(self, tradingsymbol, quantity, bl_alert_p: float = None, bp_alert_p: float = None, remarks: str = None):
        if remarks:
            remarks = re.sub("[-,&]+", "_", remarks)
        self.primary_order = I_S_MKT_Order(tradingsymbol=tradingsymbol, quantity=quantity, _remarks=remarks)
        if bl_alert_p and bp_alert_p:
            logger.debug(f'bl_alert_p: {bl_alert_p} bp_alert_p: {bp_alert_p}')
            self.follow_up_order = OCO_FOLLOW_UP_MKT_I_Order(buy_or_sell='B',
                                                             tradingsymbol=tradingsymbol,
                                                             quantity=quantity,
                                                             book_loss_alert_price=bl_alert_p,
                                                             book_profit_alert_price=bp_alert_p, _remarks=remarks)
        else:
            self.follow_up_order = None

    # Setter for the 'prime_quantity' property
    @property
    def primary_order_quantity(self):
        return self.primary_order.quantity

    @primary_order_quantity.setter
    def primary_order_quantity(self, value):
        if not isinstance(value, int):
            raise ValueError("Quantity should be integer")
        logger.debug(value)
        self.primary_order.quantity = value

    # Setter for the 'prime_quantity' property
    @property
    def order_id(self):
        return self.primary_order.order_id

    @order_id.setter
    def order_id(self, value):
        if not isinstance(value, str):
            logger.debug(traceback.print_exc())
            raise ValueError("value should be a string")
        self.primary_order.order_id = value

    # Setter for the 'al_id' property
    @property
    def al_id(self):
        return self.primary_order.al_id

    @al_id.setter
    def al_id(self, value):
        if not isinstance(value, str):
            raise ValueError("value should be a string")
        self.primary_order.al_id = value

    # Setter for the 'remarks' property
    @property
    def remarks(self):
        logger.debug(self.primary_order.remarks)
        return self.primary_order.remarks

    @remarks.setter
    def remarks(self, value):
        if not isinstance(value, str):
            raise ValueError("Name must be a string")
        remarks = re.sub("[-,&]+", "_", value)
        logger.debug(remarks)
        self.primary_order.remarks = remarks

    def __str__(self):
        return (f'primary order: {str(self.primary_order)} follow_up_order: {str(self.follow_up_order)}')


class Combi_Primary_B_MKT_And_OCO_S_MKT_I_Order_NFO (Combi_Primary_B_MKT_And_OCO_S_MKT_I_Order_NSE):
    def __init__(self, tradingsymbol, quantity, bl_alert_p: float = None, bp_alert_p: float = None, remarks: str = None):
        super().__init__(tradingsymbol, quantity, bl_alert_p, bp_alert_p, remarks)
        self.__post_init__()

    def __post_init__(self):
        # Calculate discloseqty as 12% of the quantity
        self.primary_order.exchange = 'NFO'
        if self.follow_up_order:
            self.follow_up_order.exchange = 'NFO'


@dataclass
class SimpleDataPort:
    """Generic port """
    data_q: ExtSimpleQueue
    evt: Event
    id: int = field(init=False, default=0)

    def __post_init__(self):
        type(self).id += 1

    def send_data(self, data):
        self.data_q.put(data)
        self.evt.set()

    def __str__(self):
        return f"port_id: {self.id}"


class Generic_Port(NamedTuple):
    """Generic port """
    data_q: ExtSimpleQueue
    evt: Event
    id: int     # port ID
    cmd_q: ExtQueue = None

    def send_data(self, data):
        self.data_q.put(data)
        self.evt.set()

    def send_cmd(self, cmd):
        self.cmd_q.put(cmd)
        self.evt.set()
        self.cmd_q.join_with_timeout(1.0)

    def port_flush_data(self):
        self.data_q.flush()

    def port_flush_cmd(self):
        self.cmd_q.flush()

    def port_flush(self):
        self.data_q.flush()
        self.cmd_q.flush()
        self.evt.clear()

    def __str__(self):
        return f'port_id: {self.id}'


class Component_Type (Enum):
    PASSIVE = 0
    ACTIVE = 1


class LiveFeedStatus (Enum):
    OFF = 0
    ON = 1


class Ctrl(Enum):
    OFF = 0
    ON = 1


@dataclass
class Market_Timing(object):
    mo: str = "09:15"
    mc: str = "15:30"

# For new broker create a new class here.


class BaseInst(NamedTuple):
    exch: str
    symbol: str
    index: bool = False
    expiry: str | None = None
    lot_size: int | None = None
    freeze_qty: int | None = None


class FVInstrument (NamedTuple):
    exch: str
    token: str
    tsym: str

    def prefixed_ws_token(self):
        return f'{self.exch}|{self.token}'


class SysInst (NamedTuple):
    base_inst: BaseInst
    fv_inst: FVInstrument | None = None

    def __str__(self):
        return f' {self.base_inst}  FV: {self.fv_inst}'


@dataclass
class OrderStatus():
    avg_price: float = 0.0
    sym: Optional[str] = None
    order_id: Optional[str] = None
    fillshares: int = 0
    unfilledsize: int = 0
    fill_timestamp: Optional[str] = None
    trantype: Optional[str] = None
    rejReason: Optional[str] = None
    emsg: Optional[str] = None
    remarks: Optional[str] = None
    al_id: Optional[str] = None

    def __str__(self):
        return f'''Sym: {self.sym} fillshares: {self.fillshares} unfilledsize: {self.unfilledsize} trantype:{self.trantype}
                avg_price: {self.avg_price} rejReason:{self.rejReason} remarks:{self.remarks} order_id: {self.order_id} al_id: {self.al_id}'''


InstrumentInfo = NamedTuple('InstrumentInfo', [('symbol', str),
                                               ('ul_index', str),
                                               ('exchange', str),
                                               ('expiry_date', str),
                                               ('ce_strike', Union[int, None]),
                                               ('pe_strike', Union[int, None]),
                                               ('strike_diff', int),
                                               ('ce_strike_offset', str),
                                               ('pe_strike_offset', str),
                                               ('profit_per', float),
                                               ('stoploss_per', float),
                                               ('profit_points', float),
                                               ('stoploss_points', float),
                                               ('order_prod_type', str),
                                               ('use_gtt_oco', Union[str, bool]),
                                               ('quantity', int),
                                               ("n_legs", int),
                                               ])

@dataclass
class AutoTrailerData():
    sl: float
    target: float
    mvto_cost: float
    trail_after: float
    trail_by: float
    ui_reset:bool = False
    ts: datetime.datetime = field(default_factory=datetime.datetime.now)


@dataclass
class AutoTrailerEvent():
    pnl: float
    sl_hit: bool = False
    target_hit: bool = False
    mvto_cost_hit: bool = False
    mvto_cost_ui: UI_State = UI_State.ENABLE
    trail_sl_ui:UI_State = UI_State.ENABLE
    trail_after_hit: bool = False
    trail_by_hit: bool = False
    sq_off_done:bool = False
    ts: datetime.datetime = field(default_factory=datetime.datetime.now)
