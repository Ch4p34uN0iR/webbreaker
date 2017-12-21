#!/usr/bin/env python
# osx build
# pyinstaller --clean -y --windowed webbreaker-osx.spec
# hdiutil create ./webbreaker.dmg -srcfolder webbreaker.app -ov
# linux build
# pyinstaller --clean -y --onefile --dist $(pwd)/rpmbuild/SOURCES/webbreaker-2.0/opt/webbreaker/ --name webbreaker-cli $(pwd)/webbreaker/__main__.py

import os
import subprocess
import sys


REQUIREMENTS_FILE = "requirements.txt"
SETUP_FILE = "setup.py"
PIP = "pip"
PYTHON = "python"
PIP_VERSION_COMMAND = [PIP, "-V"]
PIP_REQ_INSTALL = [PIP, "install", "-r", REQUIREMENTS_FILE]
OPEN_SSL_REQ = [PIP, "install", "pyOpenSSL"]
SETUP_BUILD = [PYTHON, SETUP_FILE, "build"]
SETUP_INSTALL = [PYTHON, SETUP_FILE, "install"]


proc = subprocess.Popen(PIP_VERSION_COMMAND, stdout=subprocess.PIPE)
output = str(proc.communicate()[0].decode())

if output:
    if os.path.isfile(REQUIREMENTS_FILE):
        subprocess.Popen(PIP_REQ_INSTALL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("{} dependencies are now installed".format(REQUIREMENTS_FILE ))
    else:
        print("You are not in the root directory of webbreaker where setup.py is located!")
        exit(1)
else:
    print("Please install pip")
    exit(1)

if sys.version_info[0] > 2.7:
    if os.path.isfile(SETUP_FILE):
        subprocess.Popen(OPEN_SSL_REQ, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.Popen(SETUP_BUILD, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.Popen(SETUP_INSTALL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("Successfully built and installed from {}".format(SETUP_FILE))
else:
    print("Please install Python 2.7 or higher")
    exit(1)
