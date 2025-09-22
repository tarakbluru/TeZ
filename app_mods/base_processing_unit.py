"""
File: base_processing_unit.py
Author: [Tarakeshwar NC] / Claude Code
Date: September 11, 2025
Description: Base processing unit class providing common infrastructure for TeZ trading components
"""
# Copyright (c) [2025] [Tarakeshwar N.C]
# This file is part of the Tez project.
# It is subject to the terms and conditions of the MIT License.
# See the file LICENSE in the top-level directory of this distribution
# for the full text of the license.

__author__ = "Tarakeshwar N.C"
__copyright__ = "2025"
__date__ = "2025/9/11"
__deprecated__ = False
__email__ = "tarakesh.nc_at_google_mail_dot_com"
__license__ = "MIT"
__maintainer__ = "Tarak"
__status__ = "Development"


import threading
import time
from enum import Enum, auto
from typing import Any, Callable, Dict, Optional
from app_utils import app_logger

logger = app_logger.get_logger(__name__)

class ProcessingUnitState(Enum):
    """States that a processing unit can be in"""
    READY = auto()      # Initialized but not started
    RUNNING = auto()    # Processing data and commands
    STOPPED = auto()    # Terminated

class ProcessingUnit:
    """Simplified base class for active processing units with command handling"""
    
    def __init__(self, unit_id: str, command_port=None, response_port=None):
        self.unit_id = unit_id
        self.command_port = command_port
        self.response_port = response_port
        
        # State management
        self._state = ProcessingUnitState.READY
        self._state_lock = threading.Lock()
        
        # Control events
        self._running = False
        self._processor_thread: Optional[threading.Thread] = None
        
        # Command handler
        self._cmd_handler: Optional[Callable[[Any, Any, int], Dict[str, Any]]] = None
        
        logger.info(f"ProcessingUnit {unit_id} initialized")
    
    @property
    def state(self) -> ProcessingUnitState:
        """Get current processing unit state"""
        with self._state_lock:
            return self._state
    
    def set_cmd_handler(self, handler: Callable[[Any, Any, int], Dict[str, Any]]) -> None:
        """Set the function to handle incoming commands"""
        self._cmd_handler = handler
        logger.debug(f"Command handler set for {self.unit_id}")
    
    def start(self) -> None:
        """Start the processing unit"""
        with self._state_lock:
            if self._state != ProcessingUnitState.READY:
                logger.warning(f"Cannot start {self.unit_id} - not in READY state")
                return
            
            self._state = ProcessingUnitState.RUNNING
            self._running = True
            
            if not self._processor_thread or not self._processor_thread.is_alive():
                self._processor_thread = threading.Thread(
                    target=self._process_commands,
                    name=f'{self.unit_id}_processor',
                    daemon=True
                )
                self._processor_thread.start()
                logger.info(f"Started ProcessingUnit: {self.unit_id}")
    
    def stop(self) -> None:
        """Stop the processing unit"""
        with self._state_lock:
            if self._state != ProcessingUnitState.RUNNING:
                return
            
            self._state = ProcessingUnitState.STOPPED
            self._running = False
        
        if self._processor_thread:
            self._processor_thread.join(timeout=5.0)
        
        logger.info(f"Stopped ProcessingUnit: {self.unit_id}")
    
    def _process_commands(self) -> None:
        """Main command processing loop"""
        logger.info(f"Command processing started for {self.unit_id}")
        
        while self._running:
            try:
                if self.command_port and self.command_port.cmd_q:
                    # Check for commands (non-blocking) - now expects 3-tuple
                    command, data, request_id = self.command_port.fetch_command()
                    
                    if command and self._cmd_handler:
                        try:
                            logger.info(f"[BACKEND] Processing command: {command} (ID: {request_id})")
                            response = self._cmd_handler(command, data, request_id)
                            
                            # Send response if response port available
                            if self.response_port and response:
                                self.response_port.send_data(response)
                                logger.info(f"[BACKEND] Sent response for command: {command} (ID: {request_id}) success={response.get('success', 'unknown')}")
                                
                        except Exception as e:
                            logger.error(f"Error processing command {command} (ID: {request_id}): {e}")
                            if self.response_port:
                                error_response = {
                                    "success": False,
                                    "command": command,
                                    "request_id": request_id,
                                    "error": str(e)
                                }
                                self.response_port.send_data(error_response)
                
                # Small sleep to prevent busy waiting
                time.sleep(0.01)
                
            except Exception as e:
                logger.error(f"Error in command processing loop for {self.unit_id}: {e}")
                time.sleep(0.1)
        
        logger.info(f"Command processing ended for {self.unit_id}")
    
    @property
    def is_running(self) -> bool:
        """Check if unit is in RUNNING state"""
        return self.state == ProcessingUnitState.RUNNING
    
    @property
    def is_stopped(self) -> bool:
        """Check if unit is in STOPPED state"""
        return self.state == ProcessingUnitState.STOPPED