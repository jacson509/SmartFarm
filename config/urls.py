"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
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
from django.urls import include, path
from config.api_errors import api_not_found
urlpatterns = [
    path('', include('apps.dashboard.urls')),
    path('', include('apps.simulator.urls')),
    path('', include('apps.accounts.urls')),
    path('', include('apps.facilities.urls')),
    path('api/v1/', include('apps.facilities.api_urls')),
    path('', include('apps.sensors.urls')),
    path('api/v1/', include('apps.sensors.api_urls')),
    path('', include('apps.actuators.urls')),
    path('api/v1/', include('apps.actuators.api_urls')),
    path('api/v1', api_not_found, name='api-root-not-found'),
    path('api/v1/<path:unmatched>', api_not_found, name='api-not-found'),
    path('admin/', admin.site.urls),
]
