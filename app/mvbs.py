#!/usr/bin/env python3

"""
Minimal Viable Base Station

Effectively is a wrapper around RTKLIB str2str application.
Script uses parameters from configuration file 'config.toml' (expected in script location directory)
If script is launched automatically, provide '-a' argument.
Available commands are shown when running script with no arguments.

Commands:
    • start
        Configures uBlox Time mode (if BASE.autoconfig is true) using GPSD/ubxtool utility
            and deploys NTRIP server using RTKLIB/str2str utility.
        If time mode is set to anything other than 'Fixed', base station coordinates are ignored
        NTRIP server expects RTCM3.3 messages on serial port and transmits them
            over TCP/IP to an NTRIP Caster specified in configuration file.
    • stop
        Interrupts background NTRIP server process and exits
    • state
        Prints whether NTRIP server launched by this script previously
            is running at the moment, stopped by 'stop' command or stopped/killed externally/itself
"""
import errno
import sys
from os import mkfifo, pipe2, O_NONBLOCK
from enum import Enum, Flag
from functools import reduce
from itertools import chain, repeat
from collections import defaultdict as dd
from operator import or_ as bitwise_or
from typing import Tuple, Dict, Iterable

import toml
from pathlib import Path
from subprocess import run, Popen, DEVNULL, STDOUT


# TODO: migrate to logging and make use of config['tracelevel']

# TODO: update mvbs docstring (incorporate proxying functionality)


__version__ = "1.2"

PROJECT = Path('/home/pi/app')
CONFIG_FILE = PROJECT/'config.toml'
STR2STR = PROJECT/'str2str'
STR2STR_LOG = PROJECT/'logs'/f'{STR2STR.stem}.log'
UBXTOOL = PROJECT/'ubxtool.py'
RTCM_PROXY = PROJECT/'rtcm_proxy.py'
RTCM_PROXY_LOG = PROJECT/'logs'/f'{RTCM_PROXY.stem}.log'
PID_FILE = Path('/run/user/bs/ntrips.pid')

str2str_process = None

help_message = f"""
Minimal viable base station v{__version__}
Commands:
    state - show current state of NTRIP server (running / stopped)
    start - start NTRIP server with parameters specified in config.toml
    stop  - terminate NTRIP server
"""


def makefifo(*args, exist_ok=True, **kwargs):
    # not used currently
    try:
        return mkfifo(*args, **kwargs)
    except OSError as err:
        if err.errno != errno.EEXIST and exist_ok is False:
            raise


class FlagEnum(Flag):
    @property
    def flags(self) -> list:
        return Flag.__str__(self)[self.__class__.__name__.__len__()+1:].split('|')


class TMode(Enum):
    DISABLED = 0
    SVIN = 1
    FIXED = 2


class MLevel(FlagEnum):
    RAM   = 1 << 0
    BBR   = 1 << 1
    FLASH = 1 << 2
    ALL   = 0b111


def die(returncode=0):
    print(f"Exiting script ({returncode})")
    sys.exit(returncode)


def test(*args) -> int:
    conf: dict = args[0]
    for name, value in conf.items():
        print(f'{name}: {value} <{value.__class__.__name__}>')
    return 0


def start_server(serial_config: dict, server_config: dict, caster_config: dict) -> int:

    in_spec = '{port}:{baudrate}:{bytesize}:{parity}:{stopbits}:{flowcontrol}'.format(**serial_config)
    out_spec = ':{password}@{domain}:{port}/{mountpoint}:{str}'.format(**caster_config)
    inject = server_config['inject']

    if inject:
        if isinstance(inject, int):
            inject = (str(inject),)
        else:
            inject = tuple(str(msgid) for msgid in server_config['inject'])

        pipe_output, pipe_input = pipe2(O_NONBLOCK)
        str2str = f'{STR2STR}', '-out', f'ntrips://{out_spec}'
        str2str_input = pipe_output
        rtcm_proxy = 'python', f'{RTCM_PROXY}', '-in', f'serial://{in_spec}', '-a', f'{server_config["anchor"]}', \
                     '-m', *inject, '-i', f'{server_config["interval"]}', '-l', str(RTCM_PROXY_LOG)

        print("Starting RTCM proxy...")
        print(f"Command: {' '.join(rtcm_proxy)}")

        Popen(rtcm_proxy, encoding='utf-8', stdout=pipe_input)

    else:
        str2str = f'{STR2STR}', '-in', f'serial://{in_spec}', '-out', f'ntrips://{out_spec}'
        str2str_input = DEVNULL

    print("Starting NTRIP server...")
    print(f"Command: {' '.join(str2str)}")

    global str2str_process
    PID_FILE.touch()
    str2str_process = Popen(str2str, encoding='utf-8', stdin=str2str_input,
                            stdout=STR2STR_LOG.open('w'), stderr=STDOUT)
    PID_FILE.write_text(str(str2str_process.pid))

    print("NTRIP server process spawned")

    return 0


def stop_server() -> int:
    print("Terminating NTRIP server... ")
    str2str_pid = PID_FILE.read_text().strip()
    result = run(f'kill -INT {str2str_pid}', shell=True, text=True, capture_output=True)

    if result.stdout:
        print(f"Got unexpected result from 'kill' command: {result.stdout.decode()}")
    if result.returncode != 0:
        print("Failed to terminate NTRIP server process")
    else:
        print(f"Terminated process #{str2str_pid}")

    if PID_FILE.exists():
        PID_FILE.unlink()

    return result.returncode


