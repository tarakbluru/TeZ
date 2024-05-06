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
__date__ = "2024/03/23"
__deprecated__ = False
__email__ = "tarakesh.nc_at_google_mail_dot_com"
__license__ = "MIT"
__maintainer__ = "Tarak"
__status__ = "Development"
__version__ = "0.7.0_TC10"

import sys
import traceback

import app_utils as utils

logger = utils.get_logger(__name__)

try:
    import json
    import threading
    import time
    import tkinter as tk
    import winsound
    from datetime import datetime
    from multiprocessing import active_children
    from sre_constants import FAILURE, SUCCESS
    from PIL import Image, ImageTk
    import app_mods
    import pandas as pd
    from app_be import (SquareOff_Info, SquareOff_InstType, SquareOff_Mode,
                        TeZ_App_BE, TeZ_App_BE_CreateConfig)
except Exception as e:
    logger.error(traceback.format_exc())
    logger.error(("Import Error " + str(e)))
    sys.exit(1)

global g_app_be
global g_slider_value
g_app_be: TeZ_App_BE | None = None
global g_price_entry
global g_SYSTEM_FEATURE_CONFIG
global g_window_state_flag
g_pnl_window = None

g_window_state_flag=None
g_SYSTEM_FEATURE_CONFIG = None

def subwindow_exposure_cb (current_value, **kwargs):
    logger.info(json.dumps(kwargs, indent=4) + f" {current_value}")
    exch = 'NSE' if kwargs.get('Ce_Pe_Bees') == 'BEES' else 'NFO'
    match kwargs.get('Ce_Pe_Bees'):
        case 'BEES':
            inst_type = SquareOff_InstType.BEES 
        case 'CE':
            inst_type = SquareOff_InstType.CE 
        case 'PE':
            inst_type = SquareOff_InstType.PE 

    ix = kwargs.get('ix')
    ix = 'NIFTY BANK' if ix == 'BANKNIFTY' else ix
    
    sqoff_info = SquareOff_Info(mode=SquareOff_Mode.SELECT, per=(100-current_value), 
                                ul_index=ix, exch=exch, inst_type=inst_type, partial_exit=True)
    g_app_be.square_off_position(sqoff_info)
    play_notify()

subwin_config_n = app_mods.SubWindow_Cc(
    win_name='SW1',
    win_text='N:',
    slider_cb=subwindow_exposure_cb,  # Assuming you have a callback function defined
    kw_args_exposure_ce={"label_name": "CE Exposure %","ix": "NIFTY", "Ce_Pe_Bees": "CE"},  # Populate kw_args with desired key-value pairs for 'N' 'CE'
    kw_args_exposure_pe={"label_name": "PE Exposure %", "ix": "NIFTY", "Ce_Pe_Bees": "PE"}  # Populate kw_args with desired key-value pairs for 'N' 'CE'
)

subwin_config_bn = app_mods.SubWindow_Cc(
    win_name='SW2',
    win_text='BN:',
    slider_cb=subwindow_exposure_cb,  # Assuming you have a callback function defined
    kw_args_exposure_ce={"label_name": "CE Exposure %", "ix": "BANKNIFTY", "Ce_Pe_Bees": "CE"},  # Populate kw_args with desired key-value pairs for 'N' 'CE'
    kw_args_exposure_pe={"label_name": "PE Exposure %", "ix": "BANKNIFTY", "Ce_Pe_Bees": "PE"}  # Populate kw_args with desired key-value pairs for 'N' 'CE'
)

subwin_config_n_bees = app_mods.SubWindow_Cc(
    win_name='SW1',
    win_text='N:',
    slider_cb=subwindow_exposure_cb,  # Assuming you have a callback function defined
    kw_args_exposure_ce={"label_name": "Bees Exposure %", "ix": "NIFTY", "Ce_Pe_Bees": "BEES"},  # Populate kw_args with desired key-value pairs for 'N' 'CE'
    kw_args_exposure_pe=None
)

subwin_config_bn_bees = app_mods.SubWindow_Cc(
    win_name='SW2',
    win_text='BN:',
    slider_cb=subwindow_exposure_cb,  # Assuming you have a callback function defined
    kw_args_exposure_ce={"label_name": "Bees Exposure %", "ix": "BANKNIFTY", "Ce_Pe_Bees": "BEES"},  # Populate kw_args with desired key-value pairs for 'N' 'CE'
    kw_args_exposure_pe=None
)

