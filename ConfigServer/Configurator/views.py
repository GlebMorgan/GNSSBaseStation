from django.http import HttpResponse
from django.shortcuts import render


def config_ui(request):
    return render(request, 'ui.html')
