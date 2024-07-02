import os
import sys
import tkinter as tk
import json
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app_mods import PNL_Window

# Example usage
if __name__ == "__main__":
    # Create a root window
    root = tk.Tk()
    root.title("Custom Widget Example")

    sub_frame = tk.Frame(root)
    pnl_window = PNL_Window(sub_frame)
    sub_frame.grid(row=0, column=0, padx=10, pady=10)

    def print_values (d:dict):
        print (f'{json.dumps(d, indent=2)}')

    pnl_window.cb = print_values

    root.mainloop()