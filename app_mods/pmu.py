"""
File: pmu.py
Author: [Tarakeshwar NC]
Date: March 15, 2024
Description: This script provides price monitoring functionality.
"""
# Copyright (c) [2024] [Tarakeshwar N.C]
# This file is part of the Tez project.
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
    import time
    from collections import defaultdict
    from dataclasses import dataclass
    from datetime import datetime
    from enum import Enum
    from threading import Event, Lock, Thread, current_thread
    from typing import NamedTuple, Union

    from .shared_classes import (Component_Type, LiveFeedStatus,
                                 SimpleDataPort, TickData, Market_Timing)
except Exception as e:
    logger.debug(traceback.format_exc())
    logger.error(("Import Error " + str(e)))
    sys.exit(1)

class PMU_CreateConfig(NamedTuple):
    inp_dataPort: SimpleDataPort
    market_hours: Union[Market_Timing, None] = None
    data_delay_callback_function: callable = None

class PMU_State(Enum):
    NOT_DEFINED=0
    CREATED=1
    READY=2
    RUNNING=3
    STOPPED=4
    ERROR=5

@dataclass
class WaitConditionData:
    cb_id: str
    condition_fn: callable
    callback_function: callable
    wait_price_lvl: int
    prev_tick_lvl: int=None
    prec_factor:int=100

    def __str__(self):
        return f"cb_id: {self.cb_id}, wait_price_lvl: {self.wait_price_lvl}, prev_tick_lvl: {self.prev_tick_lvl}"

