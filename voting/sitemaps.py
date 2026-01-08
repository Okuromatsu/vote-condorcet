from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.conf import settings
from django.utils import translation
from .models import Poll

class StaticViewSitemap(Sitemap):
    priority = 0.8
    changefreq = 'daily'

    def items(self):
        # Create an item for each view in each language
        base_views = ['voting:index', 'voting:about_condorcet', 'voting:create_poll']
        return [(view, lang_code) for view in base_views for lang_code, _ in settings.LANGUAGES]

    def location(self, item):
        view_name, lang_code = item
        with translation.override(lang_code):
            return reverse(view_name)

class PollSitemap(Sitemap):
    changefreq = 'hourly'
    priority = 0.6

    def items(self):
        # Only include public, active, non-deleted polls in all languages
        polls = Poll.objects.filter(is_public=True, is_active=True, is_deleted=False)
        return [(poll, lang_code) for poll in polls for lang_code, _ in settings.LANGUAGES]

    def location(self, obj):
        poll, lang_code = obj
        with translation.override(lang_code):
            return reverse('voting:vote_poll', args=[poll.id])

    def lastmod(self, obj):
        poll, _ = obj
        return poll.updated_at
