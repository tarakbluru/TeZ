import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app_utils

def main ():
    logger = app_utils.get_logger(__name__)
    logger.debug ("Hello World !")
    logger.info ("Hello World !")


if __name__=="__main__":
    main ()
