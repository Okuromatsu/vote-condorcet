from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.conf import settings
from django.utils import translation
from .models import Poll

def build_url(path, use_www):
    domain = "vote-condorcet.com"
    if use_www:
        domain = "www." + domain
    return f"https://{domain}{path}"

class StaticViewSitemap(Sitemap):
    priority = 0.8
    changefreq = 'daily'

    def items(self):
        # Generate (view_name, lang_code, use_www) tuples
        base_views = ['voting:index', 'voting:about_condorcet', 'voting:create_poll']
        return [
            (view, lang, www)
            for view in base_views
            for lang, _ in settings.LANGUAGES
            for www in [False, True]
        ]

    def location(self, item):
        view_name, lang_code, use_www = item
        with translation.override(lang_code):
            path = reverse(view_name)
        return build_url(path, use_www)

class PollSitemap(Sitemap):
    changefreq = 'hourly'
    priority = 0.6

    def items(self):
        # Generate (poll, lang_code, use_www) tuples
        polls = Poll.objects.filter(is_public=True, is_active=True, is_deleted=False)
        return [
            (poll, lang, www)
            for poll in polls
            for lang, _ in settings.LANGUAGES
            for www in [False, True]
        ]

    def location(self, obj):
        poll, lang_code, use_www = obj
        with translation.override(lang_code):
            path = reverse('voting:vote_poll', args=[poll.id])
        return build_url(path, use_www)

    def lastmod(self, obj):
        poll, _, _ = obj
        return poll.updated_at
