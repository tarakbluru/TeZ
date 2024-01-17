"""
File: app_telegram.py
Author: [Tarakeshwar NC]
Date: January 15, 2024
Description: This script provides notification mechanism for the system.
References:
1 https://medium.com/codex/using-python-to-send-telegram-messages-in-3-simple-steps-419a8b5e5e2
2 https://stackoverflow.com/questions/33858927/how-to-obtain-the-chat-id-of-a-private-telegram-channel
"""
# Copyright (c) [2024] [Tarakeshwar N.C]
# This file is part of the Tiny_TeZ project.
# It is subject to the terms and conditions of the MIT License.
# See the file LICENSE in the top-level directory of this distribution
# for the full text of the license.

__author__ = "Tarakeshwar N.C"
__copyright__ = "2024"
__date__ = "2024/1/14"
__deprecated__ = False
__email__ = "tarakesh.nc_at_google_mail_dot_com"
__license__ = "MIT"
__maintainer__ = "Tarak"
__status__ = "Development"

__version__ = "0.1"

from . import app_logger

logger = app_logger.get_logger(__name__)

try:
    import queue
    import sys
    import urllib.parse
    from enum import Enum
    from multiprocessing import Process as mp
    from multiprocessing import Queue as mp_Q

    import requests
except Exception as e:
    logger.error(("Import Error" + str(e)))
    sys.exit(1)


class NotifyState(Enum):
    OFF = 0
    ON = 1


class Notifier(object):
    def __init__(self, token: str = "", chat_id: str = ""):
        self.mp_q = mp_Q()
        self.telegram_process = None
        self.token = token
        self.chat_id = chat_id
        self.tel_notifier = None
        self._state: NotifyState = NotifyState.ON
        self._pre_fix = None
        self._img_folder = None
        self.telegram_process_started = False

    def get_state(self):
        return self._state

    def set_state(self, new_state: NotifyState):
        logger.debug(f"{self._state} --> {new_state}")
        try:
            self._state = new_state
        except Exception as e:
            logger.error("_state " + str(e))

    state = property(get_state, set_state)

    def set_folder(self, folder_path):
        self._img_folder = folder_path

    img_folder = property(None, set_folder)

    def set_prefix(self, pre_fix):
        self._pre_fix = (pre_fix)

    pre_fix = property(None, set_prefix)

    def __email_telegram_server__(self, q: mp_Q, token: str = "", chat_id: str | None = None, folder: str = ""):
        class Telegram(object):
            TOKEN: str | None = None

            def __init__(self, chat_id: str, folder: str):
                assert (chat_id is not None), "Chatid can not be None"
                self.chat_id: str = chat_id
                self.folder: str = folder
                return

            def send_message(self, mesg: str = ""):
                url = f'https://api.telegram.org/bot{Telegram.TOKEN}/sendMessage?chat_id={self.chat_id}&text={mesg}'
                requests.get(url).json()  # this sends the message
                return

            def send_img(self, img_file):
                # method = "sendPhoto"
                params = {'chat_id': self.chat_id}
                path = self.folder
                if self.folder is None:
                    path = "."
                f = open(f'{path}/{img_file}', 'rb')
                files = {'photo': f}
                url = f'https://api.telegram.org/bot{Telegram.TOKEN}/sendPhoto?'
                resp = requests.post(url, params, files=files)
                return resp

        assert chat_id is not None, 'chat_id is None'
        self.tel_notifier = Telegram(chat_id=chat_id, folder=folder)
        Telegram.TOKEN = token

        while True:
            # get a message
            try:
                item = q.get(timeout=60)
            except queue.Empty:
                pass
            except KeyboardInterrupt:
                break
            else:
                # check for stop
                if item is None:
                    break
                # report
                if item:
                    if item.find('Error_ScreenShot_') != -1:
                        print(item, flush=True)
                        file_name = str(item).split('_')[3]
                        self.tel_notifier.send_img(img_file=file_name)
                    else:
                        # self.tel_notifier.send_message(item)
                        self.tel_notifier.send_message(urllib.parse.quote_plus(item))
        # all done
        while not q.empty():
            q.get()
        print('Telegram Notifier Exiting...', flush=True)
        return

    def start_service(self):
        self.telegram_process = mp(target=self.__email_telegram_server__, name="Telegram Notifier",
                                   args=(self.mp_q, self.token, self.chat_id, self._img_folder,), daemon=True)
        self.telegram_process.start()
        if self.telegram_process.is_alive():
            self.telegram_process_started = True
        return (self.telegram_process_started)

    def put_message(self, mesg):
        if self._state == NotifyState.ON:
            self.mp_q.put(f'{self._pre_fix}{mesg}')

    def put_image(self, img_file):
        if self._state == NotifyState.ON:
            self.mp_q.put(f'Error_ScreenShot_Image_{img_file}')

    def stop_service(self):
        self.mp_q.put(None)
        if self.telegram_process_started and self.telegram_process is not None:
            self.telegram_process.join()
        self.mp_q.close()


def main():
    import datetime
    import os
    import yaml
    from yaml.loader import SafeLoader

    # img_file = "test.png"

    module_directory = os.path.dirname(os.path.abspath(__file__))
    yaml_file_path = os.path.join(module_directory, "..", "data", "creds", "telegram.yml")

    tel_file = yaml_file_path
    with open(tel_file) as f:
        r = yaml.load(f, Loader=SafeLoader)

    token = r['token']
    chat_id = r['chat_id']

    notifier = Notifier(token=token, chat_id=chat_id)
    notifier.pre_fix = "Tej_0.0.1"
    notifier.img_folder = './log'
    notifier.start_service()
    notifier.put_message(f':{datetime.datetime.now().strftime("%H:%M:%S")}:  Good Morning!!')
    # notifier.put_image(img_file)
    notifier.state = NotifyState.OFF
    notifier.put_message("Good Night!!")
    notifier.stop_service()


if __name__ == '__main__':
    # import requests
    # TOKEN = ""
    # url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    # print(requests.get(url).json())
    main()
