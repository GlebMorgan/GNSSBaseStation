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
from enum import Enum, Flag
from os import mkfifo, pipe2, O_NONBLOCK
from pathlib import Path
from subprocess import run, Popen, DEVNULL, STDOUT
from time import strftime
from typing import Tuple

import toml

# TODO: migrate to logging and make use of config['tracelevel']

# TODO: update mvbs docstring (incorporate proxying and reset functionalities)


__version__ = "1.2"

PROJECT = Path('/home/pi/app')
CONFIG_FILE = PROJECT/'config.toml'
STR2STR = PROJECT/'str2str-demo5'
STR2STR_LOG = PROJECT/'logs'/f'{STR2STR.stem}.log'
UBX_CONFIG = PROJECT/'ubx_config.py'
RTCM_PROXY = PROJECT/'rtcm_proxy.py'
RTCM_PROXY_LOG = PROJECT/'logs'/f'{RTCM_PROXY.stem}.log'
PID_FILE = Path('/run/user/bs/ntrips.pid')

# NOTE: ACCUMULATIVE_LOGS break configurator UI updates
ACCUMULATIVE_LOGS = False

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


class Zero2GoError(OSError):
    """ Error while communication with Zero2Go module """
    def __init__(self, *args, returncode=1):
        super().__init__(*args)
        self.returncode = returncode


def die(returncode=0):
    print(f"Exiting ({returncode})")
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

        rtcm_proxy_process = Popen(rtcm_proxy, encoding='utf-8', stdout=pipe_input)
        if rtcm_proxy_process.returncode:
            print("Failed to start RTCM proxy")  # TODO
            die(rtcm_proxy_process.returncode)

    else:
        str2str = f'{STR2STR}', '-in', f'serial://{in_spec}', '-out', f'ntrips://{out_spec}'
        str2str_input = DEVNULL

    print("Starting NTRIP server...")
    print(f"Command: {' '.join(str2str)}")

    global str2str_process
    PID_FILE.touch()

    if ACCUMULATIVE_LOGS:
        log_file = STR2STR_LOG.with_name(STR2STR_LOG.stem + '_' + strftime('%d-%m-%Y_%H-%M-%S') + STR2STR_LOG.suffix)
    else:
        log_file = STR2STR_LOG

    str2str_process = Popen(str2str, encoding='utf-8', stdin=str2str_input,
                            stdout=log_file.open('w'), stderr=STDOUT)
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


def config_ublox(receiver_params: dict, serial_params: dict) -> int:
    print("Processing receiver config...")

    tmode = receiver_params['mode']
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
              f"    lat: {receiver_params['lat']}",
              f"    lon: {receiver_params['lon']}",
              f"    height: {receiver_params['hgt']}",
              sep='\n')

        lat, lat_hp = wgs84_to_ublox(receiver_params['lat'], valtype='coordinate')
        lon, lon_hp = wgs84_to_ublox(receiver_params['lon'], valtype='coordinate')
        hgt, hgt_hp = wgs84_to_ublox(receiver_params['hgt'], valtype='height')

        spec.update({
            'CFG-TMODE-LAT':    lat,    'CFG-TMODE-LAT_HP':    lat_hp,
            'CFG-TMODE-LON':    lon,    'CFG-TMODE-LON_HP':    lon_hp,
            'CFG-TMODE-HEIGHT': hgt,    'CFG-TMODE-HEIGHT_HP': hgt_hp,
        })

    elif tmode is TMode.SVIN:
        spec.update({
            'CFG-TMODE-SVIN_MIN_DUR':   int(receiver_params['observe']),
            'CFG-TMODE-SVIN_ACC_LIMIT': int(receiver_params['accuracy'])*10,
        })

    levels = receiver_params['level']
    if isinstance(levels, str):
        levels = (levels,)

    print(f"Running 'ubx_config'...")
    ubx_config = ['python', f'{UBX_CONFIG}', '-d', serial_params['port'],
                  '-b', str(serial_params['baudrate']), '-m', *levels]
    ubx_config += ['-i', *(f'{key}={value}' for key, value in spec.items())]

    print(f"Ubx config command: {' '.join(ubx_config)}")
    sys.stdout.flush()
    return run(ubx_config, text=True).returncode


