# TeZ
:A quick trading app especially for scalpers, running on top of Finvasia APIs:

This project provides all necessary scripts to run the app. As the code is modularized, the modules can be re-used in other projects as well.

## Table of Contents

- [Introduction](#introduction)
- [Features](#features)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
- [Usage](#usage)
- [Contributing](#contributing)
- [License](#license)

## Introduction

For a scalper, quick entry and exit is a most useful feature in a trading app. Scalpers generally tend to trade in 1 or 2 instruments. So, if the app can be pre-configured for trades in those instruments, that will also be helpful.

Before learning scalping options, it would help to learn in a non-derivative instruments such as NIFTYBEES. This app provides such a mechanism. It provides very simple gui and most of the settings are configured before starting the app. Further, the app provides trading NIFTYBEES while the underlying instrument is still NIFTY index.

The app is expected to be very helpful for traders that are trying to learn scalping.

In future versions, buying CE/PE options are also planned.

## Features
Following are the features

- Very simple and intuitive gui
- Uses Bracket order facility of finvasia for trading NIFTYBEES.
- Uses Websocket feed for real time updates.
- Feed can be obtained from one Finvasia a/c and trading can be done in another a/c. This will be helpful, if you have already 
  running algos using websocket.
- Also has feature to get the session ID from a google sheet. This helps in using the session that is running on a cloud machine.
- System square off happens at pre-defined Time (<span style="font-family: Monaco;">SQ_OFF_TIMING</span> in the configuration file).
- Default order type is Bracket order for NIFTY and BANKBEES. OCO order type can be chosen by setting configuration.
- Supports Option buying. When you buy Market, CE are bought and when you sell Market, PE are bought. These trades happen at Market prices.
- Supports Order slicing. Say quantity of 1000 niftybees is to be sliced into 10 orders, then 100 qty, 10 orders are placed. In case of 
  Options, quantity is taken interms of lots. Say, 10 lots in 5 legs is required. Then there will be 2 lot per leg, 5 orders are placed. 
- At square off time, orders are fired at maximum quantity possible. That is it does not follow the ice berg order methodology.
- Supports app lock/unlock mechanism to avoid accidental clicks.

## Getting Started

### Pre-requisites
The app has been tested under Python version 3.10.5. Any recent versions also should be able to execute the app.

### Configuration file details
Step1: Update the Finvasia credentials in the file 'user_cred.yml' which is available in the folder
\data\cred.

Step2: Update the system configuration for NSE/NFO and required Expiry Date in the system config file. [sys_cfg.yml](/data/sys_cfg.yml) 

Step3: Create virtual environment for Apps use. For ease of use, a powershell script is given in the ps_scripts folder. To run this, 
you can refer: [Installation](#installation) This step is to be done only once.

#### Configuration File Explanation
[sys_cfg.yml](/data/sys_cfg.yml) This has all configurations required for using the app.

```yaml
# Configuration File details
GUI_CONFIG:
  APP_TITLE: 'TeZ'
  APP_GEOMETRY: '250x250'
  ...
TIU:
  ...
  TOKEN_FILE: null     #if the session id is to be shared with other algos, the session id file is given here.
  CRED_FILE:  './data/cred/user_cred.yml' 
  ...
  EXCHANGE: 'NSE'      # valid values : NSE NFO  ...
  QUANTITY: 1          # In case of NSE, it is actual quantity. Incase of NFO, it is lots. 
  USE_GTT_OCO: 'NO'    # 'YES' 'NO'
  N_LEGS: 1            # ice berg orders, total qty is boken into N_legs

  INSTRUMENT_INFO:
    INST_1:
      SYMBOL: 'NIFTYBEES'                 # Fixed: Do not change 
      ...
    INST_3:
      SYMBOL: 'NIFTY'                     # Fixed: Do not change    
      UL_INSTRUMENT: 'NIFTY'              # Fixed: Do not change
      EXCHANGE: 'NFO'                     # Fixed: Do not change    
      EXPIRY_DATE: '28-MAR-2024'          # Format: '01-FEB-2024'  
      CE_STRIKE_OFFSET: 0                 # 0 means ATM,   1 is OTM, -1 means ITM
      PE_STRIKE_OFFSET: 0                 # 0 means ATM,  -1 is OTM, 1 means ITM
      STRIKE_DIFF: 50                     # Fixed: Do not change
      PROFIT_PER: null                    # Fixed: Do not change
      STOPLOSS_PER: null                  # Fixed: Do not change
      PROFIT_POINTS: 30                   # Points in Option Price 
      STOPLOSS_POINTS: 10                 # Points in Option Price

    INST_4:
      SYMBOL: 'BANKNIFTY'                 # Fixed: Do not change     
      UL_INSTRUMENT: 'NIFTY BANK'         # Fixed: Do not change  
      ...
  ...
  TRADES_RECORD_FILE: './log/orders.csv'
  SAVE_TOKEN_FILE_CFG: 'YES'   #if the session id file has to be generated, make this as 'YES'
  SAVE_TOKEN_FILE_NAME: './log/user_token.json'  #session-id along with other information is stored in this file.


DIU:
  ...
  TOKEN_FILE: './log/user_token.json'   #if DIU and TIU are sharing session, use file generated by TIU above
  CRED_FILE: './data/cred/user_cred.yml' 
  ...

SYSTEM:
  LOG_FILE: './log/app.log'  # log file is generated here.
  DL_FOLDER: './log'         # intermediate files such as symbol files are downloaded here.
  ...
```

## Usage

On clicking 'Buy' market, in the NSE Exchange (in config file), NIFTYBEES/BANKBEES are bought. 
On clicking 'Short' market, in the NSE Exchange, NIFTYBEES/BANKBEES are Shorted. 

On clicking 'Buy' market, in the NFO Exchange (in config file), NIFTY/BANKNIFTY CE options are bought. 
The expiry date and strike rate configuration is to be set before starting the app.

On clicking 'Short' market, in the NFO Exchange (in config file), NIFTY/BANKNIFTY PE options are bought. 
The expiry date and strike rate configuration is to be set before starting the app.

By setting OCO feature, even options can have OCO orders placed on broker terminal. 
In case of any failure, user should take manual control.

Note: This app is not designed to replace the broker terminal. It only helps in reducing pain point 
(choosing the strikes and quick entry and exit).  The design goal was to build very simple looking tool and 
avoid complexity in UI and have most parameters pre configured; while trading, too many parameters 
actually hampers clarity in thinking (my empirical observation).

## Contributing

Thank you for considering contributing to this project! We welcome bug reports to help improve the quality of the software.

![Refer](/images/Tez.drawio.png)

### Reporting Bugs

Thank you for helping us improve the project by reporting bugs!

To report a bug, please follow these steps:

1. Check the existing issues to see if the bug has already been reported. If it has, you can provide additional information or subscribe to the existing issue.

2. If the bug has not been reported, open a new issue. Use the "Bug Report" issue template if one is available.

3. Provide a clear and descriptive title for the issue.

4. Describe the bug in detail. Include information about your environment, steps to reproduce the bug, and any relevant error messages.

5. A set of tests can be found in [Tez_Test Cases.pdf](./docs/Tez_Test%20Cases.pdf)

### Code Style

We appreciate your focus on bug reporting. However, if you notice any code-related issues, please include them in the bug report.

### Issues and Discussions

If you have questions or need assistance, feel free to open an issue for discussion.

### License

By contributing, you agree that your contributions will be licensed under the project's [MIT License](./LICENSE).

### Installation

Step-by-step guide on how to install.

```bash
# To clone the repo.
git clone https://github.com/tarakbluru/TeZ.git

````

```bash
# To create virtual environment and install required packages under windows powershell
cd TeZ
powershell -executionpolicy bypass .\ps_scripts\tez_setup.ps1
````

```bash
# To run the TeZ app while in TeZ folder
powershell -executionpolicy bypass .\ps_scripts\tez.ps1
````

### App Image for NIFTYBEES
![Refer](/images/TeZ_App.png)  

### App Image for NIFTY Option (observe bold font)
![Refer](/images/Tez_NFO.png)

### Console Image 
![Refer](/images/records.png)