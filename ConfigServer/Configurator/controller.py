import json
import re
from datetime import datetime
from itertools import count
from pathlib import Path
from subprocess import run
from time import sleep

import toml


PROJECT = Path('/home/pi/app')
CONFIG_FILE = PROJECT/'config.toml'
MVBS_PATH = PROJECT/'mvbs.py'
MVBS_PID_FILE = Path('/run/user/bs/ntrips.pid')
STR2STR = PROJECT/'str2str-demo5'
STR2STR_LOG = PROJECT/'logs'/f'{STR2STR.stem}.log'

CONFIG = toml.load(str(CONFIG_FILE))
UPDATE_PERIOD = 5

configView = {
    'power': {
        'active': True,
        'voltages': {
            'usb': {'min': 4, 'max': 6},
            'lemo': {'min': 8, 'max': 20},
            'ups': {'min': 3, 'max': 4.5},
        },
        'thresholds': {
            'shutdown': 3.7,
            'recovery': 4.2,
        },
        'timeout': 3,
    },

    'base': {
        'active': True,
        'mode': 'fixed',
        'observe': 180,
        'accuracy': 5,
        'coords': {
            'lat': 27.5590547,
            'lon': 53.9006643,
            'hgt': 289,
        },
    },

    'ntripc': {
        'active': True,
        'domain': 'https://rtk2go.com',
        'port': 2021,
        'mountpoint': 'test',
        'pass': 'password',
        'str': 'Testing;RTCM 3.1;1008(1);1;GPS;SNIP;BY;27.00;54.00;0;0;sNTRIP;;None;B;N;0;',
    },

    'ntrips': {
        'active': False,
        'msgs': [
            {'id': 1005, 'enabled': True, 'description': '1005 message description', 'speed': 1},
            {'id': 1033, 'disabled': True, 'description': '1033 message description', 'speed': 5},
        ],
    },
}


def random_status_generator(rate):
    from random import random, choice
    from time import strftime
    tempers = ('primary', 'secondary', 'success', 'info', 'warning', 'danger', 'dark')

    for n in count():
        statusView = [
            {'name': 'power-status', 'value': f'Power status {n}', 'temper': choice(tempers)},
            {'name': 'base-status', 'value': f'Base status {n}', 'temper': choice(tempers)},
            {'name': 'ntripc-status', 'value': f'NTRIPC status {n}', 'temper': choice(tempers)},
            {'name': 'ntrips-status', 'value': f'NTRIPS status {n}', 'temper': choice(tempers)},
            {'name': 'usb-voltage-bar', 'value': f'{4.75+random()/2:.2f}V'},
            {'name': 'lemo-voltage-bar', 'value': f'{12.1+random():.2f}V'},
            {'name': 'ups-voltage-bar', 'value': f'{3.7+random()/3:.2f}V'},
            {'name': 'base-details', 'value': 'Some base details'},
            {'name': 'rtcm-stream-status', 'value': 'RTCM status'},
            {'name': 'rtcm-stream-speed', 'value': f'{round(random()*100, 1)} KBit/s'},
            {'name': 'rtcm-stream-details', 'value': 'RTCM stream details'},
            {'name': 'timestamp', 'value': strftime('%d.%m.%Y %H:%M:%S')},
        ]

        yield f'data: {json.dumps(statusView)}\n\n'
        sleep(rate)


def status_updater():
    for n in count():
        yield f'data: {json.dumps(get_config_updates())}\n\n'
        sleep(UPDATE_PERIOD)


def get_rtk2go_status(caster_config):
    if 'rtk2go' not in caster_config['domain'].lower():
        return 'Unknown'
    url = 'http://rtk2go.com:{config[port]}/SNIP::MOUNTPT?NAME={config[mountpoint]}'.format(config=caster_config)
    result = run(['curl', '-s', url], text=True, capture_output=True)
    if result.returncode != 0:
        # NTEO:Sometimes RTK2Go replies with no data => curl fails with returncode 52
        return 'Unreachable'
    elif 'Base Station Mount Point Details:' not in result.stdout:
        return 'Down'
    else:
        return 'Up'


