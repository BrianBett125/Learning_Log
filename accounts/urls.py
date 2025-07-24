"""Define URL patterns for for accounts."""

from django.urls import path, include

app_name = 'accounts'
urlpatterns= [
        # include default auth urls
        path('', include('django.contrib.auth.urls')),
]
