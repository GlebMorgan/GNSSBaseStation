#!/usr/bin/env python3

"""
Minimal Viable Base Station

Effectively is a wrapper around RTKLIB str2str application.
Deploys NTRIP server that expects RTCM3.3 messages on serial port and transmits them
    over serial port to an NTRIP Caster defined in configuration file.

Configuration file 'config.toml' is expected in script location directory
    and is used to control the behaviour of str2str utility as well as launcher itself.

Available commands are shown when running script with no arguments.

When executing in automatic mode, provide '-a' argument.
In this case it will exit without launching NTRIP server if
    'autostart' config parameter is set to 'false'.

"""

import sys
from enum import Enum, Flag

import toml
from pathlib import Path
from subprocess import run, Popen, DEVNULL, STDOUT

from .ubx_config_ubxtool import wgs84_to_ublox, ubx_valset


__version__ = "1.0dev2"

PROJECT = Path('/home/pi/app')
CONFIG_FILE = PROJECT / 'config.toml'
STR2STR = PROJECT / 'bin' / 'str2str'
STR2STR_LOG = PROJECT / 'logs' / 'str2str.log'
PID_FILE_NAME = 'ntrips.pid'
PID_FILE = None

str2str_process = None

help_message = f"""
Minimal viable base station v{__version__}
Commands:
    state - show current state of NTRIP server (running / stopped)
    start - start NTRIP server with parameters specified in config.toml
    stop  - terminate NTRIP server
"""


class TMode(Enum):
    DISABLED = 0
    SVIN = 1
    FIXED = 2


class MLevel(Flag):
    RAM = 1 << 0


def die(exitcode=0):
    print(f"Exiting script ({exitcode})")
    sys.exit(exitcode)


def start_server(serial_config: dict, ntripc_config: dict) -> int:
    if PID_FILE.exists():
        print("NTRIP server is already running")
        die(0)

    in_spec = '{port}:{baudrate}:{bytesize}:{parity}:{stopbits}:{flowcontrol}'.format(**serial_config)
    out_spec = ':{password}@{domain}:{port}/{mountpoint}:{str}'.format(**ntripc_config)

    str2str_command = str(STR2STR), '-in', f'serial://{in_spec}', '-out', f'ntrips://{out_spec}'

    print("Starting NTRIP server...")
    print(' '.join(str2str_command))

    global str2str_process

    PID_FILE.touch()
    str2str_process = Popen(str2str_command, encoding='utf-8',
                            stdin=DEVNULL, stdout=STR2STR_LOG.open('w'), stderr=STDOUT)
    PID_FILE.write_text(str(str2str_process.pid))

    print("NTRIP server process spawned")

    return 0


def config_ublox(params: dict, serial_config, memlevel=''):
    spec = {}

    try:
        tmode = TMode[params['mode']]
    except KeyError:
        raise ValueError(f"Invalid time mode '{params['mode']}' in config.toml, "
                         f"expected within [{', '.join(TMode.__members__)}]")

    spec = dict(MODE=tmode.value)

    if tmode is TMode.FIXED:
        lat, lat_hp = wgs84_to_ublox(config['lat'], valtype='coordinate')
        lon, lon_hp = wgs84_to_ublox(config['lon'], valtype='coordinate')
        hgt, hgt_hp = wgs84_to_ublox(config['hgt'], valtype='height')

        spec.update(
            MODE=tmode,
            LAT=lat, LAT_HP=lat_hp,
            LON=lon, LON_HP=lon_hp,
            HGT=hgt,  HGT_HP=hgt_hp,
        )

    returncode = ubx_valset(spec, baudrate=serial_config['baudrate'], memlevel=)


def stop_server() -> int:
    if not PID_FILE.exists():
        print("NTRIP server is not running")
        die(0)

    print("Terminating NTRIP server... ")
    str2str_pid = PID_FILE.read_text().strip()
    result = run(f'kill -INT {str2str_pid}', capture_output=True, shell=True)

    if result.stdout:
        print(f"Got unexpected result from 'kill' command: {result.stdout.decode()}")
    if result.returncode != 0:
        print("Failed to terminate NTRIP server process")
    else:
        print(f"Terminated process #{str2str_pid}")
        PID_FILE.unlink()

    return result.returncode


if __name__ == '__main__':
    try:
        print(f"Environment: '{PROJECT}'")
        print(f"Script: '{__file__}'")

        config = toml.load(str(CONFIG_FILE))
        print(f"Loaded {CONFIG_FILE.name}")

        PID_FILE = Path(config['tmpfsdir']) / PID_FILE_NAME

        if len(sys.argv) < 2:
            print(help_message)
            die(0)

        command = sys.argv[1]

        if command == 'stop':
            die(stop_server())

        elif command == 'start':
            if config['autostart'] is False and '-a' in sys.argv:
                print("Automatic startup is disabled")
                print("Enable with 'autostart=true' in config.toml")
                die(0)
            config_ublox(config['BASE'], config['SERIAL'])
            die(start_server(config['SERIAL'], config['NTRIPC']))

        elif command == 'state':
            if PID_FILE.exists():
                if run('ps -C str2str', shell=True, capture_output=True).returncode != 0:
                    print("'str2str' process has terminated unexpectedly")
                    PID_FILE.unlink()
                    state = "killed"
                else:
                    state = "running"
            else:
                state = "stopped"
            print(f"NTRIP server is {state}")

        else:
            print(f"Error: invalid command '{command}'")

        die(0)

    except Exception as e:
        print(f'{e.__class__.__name__}: {e}')

        if str2str_process and str2str_process.poll() is None:
            print("Terminating 'str2str' process...")
            str2str_process.terminate()
            # Wait str2str to terminate - 3s should be by far enough
            str2str_process.wait(3)
            if str2str_process.poll() is None:
                str2str_process.kill()
        try:
            PID_FILE.unlink()
        except Exception:
            pass
        die(1)
