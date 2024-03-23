"""
File: pmu.py
Author: [Tarakeshwar NC]
Date: March 15, 2024
Description: This script provides price monitoring functionality.
"""
# Copyright (c) [2024] [Tarakeshwar N.C]
# This file is part of the Tiny_TeZ project.
# It is subject to the terms and conditions of the MIT License.
# See the file LICENSE in the top-level directory of this distribution
# for the full text of the license.

__author__ = "Tarakeshwar N.C"
__copyright__ = "2024"
__date__ = "2024/3/15"
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
    import time
    from collections import defaultdict
    from datetime import datetime
    from enum import Enum
    from typing import NamedTuple

    from .shared_classes import (Component_Type, LiveFeedStatus,
                                 SimpleDataPort, TickData)
except Exception as e:
    logger.debug(traceback.format_exc())
    logger.error(("Import Error " + str(e)))
    sys.exit(1)

class PMU_cc(NamedTuple):
    inp_dataPort: SimpleDataPort

class PMU_State(Enum):
    NOT_DEFINED=0
    CREATED=1
    READY=2
    RUNNING=3
    STOPPED=4
    ERROR=5


class PriceMonitoringUnit:
    name = "PMU"
    __count = 0
    __componentType = Component_Type.ACTIVE 
    DATAFEED_TIMEOUT:float = 20.0
    SYS_MONITOR_MAX_COUNT:int = 15    

    def __init__(self, pmu_cc: PMU_cc):
        logger.debug ("PMU initialization ...")
        self._state:PMU_State = PMU_State.NOT_DEFINED
        self.inst_id :str = f'{PriceMonitoringUnit.name}_{str(PriceMonitoringUnit.__count)}'
        self.lock = threading.Lock()
        self.sys_monitor = None
        self.notifier = None
        self._send_hb:bool = False

        self.df_status:LiveFeedStatus=LiveFeedStatus.OFF

        self._data_feed_status_callback = None
        self._state_change_callback = None

        self.inport = pmu_cc.inp_dataPort
        self.conditions = defaultdict(list)  # Dictionary to store conditions for each index
        self.hard_exit_event = threading.Event()  # Event object to signal hard exit

        self.data_rx_price_monitor_thread = threading.Thread(name='PMU Data_Rx Price Monitor',target=self.monitor_prices, daemon=True)
        self._state:PMU_State = PMU_State.CREATED
        self.__count += 1

        logger.debug (f"PMU initialization ...done Inst: {PriceMonitoringUnit.name} {PriceMonitoringUnit.__count} {PriceMonitoringUnit.__componentType}")
        return

    def __str__(self):
        return f"Inst: {PriceMonitoringUnit.name} {PriceMonitoringUnit.__count} {PriceMonitoringUnit.__componentType}"

    def simulate(self, trade_price):
        tick = TickData(tk=26000, o=21000,h=21100, l=20900, c=trade_price-1, v=100, oi=0, ft='1')
        self.inport.data_q.put(tick)
        self.inport.evt.set()
        time.sleep(1)
        tick = TickData(tk=26000, o=21000,h=21100, l=20900, c=trade_price, v=100, oi=0, ft='1')
        self.inport.data_q.put(tick)
        self.inport.evt.set()

    def send_hb (self, new_flag:bool) :
        self._send_hb = new_flag
        
    send_hbeat = property (None, send_hb)

    @property
    def state (self):
        return (self._state)

    @state.setter
    def state (self, new_state:PMU_State):
        with self.lock:
            if not (self._state == PMU_State.ERROR or self._state == PMU_State.STOPPED) :
                logger.debug (f'{self._state} --> {new_state}')
                self._state = new_state
                if self._state_change_callback is not None:
                    self._state_change_callback ()

    def register_callback(self, token:str, cond_ds):
        with self.lock:
            if isinstance(cond_ds, list):
                self.conditions[token].extend(cond_ds)
            else:
                self.conditions[token].append(cond_ds)
                logger.debug(f'Token: {token} Registered: {cond_ds["cb_id"]}')

    def unregister_callback(self, token:str, callback_id):
        with self.lock:
            if token:
                self.conditions[token] = [cond_ds for cond_ds in self.conditions[token] if cond_ds['cb_id'] != callback_id]
                logger.debug(f'Token: {token} Un Registered: {callback_id}')

    def hard_exit (self):
        logger.debug (f'Hard Exit Begin..')
        self.purge_all_conditions(token='ALL')
        if self.hard_exit_event is not None:
            self.hard_exit_event.set ()
        if self.inport is not None and self.inport.evt is not None:
            self.inport.evt.set()
        time.sleep(0.1)
        if self.data_rx_price_monitor_thread is not None:
            self.data_rx_price_monitor_thread.join(timeout=2)
        logger.debug (f'Hard Exit Complete..')

    def purge_all_conditions(self, token='ALL'):
        with self.lock:
            if token == 'ALL':
                self.conditions.clear()  # Clear all conditions
            else:
                self.conditions[token] = []  # Clear conditions for the specified index

    def start_monitoring(self):
        self.data_rx_price_monitor_thread.start ()
        self.state = PMU_State.READY

    def monitor_prices(self):

        def update_df_status (state:LiveFeedStatus):
            nonlocal self
            # if current status is different from new state
            if (self.df_status != state ) :
                logger.debug (f'Data feed status updated {self.df_status} --> {state}')
                self.df_status = state 
                now = datetime.now().strftime("%H:%M:%S")
                mesg = f'T: {now}: Datafeed : {state.name}'
                logger.debug (mesg)
                if self.notifier is not None:
                    self.notifier.put_message (mesg)
                if self._data_feed_status_callback is not None:
                    logger.debug ("Data feed status updated Call back ..")
                    self._data_feed_status_callback ()
            return        

        t_name = threading.current_thread().name
        logger.debug ("In PMU Data_Rx Price Monitor.."+ t_name)
        self.state = PMU_State.RUNNING

        do_process = bool(True)
        evt = self.inport.evt
        exit_evt = self.hard_exit_event
        q = self.inport.data_q
        tout = PriceMonitoringUnit.DATAFEED_TIMEOUT
        sys_monitor_cnt = PriceMonitoringUnit.SYS_MONITOR_MAX_COUNT
        sys_monitor = self.sys_monitor

        id = self.inst_id
        assert evt is not None, 'Event is None'        
        assert q is not None, 'Queue is None'

        while do_process:
            try :
                evt_flag = evt.wait(timeout=tout)
            except Exception as e:
                logger.error("Event Exception "+str(e))
            else :
                sys_monitor_cnt -= 1
                if sys_monitor_cnt == 0 and self._send_hb:
                    if sys_monitor is not None:
                        sys_monitor.i_am_live(f'{id}')
                    logger.debug(f'{id} - Alive')
                    sys_monitor_cnt = PriceMonitoringUnit.SYS_MONITOR_MAX_COUNT
                
                if evt_flag:
                    evt.clear()
                    if ((nelem:= q.qsize()) > 0) :
                        if not self.df_status.value:
                            update_df_status (LiveFeedStatus.ON)
                        while (nelem) :
                            try:
                                ohlc:TickData = q.get ()
                            except Exception as e :
                                logger.error("Exception during queue read"+str(e))
                            else :
                                token = str(ohlc.tk)
                                with self.lock:
                                    try:
                                        conditions = self.conditions[token]
                                    except Exception:
                                        logger.debug (f'Exception occured:')
                                    else :
                                        # Going through a copy of list
                                        for cond_ds in conditions[:]:
                                            if cond_ds['condition_fn'](ohlc.c,cond_ds['cb_id']):
                                                # callback(cond_ds['callback_function'], cond_ds['cb_id'])
                                                cond_ds['callback_function'](cond_ds['cb_id'])
                                                conditions.remove(cond_ds)  # Remove the condition after callback
                                                logger.debug (f'{token} Removed condition: {cond_ds["cb_id"]}')
                            finally :
                                nelem -= 1
                else :
                    update_df_status (LiveFeedStatus.OFF)
                    logger.debug (f"{t_name} - No Data available for {tout} secs")

            finally:
                if (exit_evt.is_set()): 
                    logger.debug ("Received Exit Command ..")
                    exit_evt.clear()
                    q.flush ()
                    do_process = False

        logger.info (f'Exiting Thread: {t_name}')
        return

