"""
File: timer_extn.py
Author: [Tarakeshwar NC]
Date: January 15, 2024
Description: This script provides timer extensions.
References:
...
"""
# Copyright (c) [2024] [Tarakeshwar N.C]
# This file is part of the Tiny_TeZ project.
# It is subject to the terms and conditions of the MIT License.
# See the file LICENSE in the top-level directory of this distribution
# for the full text of the license.

from threading import Lock, Timer
from . import app_logger

logger = app_logger.get_logger(__name__)


class RepeatTimer(Timer):
    def __init__(self, init_dly: float, interval: float, count: int, function, args=None, kwargs=None):
        if init_dly > 0.0:
            wait = init_dly
        else:
            wait = interval
        self.period = interval
        self.ft = bool(False)
        self.count = count
        self.new_period = None
        self.lock = Lock()
        logger.debug(f'period: {self.period} count:{self.count}')
        super().__init__(wait, function, args, kwargs)

    def update_scan_period(self, interval):
        with self.lock:
            if self.new_period is None:
                self.new_period = interval

    scan_period = property(None, update_scan_period)

    def run(self):
        try:
            while not self.finished.wait(self.interval):
                self.function(*self.args, **self.kwargs)
                if not self.ft:
                    self.ft = True
                    logger.debug(f"Starting the Timer with {self.period}")
                    if self.new_period is not None:
                        with self.lock:
                            self.period = self.new_period
                            self.new_period = None
                    self.interval = self.period
                if self.count:
                    self.count -= 1
                else:
                    break
        except KeyboardInterrupt:
            logger.debug("key board interrupt")
            raise
        except Exception as e:
            logger.debug("Exceptin in Timer thread: "+str(e))
            raise
