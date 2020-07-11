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
from subprocess import run, Popen, DEVNULL, STDOUT, TimeoutExpired
from time import strftime, sleep
from typing import Tuple

import toml


# TODO: update module docstring


__version__ = "1.3"

PROJECT = Path('/home/pi/app')
CONFIG_FILE = PROJECT / 'config.toml'

STR2STR = PROJECT / 'str2str-demo5'
STR2STR_LOG = PROJECT / 'logs' / f'{STR2STR.stem}.log'
UBX_CONFIG = PROJECT / 'ubx_config.py'
RTCM_PROXY = PROJECT / 'rtcm_proxy.py'
RTCM_PROXY_LOG = PROJECT / 'logs' / f'{RTCM_PROXY.stem}.log'
CONFIGURATOR_STARTUP_SCRIPT = Path('/home/pi/ConfigServer/manage.py')
CONFIGURATOR_LOG = PROJECT / 'logs' / 'ConfigServer.log'

NTRIPS_PID_FILE = Path('/run/user/bs/ntrips.pid')
CONFIGURATOR_PID_FILE = Path('/run/user/bs/django.pid')

ACCUMULATIVE_LOGS = True


def makefifo(*args, exist_ok=True, **kwargs):
    # not used currently
    try:
        return mkfifo(*args, **kwargs)
    except OSError as err:
        if err.errno != errno.EEXIST and exist_ok is False:
            raise


def ensure_started(desired: bool, pid_file: Path, name: str):
    if pid_file.exists() is not desired:
        msg = f"{name} is not running" if desired else f"{name} is already running"
        print(msg)
        die(0)


def get_state(pid_file: Path):
    if pid_file.exists():
        pid = pid_file.read_text().strip()
        if run(f'test -d /proc/{pid}', shell=True).returncode != 0:
            pid_file.unlink()
            state = "killed"
        else:
            state = "running"
    else:
        state = "stopped"
    return state


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


def start_server(serial_config: dict, server_config: dict, caster_config: dict, *, verbose: int = False) -> int:

    in_spec = '{port}:{baudrate}:{bytesize}:{parity}:{stopbits}:{flowcontrol}'.format(**serial_config)
    out_spec = ':{password}@{domain}:{port}/{mountpoint}:{str}'.format(**caster_config)
    inject = server_config['inject']

    if inject:
        if isinstance(inject, int):
            inject = (str(inject),)
        else:
            inject = tuple(str(msg_id) for msg_id in server_config['inject'])

        pipe_output, pipe_input = pipe2(O_NONBLOCK)
        verbose = ('-t', str(verbose)) if verbose else ()
        str2str = f'{STR2STR}', '-out', f'ntrips://{out_spec}', *verbose
        str2str_input = pipe_output
        rtcm_proxy = 'python', f'{RTCM_PROXY}', '-in', f'serial://{in_spec}', '-a', f'{server_config["anchor"]}', \
                     '-m', *inject, '-i', f'{server_config["interval"]}', '-l', str(RTCM_PROXY_LOG)

        print("Starting RTCM proxy...")
        print(f"Command: {' '.join(rtcm_proxy)}")

        rtcm_proxy_process = Popen(rtcm_proxy, encoding='utf-8', stdout=pipe_input)

    else:
        str2str = f'{STR2STR}', '-in', f'serial://{in_spec}', '-out', f'ntrips://{out_spec}'
        str2str_input = DEVNULL

    print("Starting NTRIP server...")
    print(f"Command: {' '.join(str2str)}")

    if ACCUMULATIVE_LOGS:
        log_file = STR2STR_LOG.with_name(STR2STR_LOG.stem + '_' + strftime('%d-%m-%Y_%H-%M-%S') + STR2STR_LOG.suffix)
    else:
        log_file = STR2STR_LOG

    str2str_process = Popen(str2str, encoding='utf-8', stdin=str2str_input, stdout=log_file.open('w'), stderr=STDOUT)

    # Wait a bit to ensure the process didn't crash short
    try:
        str2str_process.wait(0.1)
    except TimeoutExpired:
        pass
    else:
        print("Failed to start NTRIP server")
        die(str2str_process.returncode)

    NTRIPS_PID_FILE.write_text(str(str2str_process.pid))
    print("NTRIP server process spawned")

    return 0


def stop_process(pid_file, name) -> int:
    print(f"Terminating {name}...")

    if not pid_file.exists():
        print(f"Unable to stop {name} process - .pid file is missing")
        return -1

    pid = pid_file.read_text().strip()
    interrupt_result = run(f'kill -INT {pid}', shell=True, text=True, capture_output=True)

    if interrupt_result.stdout:
        print(f"Got unexpected result from 'kill' command: {interrupt_result.stdout.decode()}")
    if interrupt_result.returncode != 0:
        print(f"Failed to terminate {name} process")
        print(f"Killing #{pid}...")
        interrupt_result = run(f'kill {pid}', shell=True, text=True, capture_output=True)
        print(f"Killed process #{pid}")
    else:
        print(f"Terminated process #{pid}")

    pid_file.unlink()
    return interrupt_result.returncode


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


