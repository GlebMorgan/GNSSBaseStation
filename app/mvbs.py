#!/usr/bin python3

"""
Minimal Viable Base Station

Starts RTKLIB str2str application that expects RTCM3.3 messages on serial port
    and deploys NTRIP server that sends all messages it receives to an NTRIP Caster.

Uses configuration stored in config.toml in same directory as the script itself.

When executing in automatic mode, provide '-a' argument.
In this case it will exit without launching NTRIP server if
    'autostart' config parameter is set to 'false'.

"""

import os
import sys
import toml
from pathlib import Path
from subprocess import Popen, STDOUT, PIPE, DEVNULL


__version__ = "0.1dev2"

str2strProcess = None
autoMode = '-a' in sys.argv

PROJECT = Path(__file__).parent.absolute()
CONFIG_FILE = PROJECT / 'config.toml'
STR2STR = PROJECT / 'str2str'


if __name__ == '__main__':
    returncode = None
    try:
        print(f"Environment: '{PROJECT}'")
        print(f"Script: '{__file__}'")

        config = toml.load(str(CONFIG_FILE))

        if autoMode is True and config['autostart'] is False:
            print("Automatic startup is disabled")
            print("Enable with 'autostart=true' in config.toml")
            print("Exiting script")
            exit(0)

        in_spec = '{port}:{baudrate}:{bytesize}:{parity}:{stopbits}:{flowcontrol}'.format(**config['SERIAL'])
        out_spec = ':{password}@{domain}:{port}/{mountpoint}:{str}'.format(**config['NTRIPC'])

        str2strCommand = str(STR2STR), '-in', f'serial://{in_spec}', '-out', f'ntrips://{out_spec}'

        print("Starting NTRIP server...")
        print(' '.join(str2strCommand))
        str2strProcess = Popen(str2strCommand, encoding='utf-8', stderr=STDOUT)

        print("NTRIP server process spawned")
        str2strProcess.wait()

    except KeyboardInterrupt:
        print("Script interrupt request")
    except Exception as e:
        print(f'{e.__class__.__name__}: {e}')
        returncode = 1
    else:
        print("NTRIP server process terminated unexpectedly")
        returncode = 1
    finally:
        if str2strProcess and str2strProcess.poll() is None:
            print("Terminating NTRIP server process...")
            str2strProcess.terminate()
            str2strProcess.wait(3)  # wait str2str to terminate - 3s should be by far enough
            if str2strProcess.poll() is None:
                str2strProcess.kill()
        returncode = returncode or str2strProcess.poll()
        print(f"Exiting script ({returncode})")
        sys.exit(returncode)
