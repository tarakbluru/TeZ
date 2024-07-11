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

import ntplib
import pytz

from . import app_logger

logger = app_logger.get_logger(__name__)

class CustomTime:
    def __init__(self, use_ntp=False):
        self.use_ntp = use_ntp
        self.ntp_servers = ['time.windows.com', 'time.google.com', 'pool.ntp.org']
        self.local_timezone = pytz.timezone('Asia/Kolkata')

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

    def _get_time_from_ntp(self):
        for server in self.ntp_servers:
            try:
                # Create an NTP client
                ntp_client = ntplib.NTPClient()

                # Query the time from an NTP server
                response = ntp_client.request(server)

                # Convert the NTP time to a datetime object in UTC
                ntp_time = datetime.fromtimestamp(response.tx_time, timezone.utc)

                return ntp_time
            except Exception as e:
                print(f"Error getting time from NTP server {server}: {e}")
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
        system_time = self._get_system_time()
        ntp_time = self._get_time_from_ntp()
        ntp_time_local = self._convert_to_local_time(ntp_time)

        logger.info (f'ntp_time: {ntp_time_local} local_time: {system_time}')

        if system_time and ntp_time_local:
            # Compare system time and NTP time to see if the difference is less than 1 second
            time_difference = abs(system_time - ntp_time_local).total_seconds()
            return time_difference < 1
        return False
