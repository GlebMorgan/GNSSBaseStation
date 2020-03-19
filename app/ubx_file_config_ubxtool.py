#!/usr/bin/env python3
import sys
from argparse import ArgumentParser
from enum import Flag
from itertools import takewhile, dropwhile, islice, chain, repeat
from math import ceil
from pathlib import Path
from subprocess import run
from sys import argv
from types import SimpleNamespace as Namespace
from typing import Tuple, List, Collection, Iterable, Dict

import toml


PROJECT = Path('/home/pi/app')
UBXTOOL = PROJECT/'ubxtool.py'
PID_FILE = Path('/run/user/bs/ntrips.pid')


UBXTOOL_TIMEOUT = 0.5
MAX_ITEMS = 64


class BadConfigError(TypeError):
    """ Invalid config entry in terms of uBlox configuration protocol """


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


def get_sections_itertools(file: Path) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
    """
    Split 'file' to [del] and [set] sections and return tuple
        (<items_to_del>, <items_to_set>) with raw config file strings
    """
    lines = dropwhile(lambda line: line.strip() != '[del]', file.open())
    lines.__next__()  # consume '[del]' marker itself
    del_items = tuple(takewhile(lambda line: line.strip() != '[set]', lines))
    set_items = tuple(lines)
    return del_items, set_items


def get_sections(data: Iterable[str]) -> Tuple[List[tuple], List[tuple]]:
    """
    Split 'data' to [del] and [set] sections
        and return tuple of 2 lists containing (key, value) pairs
    """

    del_items = []
    set_items = []
    target = None
    for line in data:
        line = line.strip()
        if line == '[del]':
            target = del_items
        elif line == '[set]':
            target = set_items
        elif line and target is not None:
            spec = tuple(line.split())[1:3]
            if spec not in target:
                target.append(spec)
    return del_items, set_items


def get_config(data: Iterable[str]) -> Tuple[Dict[str, dict], Dict[str, dict]]:
    """
    Split 'data' stream to [del] and [set] sections
    Parse each config section and split it based on specified memory level
        and return dicts of the following structure for each of the two sections:
        {
            RAM:   {KEY: VALUE, ...}
            BBR:   {KEY: VALUE, ...}
            FLASH: {KEY: VALUE, ...}
        }
    If duplicate config items are encountered, latter replace ones already assigned
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


if __name__ == '__main__':

    parser = ArgumentParser(description='Configure uBlox receiver via ubxtool utility')

    parser.add_argument('-d', '--device', required=True,
                        help="target device path")

    parser.add_argument('-b', '--baudrate', required=True, type=int,
                        help="baudrate for serial output stream")

    parser.add_argument('-l', '--level', nargs='+', default='RAM',
                        help="memory level for configuration ({})"
                        .format((', '.join(MemoryLevel.__members__))))

    group = parser.add_mutually_exclusive_group(required=True)

    group.add_argument('-r', '--reset', nargs='?', metavar='LEVEL', const=['ALL'],
                       help="reset device configuration on specified memory level ({}) "
                       .format((' | '.join(DeviceMask.__members__))))

    group.add_argument('-f', '--configfile', type=Path,
                       help="uCenter Gen9 configuration file input")

    group.add_argument('-i', '--items', nargs='+', default=[],
                       dest='configitems', metavar='ITEM,VALUE',
                       help="configuration parameters for VALSET command")

    # -d    device     (-f)
    # -b    baudrate   (-s)
    # -f    file input         exclusive group
    # -i    items      (-z)    exclusive group
    # -l    level      (-l)
    # -r    reset              exclusive group

    args = parser.parse_args()

    print(*(f'{name}: {value}' for name, value in vars(args).items()), sep='\n')
    exit(0)

    if PID_FILE.exists():
        print("Error: NTRIP server is running. Could be stopped with 'mvbs stop'")
        exit(1)

    if not args.device.startswith('/dev/'):
        args.device = f'/dev/{args.device}'

    UBX_CONFIG_FILE: Path = args.configfile.expanduser().resolve()
    if not UBX_CONFIG_FILE.exists():
        parser.error(f"File {UBX_CONFIG_FILE.name} does not exist")

    valset = ['python', f'{UBXTOOL}', '-f', args.device, '-s', args.baudrate, '-w', f'{UBXTOOL_TIMEOUT}']

    if args.configfile:
        try:
            to_del, to_set = get_config(UBX_CONFIG_FILE.read_text())
        except BadConfigError as e:
            parser.error(e)
        if to_del:
            print('Config items deletion is not supported')
            exit(1)
        if not to_set:
            print(f"No items found under [set] section in config file {UBX_CONFIG_FILE.name}")
            exit(0)

        print("Write configuration from {filename}: {count} items".format(
            filename=UBX_CONFIG_FILE.name, count=sum(len(values) for values in to_set.values())
        ))
        for memory_level, config_items in to_set.items():
            print(f"{' '*4}Memory level {memory_level}: {len(config_items)} items")

            chunked = (len(config_items) > MAX_ITEMS)
            level_spec = ['-l', f'{MemoryLevel[memory_level].value}']
            for i, chunk in enumerate(chunks(config_items, MAX_ITEMS)):
                if chunked:
                    print(f"{' '*8}Chunk #{i+1}, {len(chunk)} items")

                spec = (f'{key},{value}' for key, value in chunk)
                command = valset + level_spec + [*chain(*zip(repeat('-z'), spec))]

                indent = ' ' * (12 if chunked else 8)
                print(*(f"{indent}{key} = {value}" for key, value in chunk), sep='\n')

                print(f"{indent}Command: {' '.join(command)}")
                input("Pause before sending config ...")

                ubxtool_process = run(command)
                if ubxtool_process.returncode != 0:
                    print(f"Failed to send config section #{i} to memory level {memory_level}")
                    exit(1)

    elif args.items:
        ...
    elif args.reset:
        ...
