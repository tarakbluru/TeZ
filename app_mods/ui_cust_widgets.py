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
    import tkinter as tk
    from dataclasses import dataclass
    from tkinter import ttk
    from typing import Callable, List

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