def auto_trailer (a:app_mods.AutoTrailerData|None):
    return (g_app_be.auto_trailer(a))

def create_trade_manager_window():
    global g_trade_manager_window
    if g_trade_manager_window is None or not g_trade_manager_window.winfo_exists():
        # Create the first subwindow
        if g_SYSTEM_FEATURE_CONFIG ['tm'] == 'CE_PE':
            config1 = subwin_config_n
            config2 = subwin_config_bn

            inst_info = app_mods.get_system_info("INSTRUMENT_INFO", "INST_3")
            if inst_info['ORDER_PROD_TYPE'] != 'I':
                config1 = None

            inst_info = app_mods.get_system_info("INSTRUMENT_INFO", "INST_4")
            if inst_info['ORDER_PROD_TYPE'] != 'I':
                config2 = None
        elif g_SYSTEM_FEATURE_CONFIG ['tm'] == 'BEES':
            config1 = subwin_config_n_bees
            config2 = subwin_config_bn_bees

            inst_info = app_mods.get_system_info("INSTRUMENT_INFO", "INST_1")
            if inst_info['ORDER_PROD_TYPE'] != 'I':
                config1 = None

            inst_info = app_mods.get_system_info("INSTRUMENT_INFO", "INST_2")
            if inst_info['ORDER_PROD_TYPE'] != 'I':
                config2 = None
        else :
            ...

        g_trade_manager_window = tk.Toplevel(g_root)
        g_trade_manager_window.title("Trade Manager")
        g_trade_manager_window.iconphoto(False, g_photo)

        if config1 and config2:
            g_trade_manager_window.geometry("1000x700+{}+{}".format(g_root.winfo_x() + 80, g_root.winfo_y() + 50))
        elif config1 or config2:
            g_trade_manager_window.geometry("1000x350+{}+{}".format(g_root.winfo_x() + 80, g_root.winfo_y() + 50))
        else:
            g_trade_manager_window.geometry("1000x200+{}+{}".format(g_root.winfo_x() + 80, g_root.winfo_y() + 50))
        g_trade_manager_window.transient(g_root)  # Set the TradeManager window as transient to the root window

       # Add "Row #" label, entry box, and "Cancel" button above frame1
       # "Row #" label
        row_frame = tk.Frame(g_trade_manager_window)
        row_frame.pack(side=tk.TOP, padx=5, pady=5)

        if g_SYSTEM_FEATURE_CONFIG ['limit_order_cfg']:
            row_label = tk.Label(row_frame, text="Waiting Order Row #:")
            row_label.pack(side=tk.LEFT)

            # Entry box
            entry_box = tk.Entry(row_frame)
            entry_box.pack(side=tk.LEFT, padx=5)

            # Cancel button
            cancel_button = tk.Button(row_frame, text="Cancel", command=lambda: on_cancel_clicked(entry_box.get()))
            cancel_button.pack(side=tk.LEFT)

        sub_frame1 = tk.Frame(g_trade_manager_window, bd=2, relief=tk.GROOVE)
        sub_frame2 = tk.Frame(g_trade_manager_window, bd=2, relief=tk.GROOVE)

        if config1:
            subwin_n = app_mods.SubWindow(master=sub_frame1, 
                                        config=config1)

            subwin_n.pack(side=tk.TOP, padx=10, pady=10, anchor="w")  # Align subwindow to the left

        if config2:
            # Create the second subwindow
            subwin_p = app_mods.SubWindow(master=sub_frame1, config=config2)
            subwin_p.pack(side=tk.TOP, padx=10, pady=10, anchor="w")  # Align subwindow to the left

        # Grid sub_frame1 and sub_frame2 side by side
        sub_frame1.pack(side=tk.LEFT, padx=10, pady=15, anchor='n')

        pnl_window = app_mods.PNL_Window(master=sub_frame2)
        sub_frame2.pack(side=tk.LEFT, padx=20, pady=50, anchor='n')

        pnl_window.cb = auto_trailer

        global g_pnl_window
        g_pnl_window = pnl_window

        global g_window_state_flag
        g_window_state_flag = tk.BooleanVar()
        g_window_state_flag.set(True)  # True means window is currently visible

        # toggle_window_state(window, state_flag):

        hide_button = tk.Button(g_trade_manager_window, text="Hide TM", command=hide_subwindow)
        
        hide_button.pack(side=tk.LEFT, padx=20, pady=50, anchor='n')

        g_trade_manager_window.protocol("WM_DELETE_WINDOW", on_closing_trade_manager)
        return 1
    else:
        g_trade_manager_window.lift()  # Bring the existing window to the front
        return 2