def cleanup_server():
    global str2str_process
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
    return str2str_process.returncode if str2str_process else 0


def wgs84_to_ublox(value: float, valtype: str) -> Tuple[int, int]:
    if valtype == 'height':
        raw = value * 100
    elif valtype == 'coordinate':
        raw = value * 10_000_000
    else:
        raise ValueError("Invalid 'type' argument - "
                         "expected 'height' or 'coordinate'")
    coord = int(raw)
    coord_hp = int((raw - coord) * 100)
    return coord, coord_hp


def ubx_valset(spec: Dict[str, int], *, baudrate, memlevel) -> int:
    valset = [
        'python', str(UBXTOOL),
        '-f', '/dev/serial0', '-s', str(baudrate),
        '-w', '0.5', '-l', str(memlevel)
    ]
    spec_pairs = (f'{key},{int(value)}' for key, value in spec.items())
    valset.extend(chain(*zip(repeat('-z'), spec_pairs)))

    print("Command: " + ' '.join(valset))

    ubxtool_process = run(valset, text=True, capture_output=True)
    # Proxying stdout as stdout handle inheritance induces race condition and output misalignment
    print('\n' + ubxtool_process.stdout.strip('\n') + '\n')
    print(f"ubxtool: exitcode {ubxtool_process.returncode}", end='\n')

    return ubxtool_process.returncode


def config_ublox(params: dict, serial_params: dict) -> int:
    print("Configuring uBlox receiver...")

    tmode = params['mode']
    try:
        if isinstance(tmode, int):
            tmode = TMode(tmode)
        else:
            tmode = TMode[tmode.upper()]
    except (KeyError, AttributeError):
        raise ValueError(f"Invalid time mode '{tmode}' in config.toml - "
                         f"expected within [{', '.join(TMode.__members__)}]")

    spec = {'CFG-TMODE-MODE': tmode.value}
    print(f"Time mode: {tmode.name}")

    if tmode is TMode.FIXED:
        print("Base station coordinates:",
              f"    lat: {params['lat']}",
              f"    lon: {params['lon']}",
              f"    height: {params['hgt']}",
              sep='\n')

        lat, lat_hp = wgs84_to_ublox(params['lat'], valtype='coordinate')
        lon, lon_hp = wgs84_to_ublox(params['lon'], valtype='coordinate')
        hgt, hgt_hp = wgs84_to_ublox(params['hgt'], valtype='height')

        spec.update({
            'CFG-TMODE-LAT':    lat,    'CFG-TMODE-LAT_HP':    lat_hp,
            'CFG-TMODE-LON':    lon,    'CFG-TMODE-LON_HP':    lon_hp,
            'CFG-TMODE-HEIGHT': hgt,    'CFG-TMODE-HEIGHT_HP': hgt_hp,
        })

    elif tmode is TMode.SVIN:
        spec.update({
            'CFG-TMODE-SVIN_MIN_DUR':   int(params['observe']),
            'CFG-TMODE-SVIN_ACC_LIMIT': int(params['accuracy'])*10,
        })

    level = params['level']
    if isinstance(level, int):
        level = MLevel(level)
    elif isinstance(level, str):
        level = MLevel[level.upper()]
    elif isinstance(level, Iterable):
        for item in level:
            if not isinstance(item, str) or item.upper() not in MLevel.__members__:
                raise ValueError(f"Invalid memory level '{item}' in config.toml - "
                                 f"expected within [{', '.join(MLevel.__members__)}]")
        level = reduce(bitwise_or, (MLevel[item.upper()] for item in level))
    else:
        raise ValueError("Invalid memory levels specification in config.toml")

    print(f"Save config to memory levels: {', '.join(level.flags)}")
    return ubx_valset(spec, baudrate=serial_params['baudrate'], memlevel=level.value)


if __name__ == '__main__':
    try:
        print(f"Environment: '{PROJECT}'")
        print(f"Script: '{__file__}'")

        config = dd(lambda: None, toml.load(str(CONFIG_FILE)))
        print(f"Loaded {CONFIG_FILE.name}")

        if len(sys.argv) < 2:
            print(help_message)
            die(0)

        command = sys.argv[1]

        if command == 'test':
            die(test(config))

        if command == 'stop':
            if not PID_FILE.exists():
                print("NTRIP server is not running")
                die(0)
            die(stop_server())

        elif command == 'start':
            if PID_FILE.exists():
                print("NTRIP server is already running")
                die(0)

            if config['autostart'] is False and '-a' in sys.argv:
                print("Automatic startup is disabled")
                print("Could be enabled with 'autostart = true' in config.toml")
                die(0)

            if config['BASE']['autoconfig'] is True:
                exitcode = config_ublox(config['BASE'], config['SERIAL'])
                if exitcode != 0:
                    print("uBlox configuration was not completed due to ubxtool errors")
                    die(exitcode)
            else:
                print("uBlox auto-config is disabled")
                print("Could be enabled with 'BASE.autoconfig = true' in config.toml")

            die(start_server(config['SERIAL'], config['NTRIPS'], config['NTRIPC']))

        elif command == 'state':
            if PID_FILE.exists():
                if run('ps -C str2str', shell=True, stdout=DEVNULL, stderr=DEVNULL).returncode != 0:
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

    except KeyboardInterrupt:
        print("\n\n--- Script interrupted by SIGINT ---\n")
        exitcode = cleanup_server()
        die(exitcode)

    except Exception as e:
        print(f'{e.__class__.__name__}: {e or "<No details>"}')
        cleanup_server()
        die(1)
