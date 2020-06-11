from django.http import HttpResponse
from django.shortcuts import render
from . import controller

import toml


CONFIG_FILE = '/home/pi/app/config.toml'

config = toml.load(str(CONFIG_FILE))


def status_table(request):
    context = {
        # Dirty fix... Empty string is invalid parameter and will be ignored
        'update_rate': config['status_update_rate'] or '',
        'table_title': 'Base station status',
        'data': [
            dict(name=name, value=parameter)
            for name, parameter in controller.get_status(config).items()
        ],
    }
    return render(request, 'table.html', context)
