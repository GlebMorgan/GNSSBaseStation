#!/usr/bin/env python3
from argparse import ArgumentParser
from enum import Flag
from functools import reduce
from itertools import islice, chain, repeat
from math import ceil
from operator import or_ as bitwise_or
from pathlib import Path
from subprocess import run
from types import SimpleNamespace as Namespace
from typing import Tuple, Collection, Iterable, Dict

PROJECT = Path('/home/pi/app')
UBXTOOL = PROJECT/'ubxtool.py'
PID_FILE = Path('/run/user/bs/ntrips.pid')


DEFAULT_BAUDRATE = 38400
UBXTOOL_ITEM_TIMEOUT = 0.025  # Note: values <0.005 will be rounded to 0.0
MAX_ITEMS = 64


class BadConfigError(TypeError):
    """ Invalid config entry in terms of uBlox configuration protocol """


class UbxtoolError(ChildProcessError):
    """ Failure executing ubxtool utility """


class FlagEnum(Flag):
    @property
    def flags(self) -> list:
        return Flag.__str__(self)[self.__class__.__name__.__len__()+1:].split('|')


class MemoryLevel(FlagEnum):
    RAM   = 1 << 0
    BBR   = 1 << 1
    FLASH = 1 << 2
    ALL   = 0b111


class DeviceMask(FlagEnum):
    BBR   = 1 << 0
    FLASH = 1 << 1
    ALL   = 0b11


def die(exitcode, message, **kwargs):
    print(message, **kwargs)
    exit(exitcode)


def parse_config(data: Iterable[str]) -> Tuple[Dict[str, dict], Dict[str, dict]]:
    """
    Split 'data' stream to [del] and [set] sections
    Parse each config section and split it based on specified memory level
        and return dicts of the following structure for each of the two sections:
        {
            RAM:   {KEY: VALUE, ...}
            BBR:   {KEY: VALUE, ...}
            FLASH: {KEY: VALUE, ...}
        }
    If duplicate config items are encountered, latter will replace ones already assigned
    """

    memory_levels = tuple(name for name in MemoryLevel.__members__ if name != 'ALL')
    config = Namespace(delete=dict.fromkeys(memory_levels, {}),
                       assign=dict.fromkeys(memory_levels, {}))
    target = None

    for line in data:
        line = line.strip()
        if line == '[del]':
            target = config.delete
        elif line == '[set]':
            target = config.assign
        elif line and not line.startswith('#') and target is not None:
            try:
                level, key, value = line.split(maxsplit=3)[:3]
                target[level.upper()][key] = value
            except (KeyError, IndexError) as e:
                raise BadConfigError(f"Invalid config at item {i}: {e}")
    return config.delete, config.assign


def chunks(data: Collection, volume: int, optimize=True) -> tuple:
    if optimize:
        volume = ceil(len(data) / ceil(len(data) / volume))
    iterator = iter(data)
    chunk = tuple(islice(iterator, volume))
    while chunk:
        yield chunk
        chunk = tuple(islice(iterator, volume))


def ubxtool_call(command):
    print(f"ubxtool args: {' '.join(command[:10] + ['...'] if len(command) > 10 else command)}")
    ubxtool_process = run(['python', f'{UBXTOOL}', *command], text=True, capture_output=True)
    # Proxying stdout as stdout handle inheritance induces race condition and output misalignment
    # TESTME: do I still need this proxying?
    print(*filter(None, ubxtool_process.stdout.split('\n')), sep='\n')
    return ubxtool_process.returncode


def ubx_valset(*items: Tuple[str, str], device: str, baud: int, level: MemoryLevel):

    timeout = round(UBXTOOL_ITEM_TIMEOUT*len(items), 2)
    valset = ['-f', device, '-s', str(baud), '-w', str(timeout), '-l', str(level.value)]
    spec = (f'{key},{value}' for key, value in items)
    valset.extend(chain(*zip(repeat('-z'), spec)))

    returncode = ubxtool_call(valset)

    if returncode != 0:
        subject = f"item {'='.join(items[0])}" if len(items) == 1 else f"{len(items)} items"
        raise UbxtoolError(f"Failed to send {subject} to memory level {level.name} over {device}:{baud}", returncode)
    else:
        print(f"Sent {len(items)} config item(s) to {level.name} level(s)")


def ubx_reset(device: str, baud: int, timeout: float):
    valset = ['-f', device, '-s', str(baud), '-w', str(round(timeout, 2)), '-p', 'RESET']

    returncode = ubxtool_call(valset)

    if returncode != 0:
        raise UbxtoolError(f"Device reset failed", returncode)
    else:
        print("Device reset success")


