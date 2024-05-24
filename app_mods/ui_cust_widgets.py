"""
File: ui_cust_widgets.py
Author: [Tarakeshwar NC]
Date: March 15, 2024
Description:  This script provides custom widgets.
"""
# Copyright (c) [2024] [Tarakeshwar N.C]
# This file is part of the TeZ project.
# It is subject to the terms and conditions of the MIT License.
# See the file LICENSE in the top-level directory of this distribution
# for the full text of the license.


import sys
import traceback

from app_utils import app_logger

logger = app_logger.get_logger(__name__)

try:
    import datetime
    import tkinter as tk
    from dataclasses import dataclass
    import threading 
    from tkinter import ttk, messagebox
    from typing import Callable, List

    from .shared_classes import AutoTrailerData, AutoTrailerEvent, UI_State

except Exception as e:
    logger.debug(traceback.format_exc())
    logger.error(("Import Error " + str(e)))
    sys.exit(1)


@dataclass
class CustomCreateConfig:
    win_name: str = 'N1'
    ix: str = 'N'
    label_text: str = "CE"
    button_text: str = "Click Me"
    slider_length: int = 200
    slider_width: int = 10
    initial_slider_value: float = 100.0
    step_value: float = 10.0
    slider_cb: Callable = None
    slider_kwargs: dict = None

    def __post_init__(self):
        if self.slider_cb is None:
            raise TypeError("slider_cb is a required parameter and must be a callable function")
        if self.slider_kwargs is None:
            self.slider_kwargs = {}  # Initialize kwargs if it's None


class CustomWidget(tk.Frame):
    def __init__(self, master=None, config=None, **kwargs):
        super().__init__(master, **kwargs)
        self.config = config if config else CustomCreateConfig()

        # Create a subframe with a border
        subframe = tk.Frame(self, borderwidth=1, relief="solid")
        subframe.pack(side=tk.LEFT, padx=5, pady=5)

        self.label = ttk.Label(subframe, text=self.config.label_text)
        self.label.pack(side=tk.TOP, anchor="w", padx=10, pady=(0, 2))

        self._slider_position = self.config.initial_slider_value

        # Create a standard tk.Scale widget
        self.slider = tk.Scale(subframe, from_=100, to=0, orient="vertical", length=self.config.slider_length,
                               width=self.config.slider_width, resolution=self.config.step_value)
        self.slider.set(self.config.initial_slider_value)  # Set initial value
        self.slider.pack(fill="y", padx=5, pady=5)

        self.button = ttk.Button(subframe, text=self.config.button_text, command=self.button_clicked)
        self.button.pack(fill="x", padx=5, pady=5)

        self.reset_button = ttk.Button(subframe, text='Reset', command=self.reset_button_clicked)
        self.reset_button.pack(fill="x", padx=5, pady=5)

    def reset_button_clicked(self):
        self.slider_position = 100.0

    def button_clicked(self):
        current_value = self.slider.get()
        self.config.slider_cb(current_value, **self.config.slider_kwargs)
        logger.debug(f"Slider position ({self.config.ix}: {self.config.label_text}): {current_value}%")

    @property
    def name(self):
        return self.config.win_name

    @property
    def slider_position(self):
        return self._slider_position

    @slider_position.setter
    def slider_position(self, new_position):
        self.slider.set(new_position)


@dataclass
class SubWindow_Cc:
    win_name: str = 'SW'
    win_text: str = 'N:'
    slider_cb: Callable = None
    kw_args_exposure_ce: dict = None  # Define kw_args_ce as a dictionary for CE
    kw_args_exposure_pe: dict = None  # Define kw_args_pe as a dictionary for PE

    def __post_init__(self):
        if self.slider_cb is None:
            raise TypeError("slider_cb is a required parameter and must be a callable function")
        if self.kw_args_exposure_ce is None:
            self.kw_args_exposure_ce = {}  # Initialize kw_args if it's None
        if self.kw_args_exposure_pe is None:
            self.kw_args_exposure_pe = {}  # Initialize kw_args if it's None


