from itertools import repeat, chain
from pathlib import Path
from subprocess import run
from typing import Dict, Tuple


PROJECT = Path('/home/pi/app')
UBXTOOL = Path(PROJECT) / 'ubxtool.py'


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

    print("Command: " + '\n-z'.join(' '.join(valset).split('-z')))

    input("Pause before sending config...")
    ubxtool_process = run(valset)
    print(f"ubxtool: exitcode {ubxtool_process.returncode}")

    return ubxtool_process.returncode
