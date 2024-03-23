import os
import sys
import threading
from datetime import datetime
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app_mods
import app_utils as utils


# Example usage:
def price_condition(price):
    return price > 21000

def order_placement(callback_id):
    print(f"Callback triggered for ID: {callback_id}")


def order_placement_th(callback_id):
    threading.Thread(name='Test PMU Order Placement',target=order_placement, args=(callback_id,), daemon=True).start()

def main():
    data_q = utils.ExtSimpleQueue()
    evt = threading.Event()
    pmu_cc = app_mods.PMU_cc(inp_dataPort=app_mods.SimpleDataPort(data_q=data_q, evt=evt))
    pmu = app_mods.PriceMonitoringUnit(pmu_cc=pmu_cc)
    pmu.start_monitoring ()
    time.sleep(2)

    pmu.register_callback(token='26000', cond_ds=[{'condition_fn': price_condition, 
                                                                  'callback_function': order_placement_th, 
                                                                  'cb_id': "26000_0"}])

    tick = app_mods.TickData(tk=26000, o=21000,h=21100, l=20900, c= 21000, v=100, oi=0, ft='1')
    data_q.put(tick)
    evt.set()
    time.sleep(1)

    pmu.register_callback(token='26000', cond_ds=[{'condition_fn': price_condition, 
                                                                  'callback_function': order_placement_th, 
                                                                  'cb_id': "26000_1"}])

    tick = app_mods.TickData(tk=26000, o=21000,h=21100, l=20900, c= 21010, v=100, oi=0, ft='1')
    data_q.put(tick)
    evt.set()
    time.sleep(1)

    pmu.register_callback(token='26000', cond_ds=[{'condition_fn': price_condition, 
                                                                  'callback_function': order_placement_th, 
                                                                  'cb_id': "26000_2"}])

    pmu.register_callback(token='26000', cond_ds=[{'condition_fn': price_condition, 
                                                                  'callback_function': order_placement_th, 
                                                                  'cb_id': "26000_3"}])

    tick = app_mods.TickData(tk=26000, o=21000,h=21100, l=20900, c= 21010, v=100, oi=0, ft='2')
    data_q.put(tick)
    evt.set()
    time.sleep(1)

    tick = app_mods.TickData(tk=26000, o=21000,h=21100, l=20900, c= 21000, v=100, oi=0, ft='3')
    data_q.put(tick)
    evt.set()
    time.sleep(1)

    tick = app_mods.TickData(tk=26000, o=21000,h=21100, l=20900, c= 21010, v=100, oi=0, ft='4')
    data_q.put(tick)
    evt.set()
    time.sleep(1)


    pmu.register_callback(token='26000', cond_ds=[{'condition_fn': price_condition, 
                                                                  'callback_function': order_placement_th, 
                                                                  'cb_id': "26000_4"}])

    tick = app_mods.TickData(tk=26000, o=21000,h=21100, l=20900, c= 21000, v=100, oi=0, ft='5')
    data_q.put(tick)
    evt.set()
    time.sleep(1)

    pmu.unregister_callback(token='26000',callback_id='26000_4')

    tick = app_mods.TickData(tk=26000, o=21000,h=21100, l=20900, c= 21010, v=100, oi=0, ft='2')
    data_q.put(tick)
    evt.set()
    time.sleep(1)

    time.sleep(20)

    pmu.hard_exit()


if __name__ == "__main__":
    main()
