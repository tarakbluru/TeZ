"""
File: tick_recorder.py
Author: [Tarakeshwar NC]
Date: January 15, 2024
Description: This script provides tick recording facility.
"""
# Copyright (c) [2024] [Tarakeshwar N.C]
# This file is part of the TeZ project.
# It is subject to the terms and conditions of the MIT License.
# See the file LICENSE in the top-level directory of this distribution
# for the full text of the license.

__app_name__ = 'TeZ'
__author__ = "Tarakeshwar N.C"
__copyright__ = "2024"
__date__ = "2024/1/14"
__deprecated__ = False
__email__ = "tarakesh.nc_at_google_mail_dot_com"
__license__ = "MIT"
__maintainer__ = "Tarak"
__status__ = "Development"

from . import app_logger

logger = app_logger.get_logger(__name__)

try :
    import queue
    import sys
    from enum import Enum
    from multiprocessing import Process as mp
    from multiprocessing import Queue as mp_Q
except Exception as e:
    logger.error (("Import Error"+str(e)))
    sys.exit (1)

class TickRecorderState(Enum):
    OFF=0
    ON=1


class TickRecorder(object):
    def __init__(self):
        self.mp_q = mp_Q ()
        self.tick_record_process = None
        self._state = TickRecorderState.ON
        self._file_name = None

    def set_state (self, new_state):
        logger.debug (f"{self._state} --> {new_state}")
        self._state = new_state

    state = property (None, set_state)

    def set_filename (self, filename):
        self._file_name = filename

    filename = property (None, set_filename)

    def start_service (self):
        self.tick_record_process = mp(target=self.__tick_recorder_server__, name="TickRecorder", 
                                args=(self.mp_q,self._file_name,))
        self.tick_record_process.daemon = True
        self.tick_record_process.start()

    def put_data (self, mesg):
        if self._state == TickRecorderState.ON:
            self.mp_q.put(f'{mesg}')

    def stop_service (self):
        self.mp_q.put (None)
        if self.tick_record_process is not None:
            self.tick_record_process.join()
        self.mp_q.close()

    def __tick_recorder_server__ (self, q:mp_Q, file_name:str=""):
        while True:
            # get a message
            try:
                item = q.get(timeout=60)
            except KeyboardInterrupt:                
                break
            except queue.Empty:
                pass
            else:
                # check for stop
                if item is None:
                    break
                # report
                if item:
                    with open (file_name, "a") as f:
                        f.write (str(item).strip())
                        f.write ("\n")
                    del item
        # all done
        while not q.empty():
             item = q.get()
             del item
        print('Tick Recorder is Exiting...',flush=True)
        return

def main ():
    from datetime import date

    recorder = TickRecorder ()
    today = date.today()
    recorder.filename = './logfiles/'+today.strftime("%Y_%m_%d")+".txt"
    recorder.start_service()
    recorder.put_data ("Good Morning!!")
    recorder.stop_service()

if __name__== '__main__':
    main ()