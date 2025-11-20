"""
Django Admin Configuration for Condorcet Voting System
======================================================

Configures Django admin interface for:
- Poll management
- Candidate management  
- Vote viewing (read-only for privacy)
- VoterSession tracking (for admin/debugging)

Security:
- Vote data is read-only in admin (cannot modify votes)
- Voter details limited (only fingerprint, no personal data stored anyway)
- Requires Django admin authentication
"""

from django.contrib import admin # pyright: ignore[reportMissingModuleSource, reportMissingImports]
from .models import Poll, Candidate, Vote, VoterSession


@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    """
    Admin interface for Poll model.
    
    Displays:
    - Poll title and description
    - Active status and vote count
    - Public/Private and Deleted status
    - Creation/update timestamps
    """
    
    list_display = ('title', 'get_candidates_count', 'get_vote_count', 
                   'is_active', 'is_public', 'is_deleted', 'created_at')
    list_filter = ('is_active', 'is_public', 'is_deleted', 'created_at')
    search_fields = ('title', 'description')
    readonly_fields = ('id', 'creator_code', 'created_at', 'updated_at', 'get_vote_count',
                      'get_candidates_count')
    fieldsets = (
        ('Poll Information', {
            'fields': ('id', 'title', 'description', 'creator_code', 'is_active', 'is_public', 'is_deleted')
        }),
        ('Settings', {
            'fields': ('max_votes', 'tiebreaker_method', 'results_released'),
            'description': 'Leave max_votes empty for unlimited votes'
        }),
        ('Statistics', {
            'fields': ('get_vote_count', 'get_candidates_count',
                      'created_at', 'updated_at'),
        }),
    )
    
    def has_delete_permission(self, request, obj=None):
        """Allow deletion in admin."""
        return True
    
    def get_candidates_count(self, obj):
        """Display number of candidates for this poll."""
        return obj.candidate_set.count()
    get_candidates_count.short_description = 'Candidates'
    
    def get_vote_count(self, obj):
        """Display number of votes cast for this poll."""
        return obj.get_vote_count()
    get_vote_count.short_description = 'Votes'


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    """
    Admin interface for Candidate model.
    
    Displays:
    - Candidate name and description
    - Associated poll
    - Creation timestamp
    """
    
    list_display = ('name', 'poll', 'created_at')
    list_filter = ('poll', 'created_at')
    search_fields = ('name', 'description', 'poll__title')
    readonly_fields = ('id', 'created_at')
    fieldsets = (
        ('Candidate Information', {
            'fields': ('id', 'name', 'description', 'poll')
        }),
        ('Metadata', {
            'fields': ('created_at',),
        }),
    )


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    """
    Admin interface for Vote model.
    
    IMPORTANT: Votes are READ-ONLY in admin
    - Protects voting integrity
    - Prevents accidental modification
    - Maintains audit trail
    
    Display only:
    - Poll voted on
    - Vote timestamp
    - Ranking (list of candidate IDs)
    """
    
    list_display = ('poll', 'cast_at', 'get_ranking_preview')
    list_filter = ('poll', 'cast_at')
    search_fields = ('poll__title',)
    readonly_fields = ('id', 'poll', 'voter_fingerprint', 'ranking', 'cast_at')
    
    # Make all fields read-only (no editing votes)
    def has_add_permission(self, request):
        """Prevent manual vote creation in admin."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Prevent vote deletion in admin (audit trail)."""
        return False
    
    def get_ranking_preview(self, obj):
        """Display first 3 candidates in vote ranking."""
        ranking = obj.ranking[:3] if obj.ranking else []
        preview = ' > '.join(ranking)
        if len(obj.ranking) > 3:
            preview += f' ... ({len(obj.ranking)} total)'
        return preview
    get_ranking_preview.short_description = 'Ranking'


@admin.register(VoterSession)
class VoterSessionAdmin(admin.ModelAdmin):
    """
    Admin interface for VoterSession model.
    
    Used for debugging and monitoring:
    - Track multiple votes from same IP
    - Detect voting abuse patterns
    - Audit voter activity
    
    READ-ONLY to preserve audit trail integrity
    """
    
    list_display = ('poll', 'voter_fingerprint', 'vote_count',
                   'first_visit', 'last_activity')
    list_filter = ('poll', 'first_visit')
    search_fields = ('voter_fingerprint', 'ip_address', 'poll__title')
    readonly_fields = ('poll', 'voter_fingerprint', 'cookie_token',
                      'ip_address', 'user_agent', 'first_visit',
                      'last_activity', 'vote_count')
    
    # Make all fields read-only
    def has_add_permission(self, request):
        """Prevent manual session creation."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Prevent session deletion (audit trail)."""
        return False