class PriceMonitoringUnit:
    name = "PMU"
    __count = 0
    __componentType = Component_Type.ACTIVE
    DATAFEED_TIMEOUT:float = 20.0
    SYS_MONITOR_MAX_COUNT:int = 30

    def __init__(self, pmu_cc: PMU_CreateConfig):
        logger.debug ("PMU initialization ...")
        self._state:PMU_State = PMU_State.NOT_DEFINED
        self.inst_id :str = f'{PriceMonitoringUnit.name}_{str(PriceMonitoringUnit.__count)}'
        self.lock = Lock()
        self.sys_monitor = None
        self.notifier = None
        self._send_hb:bool = False
        self.prec_factor:int = int(100)
        self.df_status:LiveFeedStatus=LiveFeedStatus.OFF

        self.chk_delay = False
        self.delay_cb:callable = pmu_cc.data_delay_callback_function
        self.delay_cb_done = False

        if pmu_cc.market_hours is None:
            self.mh = Market_Timing()
        else:
            self.mh = pmu_cc.market_hours

        hr = datetime.strptime(self.mh.mo, "%H:%M").hour
        min = datetime.strptime(self.mh.mo, "%H:%M").minute
        m_open = datetime.now().replace(hour=hr, minute=min, second=0, microsecond=0)

        hr = datetime.strptime(self.mh.mc, "%H:%M").hour
        min = datetime.strptime(self.mh.mc, "%H:%M").minute
        m_close = datetime.now().replace(hour=hr, minute=min, second=0, microsecond=0)
        logger.debug(f'{self.inst_id}: market open: {m_open} market close: {m_close}')

        if m_open <= datetime.now() < m_close:
            self.chk_delay = True
        self._data_feed_status_callback = None
        self._state_change_callback = None

        self.inport = pmu_cc.inp_dataPort
        self.conditions = defaultdict(list)  # Dictionary to store conditions for each index
        self.hard_exit_event = Event()  # Event object to signal hard exit

        self.data_rx_price_monitor_thread = Thread(name='PMU Data_Rx Price Monitor',target=self.monitor_prices, daemon=True)
        self._state:PMU_State = PMU_State.CREATED
        self.__count += 1

        logger.debug (f"PMU initialization ...done Inst: {PriceMonitoringUnit.name} {PriceMonitoringUnit.__count} {PriceMonitoringUnit.__componentType}")
        return

    def __str__(self):
        return f"Inst: {PriceMonitoringUnit.name} {PriceMonitoringUnit.__count} {PriceMonitoringUnit.__componentType}"

    def simulate(self, ultoken, trade_price, cross='up'):
        logger.info (f'simulation:')
        if cross == 'up':
            tick = TickData(tk=ultoken, o=21000,h=21100, l=20900, c=trade_price-1, v=100, oi=0, ft='1')
            self.inport.data_q.put(tick)
            self.inport.evt.set()
            time.sleep(1)
            tick = TickData(tk=ultoken, o=21000,h=21100, l=20900, c=trade_price, v=100, oi=0, ft='2')
            self.inport.data_q.put(tick)
            self.inport.evt.set()
        else:
            tick = TickData(tk=ultoken, o=21000,h=21100, l=20900, c=trade_price+1, v=100, oi=0, ft='1')
            self.inport.data_q.put(tick)
            self.inport.evt.set()
            time.sleep(1)
            tick = TickData(tk=ultoken, o=21000,h=21100, l=20900, c=trade_price, v=100, oi=0, ft='2')
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

    def register_callback(self, token:str, cond_obj):
        with self.lock:
            self.conditions[token].append(cond_obj)
            logger.debug(f'Token: {token} Registered: {cond_obj.cb_id} {cond_obj} no.of conditions: {len(self.conditions[token])}')

    def unregister_callback(self, token:str, callback_id):
        if token:
            with self.lock:
                self.conditions[token] = [cond_ds for cond_ds in self.conditions[token] if cond_ds.cb_id != callback_id]
                logger.debug(f'Token: {token} Un Registered: {callback_id}')

    def hard_exit (self):
        logger.info("PMU hard exit initiated...")
        
        # Step 1: Clear all monitoring conditions
        logger.debug("Purging all price monitoring conditions...")
        self.purge_all_conditions(token='ALL')
        
        # Step 2: Signal all threads to stop
        logger.debug("Signaling PMU threads to stop...")
        if self.hard_exit_event is not None:
            self.hard_exit_event.set()
        if self.inport is not None and self.inport.evt is not None:
            self.inport.evt.set()
            
        # Step 3: Brief pause to let threads acknowledge shutdown signal
        time.sleep(0.1)
        
        # Step 4: Wait for data monitoring thread with validation
        if self.data_rx_price_monitor_thread is not None:
            if self.data_rx_price_monitor_thread.is_alive():
                logger.debug("Waiting for PMU data monitoring thread...")
                self.data_rx_price_monitor_thread.join(timeout=3.0)  # Increased timeout
                
                if self.data_rx_price_monitor_thread.is_alive():
                    logger.warning("PMU data monitoring thread failed to stop within timeout")
                    logger.warning(f"Thread {self.data_rx_price_monitor_thread.name} may become zombie")
                else:
                    logger.debug("PMU data monitoring thread stopped cleanly")
            else:
                logger.debug("PMU data monitoring thread was already stopped")
        else:
            logger.debug("PMU data monitoring thread was not initialized")
            
        logger.info("PMU hard exit completed")

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

        t_name = current_thread().name
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

        chk_delay = self.chk_delay

        while do_process:
            try :
                evt_flag = evt.wait(timeout=tout)
            except Exception as e:
                logger.error("Event Exception "+str(e))
            else :
                sys_monitor_cnt -= 1

                if not sys_monitor_cnt:
                    log_proc = True
                    if self._send_hb:
                        if sys_monitor is not None:
                            sys_monitor.i_am_live(f'{id}')
                        logger.debug(f'{id} - Alive')
                    sys_monitor_cnt = PriceMonitoringUnit.SYS_MONITOR_MAX_COUNT
                else:
                    log_proc = False

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
                                if log_proc:
                                    logger.debug (f'processing : {ohlc.tk}:  {ohlc.ft}')
                                    log_proc = False
                                token = str(ohlc.tk)
                                try:
                                    rx_ts = round(float(ohlc.rx_ts))
                                    diff_ft = abs(rx_ts - int(ohlc.ft))
                                except ValueError:
                                    logger.info (f'{ohlc}')
                                except Exception as e:
                                    logger.info (f'{ohlc} Exception: {str(e)}')
                                else:
                                    if chk_delay and diff_ft > 4:
                                        logger.debug (f"""Check the feed, it seems to be lagging ft:{ohlc.ft}
                                                        rx_ts: {rx_ts} diff_ft: {diff_ft}""")
                                        logger.info (f'Unexpected delay:  rx_ts: {rx_ts} ft :{ohlc.ft} diff_ft: {diff_ft} secs')
                                        if self.delay_cb is not None and (not self.delay_cb_done):
                                            if self.delay_cb ():
                                                self.delay_cb_done = True
                                                # purging all conditions should not be done here
                                                # as pfmu will not know about it.                                                
                                                # Avoid --> self.purge_all_conditions(token='ALL')
                                        drop_tick = True
                                    else :
                                        drop_tick = False
                                    with self.lock:
                                        try:
                                            conditions = self.conditions[token]
                                        except Exception as e:
                                            logger.debug (f'Exception occured: {str(e)}')
                                        else :
                                            rem_list = []
                                            ltp_level = round(ohlc.c * self.prec_factor)
                                            # Going through a copy of list
                                            for cond_elem in conditions:
                                                cond_obj:WaitConditionData = cond_elem
                                                if drop_tick:
                                                    cond_obj.prev_tick_lvl = ltp_level
                                                    continue

                                                prev_tick_lvl = cond_obj.prev_tick_lvl
                                                fn = None
                                                if prev_tick_lvl is not None:
                                                    if prev_tick_lvl < cond_obj.wait_price_lvl and ltp_level >= cond_obj.wait_price_lvl:
                                                        fn = cond_obj.callback_function
                                                        logger.debug (f'{cond_obj.cb_id}: prev_tick_lvl: {prev_tick_lvl} wait_price_lvl: {cond_obj.wait_price_lvl} ltp_level: {ltp_level} Triggered ft: {ohlc.ft}')
                                                    if fn is None and prev_tick_lvl > cond_obj.wait_price_lvl and ltp_level <= cond_obj.wait_price_lvl:
                                                        fn = cond_obj.callback_function
                                                        logger.debug (f'{cond_obj.cb_id}: prev_tick_lvl: {cond_obj.prev_tick_lvl} wait_price_lvl: {cond_obj.wait_price_lvl} ltp_level: {ltp_level} Triggered ft: {ohlc.ft}')
                                                if fn is not None:
                                                    fn(cond_obj.cb_id, ohlc.ft)
                                                    rem_list.append(cond_obj)
                                                else:
                                                    cond_obj.prev_tick_lvl = ltp_level

                                            if len(rem_list):
                                                self.conditions[token] = [cond_obj for cond_obj in conditions if cond_obj not in rem_list]
                                                logger.info (f'Updated list : {len(self.conditions[token])}')
                                                for condition in self.conditions[token]:
                                                    logger.debug(condition)
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
