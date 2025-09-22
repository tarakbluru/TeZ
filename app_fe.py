"""
File: app_fe.py
Author: [Tarakeshwar NC] / Claude Code  
Date: September 7, 2025
Description: Frontend UI module for TeZ trading platform.
Separated from tez_main.py as part of architectural refactoring to implement 
clean separation of concerns and port-based communication.
"""
# Copyright (c) [2024] [Tarakeshwar N.C]
# This file is part of the TeZ project.
# It is subject to the terms and conditions of the MIT License.
# See the file LICENSE in the top-level directory of this distribution
# for the full text of the license.

__app_name__ = 'TeZ-FE'
__author__ = "Tarakeshwar N.C / Claude Code"
__copyright__ = "2024"
__date__ = "2025/09/07"
__deprecated__ = False
__email__ = "tarakesh.nc_at_google_mail_dot_com"
__license__ = "MIT"
__maintainer__ = "Tarak"
__status__ = "Development"
__version__ = "1.0.0"

# Core imports
import json
import sys
import threading
import time
import tkinter as tk
import traceback
import winsound
from datetime import datetime
from tkinter import font, messagebox

# Application imports
import app_mods
import app_utils as utils
from app_utils import FAILURE, SUCCESS
from PIL import Image, ImageTk
from app_mods.status_led import StatusLEDManager

# Get logger
logger = utils.get_logger(__name__)

