"""
Main URL Router for Condorcet Voting System
============================================

This module routes all incoming HTTP requests to appropriate views.
URL patterns are organized by app (voting).

Security: All URLs are protected with CSRF tokens and input validation.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns
from django.views.i18n import set_language

urlpatterns = [
    # Django admin panel
    path('admin/', admin.site.urls),
    
    # i18n language selection (with named URL)
    path('i18n/setlang/', set_language, name='set_language'),
]

# i18n URL patterns (language prefix on all URLs)
urlpatterns += i18n_patterns(
    # Voting app URLs (create polls, vote, view results)
    path('', include('voting.urls')),
)

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
