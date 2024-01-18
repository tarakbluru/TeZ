import os
import sys
import time
from threading import Event

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app_mods
from app_utils import ExtSimpleQueue

port = app_mods.SimpleDataPort(data_q=ExtSimpleQueue(), evt=Event())
ws_wrap = app_mods.WS_WrapU(port_cfg=port)

ws_wrap.connect_to_data_feed_servers()
time.sleep(10)
print(ws_wrap.get_latest_tick())
ws_wrap.disconnect_data_feed_servers()