def reset_ublox(receiver_params: dict, serial_params: dict) -> int:
    ubx_config = ['python', f'{UBX_CONFIG}', '-d', serial_params['port'], '-b', str(serial_params['baudrate'])]
    static_config_file = Path(receiver_params['configfile']).expanduser().resolve()
    if not static_config_file.exists():
        print(f"File '{static_config_file.name}' does not exist")
        return 2
    print(f"Using static config file at {static_config_file}")

    reset_command = [*ubx_config, '-r']
    print(f"Reset command: {' '.join(reset_command)}")
    sys.stdout.flush()
    returncode = run(reset_command, text=True).returncode
    if returncode != 0:
        return returncode

    file_config_command = [*ubx_config, '-f', f'{static_config_file}']
    print(f"Config from file command: {' '.join(file_config_command)}")
    sys.stdout.flush()
    returncode = run(file_config_command, text=True).returncode
    return returncode


def i2c_read(register):
    result = run(['i2cget', '-y', '0x01', '0x29', register], text=True, capture_output=True)
    if result.returncode or not result.stdout:
        msg = f'Read {register} register failed: ' + result.stderr.strip() or '<No details>'
        raise Zero2GoError(msg, returncode=result.returncode)
    return result.stdout


def i2c_write(register, value, verify=True):
    print(f'''Debug: write command: {' '.join(['i2cset', '-y', '0x01', '0x29', register, value])}''')
    result = run(['i2cset', '-y', '0x01', '0x29', register, value], text=True, capture_output=True)
    if result.returncode or not result.stdout:
        msg = f'Write {value} to {register} register failed: ' + result.stderr.strip() or '<No details>'
        raise Zero2GoError(msg, returncode=result.returncode)
    if verify:
        confirm = run(['i2cget', '-y', '0x01', '0x29', register], text=True, capture_output=True)
        if confirm.stdout != value:
            raise Zero2GoError('Write check failed: ' + confirm.stderr.strip() or '<No details>')


def config_zero2go(config):
    status = {
        'shutdown threshold': {
            'register': 12,
            'current': int(i2c_read('12'), 0) / 10,
            'target': config['shutdown'],
            'convert': lambda val: int(val * 10),
        },
        'recovery threshold': {
            'register': 15,
            'current': int(i2c_read('15'), 0) / 10,
            'target': config['recovery'],
            'convert': lambda val: int(val * 10),
        },
        'poweroff timeout': {
            'register': 14,
            'current': int(i2c_read('14'), 0) / 10,
            'target': config['timeout'],
            'convert': lambda val: int(val * 10),
        }
    }

    for item in status.values():
        if item['current'] != item['target']:
            i2c_write(str(item['register']), str(item['convert'](item['target'])))


if __name__ == '__main__':
    try:
        print(f"Environment: '{PROJECT}'")
        print(f"Script: '{__file__}'")

        config = toml.load(str(CONFIG_FILE))
        print(f"Loaded {CONFIG_FILE.name}")

        if len(sys.argv) < 2:
            print(help_message)
            die(0)

        command = sys.argv[1]

        if command == 'test':
            config_zero2go(config['POWER'])
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
                    print("Receiver configuration was not completed due to ubxtool errors")
                    die(exitcode)
            else:
                print("Receiver auto-config is disabled")
                print("Could be enabled with 'BASE.autoconfig = true' in config.toml")

            die(start_server(config['SERIAL'], config['NTRIPS'], config['NTRIPC']))

        elif command == 'restart':
            if not PID_FILE.exists():
                print("NTRIP server is not running")
            else:
                stop_server()

            if '-c' in sys.argv:
                exitcode = config_ublox(config['BASE'], config['SERIAL'])
                if exitcode != 0:
                    print("Receiver configuration was not completed, restart failed")
                    die(exitcode)
                else:
                    print("Receiver is reconfigured successfully")

            if '-z' in sys.argv:
                try:
                    config_zero2go(config['POWER'])
                except Zero2GoError as e:
                    print(f"Zero2Go configuration was not completed: {e}")
                    die(e.returncode)
                else:
                    print("Zero2Go is reconfigured successfully")

            exitcode = start_server(config['SERIAL'], config['NTRIPS'], config['NTRIPC'])
            print(f"NTRIP server restart {'failed' if exitcode else 'success'}")
            die(exitcode)

        elif command == 'reset':
            if PID_FILE.exists():
                stop_server()

            exitcode = reset_ublox(config['BASE'], config['SERIAL'])
            print(f"Receiver reset {'failed' if exitcode else 'success'}")
            exit(exitcode)

        elif command == 'state':
            if PID_FILE.exists():
                if run(f'ps -C {STR2STR.name}', shell=True, stdout=DEVNULL, stderr=DEVNULL).returncode != 0:
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
