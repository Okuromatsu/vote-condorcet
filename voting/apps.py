"""
Django app configuration for voting module
===========================================

AppConfig subclass that defines the voting app.
This file is required for Django to recognize the voting directory as an app.
"""

from django.apps import AppConfig # pyright: ignore[reportMissingModuleSource]


class VotingConfig(AppConfig):
    """Configuration class for the voting application."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'voting'
    verbose_name = 'Condorcet Voting System'

    def ready(self):
        """
        Method called when Django app is ready.
        Used to register signals and other startup tasks.
        """
        # Import signals here to register them
        # import voting.signals  # Uncomment if you create signals
        pass