if __name__ == '__main__':

    parser = ArgumentParser(description="Configure uBlox receiver via 'ubxtool' utility")

    parser.add_argument('-d', '--device', required=True,
                        help="target device path")

    parser.add_argument('-b', '--baudrate', required=True, type=int,
                        help="baudrate for serial output stream")

    parser.add_argument('-m', '--memory-levels', dest='levels', nargs='+', default='RAM', metavar='LEVEL',
                        help="memory level for configuration ({})"
                        .format((', '.join(MemoryLevel.__members__))))

    group = parser.add_mutually_exclusive_group(required=True)

    group.add_argument('-r', '--reset', action='store_true',
                       help="reset device configuration on all memory levels")

    group.add_argument('-f', '--configfile', type=Path,
                       help="uCenter Gen9 configuration file input, -m is ignored")

    group.add_argument('-i', '--items', nargs='+', default=[],
                       dest='configitems', metavar='ITEM=VALUE',
                       help="configuration parameters for VALSET command")

    if PID_FILE.exists():
        print("Error: NTRIP server is running. Could be stopped with 'mvbs stop'")
        exit(1)

    args = parser.parse_args()
    print("Arguments:", *(f'{" "*4}{name}: {value}' for name, value in vars(args).items()), sep='\n')

    try:

        # Ensure full path to device
        if not args.device.startswith('/dev/'):
            args.device = f'/dev/{args.device}'

        if args.configfile:
            # TODO: use transaction mode

            # Ensure config file exists
            config_file: Path = args.configfile.expanduser().resolve()
            if not config_file.exists():
                parser.error(f"File {config_file.name} does not exist")

            print(f"Loading config from {config_file}...")
            try:
                with config_file.open() as ubx_config:
                    to_del, to_set = parse_config(ubx_config)
            except BadConfigError as e:
                parser.error(e)
            print(f"Loaded {sum(len(values) for values in to_set.values())} items")

            # [del] section is not supported
            if any(items_list for items_list in to_del.values()):
                die(1, 'Config items deletion is not supported')

            # Fast-forward empty config
            if not to_set:
                die(0, f"No items found under [set] section in config file {config_file.name}")

            print()
            print(f"Writing configuration to {args.device}...")
            for memory_level, config_items in to_set.items():
                print()
                print(f"Memory level {memory_level}: {len(config_items)} items")
                for i, chunk in enumerate(chunks(config_items.items(), MAX_ITEMS)):
                    if len(config_items) > MAX_ITEMS:
                        print(f"Chunk #{i+1}, {len(chunk)} items")
                    print(f"Sending config, timeout={round(UBXTOOL_ITEM_TIMEOUT*len(chunk), 2)}s...")
                    ubx_valset(*chunk, device=args.device, baud=args.baudrate, level=MemoryLevel[memory_level])

        elif args.configitems:
            # Parse memory level
            try:
                level = reduce(bitwise_or, (MemoryLevel[item.upper()] for item in args.levels))
            except KeyError as e:
                die(1, f"Invalid memory level '{e.args[0]}', expected within [{', '.join(MemoryLevel.__members__)}]")

            # Ensure maximum amount of config items is not exceeded
            if len(args.configitems) > MAX_ITEMS:
                die(1, f"Maximum of {MAX_ITEMS} items is exceeded, got {len(args.configitems)}")

            # Check config items format ITEM=VALUE
            for i, item in enumerate(args.configitems):
                if item.count('=') != 1 or '=' not in item[1:-1]:
                    die(1, f"Invalid config item #{i} format: '{item}', expected 'ITEM=VALUE'")

            items = tuple(item.split('=') for item in args.configitems)

            print()
            print(f"Sending {len(items)} configuration item(s) to {args.device} at {level.name} memory level(s)...")
            ubx_valset(*items, device=args.device, baud=args.baudrate, level=level)

        elif args.reset:
            print()
            print("Performing device reset...")
            try:
                ubx_reset(device=args.device, baud=args.baudrate, timeout=0.1)
            except UbxtoolError:
                # Try one more time with greater timeout
                from time import sleep
                print("Waiting a moment and retry...")
                sleep(1)
                ubx_reset(device=args.device, baud=args.baudrate, timeout=1)

            # Auto config baudrate to 115200
            print()
            print(f"Set baudrate on UART1 to {args.baudrate}...")
            ubx_valset(('CFG-UART1-BAUDRATE', hex(args.baudrate)),
                       device=args.device, baud=DEFAULT_BAUDRATE, level=MemoryLevel.ALL)

    except UbxtoolError as e:
        die(e.args[1], f"Configuration was not finished properly due to {e.__class__.__name__}: {e.args[0]}")

    except Exception as e:
        import sys
        die(1, f"Device configuration interrupted due to {e.__class__.__name__}: {e.args[0]}", file=sys.stderr)

    else:
        print()
        die(0, "Device configuration completed")
