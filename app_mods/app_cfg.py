"""
File: app_cfg.py
Author: [Tarakeshwar NC]
Date: January 15, 2024
Description: This script provides functionality to extract system configuration.
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
__email__ =  "tarakesh.nc_at_google_mail_dot_com"
__license__ = "MIT"
__maintainer__ = "Tarak"
__status__ = "Development"

__version__ = "0.1"

import datetime
import json
import os
from sre_constants import FAILURE, SUCCESS

import app_utils
import gspread
import yaml

logger = app_utils.get_logger(__name__)

current_dir = os.path.dirname(os.path.abspath(__file__))
SYSTEM_CFG_FILE = os.path.join(current_dir, '..', 'data', 'sys_cfg.yml')

_G_SYSTEM_CFG = None
def get_system_config () :
    """Reads the system configuration fromt the yaml file

    Returns: None
    """
    status = FAILURE
    global _G_SYSTEM_CFG
    logger.debug ("Getting System Configuration")
    try:
        with open(SYSTEM_CFG_FILE, 'r', encoding='utf-8') as fname:
            _G_SYSTEM_CFG = yaml.load(fname, Loader=yaml.FullLoader)
        logger.debug(f'Reading config file: {SYSTEM_CFG_FILE}')
        logger.debug(json.dumps(_G_SYSTEM_CFG, sort_keys=False, indent=4))
        status = SUCCESS
    except FileNotFoundError:
        logger.error ("File Not Found Error: ")
        raise
    except Exception as error:
        logger.error (f'Exception occured {error}')
        raise

    return status

def gen_dict_extract(key, var):
    """Extracts key and its information

    Args:
        key (str): key value in the system configuration.
        var (str): key value in the system configuration.

    Yields:
        str: searches through the nested dictionary
    """
    if hasattr(var,'items'): # hasattr(var,'items') for python 3
        for var_k, var_v in var.items(): # var.items() for python 3
            if var_k == key:
                yield var_v
            if isinstance(var_v, dict):
                for result in gen_dict_extract(key, var_v):
                    yield result
            elif isinstance(var_v, list):
                for var_d in var_v:
                    for result in gen_dict_extract(key, var_d):
                        yield result

def get_system_info(key1:str, key2:str):
    """Provides information from the system config file which
    contains nested dictionary

    Args:
        key1 (str): name in the dictionary
        key2 (str): key name in the nested dictionary

    Returns:
        str: system configuration
    """
    var_a=list (gen_dict_extract (key1, _G_SYSTEM_CFG))
    return var_a[0][key2]


def get_config_info(dictname, key) :
    """The function provides mechanism to extract key value from a dictionary

    Args:
        dictname (str): dictionary name
        key (str): key name

    Returns:
        str: key value
    """
    status = FAILURE
    resp = {}

    logger.debug ("Getting Info "+dictname+"  "+key)
    dictname = dictname.upper()
    key = key.upper ()

    try:
        if key in _G_SYSTEM_CFG[dictname].keys() :
            resp =  _G_SYSTEM_CFG[dictname][key]
            status = SUCCESS
    except KeyError as key_error:
        logger.info(f"KeyError: {key_error}. System configuration Error.")
        raise

    except Exception as error:
        logger.info(f"Unexpected error: {error}. System configuration Error.")
        raise

    return status, resp

def get_session_id_from_gsheet (cred, gsheet_client_json, url, sheet_name):
    """This function reads the session id which is available in a google sheet.
    This session id is shared across different computers.

    Args:
        cred (str): contains credential info
        gsheet_client_json (str): file containing google related information.
        url (str): url of the google sheet
        sheet_name (str): Name of the sheet

    Returns:
        str: session id
    """
    susertoken = None
    if "sessionID_Range" in cred.keys():
        # with open(gsheet_client_json,'r', encoding='utf-8') as f:
        #     configdata = json.load(f)
        # print (json.dumps(configdata, indent=2))

        g_c = gspread.service_account(filename=gsheet_client_json)
        s_h = g_c.open_by_url(url)
        wks = s_h.worksheet(sheet_name)
        susertoken = wks.acell(cred['sessionID_Range']).value
        logger.debug (f'susertoken:{susertoken}')
        if susertoken is not None:
            susertoken_date_str = wks.acell(cred['datetime_range']).value
            if susertoken_date_str:
                d_obj = datetime.datetime.strptime(susertoken_date_str, '%d/%m/%Y, %H:%M:%S').date()
                today = datetime.date.today()
                if d_obj != today:
                    logger.debug ('susertoken is not generated today..')
                    susertoken = None

    return susertoken