def app_slider_position_cb_func():
    raise NotImplementedError

def on_cancel_clicked(data):
    logger.info(f"Row ID #: {data}")
    g_app_be.gen_action(action='cancel_waiting_order',data=data)


def on_closing_trade_manager():
    global g_trade_manager_window
    if g_trade_manager_window is not None:
        g_trade_manager_window.destroy()
        g_trade_manager_window = None


def qty_price_from_ui ():
    exch = app_mods.get_system_info("TRADE_DETAILS", "EXCHANGE")
    if g_SYSTEM_FEATURE_CONFIG ['limit_order_cfg']:
        price = g_price_entry.get()
        if price:
            logger.info(f"Button clicked with price: {price}")
            tp = utils.round_stock_prec(float(price))
        else:
            logger.info("Button clicked with no price entered")
            tp = None
    
    qty_str = g_qty_entry.get()
    if qty_str:
        if exch == 'NSE':
            logger.info(f"Button clicked with qty: {qty_str}")
        elif exch == 'NFO':
            logger.info(f"Button clicked with lots: {qty_str}")
        ui_qty = int (qty_str)
    else:
        logger.info("Button clicked with no qty/lots entered")
        ui_qty = None

    return ui_qty, tp

def long_market():
    logger.info(f'{datetime.now()}: Buy Click')
    if g_slider_value.lower() == 'unlocked':
        tp = None
        qty_taken = 0
        ui_qty, tp = qty_price_from_ui ()

        if ui_qty is None:
            logger.info (f'ui_qty : blank , no Trade')
            return
        try:
            qty_taken = g_app_be.market_action(action='Buy',trade_price=tp, ui_qty=ui_qty)
        except Exception:
            logger.error(traceback.format_exc())
            logger.error (f'Major Exception Occured.. Check Manually..')
        else:
            play_notify()
    else:
        logger.info('Unlock to take position')


def short_market():
    logger.info(f'{datetime.now()}: Short Click')
    if g_slider_value.lower() == 'unlocked':
        tp = None
        qty_taken = 0
        ui_qty, tp = qty_price_from_ui ()

        if ui_qty is None:
            logger.info (f'ui_qty : blank , no Trade')
            return
        try:
            qty_taken = g_app_be.market_action(action='Short',trade_price=tp, ui_qty=ui_qty)
        except Exception :
            logger.error(traceback.format_exc())
            logger.error (f'Major Exception Occured.. Check Manually..')
        else:
            play_notify()
    else:
        logger.info('Unlock to take position')

def toggle_window_state(window, state_flag):
    if window:
        if state_flag.get():
            window.withdraw()  # Hide the window
            state_flag.set(False)  # Update the flag to indicate window is hidden
        else:
            window.deiconify()  # Show the window
            state_flag.set(True)  # Update the flag to indicate window is visible
            g_app_be.show_records()

def hide_subwindow():
    toggle_window_state (g_trade_manager_window, g_window_state_flag)

def tm_action():
    logger.info(f'{datetime.now()}: TM Click')
    if create_trade_manager_window () != 1:
        toggle_window_state (g_trade_manager_window, g_window_state_flag)
    else :
        g_app_be.show_records()

def square_off_action():
    logger.info(f'{datetime.now()}: Square Off Click')
    if g_slider_value.lower() == 'unlocked':
        exch = app_mods.get_system_info("TRADE_DETAILS", "EXCHANGE")
        sqoff_info = SquareOff_Info(mode=SquareOff_Mode.SELECT, per=100.0, ul_index=g_app_be.ul_index, exch=exch)
        g_app_be.square_off_position(sqoff_info)
        play_notify()
    else:
        logger.info('Unlock to Squareoff position')


