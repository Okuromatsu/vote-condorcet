"""
ASGI config for Condorcet Voting System project
================================================

Exposes the ASGI callable as a module-level variable named ``application``.
For more information on this file, see:
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/

ASGI is used for asynchronous Python web applications.
Can be deployed with:
- Uvicorn
- Daphne
- Hypercorn
"""

import os
from django.core.asgi import get_asgi_application # pyright: ignore[reportMissingModuleSource]

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'condorcet_project.settings')

application = get_asgi_application()
