"""
File: tez_main.py
Author: [Tarakeshwar NC]
Date: January 15, 2024
Description: This is the main system file. All sub systems are created and 
data feed is connected before gui is laid out.
"""
# Copyright (c) [2024] [Tarakeshwar N.C]
# This file is part of the TeZ project.
# It is subject to the terms and conditions of the MIT License.
# See the file LICENSE in the top-level directory of this distribution
# for the full text of the license.

__app_name__ = 'TeZ'
__author__ = "Tarakeshwar N.C"
__copyright__ = "2024"
__date__ = "2024/1/14"
__deprecated__ = False
__email__ =  "tarakesh.nc_at_google_mail_dot_com"
__license__ = "MIT"
__maintainer__ = "Tarak"
__status__ = "Development"
__version__ = "0.1"

import sys
import traceback

import app_utils as utils

logger = utils.get_logger(__name__)

try:
    import threading
    import time
    import tkinter as tk
    from multiprocessing import active_children

    import app_mods
    import numpy as np
    import yaml
except Exception as e:
    logger.debug(traceback.format_exc())
    logger.error (("Import Error " + str(e)))
    sys.exit (1)


def get_ltp_strike ():
    ul_ltp = g_diu.get_latest_tick()
    strike = round(ul_ltp / 50 + 0.5) * 50
    logger.debug (f'ul_ltp:{ul_ltp} strike:{strike}')
    return ul_ltp, strike

def get_tsym_token (action):
    sym = app_mods.get_system_info("TIU", "INSTRUMENT")
    exch = app_mods.get_system_info("TIU", "EXCHANGE")
    qty = app_mods.get_system_info("TIU", "QUANTITY")
    ltp = None
    ltp,strike= get_ltp_strike()

    if exch == 'NFO':
        c_or_p = 'C' if action == 'Buy' else 'P'
        
        if c_or_p == 'C':
            strike_offset = app_mods.get_system_info("TIU", "CE_STRIKE_OFFSET")
        else:
            strike_offset = app_mods.get_system_info("TIU", "PE_STRIKE_OFFSET")
        strike += strike_offset*50
        exp = app_mods.get_system_info("TIU", "EXPIRY_DATE")
        searchtext=f'{sym}{exp}{c_or_p}{strike}'        
    elif exch == 'NSE':
        searchtext = sym
        strike = ''
        logger.debug (f'ltp:{ltp} strike:{strike}')
    else :
        ...
    token, tsym = g_tiu.search_scrip(exchange=exch, symbol=searchtext)
    ltp,ti = g_tiu.fetch_ltp (exch, token)

    logger.info (f'strike: {strike}, sym: {sym}, tsym: {tsym}, token: {token}, qty:{qty}, ltp: {ltp}, ti:{ti}')
    return strike, sym, tsym, token, qty, ltp, ti

def market_action(action):
    strike, sym, tsym, token, qty,ltp, ti = get_tsym_token (action=action)
    oco_order = np.NaN
    os = app_mods.shared_classes.OrderStatus()
    status = app_mods.Tiu_OrderStatus.HARD_FAILURE

    if app_mods.get_system_info("TIU", "TRADE_MODE") == 'PAPER':
        # tiu place order
        order_id = '1'
        oco_order = f'{order_id}_gtt_order_id_1'
    else :
        logger.info (f'sym:{sym} tsym:{tsym} ltp: {ltp}')
        if sym == 'NIFTYBEES' and ltp is not None:

            pp = app_mods.get_system_info("TIU", "PROFIT_PER")/100.0
            bp = utils.round_stock_prec(ltp * pp, base=ti)

            sl_p = app_mods.get_system_info("TIU", "STOPLOSS_PER")/100.0
            bl = utils.round_stock_prec(ltp * sl_p, base=ti)
            logger.debug (f'ltp:{ltp} pp:{pp} bp:{bp} sl_p:{sl_p} bl:{bl}')
            if action == 'Buy':
                order = app_mods.BO_B_MKT_Order(tradingsymbol=tsym, 
                                                quantity=qty, bookloss_price=bl,
                                                bookprofit_price=bp, remarks='tiny_tez_')
            else:
                order = app_mods.BO_S_MKT_Order(tradingsymbol=tsym, 
                                                quantity=qty, bookloss_price=bl,
                                                bookprofit_price=bp, remarks='tiny_tez_')
            status, os = g_tiu.place_and_confirm_tiny_tez_order (order=order)
        else:
            ...

    symbol = tsym+'_'+str(token)
    order_time = os.fill_timestamp
    status = status.name
    order_id = os.order_id
    qty = os.fillshares
    g_bku.save_order(order_id, symbol, qty, order_time, status, oco_order)
    g_bku.show()

