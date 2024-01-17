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
__date__ = "2024/1/14"
__deprecated__ = False
__email__ = "tarakesh.nc_at_google_mail_dot_com"
__license__ = "MIT"
__maintainer__ = "Tarak"
__status__ = "Development"

__version__ = "0.1"

import sys
import traceback

from app_utils import app_logger

logger = app_logger.get_logger(__name__)

try:
    import json
    from dataclasses import dataclass, field
    from enum import Enum
    from threading import Event
    from typing import NamedTuple, Optional

    from app_utils import ExtQueue, ExtSimpleQueue

except Exception as e:
    logger.debug(traceback.format_exc())
    logger.error(("Import Error " + str(e)))
    sys.exit(1)


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

    def __str__(self):
        return (f"ft: {self.ft} c: {self.c:.2f}  h: {self.h:.2f}  l: {self.l:.2f} tk: {self.tk} o: {self.o:.2f} v: {self.v} oi: {self.oi}")


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
    bookloss_price: Optional[float] = None
    bookprofit_price: Optional[float] = None
    trail_price: Optional[float] = None
    parent_order_id: Optional[str] = None
    remarks: Optional[str] = None
    order_id: Optional[str] = None
    exchange: str = 'NSE'
    retention: str = 'DAY'

    def __str__(self):
        data = {'seq_num': self.seq_num,
                'buy_or_sell': self.buy_or_sell,
                'product_type': self.product_type,
                'tradingsymbol': self.tradingsymbol,
                'quantity': self.quantity,
                'price_type': self.price_type,
                'price': self.price,
                'disclose_qty': self.discloseqty,
                'trigger_price': self.trigger_price,
                'bookloss_price': self.bookloss_price,
                'bookprofit_price': self.bookprofit_price,
                'trail_price': self.trail_price,
                'parent_order': self.parent_order_id,
                'remarks': self.remarks,
                'order_id': self.order_id,
                'exchange': self.exchange,
                'retention': self.retention
                }
        return (json.dumps(data, indent=2))


@dataclass
class I_B_MKT_Order(Order):
    # Initialize default values using default_factory to avoid sharing mutable defaults
    seq_num: int = field(default=1, init=False)
    buy_or_sell: str = field(default='B', init=False)
    product_type: str = field(default='I',  init=False)
    price_type: str = field(default='MKT',  init=False)
    price: float = field(default=0.0, init=False)


@dataclass
class I_S_MKT_Order(Order):
    # Initialize default values using default_factory to avoid sharing mutable defaults
    seq_num: int = field(default=1, init=False)
    buy_or_sell: str = field(default='S', init=False)
    product_type: str = field(default='I',  init=False)
    price: float = field(default=0.0, init=False)


@dataclass
class BO_B_SL_LMT_Order(Order):
    # Define only attributes that differ or need specific modification
    trigger_price: float
    bookloss_price: float
    bookprofit_price: float

    # Initialize default values using default_factory to avoid sharing mutable defaults
    buy_or_sell: str = field(default='B', init=False)
    product_type: str = field(default='B',  init=False)
    price_type: str = field(default='SL-LMT',  init=False)

    def __post_init__(self):
        # Calculate discloseqty as 12% of the quantity
        if not self.discloseqty:
            self.discloseqty = int(self.quantity * 0.12)
        if self.trigger_price == self.price:
            self.price = self.trigger_price + 0.05


@dataclass
class BO_B_LMT_Order(Order):
    # Define only attributes that differ or need specific modification
    bookloss_price: float
    bookprofit_price: float

    # Initialize default values using default_factory to avoid sharing mutable defaults
    buy_or_sell: str = field(default='B', init=False)
    product_type: str = field(default='B',  init=False)
    price_type: str = field(default='LMT',  init=False)

    def __post_init__(self):
        # Calculate discloseqty as 12% of the quantity
        if not self.discloseqty:
            self.discloseqty = int(self.quantity * 0.12)


@dataclass
class BO_B_MKT_Order(Order):
    # Define only attributes that differ or need specific modification
    bookloss_price: float
    bookprofit_price: float

    # Initialize default values using default_factory to avoid sharing mutable defaults
    seq_num: int = field(default=1, init=False)
    buy_or_sell: str = field(default='B', init=False)
    product_type: str = field(default='B',  init=False)
    price_type: str = field(default='MKT',  init=False)
    price: float = field(default=0.0, init=False)


@dataclass
class BO_S_MKT_Order(Order):
    # Define only attributes that differ or need specific modification
    bookloss_price: float
    bookprofit_price: float

    # Initialize default values using default_factory to avoid sharing mutable defaults
    seq_num: int = field(default=1, init=False)
    buy_or_sell: str = field(default='S', init=False)
    product_type: str = field(default='B',  init=False)
    price_type: str = field(default='MKT',  init=False)
    price: float = field(default=0.0, init=False)


@dataclass
class SimpleDataPort(object):
    """Generic port """
    data_q: ExtSimpleQueue
    evt: Event
    id: int = 0

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
    sym: str = ''
    order_id: str = '-1'
    fillshares: float = 0.0
    unfilledsize: float = 0.0
    fill_timestamp: str = ''
    trantype: str = ''
    rejReason: str = ''
    emsg: str = ''
    remarks: str = ''

    def __str__(self):
        return f'Sym: {self.sym} fillshares: {self.fillshares} unfilledsize: {self.unfilledsize} trantype:{self.trantype} rejReason:{self.rejReason} remarks:{self.remarks}'
