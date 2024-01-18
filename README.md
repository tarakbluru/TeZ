# TeZ
TeZ is quick trading app especially for scalpers and is built over the Finvasia APIs.
This project provides all necessary scripts for the app.

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
- Provides mechanism such that feed can be obtained from one Finvasia a/c and trading can be done in another a/c.
- Also has feature to get the session ID from a google sheet.

## Getting Started

### prerequisites
The app has been tested under Python version 3.10.5. Any recent versions also should be able to execute the app.

### Configuration file details
First step after having the repo is to update the Finvasia credentials in the file 'user_cred.yml' which is available in the folder
\data\cred.

Next step is creating the virtual environment for Apps use. For ease of use, a powershell script is given in the ps_scripts folder. To run this, 
you can refer: [Installation](#installation)


#### Configuration File Explanation
![Refer](/data/sys_cfg.yml) This has all configurations required for using the app.

```yaml
# Configuration File details
GUI_CONFIG:  
  APP_TITLE: 'TeZ - NIFTY'
  APP_GEOMETRY: '250x125'    # Size of the app. can be updated by changing here.
  LONG_BUTTON: ' Buy '
  SHORT_BUTTON: 'Short'
  EXIT_BUTTON: 'Exit App'
  SQUARE_OFF_BUTTON: 'Square Off'



# System configuration:
Log file gives the path of the file where log file is to be generated.
DL_FOLDER: 'F:/Python_log/tiny_tez' is where intermediate files such as downloaded symbol files are stored.

# SYSTEM:
  LOG_FILE: 'F:/Python_log/tiny_tez/app.log'
  DL_FOLDER: 'F:/Python_log/tiny_tez'
  MARKET_TIMING: 
    OPEN: "09:15"   #Zero padded
    CLOSE: "15:30"
  SQ_OFF_TIMING: "15:19"  #Future Use
  TELEGRAM:          #Future Use
    NOTIFY : "OFF"  #Notifier is created but only the notifications are not pushed by this control parameter.
    CFG_FILE: null
```

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