def exit_action():
    logger.info(f"{datetime.now()}: Exit Click")
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

    global g_photo

    root = tk.Tk()

    exch = app_mods.get_system_info("TRADE_DETAILS", "EXCHANGE")
    if exch == 'NSE':
        # Load the image
        image = Image.open(r'./images/bees1.jpg')
        g_photo = ImageTk.PhotoImage(image)
        # Set the image as the icon of the window
        root.iconphoto(False, g_photo)
    elif exch == 'NFO':
        # Load the image
        image = Image.open(r'./images/opt1.jpg')
        g_photo = ImageTk.PhotoImage(image)
        # Set the image as the icon of the window
        root.iconphoto(False, g_photo)
    else :
        ...

    root.title(app_mods.get_system_info("GUI_CONFIG", "APP_TITLE")+f'-{exch}')

    # Set the window size approximately to 2 inches by 2 inches
    root.geometry(app_mods.get_system_info("GUI_CONFIG", "APP_GEOMETRY"))

    # Make the window stay on top
    root.attributes("-topmost", True)

    # Create frames to organize buttons
    frame_top = tk.Frame(root)
    frame_top.pack(side=tk.TOP, pady=5)  # Adds padding above top buttons

    frame_mid = tk.Frame(root)
    frame_mid.pack(side=tk.TOP)  # Pack frame_mid below frame_top

    frame_bottom = tk.Frame(root)
    frame_bottom.pack(side=tk.BOTTOM)

    # Long and Short buttons in one line with space between them
    l_button_text = app_mods.get_system_info("GUI_CONFIG", "LONG_BUTTON")

    exch = app_mods.get_system_info("TRADE_DETAILS", "EXCHANGE")
    if exch == 'NSE':
        font = font.Font(weight="normal")
    else:
        font = font.Font(weight="bold")

    buy_button = tk.Button(frame_top, text=l_button_text, command=long_market, bg='#00EF00',  font=font, fg='black', state='disabled')
    buy_button.pack(side=tk.LEFT, padx=5)  # Adds space between buttons

    # Label to display NIFTY index data
    tick_label = tk.Label(frame_top, text="", width=7)
    tick_label.pack(side=tk.LEFT, padx=5)  # Adds space between label and buttons

    s_button_text = app_mods.get_system_info("GUI_CONFIG", "SHORT_BUTTON")
    sell_button = tk.Button(frame_top, text=s_button_text, command=short_market, bg='#EF0000',  font=font, fg='black', state="disabled")
    sell_button.pack(side=tk.LEFT, padx=5)  # Adds space between buttons

    # Exit App button in another line
    e_button_text = app_mods.get_system_info("GUI_CONFIG", "EXIT_BUTTON")
    exit_button = tk.Button(frame_bottom, text=e_button_text, command=exit_action, font=font, state="disabled")
    exit_button.pack(side=tk.RIGHT, padx=5, pady=5)  # Adds space between buttons

    # Square Off button in the same line
    sq_button_text = app_mods.get_system_info("GUI_CONFIG", "SQUARE_OFF_BUTTON")
    square_off_button = tk.Button(frame_bottom, text=sq_button_text, command=square_off_action, font=font,state="disabled")
    square_off_button.pack(side=tk.RIGHT, padx=5, pady=5)  # Adds space between buttons

    tm_button = tk.Button(frame_bottom, text="TM", command=tm_action, font=font,state="disabled")
    tm_button.pack(side=tk.RIGHT, padx=5, pady=5)  # Adds space between buttons

    def validate_price(new_value):
        if new_value == "":
            return True
        try:
            float_value = float(new_value)
            if float_value >= 0:
                return True
            else:
                return False
        except ValueError:
            return False

    validate_float = root.register(validate_price)

    if g_SYSTEM_FEATURE_CONFIG ['limit_order_cfg']:

        def on_validate_input(event):
            if event.char.isdigit() or event.char == ".":
                current_text = g_price_entry.get()
                cursor_index = g_price_entry.index(tk.INSERT)
                if event.char == "." and current_text.count(".") >= 2:
                    return "break"
                if current_text.find(".") != -1 and len(current_text[current_text.find("."):]) >= 3 and cursor_index > current_text.find("."):
                    return "break"
                return
            elif event.keysym == "BackSpace":
                if g_price_entry.selection_present():
                    start, end = g_price_entry.index(tk.SEL_FIRST), g_price_entry.index(tk.SEL_LAST)
                    g_price_entry.delete(start, end)
                elif g_price_entry.index(tk.INSERT) > 0:
                    g_price_entry.delete(g_price_entry.index(tk.INSERT) - 1)
                return "break"  # Prevent default behavior of Backspace key
            elif event.keysym == "Delete":  
                if g_price_entry.selection_present():
                    start, end = g_price_entry.index(tk.SEL_FIRST), g_price_entry.index(tk.SEL_LAST)
                    g_price_entry.delete(start, end)
                elif g_price_entry.index(tk.INSERT) < len(g_price_entry.get()):
                    g_price_entry.delete(g_price_entry.index(tk.INSERT))
                return "break"  # Prevent default behavior of Delete key
            elif event.keysym in ["Left", "Right"]:  
                return
            else:
                return "break"

        label_entry_price = tk.Label(frame_mid, text="Entry Price:")
        label_entry_price.pack(side=tk.LEFT, padx=(5, 10)) 

        global g_price_entry
        g_price_entry = tk.Entry(frame_mid, width=8, validate="key", validatecommand=(validate_float, '%P'))
        g_price_entry.pack(side=tk.LEFT, padx=(0, 5))
        g_price_entry.bind("<Key>", on_validate_input)

    def validate_qty(new_value):
        if new_value == "":
            return True
        try:
            int_value = int(new_value)
            if int_value >= 0:
                return True
            else:
                return False
        except ValueError:
            return False


    def on_validate_qty_input(event):
        if event.char.isdigit():
            current_text = g_qty_entry.get()
            if len(current_text) >= 4:
                return "break"
            return
        elif event.keysym == "BackSpace":
            if g_qty_entry.selection_present():
                start, end = g_qty_entry.index(tk.SEL_FIRST), g_qty_entry.index(tk.SEL_LAST)
                g_qty_entry.delete(start, end)
            elif g_qty_entry.index(tk.INSERT) > 0:
                g_qty_entry.delete(g_qty_entry.index(tk.INSERT) - 1)
            return "break"  # Prevent default behavior of Backspace key
        elif event.keysym == "Delete":  
            if g_qty_entry.selection_present():
                start, end = g_qty_entry.index(tk.SEL_FIRST), g_qty_entry.index(tk.SEL_LAST)
                g_qty_entry.delete(start, end)
            elif g_qty_entry.index(tk.INSERT) < len(g_qty_entry.get()):
                g_qty_entry.delete(g_qty_entry.index(tk.INSERT))
            return "break"  # Prevent default behavior of Delete key
        elif event.keysym in ["Left", "Right"]:  
            return
        else:
            return "break"
        

    validate_int = root.register(validate_qty)

    exch = app_mods.get_system_info("TRADE_DETAILS", "EXCHANGE")
    if exch == 'NSE':
        qty_str = 'Qty:'
    elif exch == 'NFO':
        qty_str = 'Lots:'

    label_qty = tk.Label(frame_mid, text=qty_str)
    label_qty.pack(side=tk.LEFT, padx=(5, 10)) 

    global g_qty_entry
    g_qty_entry = tk.Entry(frame_mid, width=5, validate="key", validatecommand=(validate_int, '%P'))
    g_qty_entry.insert(0, "1")  # Insert the default value "1"
    g_qty_entry.pack(side=tk.LEFT, padx=(0, 5))
    g_qty_entry.bind("<Key>", on_validate_qty_input)

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

    def update_button_states(value):
        if int(value) == 1:
            buy_button.config(state="normal")
            sell_button.config(state="normal")
            square_off_button.config(state="normal")
            exit_button.config(state='normal')
            tm_button.config(state='normal')
        else:
            buy_button.config(state="disabled")        
            sell_button.config(state="disabled")
            square_off_button.config(state="disabled")
            exit_button.config(state='disabled')
            tm_button.config(state='disabled')

    def slider_changed(value):
        update_button_states (value)
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
        logger.info(f'{old_value} -> {ul_selection}')
        g_app_be.ul_index = ul_selection
        clear_price_entry()

    def clear_price_entry():
        if g_price_entry:
            g_price_entry.delete(0, tk.END)

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
    rb2.pack(anchor="w", padx=8)

    return root

