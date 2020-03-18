#!/usr/bin/env python3
import sys
from argparse import ArgumentParser
from enum import Flag
from itertools import takewhile, dropwhile, islice, chain, repeat
from math import ceil
from pathlib import Path
from subprocess import run
from sys import argv
from typing import Tuple, List, Collection, Iterable

import toml


PROJECT = Path('/home/pi/app')
PID_FILE = Path('/run/user/bs/ntrips.pid')


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
    target = []
    for line in data:
        line = line.strip()
        if line == '[del]':
            target = del_items
        elif line == '[set]':
            target = set_items
        elif line:
            spec = tuple(line.split())[1:3]
            if spec not in target:
                target.append(spec)
    return del_items, set_items


def chunks(data: Collection, volume: int, optimize=True) -> tuple:
    if optimize:
        volume = ceil(len(data) / ceil(len(data) / volume))
    iterator = iter(data)
    chunk = tuple(islice(iterator, volume))
    while chunk:
        yield chunk
        chunk = tuple(islice(iterator, volume))


if __name__ == '__main__':

    # 'python', 'ubxtool.py', '-f', '/dev/serial0', '-s', '115200', '-w', '0.5'

    parser = ArgumentParser(description='Configure uBlox receiver via ubxtool utility')

    parser.add_argument('-d', '--device', required=True,
                        help="target device path")

    parser.add_argument('-b', '--baudrate', required=True,
                        help="baudrate for serial output stream")

    parser.add_argument('-l', '--level', nargs='+', default='RAM',
                        help="memory level for configuration ({})"
                        .format((', '.join(MemoryLevel.__members__))))

    group = parser.add_mutually_exclusive_group()

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

    UBX_CONFIG_FILE: Path = args.configfile.expanduser().resolve()
    if not UBX_CONFIG_FILE.exists():
        parser.error(f"File {UBX_CONFIG_FILE.name} does not exist")

    VALSET = ['python', 'ubxtool.py', '-f', '/dev/serial0', '-s', '115200', '-w', '0.5']

    to_del, to_set = get_sections(UBX_CONFIG_FILE.read_text())

    if to_del:
        print('Config items deletion is not supported')
        exit(1)

    for i, items in enumerate(chunks(to_set, 64)):
        print(f"Chunk #{i+1}, {len(items)} of {len(to_set)} items")

        spec_pairs = []
        for key, val in items:
            spec_pairs.append(f"{key},{int(val, 16)}")

        VALSET.extend(chain(*zip(repeat('-z'), spec_pairs)))

        print("Command: " + '\n-z'.join(' '.join(VALSET).split('-z')))

        reply = ''
        while reply.strip() not in ('y', 'n'):
            reply = input('Send values [y/n]? ')
        if reply == 'y':
            ubxtool_process = run(VALSET)
            print(f"ubxtool.py exitcode: {ubxtool_process.returncode}")
        else:
            print("Cancelled")
            exit(0)
        print()
