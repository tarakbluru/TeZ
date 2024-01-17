"""
File: q_extn.py
Author: [Tarakeshwar NC]
Date: January 15, 2024
Description: This script provides general utilities required for the system.
References: 
...
"""
# Copyright (c) [2024] [Tarakeshwar N.C]
# This file is part of the Tiny_TeZ project.
# It is subject to the terms and conditions of the MIT License.
# See the file LICENSE in the top-level directory of this distribution
# for the full text of the license.

import sys
import traceback

from . import app_logger

logger = app_logger.get_logger(__name__)

try :
    import queue
    from time import monotonic as time
except Exception as e:
    logger.debug(traceback.format_exc())
    logger.error (("Import Error " + str(e)))
    sys.exit (1)

class ExtSimpleQueue (queue.SimpleQueue):
    def flush (self):
        while (not super().empty()):
            super().get() 
        return

class ExtQueue (queue.Queue):
    def flush (self):
        nelem = super().qsize ()
        while (nelem > 0):
            super().get()
            super().task_done () 
            nelem -= 1
        return
    
    def join_with_timeout(self, timeout:float = 1.0):
        if timeout < 0.0:
            raise ValueError("'timeout' must be a non-negative number")

        self.all_tasks_done.acquire()
        try:
            endtime = time() + timeout
            while self.unfinished_tasks:
                remaining = endtime - time()
                if remaining <= 0.0:
                    raise TimeoutError("UnFinished..TimedOut")
                self.all_tasks_done.wait(remaining)
        finally:
            self.all_tasks_done.release()
