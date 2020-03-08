from django.http import HttpResponse
from django.shortcuts import render
from . import controller


def status_table(request):
    context = {
        'table_title': 'Base station status',
        'data': [
            dict(name=name, value=parameter)
            for name, parameter in controller.get_status().items()
        ],
    }
    return render(request, 'table.html', context)
