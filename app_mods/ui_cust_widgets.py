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

class PNL_Window(tk.Frame):
    def __init__(self, master=None, ui_update_frequency=2.0, auto_trailer=None, **kw):
        """
        Initialize the PNL Window
        
        Args:
            master: The parent widget
            ui_update_frequency: Frequency for UI updates in seconds
            auto_trailer: The AutoTrailer instance for direct access (required)
            **kw: Additional keyword arguments for Frame
        """
        super().__init__(master, **kw)

        self.lock = threading.Lock()
        self._cb_running = False
        self._cb_running_lock = threading.Lock()
        self.error_shown = False

        # Store references
        self.ui_update_frequency = ui_update_frequency
        self.auto_trailer = auto_trailer  # Direct reference to the AutoTrailer instance

        # Regular UI initialization
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

        # Radio buttons for mode selection
        self.radio_var = tk.StringVar(value='Manual')  # Start in Manual mode

        rb_manual = tk.Radiobutton(master=master, text="Manual", variable=self.radio_var,
                                  value="Manual", command=self._on_mode_change)
        rb_manual.grid(row=3, column=0, padx=5, pady=5, sticky='w')

        rb_auto = tk.Radiobutton(master=master, text="Auto", variable=self.radio_var,
                                value="Auto", command=self._on_mode_change)
        rb_auto.grid(row=3, column=1, padx=5, pady=5, sticky='w')

        self.pnl_label = tk.Label(master=master, text='PnL (In Rs): ', font=('Arial', 12, "bold"))
        self.pnl_label.grid(row=4, column=0, padx=5, pady=5, sticky='e')

        self.pnl_value_label = tk.Label(master=master, text='', font=('Arial', 10))
        self.pnl_value_label.grid(row=4, column=1, padx=5, pady=5, sticky='w')

        # Start the UI update loop
        self.start_ui_updates()

    def start_ui_updates(self):
        """Start the UI update timer"""
        self.update_ui()
        
    def _on_mode_change(self):
        """
        Handle radio button mode changes immediately
        This method is called directly when the radio button is clicked
        """
        new_mode = self.radio_var.get()
        logger.info(f'Mode changed to: {new_mode}')
        
        if new_mode == 'Auto':
            # Switching to Auto mode - validate parameters first
            logger.info('Manual -> Auto')
            
            # Get parameters from UI, ensure negative SL value
            sl_value = self.sl.value.get()
            if sl_value > 0:
                sl_value = -sl_value
                logger.debug(f"TRACE: Converted positive SL to negative: {sl_value}")
            
            target_value = self.target.value.get()
            
            # Get current PNL for validation
            current_pnl = 0.0
            if self.auto_trailer:
                current_pnl = self.auto_trailer.current_state.pnl
            
            # Validate parameters before activating
            if current_pnl <= sl_value:
                logger.warning(f"Cannot activate - current PNL ({current_pnl}) already below SL threshold ({sl_value})")
                messagebox.showwarning("Invalid Parameters", 
                                    f"Current PNL ({current_pnl}) is already below Stop Loss ({sl_value}).\n"
                                    f"Please set a lower Stop Loss value.")
                # Revert to Manual mode
                self.radio_var.set('Manual')
                return
                
            if current_pnl >= target_value:
                logger.warning(f"Cannot activate - current PNL ({current_pnl}) already above target threshold ({target_value})")
                messagebox.showwarning("Invalid Parameters", 
                                    f"Current PNL ({current_pnl}) is already above Target ({target_value}).\n"
                                    f"Please set a higher Target value.")
                # Revert to Manual mode
                self.radio_var.set('Manual')
                return
            
            # Parameters are valid, update UI controls
            self.sl.disable_entry()
            self.target.disable_entry()
            self.mvto_cost.disable_entry()
            self.trail_after.disable_entry()
            self.trail_by.disable_entry()
            
            # Create auto trailer data with parameters from UI
            atd = AutoTrailerData(
                sl=sl_value,
                target=self.target.value.get(),
                mvto_cost=self.mvto_cost.value.get(),
                trail_after=self.trail_after.value.get(),
                trail_by=self.trail_by.value.get(),
                ui_reset=True  # Signal mode change
            )
            
            # Debug values
            logger.debug(f"TRACE: Auto Trailer Values: SL={atd.sl}, Target={atd.target}, MvtoCost={atd.mvto_cost}, TrailAfter={atd.trail_after}, TrailBy={atd.trail_by}")
            
            # Enable auto trading immediately
            if self.auto_trailer:
                logger.debug("TRACE: Calling auto_trailer.process(atd)")
                result = self.auto_trailer.process(atd)
                logger.debug(f"TRACE: Result from auto_trailer.process: {result}")
                
                # Check if auto trailer rejected our parameters
                if result.sq_off_done:
                    logger.warning("Auto trader rejected parameters")
                    messagebox.showwarning("Auto Trading", "Parameters rejected by auto trader.")
                    # Revert to Manual mode
                    self.radio_var.set('Manual')
                    self._on_mode_change()  # Call again to update UI for Manual mode
                    return
            else:
                logger.error("TRACE: self.auto_trailer is None!")
                # Revert to Manual mode
                self.radio_var.set('Manual')
                return
            
        elif new_mode == 'Manual':
            # Switching to Manual mode - disable auto trader immediately
            logger.info('Auto -> Manual')
            
            # Update UI controls
            self.sl.enable_entry()
            self.target.enable_entry()
            self.mvto_cost.enable_entry()
            self.trail_after.enable_entry()
            self.trail_by.enable_entry()
            
            # Disable auto trading immediately
            if self.auto_trailer:
                logger.debug("TRACE: Calling auto_trailer.process(None)")
                self.auto_trailer.process(None)
            else:
                logger.error("TRACE: self.auto_trailer is None!")

    def update_ui(self):
        """
        Update the UI with current state information
        This runs on a regular timer and updates PNL, button states, etc.
        """
        with self._cb_running_lock:
            if self._cb_running:
                return
            self._cb_running = True
        
        try:
            # Get current state from auto trader without deactivating it!
            if self.auto_trailer:
                # IMPORTANT: Don't call process(None) - this causes deactivation!
                # Just access current_state directly
                ate = self.auto_trailer.current_state
                
                # Update PNL display
                self.pnl_value_label.config(text=f"{ate.pnl:.2f}")
                
                # Handle state updates if in Auto mode
                if self.radio_var.get() == 'Auto':
                    # Update button states based on auto trader state
                    if ate.mvto_cost_ui == UI_State.DISABLE:
                        self.mvto_cost.disable_buttons()
                    elif ate.mvto_cost_ui == UI_State.ENABLE:
                        self.mvto_cost.enable_buttons()

                    if ate.trail_sl_ui == UI_State.DISABLE:
                        self.trail_after.disable_buttons()
                    elif ate.trail_sl_ui == UI_State.ENABLE:
                        self.trail_after.enable_buttons()
                    
                    # Handle square off if needed
                    if ate.sq_off_done:
                        # Switch back to Manual mode
                        self.radio_var.set('Manual')
                        self._on_mode_change()  # Trigger the mode change handler
        
        except tk.TclError as e:
            if not self.error_shown:
                messagebox.showerror("Error", f"A TclError occurred: {e}")
                self.error_shown = True
                
        except Exception as e:
            logger.error(f'Exception occurred: {str(e)}')
            logger.debug(traceback.format_exc())
            
        finally:
            with self._cb_running_lock:
                self._cb_running = False
        
        # Schedule next update
        self.after(int(self.ui_update_frequency * 1000), self.update_ui)
        
    def ui_update_sys_sq_off(self):
        """Update UI when system square off happens"""
        self.radio_var.set('Manual')
        self._on_mode_change()  # Trigger mode change handler to update UI

    def grid_in_root(self, row, column):
        """Grid the PNL_Window instance within the root window"""
        self.grid(row=row, column=column)
        
def show_custom_messagebox(title, message, timeout=3000):
    def on_close():
        top.destroy()

    def timeout_close():
        if top.winfo_exists():
            top.destroy()

    top = tk.Toplevel()
    top.title(title)
    top.geometry("300x150")
    top.grab_set()  # Prevent interaction with other windows

    label = ttk.Label(top, text=message, wraplength=250)
    label.pack(pady=20)

    button = ttk.Button(top, text="OK", command=on_close)
    button.pack(pady=10)

    top.after(timeout, timeout_close)