def long_market():
    logger.debug ('Buy Click')
    market_action (action='Buy')

def short_market():
    logger.debug ('Short Click')
    market_action (action='Short')

def square_off_action():
    logger.debug ('Square Off Click')
    order_list = g_bku.fetch_order_id ()
    g_tiu.square_off_position(order_details=order_list)
    print("Position squared off")

def exit_action():
    print("Exiting the app")
    g_root.destroy()

def update_tick_data(label):
    # Get NIFTY index data from the queue or source
    ltp = g_diu.get_latest_tick()
    # Update the label text with the fetched NIFTY index data
    label.config(text=str(ltp))

def gui_tk_layout ():
    g_root = tk.Tk()
    g_root.title(app_mods.get_system_info("GUI_CONFIG", "APP_TITLE"))

    # Set the window size approximately to 2 inches by 2 inches
    g_root.geometry(app_mods.get_system_info("GUI_CONFIG", "APP_GEOMETRY"))

    # Make the window stay on top
    g_root.attributes("-topmost", True)

    # Create frames to organize buttons
    frame_top = tk.Frame(g_root)
    frame_bottom = tk.Frame(g_root)
    frame_top.pack(side=tk.TOP, pady=5)  # Adds padding above top buttons
    frame_bottom.pack(side=tk.BOTTOM)

    # Long and Short buttons in one line with space between them
    l_button_text = app_mods.get_system_info("GUI_CONFIG", "LONG_BUTTON")
    buy_button = tk.Button(frame_top, text=l_button_text, command=long_market)
    buy_button.pack(side=tk.LEFT, padx=5)  # Adds space between buttons

    # Label to display NIFTY index data
    tick_label = tk.Label(frame_top, text="", width=7)
    tick_label.pack(side=tk.LEFT, padx=5)  # Adds space between label and buttons

    s_button_text = app_mods.get_system_info("GUI_CONFIG", "SHORT_BUTTON")
    sell_button = tk.Button(frame_top, text=s_button_text, command=short_market)
    sell_button.pack(side=tk.LEFT, padx=5)  # Adds space between buttons
    
    # Exit App button in another line
    e_button_text = app_mods.get_system_info("GUI_CONFIG", "EXIT_BUTTON")
    exit_button = tk.Button(frame_bottom, text=e_button_text, command=exit_action)
    exit_button.pack(side=tk.BOTTOM, padx=5, pady=5)  # Adds space between buttons

     # Square Off button in the same line
    sq_button_text = app_mods.get_system_info("GUI_CONFIG", "SQUARE_OFF_BUTTON")
    square_off_button = tk.Button(frame_bottom, text=sq_button_text, command=square_off_action)
    square_off_button.pack(side=tk.BOTTOM, padx=5, pady=5)  # Adds space between buttons

   # Update the NIFTY index data periodically (every second)
    def update_label():
        update_tick_data(tick_label)
        g_root.after(500, update_label)

    update_label()

    return g_root

