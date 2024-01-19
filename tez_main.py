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
__email__ = "tarakesh.nc_at_google_mail_dot_com"
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
    from app_be import TeZ_App_BE
except Exception as e:
    logger.debug(traceback.format_exc())
    logger.error(("Import Error " + str(e)))
    sys.exit(1)

global g_app_be
g_app_be: TeZ_App_BE = None


def long_market():
    logger.debug('Buy Click')
    g_app_be.market_action(action='Buy')


def short_market():
    logger.debug('Short Click')
    g_app_be.market_action(action='Short')


def square_off_action():
    logger.debug('Square Off Click')
    g_app_be.square_off_position()


def exit_action():
    print("Exiting the app")
    g_root.destroy()


def gui_tk_layout():
    from tkinter import font

    root = tk.Tk()
    root.title(app_mods.get_system_info("GUI_CONFIG", "APP_TITLE"))

    # Set the window size approximately to 2 inches by 2 inches
    root.geometry(app_mods.get_system_info("GUI_CONFIG", "APP_GEOMETRY"))

    # Make the window stay on top
    root.attributes("-topmost", True)

    # Create frames to organize buttons
    frame_top = tk.Frame(root)
    frame_bottom = tk.Frame(root)
    frame_top.pack(side=tk.TOP, pady=5)  # Adds padding above top buttons
    frame_bottom.pack(side=tk.BOTTOM)

    # Long and Short buttons in one line with space between them
    l_button_text = app_mods.get_system_info("GUI_CONFIG", "LONG_BUTTON")

    symbol = app_mods.get_system_info("TIU", "EXCHANGE")
    if symbol == 'NSE':
        bold_font = font.Font(weight="normal")
    else:
        bold_font = font.Font(weight="bold")

    buy_button = tk.Button(frame_top, text=l_button_text, command=long_market, bg='#00EF00',  font=bold_font, fg='black')
    buy_button.pack(side=tk.LEFT, padx=5)  # Adds space between buttons

    # Label to display NIFTY index data
    tick_label = tk.Label(frame_top, text="", width=7)
    tick_label.pack(side=tk.LEFT, padx=5)  # Adds space between label and buttons

    s_button_text = app_mods.get_system_info("GUI_CONFIG", "SHORT_BUTTON")
    sell_button = tk.Button(frame_top, text=s_button_text, command=short_market, bg='#EF0000',  font=bold_font, fg='black')
    sell_button.pack(side=tk.LEFT, padx=5)  # Adds space between buttons

    # Exit App button in another line
    e_button_text = app_mods.get_system_info("GUI_CONFIG", "EXIT_BUTTON")
    exit_button = tk.Button(frame_bottom, text=e_button_text, command=exit_action, font=bold_font)
    exit_button.pack(side=tk.BOTTOM, padx=5, pady=5)  # Adds space between buttons

    # Square Off button in the same line
    sq_button_text = app_mods.get_system_info("GUI_CONFIG", "SQUARE_OFF_BUTTON")
    square_off_button = tk.Button(frame_bottom, text=sq_button_text, command=square_off_action, font=bold_font)
    square_off_button.pack(side=tk.BOTTOM, padx=5, pady=5)  # Adds space between buttons

    # Update the NIFTY index data periodically (every second)
    def update_label():
        ltp = g_app_be.get_latest_tick()
        # Update the label text with the fetched NIFTY index data
        tick_label.config(text=str(ltp), font=bold_font)
        root.after(500, update_label)

    update_label()

    return root


def main():
    logger.info(f'{__app_name__}: {__version__}')
    global g_root
    global g_app_be

    r = app_mods.get_system_config()
    logger.info(f'System Config Read: {r}')

    g_app_be = TeZ_App_BE()

    g_app_be.data_feed_connect()
    g_root = gui_tk_layout()
    try:
        g_root.mainloop()
    except KeyboardInterrupt:
        g_root.destroy()

    g_app_be.data_feed_disconnect()
    time.sleep(1)
    logger.info(f'{__app_name__} Version: {__version__} -- Ends')


if __name__ == "__main__":
    main()

    nthreads = threading.active_count()
    logger.info(f"nthreads in the system: {nthreads}")

    for count, t in enumerate(threading.enumerate()):
        logger.info(f"{count+1}. Thread name: {t.name} ")

    children = active_children()
    logger.info(f'Active Child Processes: {len(children)}')
    if len(children):
        logger.info(children)
    sys.exit(0)
