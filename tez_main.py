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
__version__ = "0.5.0_Rc1"

import sys
import traceback

import app_utils as utils

logger = utils.get_logger(__name__)

try:
    import threading
    import time
    import tkinter as tk
    import winsound
    from multiprocessing import active_children

    import app_mods
    from app_be import TeZ_App_BE
except Exception as e:
    logger.debug(traceback.format_exc())
    logger.error(("Import Error " + str(e)))
    sys.exit(1)

global g_app_be
global g_slider_value
g_app_be: TeZ_App_BE | None = None


def long_market():
    logger.debug('Buy Click')
    if g_slider_value.lower() == 'unlocked':
        g_app_be.market_action(action='Buy')
        play_notify()
    else:
        logger.info('Unlock to take position')


def short_market():
    logger.debug('Short Click')
    if g_slider_value.lower() == 'unlocked':
        g_app_be.market_action(action='Short')
        play_notify()
    else:
        logger.info('Unlock to take position')


def square_off_action():
    logger.debug('Square Off Click')
    if g_slider_value.lower() == 'unlocked':
        g_app_be.square_off_position()
        play_notify()
    else:
        logger.info('Unlock to Squareoff position')


def exit_action():
    print("Exiting the app")
    if g_slider_value.lower() == 'unlocked':
        g_root.destroy()
    else:
        logger.info('Unlock to Exit..')


def play_notify():
    # Play the beep sound with reduced volume
    pb = app_mods.get_system_info("GUI_CONFIG", "PLAY_NOTIFY")
    if pb.upper() == 'YES':
        winsound.PlaySound("C:/Windows/Media/notify.wav", winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NOWAIT)


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
        font = font.Font(weight="normal")
    else:
        font = font.Font(weight="bold")

    buy_button = tk.Button(frame_top, text=l_button_text, command=long_market, bg='#00EF00',  font=font, fg='black')
    buy_button.pack(side=tk.LEFT, padx=5)  # Adds space between buttons

    # Label to display NIFTY index data
    tick_label = tk.Label(frame_top, text="", width=7)
    tick_label.pack(side=tk.LEFT, padx=5)  # Adds space between label and buttons

    s_button_text = app_mods.get_system_info("GUI_CONFIG", "SHORT_BUTTON")
    sell_button = tk.Button(frame_top, text=s_button_text, command=short_market, bg='#EF0000',  font=font, fg='black')
    sell_button.pack(side=tk.LEFT, padx=5)  # Adds space between buttons

    # Exit App button in another line
    e_button_text = app_mods.get_system_info("GUI_CONFIG", "EXIT_BUTTON")
    exit_button = tk.Button(frame_bottom, text=e_button_text, command=exit_action, font=font)
    exit_button.pack(side=tk.RIGHT, padx=5, pady=5)  # Adds space between buttons

    # Square Off button in the same line
    sq_button_text = app_mods.get_system_info("GUI_CONFIG", "SQUARE_OFF_BUTTON")
    square_off_button = tk.Button(frame_bottom, text=sq_button_text, command=square_off_action, font=font)
    square_off_button.pack(side=tk.RIGHT, padx=5, pady=5)  # Adds space between buttons

    # Update the NIFTY index data periodically (every second)
    def update_tick_label():
        ltp = g_app_be.get_latest_tick()
        # Update the label text with the fetched NIFTY index data
        tick_label.config(text=str(ltp), font=font)
        root.after(500, update_tick_label)

    update_tick_label()

    def update_status_label(value):
        nonlocal status_label
        global g_slider_value
        if int(value) == 1:
            g_slider_value = app_mods.get_system_info("GUI_CONFIG", "SLIDER_POSN2_TEXT")
            status_label.config(text=g_slider_value)
        else:
            g_slider_value = app_mods.get_system_info("GUI_CONFIG", "SLIDER_POSN1_TEXT")
            status_label.config(text=g_slider_value)

    def slider_changed(value):
        update_status_label(value)

    # Create a slider (Scale widget) to control the ON/OFF status
    slider_frame = tk.Frame(root)
    slider_frame.pack(side=tk.BOTTOM, pady=10, padx=10, fill=tk.X)

    # Create a label to display the status
    g_slider_value = app_mods.get_system_info("GUI_CONFIG", "SLIDER_POSN1_TEXT")
    slider_font = app_mods.get_system_info("GUI_CONFIG", "SLIDER_FONT")
    slider_font_size = app_mods.get_system_info("GUI_CONFIG", "SLIDER_FONT_SIZE")
    status_label = tk.Label(slider_frame, text=g_slider_value, font=(slider_font, slider_font_size))
    status_label.pack(side=tk.BOTTOM, padx=5)

    slider = tk.Scale(slider_frame, from_=0, to=1, orient=tk.HORIZONTAL, command=slider_changed, showvalue=False)
    slider.pack(side=tk.BOTTOM, expand=True)

    # Initialize the label based on the initial value of the slider
    update_status_label(slider.get())

    # Function to handle the selection
    def show_ul_selection():
        nonlocal ul_selection
        old_value = ul_selection
        ul_selection = selection.get()
        logger.debug(f'{old_value} -> {ul_selection}')
        g_app_be.ul_symbol = ul_selection

    # Create a StringVar to store the selection and set default value to "N"

    def_value = app_mods.get_system_info("GUI_CONFIG", "RADIOBUTTON_DEF_VALUE")
    selection = tk.StringVar(value=def_value)
    # Set global variable after creating StringVar
    ul_selection = selection.get()

    # Create radio buttons for Nifty and BankNifty
    bt = app_mods.get_system_info("GUI_CONFIG", "RADIOBUTTON_1_TEXT")
    bv = app_mods.get_system_info("GUI_CONFIG", "RADIOBUTTON_1_VALUE")
    rb1 = tk.Radiobutton(root, text=bt, variable=selection, value=bv, command=show_ul_selection)
    rb1.pack(anchor="w", padx=8)

    bt = app_mods.get_system_info("GUI_CONFIG", "RADIOBUTTON_2_TEXT")
    bv = app_mods.get_system_info("GUI_CONFIG", "RADIOBUTTON_2_VALUE")
    rb2 = tk.Radiobutton(root, text=bt, variable=selection, value=bv, command=show_ul_selection)
    # banknifty_radio.pack(side="left", padx=10, pady=10)
    rb2.pack(anchor="w", padx=8)

    return root


def main():
    logger.info(f'{__app_name__}: {__version__}')
    global g_root
    global g_app_be

    r = app_mods.get_system_config()
    logger.info(f'System Config Read: {r}')

    try:
        g_app_be = TeZ_App_BE()
    except Exception as e:
        logger.info(f'Exception occured: {e}')
        return

    g_app_be.data_feed_connect()
    g_root = gui_tk_layout()
    try:
        g_root.mainloop()
    except KeyboardInterrupt:
        g_root.destroy()

    g_app_be.data_feed_disconnect()
    g_app_be.exit_app_be()
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

    if nthreads == 1 and not len(children):
        logger.info('App Shuts down Cleanly..')
    sys.exit(0)
