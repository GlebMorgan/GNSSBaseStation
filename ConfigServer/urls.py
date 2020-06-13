"""status_table URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from StatusServer.views import status_table
from Configurator.views import config_ui, status_updates, submit_config

urlpatterns = [
    path('', config_ui, name='config'),
    path('update/', status_updates, name='update-status'),
    path('status/', status_table, name='static-status'),
    path('submit/', submit_config, name='submit-config'),
]
