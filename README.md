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

The app is helpful for traders that are trying to learn scalping as well as those who use discretionary techniques.

## Features
Following are the features

- Very simple and intuitive gui
- Uses Bracket order facility of finvasia for trading NIFTYBEES.
- Uses Websocket feed for real time updates.
- Feed can be obtained from one Finvasia a/c and trading can be done in another a/c. This will be helpful, if you have already 
  running algos using websocket.
- Also has feature to get the session ID from a google sheet. This helps in using the session that is running on a cloud machine.
- System square off happens at pre-defined Time (```SQ_OFF_TIMING``` in the configuration file [Here](data/sys_cfg.yml#L155)).
- Default order type is Bracket order for NIFTY and BANKBEES. OCO order type can be chosen by setting configuration.
- Supports Option buying. When you buy Market, CE are bought and when you sell Market, PE are bought. These trades happen at Market prices.
- Supports Order slicing. Say quantity of 1000 niftybees is to be sliced into 10 orders, then 100 qty, 10 orders are placed. In case of 
  Options, quantity is taken interms of lots. Say, 10 lots in 5 legs is required. Then there will be 2 lot per leg, 5 orders are placed. 
- At square off time, orders are fired at maximum quantity possible. That is it does not follow the ice berg order methodology.
- Supports app lock/unlock mechanism to avoid accidental clicks.
- Scale out Mechanism 
- Day wise pnl tracking 
- Tick Recorder (```TR``` in the configuration file, [Here](data/sys_cfg.yml#L149))

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
  APP_GEOMETRY: '350x250'
  ...
TIU:
  ...
  TOKEN_FILE: null     #if the session id is to be shared with other algos, the session id file is given here.
  CRED_FILE:  './data/cred/user_cred.yml' 
  ...

DIU:
  ...
  TOKEN_FILE: './log/user_token.json'   #if DIU and TIU are sharing session, use file generated by TIU above
  CRED_FILE: './data/cred/user_cred.yml' 
  ...

BKU:
  TRADES_RECORD_FILE: './log/orders.csv'

PFMU:  
  PF_RECORD_FILE: './log/pf.csv'

TRADE_DETAILS:
  ############################################################################################
  # Risk Disclosure on Derivatives.
  ############################################################################################
  # A. 9 out of 10 individual traders in equity Futures and Options Segment, incurred net 
  #    losses.
  # B. On an average, loss makers registered net trading loss close to ₹50,000.
  #    Over and above the net trading losses incurred, loss makers expended an additional 
  #    28% of net trading losses as transaction costs.
  # C. Those making net trading profits, incurred between 15% to 50% of such profits 
  #    as transaction cost.
  #
  # D. This program is made open source with  intent ONLY to show how to design a execution 
  #    platform and that is only for educational purpose.
  # 
  #  In case, you use this software, Risk, Reward and Losses are all yours.

  EXCHANGE: 'NSE'             # valid values : NSE NFO
  ###########################################################################################

  EXPIRY_DATE_CFG: 'AUTO'           # Options : 'AUTO' 'MANUAL' Auto - means, nearest next expiry is chosen till 0DTE, 
                                    # on Exp day, Next Expiry date is chosen
                                    # Other option is Manual
  CE_STRIKE_OFFSET_CFG: 'AUTO'      # Options : 'AUTO' 'MANUAL' Till 1 DTE, ATM is chosen, On 1DTE, ITM are chosen, 
                                    # On exp day ATM is chosen
  PE_STRIKE_OFFSET_CFG: 'AUTO'      # Options : 'AUTO' 'MANUAL'

  INSTRUMENT_INFO:
    INST_1:
      SYMBOL: 'NIFTYBEES'                 # Fixed: Do not change 
      ...
    INST_3:
      SYMBOL: 'NIFTY'                     # Fixed: Do not change    
      UL_INDEX: 'NIFTY'                   # Fixed: Do not change
      EXCHANGE: 'NFO'                     # Fixed: Do not change    
      EXPIRY_DATE: '28-MAR-2024'          # Format: '01-FEB-2024'  
      CE_STRIKE_OFFSET: 0                 # 0 means ATM,   1 is OTM, -1 means ITM
      PE_STRIKE_OFFSET: 0                 # 0 means ATM,  -1 is OTM, 1 means ITM
      STRIKE_DIFF: 50                     # Fixed: Do not change
      PROFIT_PER: null                    # Fixed: Do not change
      STOPLOSS_PER: null                  # Fixed: Do not change
      PROFIT_POINTS: 30                   # Points in Option Price 
      STOPLOSS_POINTS: 10                 # Points in Option Price
      ORDER_PROD_TYPE: 'I'                # I - M'I'S  O - GTT_'O'CO
      N_LEGS: 1

    INST_4:
      SYMBOL: 'BANKNIFTY'                 # Fixed: Do not change     
      UL_INSTRUMENT: 'NIFTY BANK'         # Fixed: Do not change  
      ...
  ...

SYSTEM:
  LOG_FILE: './log/app.log'               # log file is generated here.
  DL_FOLDER: './log'                      # intermediate files such as symbol files are downloaded here.
  LMT_ORDER_FEATURE : "ENABLED"           # Do not change
  VIRTUAL_ENV: "NO"                       # Fixed, Do not change
  ...
```
## Usage
Trader requires 2 main UIs Viz., Entry and Trade management. Since these are 2 different operations,
the UI has been designed to reduce the app space on desktop. Also, the app sits on top of all 
other running apps. This is useful while entering numbers based on the chart.

On clicking 'Buy' market, in the NSE Exchange (in config file), NIFTYBEES/BANKBEES are bought. 
On clicking 'Short' market, in the NSE Exchange, NIFTYBEES/BANKBEES are Shorted. 

On clicking 'Buy' market, in the NFO Exchange (in config file), NIFTY/BANKNIFTY CE options are bought. 
The expiry date and strike rate configuration is to be set before starting the app.

On clicking 'Short' market, in the NFO Exchange (in config file), NIFTY/BANKNIFTY PE options are bought. 
The expiry date and strike rate configuration is to be set before starting the app.

By setting OCO feature, even options can have OCO orders placed on broker terminal. 
In case of any failure, user should take manual control.

By having a specific price, system will wait for price to touch or cross over that price for taking position.

Before clicking on Buy or Sell, ensure to have required quantity. For NFO, it is lots.

Order which is waiting for index to cross or touch can be cancelled by specifying in the 
TM(TradeManager) window. This window appears on clicking TM button. 
If there are multiple rows, they can be specified as (say 5-9).

Partial square off can be achieved by setting slider and clicking on the Partial SqOff Button in TM window.
Important Note: Partial square off is available only for the ordertype MIS. It is not available for 
Bracket/OCO order This Helps in scaling out the position.

Trade Manager Window - Toggle functionality - when TM window is open, you can hide it by 
clicking the 'TM' Button again. While in Trademanager window, it can be hidden by clicking on 
'Hide TM' button

Difference between Sqoff in main window and 0% exposure in partial square off
1. When sqoff in main window is clicked, waiting orders are cancelled.
	where as partial square off with 0% is clicked, waiting orders are not cancelled.

2. When sqoff in main window is clicked, only N or BN (based on radio button selection)
	is squared off but not Both.

3. Auto square off at specified time would square off both N and BN.

Behaviour of Auto in strike and expiry date selection in config file
1. When Auto is selected, Nearest expiry date is chosen. On 0DTE,  next expiry is chosen.

2. When strike offset configuration is Auto,  Except on 1DTE, strikes are at ATM. 
	On 1DTE, ITM by one strike is selelected. Objective for this is to avoid theta decay.
	
However, User can overridde by making config Manual and also specifying the offset in the 
INSTRUMENT details.

Daywise (and Not Tradewise) PNL Tracker:
1. Stoloss - Day wise stoploss
2. Target - Day wise Profit
3. Move to Cost - Once a trade is in profits, if the profits go below this, position is squared off.
4. Trail After - Once pnl hits this level, trailing starts.
5. Trailby - After hitting Trail After level, pnl is trailed by this value.

After setting these values, mode mode should be switched from Manual to Auto. Until the levels are touched, 
minor updates can be done using + / - buttons near the Entry box.

If there are major changes are to be done, mode should be brought back to the Manual mode before 
setting new values. Radio button selection from manual to Auto will be treated as new beginning 
and previous levels even though touched are dropped from scanning. 

If the multiple trades are to be taken in a day, the cumulative thresholds should be used. 

For example, if first trade results in profit of 1k, then if to secure atleast profit for the day, SL for next 
trade should be 1k. 

Reasoning behind the design: At EOD, it is day wise PNL that matters. As a trick to understand Day wise PNL, 
imagine there is a stock by the name DayWisePNL. This can have movement from SL to Target.

Note: This app is NOT designed to replace the broker terminal. It only helps in reducing pain point 
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
### App Image for NIFTYBEES (observe normal font, icon - bees, title - TeZ-NSE)
![Refer](/images/TeZ_App.png)

### App Image for NIFTY Option (observe bold font, icon - pay_off, title - TeZ-NFO)
![Refer](/images/Tez_NFO.png)

### Console Image 
![Refer](/images/records.png)

### Trade Manager Image 
![Refer](/images/Trademanager.png)

### Notficaion Channel
https://t.me/github_com_tarakbluru_TeZ