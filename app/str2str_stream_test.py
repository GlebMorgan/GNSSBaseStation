from subprocess import Popen, run, PIPE, STDOUT
from os import system
import argparse
import sys
from time import sleep
from signal import SIGINT
import serial


# |date        |time      |in/out4x   |received    |rate   |streams   |status         |error_code
# 2020/02/15   14:18:42   [EC---]     0 B          0 bps   (2)        connect error   (111)

# statuses: E: error, -: Close, W: wait, C: connect, C: active


START_BYTES = 0xb5, 0x62


def prepend(prefix, iterable):
    for item in iterable:
        yield prefix
        yield item


def test(arg):
    print("Is 'str2str' process running?")
    result = run('ps -A | grep str2str', shell=True, capture_output=True, text=True).stdout
    print(result or 'No processes found')


parser = argparse.ArgumentParser(description='Testing str2str')

parser.add_argument('-f', '--file', nargs='?', const='log.rtcm', metavar='FILENAME',
                    help="Output RTCM stream to a specified file (default: '%(const)s')")

parser.add_argument('-n', '--ntrip', nargs='?', const='TEST',
                    dest='mntpoint', metavar='SERVER',
                    help="Output RTCM stream to 192.168.100.12:2101 "
                         "to specified mount point (default: %(const)s)")

parser.add_argument('-b', '--baud', default=115200, type=int, metavar='BAUDRATE',
                    help="Serial input stream baudrate (default: %(const)s)")

parser.add_argument('-t', '--test', nargs='?', const=True,
                    help='run test action (for development purposes)')

args = parser.parse_args()

if __name__ == '__main__':

    if args.test:
        exit(test(args.test))

    in_arg = rf'serial://serial0:{args.baud}'

    out_args = []
    if args.file:
        out_args.append(rf'file://{args.file}')
    if args.mntpoint:
        out_args.append(rf'ntrips://:123@192.168.100.21:2101/{args.mntpoint}')

    args = './str2str', '-in', in_arg, *prepend('-out', out_args), '-t', '5'
    print(*args)
    # system(' '.join(args))
    with Popen(args, encoding='cp866', stdout=PIPE, stderr=STDOUT) as process:

        for i in range(50):
            print(f'stdout: {process.stdout.readline()}', end='')
        process.terminate()
        process.wait()

    print(f"Exit code: {process.poll()}")

    # print(subprocess.run(['dir'], shell=True, capture_output=True, encoding='cp866').stdout)