class SubWindow(tk.Frame):
    def __init__(self, master=None, config: SubWindow_Cc = None, **kwargs):
        super().__init__(master, **kwargs)

        self.cws: List[CustomWidget] = []

        # Add a label indicating Nifty (N:) at the top-left corner of frame1
        label1 = tk.Label(self, text=config.win_text, font=("Arial", 18, "bold"))
        label1.pack(side=tk.TOP, anchor="nw", padx=10, pady=(5, 2))

        if config.kw_args_exposure_ce:
            # Configure custom widget for CE exposure
            custom_config_ce = CustomCreateConfig(
                win_name=config.win_name + '_Wid_1',
                ix=config.win_text,
                label_text=config.kw_args_exposure_ce['label_name'],
                button_text="Partial SqOff",
                slider_length=100,
                slider_width=10,
                initial_slider_value=100.0,
                slider_cb=config.slider_cb,
                slider_kwargs=config.kw_args_exposure_ce)
            self.custom_widget_ce = CustomWidget(self, config=custom_config_ce)
            self.custom_widget_ce.pack(side=tk.LEFT, padx=10, pady=10)

            self.cws.append(self.custom_widget_ce)

        if config.kw_args_exposure_pe:
            # Configure custom widget for PE exposure
            custom_config_pe = CustomCreateConfig(
                win_name=config.win_name + '_Wid_2',
                ix=config.win_text,
                label_text=config.kw_args_exposure_pe['label_name'],
                button_text="Partial SqOff",
                slider_length=100,
                slider_width=10,
                initial_slider_value=100.0,
                slider_cb=config.slider_cb,
                slider_kwargs=config.kw_args_exposure_pe)
            self.custom_widget_pe = CustomWidget(self, config=custom_config_pe)
            self.custom_widget_pe.pack(side=tk.LEFT, padx=10, pady=10)

            self.cws.append(self.custom_widget_pe)

    def get_slider_names(self):
        slider_names: List[CustomWidget] = []

        for wid in self.cws:
            slider_names.append(wid.name)

        return slider_names

    def set_slider_position(self, wid_name: str, position):
        for wid in self.cws:
            if wid_name == wid.name:
                wid.slider_position = position

class EntryWithButtons(tk.Frame):
    def __init__(self, master=None, label:str|None = None,init_value=None, min_value=None, **kw):
        super().__init__(master, **kw)
        
        self.label = tk.Label(self, text=label, width=7, font=("Arial", 10), justify="left")
        self.label.grid(row=0, column=0, padx=2, pady=5, sticky='w')
        
        # Create minus button
        self.minus_button = ttk.Button(self, text="-", width=1)
        self.minus_button.grid(row=0, column=1)
        self.minus_button.bind("<ButtonPress-1>", self.start_decrement)
        self.minus_button.bind("<ButtonRelease-1>", self.stop_decrement)

        self.min_value = min_value

        def validate_entry(event):
            nonlocal self
            entry_text = self.entry.get()
            if entry_text.count('-') > 1:
                # If more than one negative sign is present, remove the last one entered
                entry_text = entry_text[:-1]
                self.entry.delete(0, tk.END)
                self.entry.insert(0, entry_text)
            if '+' in entry_text:
                # If a positive sign is found, remove it
                entry_text = entry_text.replace('+', '')
                self.entry.delete(0, tk.END)
                self.entry.insert(0, entry_text)            

        # Create entry box
        self.entry = ttk.Entry(self,width=9)
        self.entry.grid(row=0, column=2, padx=1)
        self.entry.bind("<KeyRelease>", validate_entry)

        # Create plus button
        self.plus_button = ttk.Button(self, text="+", width=1)
        self.plus_button.grid(row=0, column=3)
        self.plus_button.bind("<ButtonPress-1>", self.start_increment)
        self.plus_button.bind("<ButtonRelease-1>", self.stop_increment)

        # Variable to store the value
        self.value = tk.IntVar()
        if init_value:
            self.value.set(init_value)
        else:
            self.value.set(0)
        self.entry.config(textvariable=self.value)

        # Variables to store the job IDs for incrementing and decrementing
        self.increment_job = None
        self.decrement_job = None

    def disable_buttons (self):
        self.plus_button.config(state="disabled")
        self.minus_button.config(state="disabled")

    def enable_buttons (self):
        self.plus_button.config(state="normal")
        self.minus_button.config(state="normal")

    def disable (self):
        self.disable_buttons ()
        self.disable_entry ()

    def enable (self):
        self.enable_buttons ()
        self.enable_entry ()

    def start_increment(self, event=None):
        self.increment()
        self.increment_job = self.after(100, self.start_increment)  # Repeat every 500 ms
        
    def stop_increment(self, event=None):
        if self.increment_job:
            self.after_cancel(self.increment_job)

    def start_decrement(self, event=None):
        self.decrement()
        self.decrement_job = self.after(100, self.start_decrement)  # Repeat every 500 ms

    def stop_decrement(self, event=None):
        if self.decrement_job:
            self.after_cancel(self.decrement_job)

    def increment(self):
        self.value.set(self.value.get() + 1)

    def decrement(self):
        if self.min_value is None or (self.min_value is not None and abs(self.value.get()) > abs(self.min_value)):
            self.value.set(self.value.get() - 1)

    def disable_entry(self):
        self.entry.config(state='disabled')

    def enable_entry(self):
        self.entry.config(state='normal')

