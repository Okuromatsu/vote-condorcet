"""
WSGI config for Condorcet Voting System project
================================================

Exposes the WSGI callable as a module-level variable named ``application``.
For more information on this file, see:
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/

This configuration is used by:
- Gunicorn for local development (python manage.py runserver)
- Apache mod_wsgi for production deployment
- Other WSGI servers (Nginx + Gunicorn, etc.)
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'condorcet_project.settings')

application = get_wsgi_application()