def print_help():
    command_description = {
        'state':              ('show current state of NTRIP server (running / stopped / killed)',),
        'start [-c] [-z]':    ('start NTRIP server with parameters specified in config.toml',
                               '-c and -z parameters will reconfigure uBlox chip and zero2go module respectively',
                               'with parameters specified in config.toml'),
        'restart [-c] [-z]':  ('restart NTRIP server and reconfigure uBlox (-c) or/and zero2go (-z)',),
        'stop':               ('terminate NTRIP server',),
        'log [lines]':        ('show NTRIP server log (truncated to \'lines\' number of lines, if specified)',),
        'reset':              ('reset all (!) uBlox configuration to factory defaults',
                               'May be later configured once again with \'start -c\' command'),
        'server run':         ('start Config server in foreground (blocking, output is shown in console)',),
        'server start':       ('start Config server in background (non-blocking, output is redirected to log file)',),
        'server stop':        ('terminate Config server',),
        'server log [lines]': ('show Config server log, similarly to above',),
    }

    commands_col_width = max(len(item) for item in command_description.keys())

    print("Minimal viable base station v{__version__}")
    print("Commands:")
    for name, description in command_description.items():
        command_column = name.ljust(commands_col_width)
        for line in description:
            print(f"    {command_column}  {line}")
            command_column = ''.ljust(commands_col_width+4)


if __name__ == '__main__':
    command = None
    try:
        config = toml.load(str(CONFIG_FILE))

        if len(sys.argv) < 2:
            print_help()
            die(0)

        command = sys.argv[1]

        if command == 'test':
            die(test(config))

        if command == 'stop':
            ensure_started(True, NTRIPS_PID_FILE, 'NTRIP server')
            die(stop_process(NTRIPS_PID_FILE, 'NTRIP server'))

        elif command == 'start' or command == 'restart':
            if command == 'start':
                ensure_started(False, NTRIPS_PID_FILE, 'NTRIP server')
                if '-a' in sys.argv and config['autostart'] is False:
                    print("Automatic startup is disabled, enable in config.toml")
                    die(0)

            if command == 'restart':
                if NTRIPS_PID_FILE.exists():
                    stop_process(NTRIPS_PID_FILE, 'NTRIP server')
                else:
                    print("NTRIP server is not running")

            if '-c' in sys.argv:
                exitcode = config_ublox(config['BASE'], config['SERIAL'])
                if exitcode != 0:
                    print(f"Receiver configuration was not completed. {command.capitalize()} failed")
                    die(exitcode)
                else:
                    print("Receiver is reconfigured successfully")

            if '-z' in sys.argv:
                try:
                    config_zero2go(config['POWER'])
                except Zero2GoError as e:
                    print(f"Zero2Go configuration was not completed: {e}. {command.capitalize()} failed")
                    die(e.returncode)
                else:
                    print("Zero2Go is reconfigured successfully")

            verbosity = 5 if '-v' in sys.argv else False
            exitcode = start_server(config['SERIAL'], config['NTRIPS'], config['NTRIPC'], verbose=verbosity)

            print(f"NTRIP server {command} {'failed' if exitcode else 'success'}")
            die(exitcode)

        elif command == 'reset':
            if NTRIPS_PID_FILE.exists():
                was_running = True
                stop_process(NTRIPS_PID_FILE, 'NTRIP server')
            else:
                was_running = False

            exitcode = reset_ublox(config['BASE'], config['SERIAL'])
            print(f"Receiver reset {'failed' if exitcode else 'success'}")

            if exitcode:
                die(exitcode)
            elif was_running:
                exitcode = start_server(config['SERIAL'], config['NTRIPS'], config['NTRIPC'])
                die(exitcode)

        elif command == 'state':
            print(f"NTRIP server is {get_state(NTRIPS_PID_FILE)}")
            die(0)

        elif command == 'log':
            max_lines = int(sys.argv[-1]) if len(sys.argv) == 3 else None
            logfiles = STR2STR_LOG.parent.glob(STR2STR.stem + '*.log')
            logfile = max(logfiles, key=lambda file: file.stat().st_mtime)
            lines = logfile.read_text(encoding='utf-8', errors='replace').split('\n')
            print(*lines[-(max_lines or 0):], sep='\n')

        elif command == 'server':
            if len(sys.argv) == 2:
                # No command - show status
                print(f"Config server is {get_state(CONFIGURATOR_PID_FILE)}")
                die(0)

            action = sys.argv[2]

            if action == 'start' or action == 'run':
                if config['autostart'] is False and '-a' in sys.argv:
                    print("Automatic startup is disabled, enable in config.toml")
                    die(0)

                django_command = ['python', f'{CONFIGURATOR_STARTUP_SCRIPT}', 'runserver', '0:8000']
                print(f"Command: {' '.join(django_command)}")

                if action == 'run':
                    # Run in foreground, blocking, output is shown in console
                    result = run(django_command, text=True)
                    die(result.returncode)

                if action == 'start':
                    # Run in background, non-blocking, output is redirected to log file
                    django_process = Popen(django_command, encoding='utf-8',
                                           stdout=CONFIGURATOR_LOG.open('w'), stderr=STDOUT)
                    CONFIGURATOR_PID_FILE.write_text(str(django_process.pid))
                    print("Config server process spawned")

            elif action == 'stop':
                ensure_started(True, CONFIGURATOR_PID_FILE, 'Config server')
                die(stop_process(CONFIGURATOR_PID_FILE, 'Config server'))

            elif action == 'log':
                max_lines = int(sys.argv[-1]) if len(sys.argv) == 4 else None
                lines = CONFIGURATOR_LOG.read_text(encoding='utf-8', errors='replace').split('\n')
                print(*lines[-(max_lines or 0):], sep='\n')

            else:
                print(f"Error: invalid action '{action}'")

        else:
            print(f"Error: invalid command '{command}'")

        die(0)

    except KeyboardInterrupt:
        print("\n\n--- Script interrupted by SIGINT ---\n")
        die(0)

    except Exception as e:
        print(f'{e.__class__.__name__}: {e or "<No details>"}')
        die(1)