def system_sqoff_cb ():
    global g_pnl_window
    if g_pnl_window:
        g_pnl_window.ui_update_sys_sq_off()


def is_exp_date_lapsed(date_string):
    try:
        # Convert the date string to a datetime object
        date_object = datetime.strptime(date_string, "%d-%b-%Y")  # Adjust the format according to your date string
        # Get the current date and time
        current_date = datetime.now().date()
        # Compare the date with the current date
        if date_object.date() < current_date:
            return True  # Date has already lapsed
        else:
            return False  # Date is in the future
    except ValueError:
        return False  # Invalid date string format
    
def check_expiry_dates(data):
    
    for key, value in data.items():
        if isinstance(value, dict):
            # If the value is a dictionary, recursively check for expiry dates
            check_expiry_dates(value)
        elif key == 'EXPIRY_DATE':
            # If the key is 'expiry_date', check if the value has lapsed
            expiry_date = value
            if expiry_date and is_exp_date_lapsed(expiry_date):
                logger.info(f"Expiry date: {expiry_date} has already lapsed.")
                sys.exit (1)

def get_nth_nearest_expiry_date(symbol_prefix, n, url='EXPIRY_DATE_CALC_URL1'):
    file_url = app_mods.get_system_info("TRADE_DETAILS", url)
    symboldf = pd.read_csv(file_url)
    symboldf = symboldf.rename(columns=str.lower)
    symboldf = symboldf.rename(columns=lambda x: x.strip())
    symboldf['expiry'] = pd.to_datetime(symboldf['expiry'], format='%d-%b-%Y')
    today = pd.Timestamp.now().floor('D').date()
    symboldf['days_until_expiry'] = (symboldf['expiry'] - pd.Timestamp(today)).dt.days

    if url == 'EXPIRY_DATE_CALC_URL2':
        nfodf = symboldf[(symboldf.last_price.notnull()) & 
                        symboldf['tradingsymbol'].str.startswith(symbol_prefix) & 
                        (symboldf.exchange == 'NSE_FO') & 
                        (symboldf.tick_size == 0.05) & 
                        (symboldf.instrument_type == 'OPTIDX')]
    else :
        nfodf = symboldf[(symboldf['tradingsymbol'].str.startswith(symbol_prefix)) & 
                         (symboldf.exchange == 'NFO') & 
                         (symboldf.ticksize == 0.05) & 
                         (symboldf.instrument == 'OPTIDX')]
    
    # Get unique expiry dates and sort them
    unique_expiry_dates = sorted(nfodf['expiry'].unique())

    # Check if there are enough unique expiry dates
    if len(unique_expiry_dates) < n:
        return None  # Return None if there are not enough unique expiry dates

    # Get the nth unique expiry date
    nth_expiry_date = unique_expiry_dates[n - 1]
    
    return pd.Timestamp(nth_expiry_date).strftime('%d-%b-%Y').upper()