def get_config_updates():
    from StatusServer.controller import get_str2str_status, get_ntrips_status, get_zero2go_status, format_unit
    from StatusServer.controller import StreamStatus

    str2str_timestamp_fmt = r'%Y/%m/%d %H:%M:%S'
    target_timestamp_fmt = r'%d.%m.%Y %H:%M:%S'

    voltages = get_zero2go_status()
    active_channel = ('usb', 'lemo', 'ups')[voltages.index(max(voltages))]

    base_status = get_ntrips_status()
    if base_status == 'running':
        base_temper = 'success'
        str2str_details = get_str2str_status(STR2STR_LOG)
        if str2str_details:
            server_status = 'Up'
            server_temper = 'success'
            timestamp = datetime.strptime(str2str_details['timestamp'], str2str_timestamp_fmt)
        else:
            server_status = 'Error'
            server_temper = 'warning'
            timestamp = datetime.now()
    else:
        base_temper = {
            'killed': 'danger',
            'stopped': 'dark'
        }.get(base_status, 'warning')
        str2str_details = {
            'state': ('Down', 'Down'),
            'received': 0,
            'rate': 0,
            'streams': 0,
            'info': '',
        }
        server_status = 'Down'
        server_temper = 'dark'
        timestamp = datetime.now()

    caster_status = get_rtk2go_status(CONFIG['NTRIPC'])
    caster_temper = {
        'Unknown': 'danger',
        'Unreachable': 'secondary',
        'Down': 'dark',
        'Up': 'success',
    }.get(caster_status, 'warning')

    base_mode_description = {
        'disabled': 'Rover mode',
        'svin': 'Coordinates are determined dynamically',
        'fixed': 'Coordinates specified below are used'
    }

    stream_status_tempers = {
        'Down': 'dark',
        'Error': 'danger',
        'Closed': 'secondary',
        'Waiting': 'warning',
        'Connected': 'success',
    }

    rtcm_status = {
        'input': StreamStatus(str2str_details['state'][0]).name,
        'output': StreamStatus(str2str_details['state'][1]).name,
    }

    return [
    {'name': 'power-status', 'value': active_channel.upper(), 'temper': 'success'},
    {'name': 'base-status', 'value': base_status.upper(), 'temper': base_temper},
    {'name': 'ntripc-status', 'value': caster_status.upper(), 'temper': caster_temper},
    {'name': 'ntrips-status', 'value': server_status.upper(), 'temper': server_temper},
    {'name': 'usb-voltage-bar', 'value': f'{voltages[0]}V'},
    {'name': 'lemo-voltage-bar', 'value': f'{voltages[1]}V'},
    {'name': 'ups-voltage-bar', 'value': f'{voltages[2]}V'},  # may be useful: format = :.2f
    {'name': 'base-details', 'value': base_mode_description[CONFIG['BASE']['mode'].lower()]},
    {'name': 'rtcm-input-stream-status', 'value': rtcm_status['input'],
                                         'temper': stream_status_tempers[rtcm_status['input']]},
    {'name': 'rtcm-input-stream-details', 'value': format_unit(int(str2str_details['rate']), 'B', decimals=2)},
    {'name': 'rtcm-output-stream-status', 'value': rtcm_status['output'],
                                          'temper': stream_status_tempers[rtcm_status['output']]},
    {'name': 'rtcm-output-stream-details', 'value': format_unit(int(str2str_details['received']), 'B/s', decimals=2)},
    {'name': 'rtcm-stream-details', 'value': str2str_details['info']},
    {'name': 'timestamp', 'value': datetime.strftime(timestamp, target_timestamp_fmt)},
    ]


def mvbs_handler(command, reconfigure_ublox=True):
    reconfigure_ublox_flag = '-c' if (command == 'restart' and reconfigure_ublox is True) else ''
    result = run([str(MVBS_PATH), command, reconfigure_ublox_flag])
    return not bool(result.returncode)


class RegexDict(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__patterns__ = {}
        for key in tuple(self.keys()):
            if isinstance(key, re.Pattern):
                self.__patterns__[key] = self[key]
                super().__delitem__(key)

    def __getitem__(self, item):
        try:
            return super().__getitem__(item)
        except KeyError:
            if not isinstance(item, str):
                raise
            for regex, value in self.__patterns__.items():
                if re.fullmatch(regex, item):
                    return value
            raise

    def __setitem__(self, key, value):
        if isinstance(key, re.Pattern):
            self.__patterns__[key] = value
        else:
            super().__setitem__(key, value)

    def __delitem__(self, key):
        if key in self.__patterns__:
            del self.__patterns__[key]
        else:
            super().__delitem__(key)


class Action:

    mvbs_action = None
    ublox_restart = None

    @classmethod
    def alterConfig(cls, item, value):
        module, *_, parameter = item.split('-')
        currentValue = CONFIG[module.upper()][parameter]

        try:
            value = type(currentValue)(value)
        except TypeError as e:
            raise TypeError(f"Failed to change configuration: "
                            f"invalid parameter type {type(value)}, expected {type(currentValue)}")

        if value != currentValue:
            CONFIG[module.upper()][parameter] = value

        cls.ublox_restart = parameter.startswith('base-')
        if cls.mvbs_action != 'stop':
            cls.mvbs_action = 'restart'

    @classmethod
    def switchBaseStation(cls, item, value):
        if value == 'on' and not MVBS_PID_FILE.exists():
            cls.mvbs_action = 'start'
        elif MVBS_PID_FILE.exists():
            cls.mvbs_action = 'stop'

    @classmethod
    def switchCaster(cls, item, value):
        return NotImplemented

    @classmethod
    def switchServer(cls, item, value):
        return NotImplemented

    @classmethod
    def switchRTCM(cls, item, value):
        msgs = CONFIG['NTRIPS']['inject']
        target_msg = int(item.strip('rtcm-'))
        value = (value == 'on')
        if target_msg in msgs and value is False:
            msgs.remove(target_msg)
        elif target_msg not in msgs and value is True:
            msgs.append(target_msg)

    @classmethod
    def reset_uBlox(cls):
        return mvbs_handler('reset', reconfigure_ublox=False)

    @classmethod
    def dispatch(cls, params: dict, mapping: dict):
        # params: Dict[<subset of Action.MAPPING>, <one-element lists>] - expected POST request here
        # mapping: Dict[<ui element names>, <method names>] - maps frontend controls to config actions
        for key, value in params.items():
            handler = mapping.get(key, None)
            if handler not in (None, NotImplemented):
                handler(key, value[0])

        print(cls.mvbs_action)
        mvbs_handler(cls.mvbs_action, reconfigure_ublox=cls.ublox_restart)

        with CONFIG_FILE.open('tw', encoding='utf-8') as file:
            toml.dump(CONFIG, file)
            # TODO: preserve comments
