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
from subprocess import run, Popen, STDOUT, PIPE, DEVNULL


__version__ = "1.0dev1"

str2strProcess = None

PROJECT = Path(__file__).parent.absolute()
CONFIG_FILE = PROJECT / 'config.toml'
STR2STR = PROJECT / 'str2str'
PID_FILE = Path('/run/user/ntrips.pid')


def die(exitcode=0):
    print(f"Exiting script ({exitcode})")
    sys.exit(exitcode)


def start_server(config):
    if PID_FILE.exists():
        print("NTRIP server is already running")
        die(0)

    in_spec = '{port}:{baudrate}:{bytesize}:{parity}:{stopbits}:{flowcontrol}'.format(**config['SERIAL'])
    out_spec = ':{password}@{domain}:{port}/{mountpoint}:{str}'.format(**config['NTRIPC'])

    str2strCommand = str(STR2STR), '-in', f'serial://{in_spec}', '-out', f'ntrips://{out_spec}'

    print("Starting NTRIP server...")
    print(' '.join(str2strCommand))
    str2strProcess = Popen(str2strCommand, encoding='utf-8', stderr=STDOUT)

    print("NTRIP server process spawned")
    ...
    PID_FILE.touch()
    PID_FILE.write_text(str(os.getpid()))

    return str2strProcess.returncode


def stop_server():
    if not PID_FILE.exists():
        print("NTRIP server is not running")
        die(0)

    print("Terminating NTRIP server... ")
    str2str_pid = PID_FILE.read_text().strip()
    result = run(['kill', '-INT', str2str_pid], capture_output=True, shell=True)
    PID_FILE.unlink()

    if result.stdout:
        print(f"Unexpected result from 'kill' command: {result.stdout.decode()}")
    else:
        print(f"Killed process {str2str_pid}")

    return result.returncode


if __name__ == '__main__':
    try:
        print(f"Environment: '{PROJECT}'")
        print(f"Script: '{__file__}'")

        if sys.argv[1] == 'stop':
            sys.exit(stop_server())

        elif sys.argv[1] == 'start':
            config = toml.load(str(CONFIG_FILE))
            if config['autostart'] is False and '-a' in sys.argv:
                print("Automatic startup is disabled")
                print("Enable with 'autostart=true' in config.toml")
                die(0)
            sys.exit(start_server(config))

        else:
            print("TODO: print launcher info")  # TODO

    except KeyboardInterrupt:
        print("Script interrupt request")
    except Exception as e:
        print(f'{e.__class__.__name__}: {e}')
        exitcode = 1
    else:
        print("NTRIP server process terminated unexpectedly")
        exitcode = 1
    finally:
        if str2strProcess and str2strProcess.poll() is None:
            print("Terminating NTRIP server process...")
            str2strProcess.terminate()
            str2strProcess.wait(3)  # wait str2str to terminate - 3s should be by far enough
            if str2strProcess.poll() is None:
                str2strProcess.kill()
        exitcode = exitcode or str2strProcess.poll()
        die(exitcode)
