import os
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app_mods

def main ():
    book_keeper = app_mods.BookKeeperUnit(r'F:\Python_log\tiny_tez\nifty_bku.csv', reset=False)

    # Place a new order
    order_id = '1'
    symbol = 'AAPL'
    qty = 10
    order_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    status = 'Placed'
    oco_order = 'gtt_order_id_1'

    book_keeper.save_order(order_id, symbol, qty, order_time, status, oco_order)

    book_keeper.show()

    order_id = '12'
    symbol = 'NIFTYBEES'
    qty = 10
    order_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    status = 'Placed'
    oco_order = 'gtt_order_id_2'

    book_keeper.save_order(order_id, symbol, qty, order_time, status, oco_order)
    book_keeper.show()


if __name__=="__main__":
    main ()