def update_expiry_date(symbol_prefix):
    exp_date = get_nth_nearest_expiry_date (symbol_prefix, n=1)
    if exp_date:
        current_date = datetime.now().date()
        # Convert expir dates to datetime object
        exp_date_obj = datetime.strptime(exp_date, '%d-%b-%Y').date()
        opt_diff = (exp_date_obj - current_date).days
        if opt_diff <= 0:
            exp_date = get_nth_nearest_expiry_date (symbol_prefix, n=2)
        app_mods.replace_system_config ('SYMBOL', symbol_prefix, 'EXCHANGE', 'NFO', 'EXPIRY_DATE', exp_date)

def update_strike(symbol_prefix, ce_or_pe):
    if symbol_prefix == 'NIFTY':
        inst_info = app_mods.get_system_info("INSTRUMENT_INFO", "INST_3")
    else:
        inst_info = app_mods.get_system_info("INSTRUMENT_INFO", "INST_4")

    exp_date = inst_info['EXPIRY_DATE']
    # Convert expiry dates to datetime object
    exp_date_obj = datetime.strptime(exp_date, '%d-%b-%Y').date()
    current_date = datetime.now().date()
    # Calculate the difference between expiry date and current date
    opt_diff = (exp_date_obj - current_date).days

    if ce_or_pe == 'CE':
        ce_or_pe_offset = 'CE_STRIKE_OFFSET'
        if opt_diff == 1:
            strike_offset = -1
        else:
            strike_offset = 0        
    else:
        ce_or_pe_offset = 'PE_STRIKE_OFFSET'
        if opt_diff == 1:
            strike_offset = 1
        else:
            strike_offset = 0
    app_mods.replace_system_config ('SYMBOL', symbol_prefix, 'EXCHANGE', 'NFO', ce_or_pe_offset, strike_offset)


