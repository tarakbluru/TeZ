"""
File: port_system.py
Author: [Tarakeshwar NC] / Claude Code
Date: September 11, 2025
Description: 3-port communication system for loose coupling between UI and backend components
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
from dataclasses import dataclass, field
from itertools import count
from queue import Empty
from typing import Any, Optional, Dict, Tuple
import time

from app_utils.q_extn import ExtQueue, ExtSimpleQueue
from app_utils import app_logger

logger = app_logger.get_logger(__name__)

@dataclass
class Port:
    """
    Simplified communication port for processing units
    Based on proven design with dual queue system for commands and data
    """
    _id_counter = count(1)  # Class-level counter for unique IDs
    
    # Core queues
    data_q: ExtSimpleQueue = field(default_factory=ExtSimpleQueue)
    cmd_q: ExtQueue = field(default_factory=ExtQueue)
    
    # Synchronization
    evt: threading.Event = field(default_factory=threading.Event)
    
    # Identification
    name: str = field(default_factory=lambda: f"port_{next(Port._id_counter)}")
    _id: int = field(init=False)  # Hidden from init, set in __post_init__

    def __post_init__(self):
        """Initialize internal ID after dataclass creation"""
        self._id = next(Port._id_counter)
        logger.debug(f"Created port: {self.name} (ID: {self._id})")

    @property
    def id(self) -> int:
        """Read-only access to internal ID"""
        return self._id

    def send_data(self, data: Any) -> None:
        """
        Send data through the data queue (non-blocking)
        
        Args:
            data: Data payload to send
        """
        try:
            self.data_q.put(data)
            self.evt.set()  # Wake up any waiting consumers
            # Removed routine data transmission logging to reduce log noise
            # Meaningful data changes are logged at higher application levels
        except Exception as e:
            logger.error(f"{self.name}: Error sending data: {e}")

    def send_command(self, cmd: Any, data: Any = None, request_id: int = None, wait_time: float = 0.0) -> None:
        """
        Send command with data and mandatory request ID
        
        Args:
            cmd: Command identifier
            data: Optional data associated with command
            request_id: Mandatory request ID for command tracking
            wait_time: Time to wait for command completion (0.0 = no wait)
        """
        if request_id is None:
            raise ValueError("request_id is mandatory for all commands")
            
        try:
            # Create command tuple - always 3-tuple (cmd, data, request_id)
            cmd_data = (cmd, data, request_id)
            
            self.cmd_q.put(cmd_data)
            self.evt.set()  # Wake up any waiting consumers
            
            if wait_time > 0.0:
                try:
                    self.cmd_q.join_with_timeout(wait_time)
                except TimeoutError:
                    logger.debug(f'{self.name}: Command timeout after {wait_time}s: {cmd} (ID: {request_id})')
                    
            logger.debug(f"{self.name}: Sent command: {cmd} (ID: {request_id})")
            
        except Exception as e:
            logger.error(f"{self.name}: Error sending command: {e}")

    def fetch_data(self) -> Optional[Any]:
        """
        Fetch next data item if available (non-blocking)
        
        Returns:
            Data item or None if no data available
        """
        try:
            if self.data_q.empty():
                return None
            return self.data_q.get()
        except Empty:
            return None
        except Exception as e:
            logger.error(f"{self.name}: Error fetching data: {e}")
            return None

    def fetch_command(self) -> tuple[Optional[Any], Optional[Any], Optional[int]]:
        """
        Fetch next command, data, and request ID if available (non-blocking)
        
        Returns:
            Tuple of (command, data, request_id) or (None, None, None) if no command available
        """
        try:
            if self.cmd_q.empty():
                return None, None, None
            
            cmd_data = self.cmd_q.get()
            self.cmd_q.task_done()
            
            # Expect 3-tuple format (cmd, data, request_id)
            if isinstance(cmd_data, tuple) and len(cmd_data) == 3:
                return cmd_data[0], cmd_data[1], cmd_data[2]
            else:
                logger.error(f"{self.name}: Invalid command format - expected 3-tuple, got: {cmd_data}")
                return None, None, None
                
        except Empty:
            return None, None, None
        except Exception as e:
            logger.error(f"{self.name}: Error fetching command: {e}")
            return None, None, None

    def flush(self) -> tuple[int, int]:
        """
        Clear all pending messages in both queues
        
        Returns:
            Tuple of (data_count, cmd_count) - number of messages discarded
        """
        data_count = self.data_q.qsize()
        cmd_count = self.cmd_q.qsize()
        
        self.data_q.flush()
        self.cmd_q.flush() 
        self.evt.clear()
        
        if data_count > 0 or cmd_count > 0:
            logger.debug(f"{self.name}: Flushed {data_count} data, {cmd_count} commands")
        
        return data_count, cmd_count

    def get_queue_sizes(self) -> tuple[int, int]:
        """
        Get current queue sizes
        
        Returns:
            Tuple of (data_queue_size, command_queue_size)
        """
        return self.data_q.qsize(), self.cmd_q.qsize()

    def is_empty(self) -> bool:
        """Check if both queues are empty"""
        return self.data_q.empty() and self.cmd_q.empty()

    def __str__(self) -> str:
        """String representation showing name and internal ID"""
        data_size, cmd_size = self.get_queue_sizes()
        return f"{self.name} (ID: {self._id}, Data: {data_size}, Cmd: {cmd_size})"


class PortManager:
    """
    Simple manager for the 3-port system
    Creates and manages Command, Response, and Data ports
    """
    
    def __init__(self):
        """Initialize the 3 ports with descriptive names"""
        self.command_port = Port(name="UI_COMMAND_PORT")
        self.response_port = Port(name="BACKEND_RESPONSE_PORT")
        self.data_port = Port(name="BACKEND_DATA_PORT")
        
        # Basic monitoring
        self._start_time = time.time()
        
        logger.info("PortManager initialized with 3 ports")
    
    def get_all_ports(self) -> Dict[str, Port]:
        """Get dictionary of all managed ports"""
        return {
            "command": self.command_port,
            "response": self.response_port,
            "data": self.data_port
        }
    
    def get_port_statistics(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all ports"""
        stats = {}
        
        for port_name, port in self.get_all_ports().items():
            data_size, cmd_size = port.get_queue_sizes()
            stats[port_name] = {
                "name": port.name,
                "id": port.id,
                "data_queue_size": data_size,
                "command_queue_size": cmd_size,
                "is_empty": port.is_empty()
            }
        
        return stats
    
    def flush_all_ports(self) -> Dict[str, Tuple[int, int]]:
        """
        Flush all ports and return statistics
        
        Returns:
            Dict mapping port names to (data_flushed, cmd_flushed) tuples
        """
        flush_stats = {}
        
        for port_name, port in self.get_all_ports().items():
            data_count, cmd_count = port.flush()
            flush_stats[port_name] = (data_count, cmd_count)
            
        logger.info(f"Flushed all ports: {flush_stats}")
        return flush_stats
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status"""
        return {
            "uptime": time.time() - self._start_time,
            "ports": self.get_port_statistics()
        }


def fetch_latest_data_only(port: Port) -> Optional[Any]:
    """
    Utility function to get only the latest data item, discard older ones
    Useful for high-frequency updates where only current value matters
    
    Args:
        port: Port to fetch data from
        
    Returns:
        Latest data item or None
    """
    latest_data = None
    
    # Drain the data queue, keeping only the last item
    while True:
        data = port.fetch_data()
        if data is None:
            break
        latest_data = data
    
    return latest_data