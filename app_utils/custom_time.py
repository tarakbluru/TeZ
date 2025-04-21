"""
File: custom_time.py
Author: [Tarakeshwar NC]
Date: July 11, 2024
Description: This script provides timer extensions.
References:
...
"""
# Copyright (c) [2024] [Tarakeshwar N.C]
# This file is part of the Tez project.
# It is subject to the terms and conditions of the MIT License.
# See the file LICENSE in the top-level directory of this distribution
# for the full text of the license.

from datetime import datetime, timezone
import socket
import ntplib
import pytz

from . import app_logger

logger = app_logger.get_logger(__name__)

class CustomTime:
    def __init__(self, use_ntp=False, time_threshold=1):
        self.use_ntp = use_ntp
        self.ntp_servers = ['time.windows.com', 'time.google.com', 'pool.ntp.org']
        self.local_timezone = pytz.timezone('Asia/Kolkata')
        self.time_threshold = time_threshold  # Threshold in seconds for time comparison

    def get_current_time(self):
        if self.use_ntp:
            ntp_time = self._get_time_from_ntp()
            return self._convert_to_local_time(ntp_time)
        else:
            return self._get_system_time()

    def _get_system_time(self):
        # Get the current system time and convert it to IST
        system_time = datetime.now(self.local_timezone)
        return system_time

    def _is_internet_available(self):
        """Check if internet connection is available"""
        try:
            # Try to create a socket connection to Google's DNS server
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True
        except OSError:
            logger.warning("No internet connection available")
            return False

    def _get_time_from_ntp(self):
        # First check internet connectivity
        if not self._is_internet_available():
            logger.warning("Cannot get NTP time - no internet connection")
            return None
            
        for server in self.ntp_servers:
            try:
                # Create an NTP client
                ntp_client = ntplib.NTPClient()
                
                # Query the time from an NTP server with timeout
                response = ntp_client.request(server, timeout=5)

                # Convert the NTP time to a datetime object in UTC
                ntp_time = datetime.fromtimestamp(response.tx_time, timezone.utc)
                
                logger.info(f"Successfully retrieved time from NTP server {server}")
                return ntp_time
            except ntplib.NTPException as e:
                logger.warning(f"NTP protocol error with {server}: {e}")
            except socket.gaierror as e:
                logger.warning(f"DNS resolution error for {server}: {e}")
            except socket.timeout:
                logger.warning(f"Connection to {server} timed out")
            except Exception as e:
                logger.warning(f"Error getting time from NTP server {server}: {e}")
        
        logger.warning("Could not connect to any NTP server")
        return None

    def _convert_to_local_time(self, utc_time):
        if utc_time is not None:
            # Convert UTC time to local time (IST)
            local_time = utc_time.astimezone(self.local_timezone)
            return local_time
        return None

    def get_current_unix_epoch(self):
        current_time = self.get_current_time()
        if current_time is not None:
            # Return the Unix epoch time as an integer
            return int(current_time.timestamp())
        return None

    def compare_system_and_ntp_time(self):
        ntp_time = self._get_time_from_ntp()
        
        if ntp_time is None:
            logger.warning("System clock verification failed: Could not retrieve NTP time")
            return False
        ntp_time_local = self._convert_to_local_time(ntp_time)
        system_time = self._get_system_time()

        if system_time and ntp_time_local:
            # Compare system time and NTP time
            time_difference = abs(system_time - ntp_time_local).total_seconds()
            logger.info(f'ntp_time: {ntp_time_local} local_time: {system_time}')
            logger.info(f'Time difference: {time_difference:.2f} seconds (threshold: {self.time_threshold} seconds)')
            
            return time_difference < self.time_threshold
        
        logger.warning("System clock verification failed: Missing time data")
        return False