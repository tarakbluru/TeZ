import os
import sys
import tkinter as tk
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app_mods import CustomCreateConfig,CustomWidget, SubWindow, SubWindow_Cc

def subwindow_exposure_cb (current_value, **kwargs):
    print(json.dumps(kwargs, indent=4) + f" {current_value}")

subwin_config_n = SubWindow_Cc(
    win_text='N:',
    slider_cb=subwindow_exposure_cb,  # Assuming you have a callback function defined
    kw_args_exposure_ce={"ix": "NIFTY", "Ce_Or_Pe": "CE"},  # Populate kw_args with desired key-value pairs for 'N' 'CE'
    kw_args_exposure_pe={"ix": "NIFTY", "Ce_Or_Pe": "PE"}  # Populate kw_args with desired key-value pairs for 'N' 'CE'
)

subwin_config_bn = SubWindow_Cc(
    win_text='BN:',
    slider_cb=subwindow_exposure_cb,  # Assuming you have a callback function defined
    kw_args_exposure_ce={"ix": "BANKNIFTY", "Ce_Or_Pe": "CE"},  # Populate kw_args with desired key-value pairs for 'N' 'CE'
    kw_args_exposure_pe={"ix": "BANKNIFTY", "Ce_Or_Pe": "PE"}  # Populate kw_args with desired key-value pairs for 'N' 'CE'
)

# Example usage
if __name__ == "__main__":
    # Create a root window
    root = tk.Tk()
    root.title("Custom Widget Example")

    # Create the first subwindow
    subwin_n = SubWindow(master=root, config=subwin_config_n)
    subwin_n.pack(side=tk.TOP, padx=10, pady=10)

    # Create the second subwindow
    subwin_p = SubWindow(master=root, config=subwin_config_bn)
    subwin_p.pack(side=tk.TOP, padx=10, pady=10)

    root.mainloop()