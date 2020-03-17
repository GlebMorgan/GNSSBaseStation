#!/usr/bin/env python3

from itertools import takewhile, dropwhile, islice
from math import ceil
from pathlib import Path
from subprocess import run
from sys import argv
from typing import Tuple, List, Collection

import toml


PROJECT = Path('/home/pi/app')
PID_FILE = Path('/run/user/bs/ntrips.pid')


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


def get_sections(file: Path) -> Tuple[List[tuple], List[tuple]]:
    """
    Split 'file' to [del] and [set] sections
        and return tuple of 2 lists containing (key, value) pairs
    """
    del_items = []
    set_items = []
    target = []
    for line in file.open():
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


def prepend(prefix, iterable):
    for item in iterable:
        yield prefix
        yield item


if __name__ == '__main__':

    if PID_FILE.exists():
        print("Error: NTRIP server is running. Stop it with 'mvbs stop' and run the script once again")
        exit(1)

    if len(argv) < 2:
        print("Error: uCenter config file path should be provided as an argument")
        exit(1)

    UBX_CONFIG_FILE = Path(argv[1]).resolve().absolute()
    VALSET = ['python', 'ubxtool.py', '-f', '/dev/serial0', '-s', '115200', '-w', '0.5']

    to_del, to_set = get_sections(UBX_CONFIG_FILE)

    if to_del:
        print('Config items deletion is not supported')
        exit(1)

    for i, items in enumerate(chunks(to_set, 64)):
        print(f"Chunk #{i+1}, {len(items)} of {len(to_set)} items")

        spec_pairs = []
        for key, val in items:
            spec_pairs.append(f"{key},{int(val, 16)}")

        VALSET.extend(prepend('-z', spec_pairs))

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
