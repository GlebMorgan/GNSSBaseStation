import re
from pathlib import Path
from subprocess import run

import toml


PROJECT = Path('/home/pi/app')
CONFIG_FILE = PROJECT/'config.toml'
MVBS_PATH = PROJECT/'mvbs.py'
MVBS_PID_FILE = Path('/run/user/bs/ntrips.pid')

CONFIG = toml.load(str(CONFIG_FILE))


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
        'port': '2021',
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


def mvbs_handler(command, reconfigure_ublox=True):
    reconfigure_ublox_flag = '-c' if (command == 'restart' and reconfigure_ublox is True) else ''
    run([str(MVBS_PATH), command, reconfigure_ublox_flag])


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