def create_tiu ():
    global g_tiu

    cred_file = app_mods.get_system_info("TIU", "CRED_FILE")
    logger.info (f'credfile{cred_file}')

    with open(cred_file) as f:
        cred = yaml.load(f, Loader=yaml.FullLoader)

    session_id = None

    if app_mods.get_system_info("TIU", "USE_GSHEET_TOKEN") == 'YES':
        gsheet_info = app_mods.get_system_info("TIU", "GOOGLE_SHEET")
        print (gsheet_info)
        gsheet_client_json = gsheet_info['CLIENT_SECRET']
        url = gsheet_info['URL']
        sheet_name = gsheet_info['NAME']
        if gsheet_client_json != '' and url != '' and sheet_name != '':
            session_id = app_mods.get_session_id_from_gsheet(cred, 
                                                gsheet_client_json = gsheet_client_json, 
                                                url=url, 
                                                sheet_name=sheet_name)

    dl_filepath = app_mods.get_system_info("SYSTEM", "DL_FOLDER")
    logger.info (f'dl_filepath: {dl_filepath}')

    tiu_token_file = app_mods.get_system_info("TIU", "TOKEN_FILE")
    logger.info (f'token_file: {tiu_token_file}')

    tiu_cred_file = app_mods.get_system_info("TIU", "CRED_FILE")

    tiu_save_token_file_cfg = app_mods.get_system_info("TIU", "SAVE_TOKEN_FILE_CFG")
    tiu_save_token_file = app_mods.get_system_info("TIU", "SAVE_TOKEN_FILE_NAME")

    tcc = app_mods.Tiu_CreateConfig(tiu_cred_file, 
                                    session_id, 
                                    tiu_token_file,
                                    False,
                                    dl_filepath,
                                    None,
                                    tiu_save_token_file_cfg,
                                    tiu_save_token_file)
    logger.debug (f'tcc:{str(tcc)}')
    g_tiu = app_mods.Tiu(tcc=tcc)

    exp_date = app_mods.get_system_info("TIU", "EXPIRY_DATE")
    symbol = app_mods.get_system_info("TIU", "INSTRUMENT")
    exch = app_mods.get_system_info("TIU", "EXCHANGE")

    if symbol != '':
        if exch == 'NSE':
            g_tiu.create_sym_token_tsym_q_access ([symbol])
        elif exch  == 'NFO':
            g_tiu.compact_search_file(symbol, exp_date)

def create_diu ():
    global g_diu
    diu_cred_file = app_mods.get_system_info("DIU", "CRED_FILE")
    diu_token_file = app_mods.get_system_info("DIU", "TOKEN_FILE")
    logger.info (f'token_file: {diu_token_file}')
    diu_save_token_file_cfg = app_mods.get_system_info("DIU", "SAVE_TOKEN_FILE_CFG")
    diu_save_token_file = app_mods.get_system_info("DIU", "SAVE_TOKEN_FILE_NAME")

    dcc = app_mods.Diu_CreateConfig(diu_cred_file, None, diu_token_file, False, None,None, diu_save_token_file_cfg,diu_save_token_file)
    logger.debug (f'dcc:{str(dcc)}')
    g_diu = app_mods.Diu(dcc=dcc)
   
def create_bku ():
    global g_bku
    bku_file = app_mods.get_system_info("TIU", "TRADES_RECORD_FILE")
    g_bku = app_mods.BookKeeperUnit(bku_file, reset=False)

def main():
    logger.info (f'{__app_name__}: {__version__}')

    global g_root
    r = app_mods.get_system_config()
    logger.info (f'System Config Read: {r}')

    logger.info ('Creating Book Keeper')
    create_bku ()
    logger.info ('Creating TIU')
    create_tiu ()
    logger.info ('Creating DIU')
    create_diu ()
    g_diu.connect_to_data_feed_servers ()

    g_root = gui_tk_layout()
    try:
        g_root.mainloop()
    except KeyboardInterrupt:
        g_root.destroy()

    g_diu.disconnect_data_feed_servers ()
    time.sleep (1)
    logger.info (f'{__app_name__} Version: {__version__} -- Ends')    

if __name__ == "__main__":
    main()

    nthreads = threading.active_count()
    logger.info (f"nthreads in the system: {nthreads}")
    
    for count, t in enumerate(threading.enumerate()):
        logger.info (f"{count+1}. Thread name: {t.name} ")
    
    children = active_children()
    logger.info(f'Active Child Processes: {len(children)}')
    if len(children): 
        logger.info(children)
    sys.exit(0)