class PNL_Window (tk.Frame):
    def __init__(self, master=None, label:str|None = None,init_value=None, min_value=None, **kw):
        super().__init__(master, **kw)

        self.lock = threading.Lock()

        self._cb:None|Callable = None
        self._cb_running = False
        self._cb_running_lock = threading.Lock()
        self.cb_ts = None
        self.error_shown = False

        title = tk.Label(master=master, text='DayWise PNL Tracker', font=('Arial', 12, "bold"))
        title.grid(row=0, column=1, padx=5, pady=5, sticky='w')

        self.sl = EntryWithButtons(master=master, label="SL:", init_value=-1000)
        self.sl.grid(row=1, column=0, padx=5, pady=5, sticky='w')

        self.target = EntryWithButtons(master=master, label="Target:", init_value=2000, min_value=0)
        self.target.grid(row=1, column=1, padx=5, pady=5, sticky='w')

        self.label = tk.Label(master=master, text='All Values in INR', width=15, font=("Arial", 10), justify="left")
        self.label.grid(row=1, column=2, padx=5, pady=5, sticky='w')

        self.mvto_cost = EntryWithButtons(master=master, label="Mov2Cost:", init_value=300, min_value=0)
        self.mvto_cost.grid(row=2, column=0, padx=5, pady=5, sticky='w')

        self.trail_after = EntryWithButtons(master=master, label="Trail_After:", init_value=400, min_value=0)
        self.trail_after.grid(row=2, column=1, padx=5, pady=5, sticky='w')

        self.trail_by = EntryWithButtons(master=master, label="Trail_by:", init_value=300, min_value=0)
        self.trail_by.grid(row=2, column=2, padx=5, pady=5, sticky='w')

        self.radio_var_local = 'Manual'

        self.radio_var = tk.StringVar()  # set default value to "Manual"

        rb2 = tk.Radiobutton(master=master, text="Manual", variable=self.radio_var, 
                             value="Manual", command=self.__on_radio_button_selected__)
        rb2.grid(row=3, column=0, padx=5, pady=5, sticky='w')

        rb1 = tk.Radiobutton(master=master, text="Auto", variable=self.radio_var, 
                             value="Auto", command=self.__on_radio_button_selected__)
        rb1.grid(row=3, column=1, padx=5, pady=5, sticky='w')

        self.radio_var.set(self.radio_var_local)

        self.pnl_label = tk.Label(master=master, text='PnL (In Rs): ', font=('Arial', 12, "bold"))
        self.pnl_label.grid(row=4, column=0, padx=5, pady=5, sticky='e')
    
        self.pnl_value_label = tk.Label(master=master, text='', font=('Arial', 10))
        self.pnl_value_label.grid(row=4, column=1, padx=5, pady=5, sticky='w')

        # # # Create 'Start Tracking' button
        # start_tracking_button = tk.Button(master=master, text="Start Tracking", command=lambda: print("Start Tracking"))
        # start_tracking_button.grid(row=3, column=0, pady=5)

        # # # Create 'Stop Tracking' button
        # stop_tracking_button = tk.Button(master=master, text="Stop Tracking", command=lambda: print("Stop Tracking"))
        # stop_tracking_button.grid(row=3, column=1, pady=5)

        # Schedule scanning and printing function
        self.scan_and_print_values()

    def set_cb_value(self, new_value:Callable):
        self._cb = new_value
    
    cb = property(None, set_cb_value)

    def __on_radio_button_selected__(self):
        with self.lock:
            if self.radio_var.get() == 'Auto':
                logger.info ('Manual -> Auto')
                self.sl.disable_entry()
                self.target.disable_entry()
                self.mvto_cost.disable_entry()
                self.trail_after.disable_entry()
                self.trail_by.disable_entry()
            elif self.radio_var.get() == 'Manual':
                logger.info ('Auto -> Manual')
                self.sl.enable_entry()
                self.target.enable_entry()
                self.mvto_cost.enable_entry()
                self.trail_after.enable_entry()
                self.trail_by.enable_entry()
            logger.debug(f"Selected option: {self.radio_var.get()} callback last timestamp: {self.cb_ts}")

    def ui_update_sys_sq_off (self):
        self.radio_var_local = 'Manual'
        self.radio_var.set(self.radio_var_local)
        with self.lock:
            self.sl.enable_entry()
            self.target.enable_entry()
            self.mvto_cost.enable_entry()
            self.trail_after.enable_entry()
            self.trail_by.enable_entry()
            self.mvto_cost.enable_buttons ()

    def scan_and_print_values(self):

        with self._cb_running_lock:
            if self._cb_running: 
                logger.debug (f'cb_running: ..callback last timestamp: {self.cb_ts}')
                return
            self._cb_running = True

        # Function to retrieve values and print them
        try:
            self.cb_ts = datetime.datetime.now()
            if self._cb is not None:
                if self.radio_var.get() == 'Auto':            
                    # print(f"now: {datetime.datetime.now()}: SL: {sl_value}, Target: {target_value}, Mv2Cst: {mvto_cost_value}, Trail_After: {trail_after_value}, Trail_by: {trail_by_value}")
                    
                    ui_reset = False
                    if self.radio_var_local == 'Manual':
                        ui_reset = True
                        self.radio_var_local = 'Auto'
                    
                    sl = self.sl.value.get()
                    target = self.target.value.get()
                    mvto_cost = self.mvto_cost.value.get()
                    trail_after = self.trail_after.value.get()
                    trail_by = self.trail_by.value.get()

                    atd = AutoTrailerData (sl=sl, target=target, mvto_cost=mvto_cost, 
                                           trail_after=trail_after, trail_by=trail_by, 
                                           ui_reset=ui_reset)

                    ate:AutoTrailerEvent = self._cb (atd)
                    self.pnl_value_label.config(text=str(ate.pnl))

                    if ate.mvto_cost_ui == UI_State.DISABLE:
                        with self.lock:
                            self.mvto_cost.disable_buttons ()
                    if ate.mvto_cost_ui == UI_State.ENABLE:
                        with self.lock:
                            self.mvto_cost.enable_buttons ()

                    if ate.trail_sl_ui == UI_State.DISABLE:
                        with self.lock:
                            self.trail_after.disable_buttons ()

                    if ate.trail_sl_ui == UI_State.ENABLE:
                        with self.lock:
                            self.trail_after.enable_buttons ()

                    if ate.sq_off_done:
                        with self.lock:
                            self.radio_var_local = 'Manual'
                            self.radio_var.set(self.radio_var_local)
                            self.sl.enable_entry()
                            self.target.enable_entry()
                            self.mvto_cost.enable_entry()
                            self.trail_after.enable_entry()
                            self.trail_by.enable_entry()
                            self.mvto_cost.enable_buttons ()
                            self.trail_after.enable_buttons ()
                            self.trail_by.enable_buttons ()

                elif self.radio_var.get() == 'Manual':
                    self.radio_var_local = 'Manual'
                    ate = self._cb (None)
                    self.pnl_value_label.config(text=f'{ate.pnl:.2f}')
            self.error_shown = False
        except tk.TclError as e:
            if not self.error_shown:
                messagebox.showerror("Error", f"A TclError occurred: {e}")
                self.error_shown = True

        except Exception as e:
            logger.error (f'Exception occured : {str(e)}')
            logger.debug(traceback.format_exc())

        finally:
            with self._cb_running_lock: 
                self._cb_running = False

        # Schedule to run again after 1000 ms (1 second)
        self.after(1000, self.scan_and_print_values)

    def grid_in_root(self, row, column):
        self.grid(row=row, column=column)  # Grid the PNL_Window instance within the root window
       
        return
