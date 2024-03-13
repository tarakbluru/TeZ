"""
File: app_logger.py
Author: [Tarakeshwar NC]
Date: January 15, 2024
Description:  This script provides application logging.
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


import logging
import os

import yaml
from datetime import datetime

LOG_FILE = None

try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    yml_file = os.path.join(current_dir, '..', 'data', 'sys_cfg.yml')
    with open(yml_file, 'r') as file:
        data = yaml.load(file, Loader=yaml.FullLoader)
        log_file_name = data['SYSTEM']['LOG_FILE']
        # Extract the extension from the original log_file_name
        file_name, file_extension = os.path.splitext(log_file_name)
        current_datetime = datetime.now().strftime('%m_%d_%H_%M_%S')
        LOG_FILE = f'{file_name}_{current_datetime}{file_extension}'
except TypeError as e:
    print (f'Exception:{e}')
    sys.exit (1)
except Exception:
    ...

def init_logger(file: str):
    global LOG_FILE
    LOG_FILE = file
    print (f'Logfile: {LOG_FILE}')
    return


def get_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    # %Z for time zone
    formatter = logging.Formatter('[%(asctime)s] {%(filename)s:%(lineno)4d} %(levelname)s - %(message)s', '%m-%d %H:%M:%S')

    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter('{%(filename)s:%(lineno)4d} %(message)s')

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(logging.INFO)

    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    return logger