class AppFE:
    """
    Frontend UI class for TeZ trading platform
    Handles all UI components and user interactions via port-based communication
    """
    
    def __init__(self, port_manager, system_feature_config, app_be):
        """
        Initialize the frontend with port manager and system config
        
        Args:
            port_manager: Backend port manager for 3-port communication
            system_feature_config: System feature configuration dict
            app_be: Backend reference for acceptable direct calls (like get_latest_tick)
        """
        logger.info("Initializing TeZ Frontend UI...")
        
        # Store backend reference for acceptable direct calls
        self.app_be = app_be
        
        # Store port manager and create UI port manager
        self.port_manager = port_manager
        from app_mods.ui_port_integration import SimpleUIPortManager
        self.ui_port_manager = SimpleUIPortManager(port_manager.get_all_ports(), frontend=self)
        
        # Store system configuration
        self.system_feature_config = system_feature_config
        self.gui_config = system_feature_config.get('gui', {})
        
        # UI state variables (replacing globals)
        self.root = None
        self.pnl_window = None
        self.trade_manager_window = None
        self.slider_value = "locked"  # Default state
        self.price_entry = None
        self.window_state_flag = None
        self.photo = None  # For window icon
        
        # Radio button selection for N/BN
        self.ul_selection = self.gui_config.get('radiobutton_def_value', 'NIFTY')
        self.selection_var = None  # Will be created with root window
        
        # UI update tracking
        self.last_tick_update = 0
        
        # Create SubWindow configurations for Trade Manager
        self._create_subwindow_configs()
        
        logger.info("TeZ Frontend UI initialized successfully")
    
    def _create_subwindow_configs(self):
        """Create SubWindow configurations for Trade Manager partial exit sliders"""
        # NIFTY SubWindow config for CE/PE options
        self.subwin_config_n = app_mods.SubWindow_Cc(
            win_name='SW1',
            win_text='N:',
            slider_cb=self.subwindow_exposure_cb,
            kw_args_exposure_ce={"label_name": "CE Exposure %", "ix": "NIFTY", "Ce_Pe_Bees": "CE"},
            kw_args_exposure_pe={"label_name": "PE Exposure %", "ix": "NIFTY", "Ce_Pe_Bees": "PE"}
        )

        # BANKNIFTY SubWindow config for CE/PE options
        self.subwin_config_bn = app_mods.SubWindow_Cc(
            win_name='SW2',
            win_text='BN:',
            slider_cb=self.subwindow_exposure_cb,
            kw_args_exposure_ce={"label_name": "CE Exposure %", "ix": "BANKNIFTY", "Ce_Pe_Bees": "CE"},
            kw_args_exposure_pe={"label_name": "PE Exposure %", "ix": "BANKNIFTY", "Ce_Pe_Bees": "PE"}
        )

        # NIFTY SubWindow config for BEES
        self.subwin_config_n_bees = app_mods.SubWindow_Cc(
            win_name='SW1',
            win_text='N:',
            slider_cb=self.subwindow_exposure_cb,
            kw_args_exposure_ce={"label_name": "Bees Exposure %", "ix": "NIFTY", "Ce_Pe_Bees": "BEES"},
            kw_args_exposure_pe=None
        )

        # BANKNIFTY SubWindow config for BEES
        self.subwin_config_bn_bees = app_mods.SubWindow_Cc(
            win_name='SW2',
            win_text='BN:',
            slider_cb=self.subwindow_exposure_cb,
            kw_args_exposure_ce={"label_name": "Bees Exposure %", "ix": "BANKNIFTY", "Ce_Pe_Bees": "BEES"},
            kw_args_exposure_pe=None
        )

    def subwindow_exposure_cb(self, current_value, **kwargs):
        """Callback for SubWindow exposure sliders - handles partial exit via square-off"""
        logger.info(json.dumps(kwargs, indent=4) + f" {current_value}")
        exch = 'NSE' if kwargs.get('Ce_Pe_Bees') == 'BEES' else 'NFO'
        
        # Map Ce_Pe_Bees to inst_type string
        ce_pe_bees = kwargs.get('Ce_Pe_Bees')
        if ce_pe_bees == 'BEES':
            inst_type = 'BEES'
        elif ce_pe_bees == 'CE':
            inst_type = 'CE'
        elif ce_pe_bees == 'PE':
            inst_type = 'PE'
        else:
            inst_type = 'ALL'

        ix = kwargs.get('ix')
        ix = 'NIFTY BANK' if ix == 'BANKNIFTY' else ix

        # Send square-off command through ports instead of direct call
        if self.ui_port_manager:
            request_id = self.ui_port_manager.send_square_off(
                mode="SELECT", 
                per=(100-current_value),
                ul_index=ix,
                exch=exch,
                inst_type=inst_type,
                partial_exit=True
            )
            
            # Process any immediately available responses (non-blocking)
            response_summary = self.ui_port_manager.process_responses()
            
            if response_summary.get("count", 0) > 0:
                logger.info(f"Slider square-off processed {response_summary['count']} immediate responses")
            
            logger.info(f"SQUARE_OFF slider command sent (ID: {request_id}) - returning immediately, response will be processed in next poll cycle")
        else:
            logger.error("UI port manager not initialized")
        
        self._play_notify()

    def _on_cancel_clicked(self, data):
        """Handle cancel button click for waiting orders"""
        logger.info(f"Row ID #: {data}")
        if self.ui_port_manager:
            request_id = self.ui_port_manager.send_cancel_waiting_order(data)
            
            # Process any immediately available responses (non-blocking)
            response_summary = self.ui_port_manager.process_responses()
            
            if response_summary.get("count", 0) > 0:
                logger.info(f"Cancel order processed {response_summary['count']} immediate responses")
                
            logger.info(f"CANCEL_WAITING_ORDER command sent (ID: {request_id})")
        else:
            logger.error("UI port manager not initialized")

    def _hide_subwindow(self):
        """Hide the Trade Manager window"""
        self._toggle_window_state(self.trade_manager_window, self.window_state_flag)

    def start(self):
        """Start the UI main loop"""
        logger.info("Starting TeZ Frontend UI...")
        
        # Set custom exception handler
        sys.excepthook = self._show_exception
        
        # Create main UI
        self.root = self._create_main_window()
        
        # Start periodic UI updates
        self._start_periodic_updates()
        
        try:
            # Start Tkinter main loop
            self.root.mainloop()
        except KeyboardInterrupt:
            logger.info("UI interrupted by keyboard")
            self.root.destroy()
        
        logger.info("TeZ Frontend UI stopped")
    
    def _show_exception(self, exc_type, exc_value, exc_traceback):
        """Handle exceptions with UI display"""
        error_message = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        tk.messagebox.showerror("Error", f"An error occurred:\\n{error_message}")
    
    def _start_periodic_updates(self):
        """Start periodic UI updates for tick data and port processing"""
        # Start port processing updates (less frequent)
        def process_ports():
            try:
                if self.ui_port_manager:
                    self.ui_port_manager.process_responses()
                    self.ui_port_manager.process_data_updates()
            except Exception as e:
                logger.error(f"Error in port processing: {e}")
            
            # Schedule next port processing (much more frequent - every 100ms)
            if self.root:
                self.root.after(100, process_ports)
        
        # Start dedicated tick update cycle (using system frequency like original)
        def update_tick_label():
            try:
                if hasattr(self, 'tick_label') and self.app_be:
                    # Get latest tick data directly from backend (acceptable direct call)
                    ltp = self.app_be.get_latest_tick()  # Direct call - triggers port publishing
                    font = getattr(self, 'button_font', None)  # Get stored font
                    if ltp and ltp > 0:
                        self.tick_label.config(text=f"{ltp:.2f}", font=font)
                    else:
                        self.tick_label.config(text="No tick data", font=font)
                else:
                    if hasattr(self, 'tick_label'):
                        font = getattr(self, 'button_font', None)
                        self.tick_label.config(text="Backend not available", font=font)
            except Exception as e:
                if hasattr(self, 'tick_label'):
                    font = getattr(self, 'button_font', None)
                    self.tick_label.config(text="Tick error", font=font)
                logger.error(f"Tick update error: {e}")
            
            # Schedule next tick update using EXACT system frequency (like original)
            if self.root:
                try:
                    ui_update_ms = int(app_mods.get_system_info("SYSTEM", "UI_UPDATE_FREQUENCY") * 1000)
                    self.root.after(ui_update_ms, update_tick_label)
                except:
                    self.root.after(500, update_tick_label)  # Fallback to 500ms only if config fails
        
        # Start both cycles
        if self.root:
            self.root.after(100, process_ports)  # Start port processing
            update_tick_label()  # Start tick updates immediately like original
    def _create_main_window(self):
        """Create and return the main UI window"""
        from tkinter import font as tk_font
        
        root = tk.Tk()
        
        # Set window icon based on exchange
        exch = app_mods.get_system_info("TRADE_DETAILS", "EXCHANGE")
        if exch == 'NSE':
            image = Image.open(r'./images/bees1.jpg')
            self.photo = ImageTk.PhotoImage(image)
            root.iconphoto(False, self.photo)
        elif exch == 'NFO':
            image = Image.open(r'./images/opt1.jpg')
            self.photo = ImageTk.PhotoImage(image)
            root.iconphoto(False, self.photo)
        
        # Set window properties
        root.title(self.gui_config.get('app_title', 'TeZ') + f'-{exch}')
        root.geometry(self.gui_config.get('app_geometry', '300x225'))
        root.attributes("-topmost", True)
        
        # Create frames
        frame_top = tk.Frame(root)
        frame_top.pack(side=tk.TOP, pady=5)
        
        frame_mid = tk.Frame(root)
        frame_mid.pack(side=tk.TOP)
        
        frame_bottom = tk.Frame(root)
        frame_bottom.pack(side=tk.BOTTOM)
        
        # Set font based on exchange
        button_font = tk_font.Font(weight="bold" if exch != 'NSE' else "normal")
        
        # Buy button
        l_button_text = self.gui_config.get('long_button', 'LONG')
        buy_button = tk.Button(frame_top, text=l_button_text, command=self._long_market, 
                             bg='#00EF00', font=button_font, fg='black', state='disabled')
        buy_button.pack(side=tk.LEFT, padx=5)
        
        # Tick label with proper font (same as buttons)
        self.tick_label = tk.Label(frame_top, text="", width=7, font=button_font)
        self.tick_label.pack(side=tk.LEFT, padx=5)
        
        # Sell button
        s_button_text = self.gui_config.get('short_button', 'SHORT')
        sell_button = tk.Button(frame_top, text=s_button_text, command=self._short_market,
                              bg='#EF0000', font=button_font, fg='black', state="disabled")
        sell_button.pack(side=tk.LEFT, padx=5)
        
        # Bottom buttons
        e_button_text = self.gui_config.get('exit_button', 'EXIT')
        exit_button = tk.Button(frame_bottom, text=e_button_text, command=self._exit_action, 
                               font=button_font, state="disabled")
        exit_button.pack(side=tk.RIGHT, padx=5, pady=5)
        
        sq_button_text = self.gui_config.get('square_off_button', 'SQ OFF')
        square_off_button = tk.Button(frame_bottom, text=sq_button_text, command=self._square_off_action,
                                    font=button_font, state="disabled")
        square_off_button.pack(side=tk.RIGHT, padx=5, pady=5)
        
        tm_button = tk.Button(frame_bottom, text="TM", command=self._tm_action, 
                            font=button_font, state="disabled")
        tm_button.pack(side=tk.RIGHT, padx=5, pady=5)
        
        # Store references to buttons and font for later use
        self.buy_button = buy_button
        self.sell_button = sell_button
        self.exit_button = exit_button
        self.square_off_button = square_off_button
        self.tm_button = tm_button
        self.button_font = button_font  # Store font reference for tick updates
        
        # Add price entry and quantity controls if limit order feature is enabled
        if self.system_feature_config.get('limit_order_cfg', False):
            self._add_limit_order_controls(frame_mid, root)
        
        # Add radio buttons for N/BN selection
        self._add_radio_buttons(root)
        
        # Add slider controls (in separate frame at bottom)
        self._add_slider_controls(root)

        # Add StatusLED in top-right corner
        self._add_status_led(root)

        return root
        
    def _add_limit_order_controls(self, parent_frame, root):
        """Add limit order price entry and quantity controls"""
        # Price validation
        def validate_price(new_value):
            if new_value == "":
                return True
            try:
                float_value = float(new_value)
                return float_value >= 0
            except ValueError:
                return False
        
        validate_float = root.register(validate_price)
        
        # Price entry with validation
        def on_validate_input(event):
            if event.char.isdigit() or event.char == ".":
                current_text = self.price_entry.get()
                cursor_index = self.price_entry.index(tk.INSERT)
                if event.char == "." and current_text.count(".") >= 2:
                    return "break"
                if current_text.find(".") != -1 and len(current_text[current_text.find("."):]) >= 3 and cursor_index > current_text.find("."):
                    return "break"
                return
            elif event.keysym == "BackSpace":
                return
            else:
                return "break"
        
        # Create price entry
        price_label = tk.Label(parent_frame, text="Price:")
        price_label.pack(side=tk.LEFT, padx=5)
        
        self.price_entry = tk.Entry(parent_frame, width=8, validate='key', validatecommand=(validate_float, '%P'))
        self.price_entry.pack(side=tk.LEFT, padx=5)
        self.price_entry.bind("<Key>", on_validate_input)
        
        # Quantity validation and entry
        def validate_qty(new_value):
            if new_value == "":
                return True
            try:
                int_value = int(new_value)
                return int_value >= 0
            except ValueError:
                return False
        
        validate_int = root.register(validate_qty)
        
        def on_validate_qty_input(event):
            if event.char.isdigit():
                return
            elif event.keysym == "BackSpace":
                return
            else:
                return "break"
        
        # Create quantity entry
        qty_label = tk.Label(parent_frame, text="Qty:")
        qty_label.pack(side=tk.LEFT, padx=5)
        
        self.qty_entry = tk.Entry(parent_frame, width=8, validate='key', validatecommand=(validate_int, '%P'))
        self.qty_entry.pack(side=tk.LEFT, padx=5)
        self.qty_entry.bind("<Key>", on_validate_qty_input)
        self.qty_entry.insert(0, "1")  # Insert default value "1"
    
    def _add_slider_controls(self, root):
        """Add slider controls for position management"""
        # Create separate slider frame at bottom (like original)
        slider_frame = tk.Frame(root)
        slider_frame.pack(side=tk.BOTTOM, pady=10, padx=10, fill=tk.X)
        
        # Get slider configuration from system config
        self.slider_value = self.gui_config.get('slider_posn1_text', 'locked')
        slider_font = self.gui_config.get('slider_font', 'Arial')
        slider_font_size = self.gui_config.get('slider_font_size', 10)
        
        # Status label with proper font
        self.status_label = tk.Label(slider_frame, text=self.slider_value, 
                                    font=(slider_font, slider_font_size))
        self.status_label.pack(side=tk.BOTTOM, padx=5)
        
        # Slider change handler
        def slider_changed(value):
            self._update_status_label(value)
            self._update_button_states(value)
        
        # Create slider with proper positioning
        self.slider = tk.Scale(slider_frame, from_=0, to=1, orient=tk.HORIZONTAL, 
                              command=slider_changed, showvalue=False)
        self.slider.set(0)  # Initialize to locked position
        self.slider.pack(side=tk.BOTTOM, expand=True)
        
        # Initialize the label and button states
        self._update_status_label(self.slider.get())
    
    def _update_status_label(self, value):
        """Update status label based on slider value"""
        if int(value) == 1:
            self.slider_value = self.gui_config.get('slider_posn2_text', 'unlocked')
            self.status_label.config(text=self.slider_value)
        else:
            self.slider_value = self.gui_config.get('slider_posn1_text', 'locked')
            self.status_label.config(text=self.slider_value)
    
    def _update_button_states(self, value):
        """Update button states based on slider value"""
        if int(value) == 1:
            # Unlocked - enable buttons
            if hasattr(self, 'buy_button'):
                self.buy_button.config(state='normal')
            if hasattr(self, 'sell_button'):
                self.sell_button.config(state='normal')
            if hasattr(self, 'square_off_button'):
                self.square_off_button.config(state='normal')
            if hasattr(self, 'exit_button'):
                self.exit_button.config(state='normal')
            if hasattr(self, 'tm_button'):
                self.tm_button.config(state='normal')
        else:
            # Locked - disable buttons
            if hasattr(self, 'buy_button'):
                self.buy_button.config(state='disabled')
            if hasattr(self, 'sell_button'):
                self.sell_button.config(state='disabled')
            if hasattr(self, 'square_off_button'):
                self.square_off_button.config(state='disabled')
            if hasattr(self, 'exit_button'):
                self.exit_button.config(state='disabled')
            if hasattr(self, 'tm_button'):
                self.tm_button.config(state='disabled')
        
    def _long_market(self):
        """Handle buy button action"""
        logger.info(f'{datetime.now()}: Buy Click')
        if self.slider_value.lower() == 'unlocked':
            ui_qty, tp = self._qty_price_from_ui()
            
            if ui_qty is None:
                logger.info('ui_qty : blank , no Trade')
                return
                
            # Send market action command through ports
            if self.ui_port_manager:
                request_id = self.ui_port_manager.send_market_action(action='Buy', trade_price=tp, ui_qty=ui_qty)
                
                # Process any immediately available responses (non-blocking)
                response_summary = self.ui_port_manager.process_responses()
                
                if response_summary.get("count", 0) > 0:
                    logger.info(f"Buy action processed {response_summary['count']} immediate responses")
                
                logger.info(f"Buy command sent (ID: {request_id}) - returning immediately, response will be processed in next poll cycle")
                
                self._play_notify()
            else:
                logger.error("UI port manager not initialized")
        else:
            logger.info('Unlock to take position')
        
    def _short_market(self):
        """Handle sell button action"""
        logger.info(f'{datetime.now()}: Short Click')
        if self.slider_value.lower() == 'unlocked':
            ui_qty, tp = self._qty_price_from_ui()
            
            if ui_qty is None:
                logger.info('ui_qty : blank , no Trade')
                return
                
            # Send market action command through ports
            if self.ui_port_manager:
                request_id = self.ui_port_manager.send_market_action(action='Short', trade_price=tp, ui_qty=ui_qty)
                
                # Process any immediately available responses (non-blocking)
                response_summary = self.ui_port_manager.process_responses()
                
                if response_summary.get("count", 0) > 0:
                    logger.info(f"Short action processed {response_summary['count']} immediate responses")
                
                logger.info(f"Short command sent (ID: {request_id}) - returning immediately, response will be processed in next poll cycle")
                
                self._play_notify()
            else:
                logger.error("UI port manager not initialized")
        else:
            logger.info('Unlock to take position')
        
    def _square_off_action(self):
        """Handle square-off button action"""
        logger.info(f'{datetime.now()}: Square Off Click')
        if self.slider_value.lower() == 'unlocked':
            # Send square-off command through ports
            if self.ui_port_manager:
                # Choose command based on limit order configuration
                if self.system_feature_config.get('limit_order_cfg', False):
                    # Use enhanced method with waiting order cancellation
                    request_id = self.ui_port_manager.send_enhanced_square_off()
                    command_type = "ENHANCED_SQUARE_OFF"
                else:
                    # Use simple method without waiting order cancellation
                    request_id = self.ui_port_manager.send_simple_square_off()
                    command_type = "SIMPLE_SQUARE_OFF"
                
                # Process any immediately available responses (non-blocking)
                response_summary = self.ui_port_manager.process_responses()
                
                if response_summary.get("count", 0) > 0:
                    logger.info(f"Square-off action processed {response_summary['count']} immediate responses")
                
                logger.info(f"{command_type} command sent (ID: {request_id}) - returning immediately, response will be processed in next poll cycle")
                
                self._play_notify()
            else:
                logger.error("UI port manager not initialized")
                tk.messagebox.showerror("Square-Off Error", "UI port manager not initialized")
        else:
            logger.info('Unlock to Squareoff position')
        
    def _exit_action(self):
        """Handle exit button action"""
        logger.info(f"{datetime.now()}: Exit Click")
        if self.slider_value.lower() == 'unlocked':
            if self.root:
                self.root.destroy()
        else:
            logger.info('Unlock to Exit..')
    
    def _tm_action(self):
        """Handle trade manager button action"""
        logger.info(f'{datetime.now()}: TM Click')
        if self.slider_value.lower() == 'unlocked':
            if self._create_trade_manager_window() != 1:
                # Window already exists, toggle its visibility
                self._toggle_window_state(self.trade_manager_window, self.window_state_flag)
            else:
                # New window created, send SHOW_RECORDS command
                if self.ui_port_manager:
                    request_id = self.ui_port_manager.send_show_records()
                    
                    # Process any immediately available responses (non-blocking)
                    response_summary = self.ui_port_manager.process_responses()
                    
                    if response_summary.get("count", 0) > 0:
                        logger.info(f"TM show records processed {response_summary['count']} immediate responses")
                    
                    logger.info(f"SHOW_RECORDS from TM command sent (ID: {request_id}) - returning immediately, response will be processed in next poll cycle")
                else:
                    logger.error("UI port manager not initialized")
        else:
            logger.info('Unlock to open Trade Manager')
    
    def _qty_price_from_ui(self):
        """Extract quantity and price from UI elements"""
        ui_qty = None
        tp = None
        
        # Get quantity (always required)
        if self.qty_entry:
            qty_text = self.qty_entry.get().strip()
            if qty_text:
                try:
                    ui_qty = int(qty_text)
                except ValueError:
                    logger.error(f"Invalid quantity: {qty_text}")
                    return None, None
        
        # Get price if limit order feature is enabled
        if self.system_feature_config.get('limit_order_cfg', False):
            if hasattr(self, 'price_entry') and self.price_entry:
                price_text = self.price_entry.get().strip()
                if price_text:
                    try:
                        tp = float(price_text)
                    except ValueError:
                        logger.error(f"Invalid price: {price_text}")
                        return None, None
        
        return ui_qty, tp
    
    def _play_notify(self):
        """Play notification sound"""
        # Check if play notify is enabled in config (like original)
        pb = self.gui_config.get('play_notify', 'NO')
        if pb.upper() == 'YES':
            try:
                winsound.PlaySound("C:/Windows/Media/notify.wav", winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NOWAIT)
            except Exception as e:
                logger.debug(f"Sound notification failed: {e}")
                # Fallback to beep if wav file not found
                try:
                    winsound.Beep(1000, 200)  # 1000 Hz, 200ms
                except:
                    pass
    
    def _toggle_window_state(self, window, state_flag):
        """Toggle window visibility state (exactly like original)"""
        if window and state_flag:
            if state_flag.get():
                window.withdraw()  # Hide the window
                state_flag.set(False)  # Update flag to indicate window is hidden
            else:
                window.deiconify()  # Show the window
                state_flag.set(True)  # Update flag to indicate window is visible
                if self.ui_port_manager:
                    request_id = self.ui_port_manager.send_show_records()
    
    def _create_trade_manager_window(self):
        """Create trade manager window if it doesn't exist, or bring existing to front"""
        # Check if window already exists and is valid (like original)
        try:
            window_exists = (self.trade_manager_window is not None and 
                           self.trade_manager_window.winfo_exists())
        except:
            # Window reference is invalid
            window_exists = False
            self.trade_manager_window = None
        
        if not window_exists:
            logger.info('Creating Trade Manager window')
            
            try:
                # Create new window
                tm_window = tk.Toplevel(self.root)
                tm_window.title("Trade Manager")
                tm_window.iconphoto(False, self.photo)
                
                # Window state flag for toggle functionality (create only once like original)
                if self.window_state_flag is None:
                    self.window_state_flag = tk.BooleanVar()
                    self.window_state_flag.set(True)  # True means window is currently visible

                # Add "Row #" label, entry box, and "Cancel" button above frame1 (like original)
                row_frame = tk.Frame(tm_window)
                row_frame.pack(side=tk.TOP, padx=5, pady=5)

                if self.system_feature_config['limit_order_cfg']:
                    row_label = tk.Label(row_frame, text="Waiting Order Row #:")
                    row_label.pack(side=tk.LEFT)

                    # Entry box
                    entry_box = tk.Entry(row_frame)
                    entry_box.pack(side=tk.LEFT, padx=5)

                    # Cancel button
                    cancel_button = tk.Button(row_frame, text="Cancel", command=lambda: self._on_cancel_clicked(entry_box.get()))
                    cancel_button.pack(side=tk.LEFT)
                
                # Create frame structure exactly like original  
                sub_frame1 = tk.Frame(tm_window, bd=2, relief=tk.GROOVE)
                sub_frame2 = tk.Frame(tm_window, bd=2, relief=tk.GROOVE)

                # Determine which SubWindow configs to use based on system feature config
                config1 = None
                config2 = None
                
                if self.system_feature_config['tm'] == 'CE_PE':
                    config1 = self.subwin_config_n
                    config2 = self.subwin_config_bn

                    # Check instrument info to see if intraday orders are enabled
                    inst_info = app_mods.get_system_info("INSTRUMENT_INFO", "INST_3")
                    if inst_info['ORDER_PROD_TYPE'] != 'I':
                        config1 = None

                    inst_info = app_mods.get_system_info("INSTRUMENT_INFO", "INST_4")
                    if inst_info['ORDER_PROD_TYPE'] != 'I':
                        config2 = None
                        
                elif self.system_feature_config['tm'] == 'BEES':
                    config1 = self.subwin_config_n_bees
                    config2 = self.subwin_config_bn_bees

                    # Check instrument info for BEES
                    inst_info = app_mods.get_system_info("INSTRUMENT_INFO", "INST_1")
                    if inst_info['ORDER_PROD_TYPE'] != 'I':
                        config1 = None

                    inst_info = app_mods.get_system_info("INSTRUMENT_INFO", "INST_2")
                    if inst_info['ORDER_PROD_TYPE'] != 'I':
                        config2 = None

                # Create SubWindow components if configs are available
                if config1:
                    subwin_n = app_mods.SubWindow(master=sub_frame1, config=config1)
                    subwin_n.pack(side=tk.TOP, padx=10, pady=10, anchor="w")

                if config2:
                    subwin_bn = app_mods.SubWindow(master=sub_frame1, config=config2)
                    subwin_bn.pack(side=tk.TOP, padx=10, pady=10, anchor="w")

                # Pack sub_frame1 for SubWindows
                sub_frame1.pack(side=tk.LEFT, padx=10, pady=15, anchor='n')

                # Set window geometry based on configs (like original)
                if config1 and config2:
                    tm_window.geometry("1000x700+{}+{}".format(self.root.winfo_x() + 80, self.root.winfo_y() + 50))
                elif config1 or config2:
                    tm_window.geometry("1000x350+{}+{}".format(self.root.winfo_x() + 80, self.root.winfo_y() + 50))
                else:
                    tm_window.geometry("1000x200+{}+{}".format(self.root.winfo_x() + 80, self.root.winfo_y() + 50))
                
                # Set transient relationship (like original)
                tm_window.transient(self.root)
                
                # Create PNL window widget in its dedicated frame (like original)
                pnl_window = app_mods.PNL_Window(
                    master=sub_frame2,
                    ui_update_frequency=app_mods.get_system_info("SYSTEM", "UI_UPDATE_FREQUENCY"),
                    ui_port_manager=self.ui_port_manager  # Mandatory shared instance
                )
                
                # Pack sub_frame2 for PNL_Window (like original)
                sub_frame2.pack(side=tk.LEFT, padx=20, pady=50, anchor='n')

                # Add Hide button (like original)
                hide_button = tk.Button(tm_window, text="Hide TM", command=self._hide_subwindow)
                hide_button.pack(side=tk.LEFT, padx=20, pady=50, anchor='n')
                
                # Store references
                self.trade_manager_window = tm_window
                self.pnl_window = pnl_window
                
                # Set up window close handler (exactly like original)
                def on_closing():
                    if self.trade_manager_window is not None:
                        self.trade_manager_window.destroy()
                        self.trade_manager_window = None
                
                tm_window.protocol("WM_DELETE_WINDOW", on_closing)
                
                logger.info('Trade Manager window created successfully')
                return 1  # New window created
                
            except Exception as e:
                logger.error(f"Failed to create Trade Manager window: {e}")
                logger.error(traceback.format_exc())
                return 1  # Still return 1 if creation failed
        else:
            # Window already exists, bring it to the front (like original)
            logger.info('Trade Manager window already exists, bringing to front')
            try:
                self.trade_manager_window.lift()
            except:
                logger.warning("Failed to lift Trade Manager window")
            return 2  # Existing window
    
    def _add_radio_buttons(self, root):
        """Add radio buttons for NIFTY/BANKNIFTY selection"""
        # Create StringVar for radio button selection
        def_value = self.gui_config.get('radiobutton_def_value', 'NIFTY')
        self.selection_var = tk.StringVar(value=def_value)
        self.ul_selection = self.selection_var.get()
        
        # Radio button change handler
        def show_ul_selection():
            old_value = self.ul_selection
            self.ul_selection = self.selection_var.get()
            logger.info(f'{old_value} -> {self.ul_selection}')
            
            if self.ui_port_manager:
                request_id = self.ui_port_manager.send_set_ul_index(self.ul_selection)
                
                # Process any immediately available responses (non-blocking)
                response_summary = self.ui_port_manager.process_responses()
                
                if response_summary.get("count", 0) > 0:
                    logger.info(f"Radio button change processed {response_summary['count']} immediate responses")
                
                logger.info(f"SET_UL_INDEX command sent (ID: {request_id}) - returning immediately, response will be processed in next poll cycle")
                
                # Force immediate tick update (simple approach)
                def immediate_tick_update():
                    try:
                        if hasattr(self, 'tick_label') and self.app_be:
                            ltp = self.app_be.get_latest_tick()
                            font = getattr(self, 'button_font', None)  # Use same font as original
                            if ltp and ltp > 0:
                                self.tick_label.config(text=f"{ltp:.2f}", font=font)
                                logger.debug(f"Immediate tick update after radio change: {ltp:.2f}")
                            else:
                                self.tick_label.config(text="No tick data", font=font)
                    except Exception as e:
                        logger.error(f"Error in immediate tick update: {e}")
                
                # Trigger immediate tick update and then a few more soon
                immediate_tick_update()  # Update immediately
                if self.root:
                    self.root.after(100, immediate_tick_update)  # Update again in 100ms
                    self.root.after(250, immediate_tick_update)  # And again in 250ms
                    
            else:
                logger.error("UI port manager not initialized")
            
            # Clear price entry when selection changes
            self._clear_price_entry()
        
        # Create radio button 1 (NIFTY)
        bt1 = self.gui_config.get('radiobutton_1_text', 'NIFTY')
        bv1 = self.gui_config.get('radiobutton_1_value', 'NIFTY')
        rb1 = tk.Radiobutton(root, text=bt1, variable=self.selection_var, value=bv1, command=show_ul_selection)
        rb1.pack(anchor="w", padx=8)
        
        # Create radio button 2 (BANKNIFTY)
        bt2 = self.gui_config.get('radiobutton_2_text', 'BANKNIFTY')
        bv2 = self.gui_config.get('radiobutton_2_value', 'BANKNIFTY')
        rb2 = tk.Radiobutton(root, text=bt2, variable=self.selection_var, value=bv2, command=show_ul_selection)
        rb2.pack(anchor="w", padx=8)
        
        # Store references
        self.rb1 = rb1
        self.rb2 = rb2
    
    def _clear_price_entry(self):
        """Clear price entry when radio button selection changes"""
        if hasattr(self, 'price_entry') and self.price_entry:
            self.price_entry.delete(0, tk.END)

    def _add_status_led(self, root):
        """Add StatusLED widget for network connectivity indication"""
        try:
            # Create StatusLED manager
            self.status_led_manager = StatusLEDManager(root)

            # Position LED using config values
            # Get window dimensions for positioning
            root.update_idletasks()  # Ensure geometry is calculated
            window_width = root.winfo_width() if root.winfo_width() > 1 else 300
            window_height = root.winfo_height() if root.winfo_height() > 1 else 225

            # Position LED using config values - bottom-left corner
            led_x = app_mods.get_system_info("GUI_CONFIG", "STATUS_LED_X")
            led_y_offset = app_mods.get_system_info("GUI_CONFIG", "STATUS_LED_Y_OFFSET")
            led_y = window_height - led_y_offset

            self.status_led_manager.get_led_widget().place(x=led_x, y=led_y)

            logger.info("StatusLED added to main window")

        except Exception as e:
            logger.error(f"Failed to add StatusLED: {e}")
            # Don't fail the entire UI if LED fails
            self.status_led_manager = None