def update_system_config ():
    exch = app_mods.get_system_info("TRADE_DETAILS", "EXCHANGE")
    if exch == 'NFO':
        exp_date_cfg = app_mods.get_system_info("TRADE_DETAILS", "EXPIRY_DATE_CFG")
        if exp_date_cfg == 'AUTO':
            update_expiry_date('NIFTY')
            update_expiry_date('BANKNIFTY')

        offset_cfg = app_mods.get_system_info("TRADE_DETAILS", "CE_STRIKE_OFFSET_CFG")
        if offset_cfg == 'AUTO':
            update_strike('NIFTY','CE')
            update_strike('BANKNIFTY','CE')

        offset_cfg = app_mods.get_system_info("TRADE_DETAILS", "PE_STRIKE_OFFSET_CFG")
        if offset_cfg == 'AUTO':
            update_strike('NIFTY','PE')
            update_strike('BANKNIFTY','PE')

def main():
    logger.info(f'{__app_name__}: {__version__}')
    global g_root
    global g_app_be
    global g_trade_manager_window
    global g_SYSTEM_FEATURE_CONFIG

    r = app_mods.get_system_config()
    logger.info(f'System Config Read: {r}')

    logger.info(f'Updating System Config Expiry Date and Offsets: {r}')
    update_system_config ()

    g_SYSTEM_FEATURE_CONFIG = dict()
    g_SYSTEM_FEATURE_CONFIG ['limit_order_cfg'] = True if app_mods.get_system_info("SYSTEM", "LMT_ORDER_FEATURE")=='ENABLED' else False
    
    exch = app_mods.get_system_info("TRADE_DETAILS", "EXCHANGE")

    g_SYSTEM_FEATURE_CONFIG ['tm'] = 'CE_PE' if exch == 'NFO' else None
    if not g_SYSTEM_FEATURE_CONFIG ['tm']:
        g_SYSTEM_FEATURE_CONFIG ['tm'] = 'BEES' if exch == 'NSE' else None
    logger.info (f'{json.dumps(g_SYSTEM_FEATURE_CONFIG, indent=2)}')

    # Verification Step: 
    # If the exchange is NFO and the expiry dates are already lapsed, 
    # it should be flagged.
    if exch == 'NFO':
        inst_info = app_mods.get_system_info("TRADE_DETAILS", "INSTRUMENT_INFO")
        check_expiry_dates (inst_info)
        logger.info (f'NIFTY OPTION: {json.dumps(app_mods.get_system_info("INSTRUMENT_INFO", "INST_3"),indent=2)}')
        logger.info (f'BANK NIFTY OPTION: {json.dumps(app_mods.get_system_info("INSTRUMENT_INFO", "INST_4"),indent=2)}')

    if exch == 'NSE':
        logger.info (f'NIFTYBEES: {json.dumps(app_mods.get_system_info("INSTRUMENT_INFO", "INST_1"),indent=2)}')
        logger.info (f'BANKBEES: {json.dumps(app_mods.get_system_info("INSTRUMENT_INFO", "INST_2"),indent=2)}')

    app_be_cc_cfg = TeZ_App_BE_CreateConfig(g_SYSTEM_FEATURE_CONFIG ['limit_order_cfg'], system_sqoff_cb=system_sqoff_cb)
    try:
        g_app_be = TeZ_App_BE(app_be_cc_cfg)
    except app_mods.tiu.LoginFailureException:
        logger.info (f'Login Failure')
        return
    except Exception as e:
        logger.info(traceback.format_exc())
        logger.info(f'Exception occured: {e}')
        return

    try:
        if g_app_be.data_feed_connect() == FAILURE:
            g_app_be.data_feed_disconnect()
            logger.error (f'Web socket Failure, exiting')
            sys.exit (1)
    except KeyboardInterrupt:
        logger.info (f'CTRL+C interrupt..Exiting')
        sys.exit (2)
    except Exception as e:
        logger.error (f'Exception Occured {repr(e)}')
        sys.exit (3)
    else:
        ...
    g_root = gui_tk_layout()
    g_trade_manager_window = None

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
