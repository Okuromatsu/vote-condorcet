"""
Database models for Condorcet Voting System
============================================

Defines the data structure for:
- Poll: A voting poll with multiple candidates
- Candidate: A candidate in a poll
- Vote: A ranked ballot cast by a voter
- VoterSession: Tracks voters to prevent duplicate votes (via cookies/IP)

Security:
- All models use Django ORM (prevents SQL injection)
- Input validation at model level
- Timestamps for audit trail
- Voter anonymity maintained (no personal data stored)
"""

from django.db import models # pyright: ignore[reportMissingModuleSource]
from django.core.validators import MinValueValidator, MaxLengthValidator # pyright: ignore[reportMissingModuleSource]
from django.utils import timezone # pyright: ignore[reportMissingModuleSource]
import uuid
import string
import random


def generate_token():
    """Generate unique hex token for cookies."""
    return uuid.uuid4().hex
import hashlib


class Poll(models.Model):
    """
    Represents a single voting poll/election.
    
    Attributes:
        id: UUID primary key for shareable unique identifier
        title: Poll title/question
        description: Optional description
        candidates: Related candidates (reverse FK)
        created_at: Timestamp of poll creation
        updated_at: Timestamp of last update
        is_active: Whether poll is open for voting
        max_votes: Optional limit on number of votes (None = unlimited)
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(
        max_length=200,
        validators=[MaxLengthValidator(200)],
        help_text="Poll question or title"
    )
    description = models.TextField(
        blank=True,
        null=True,
        max_length=1000,
        help_text="Optional details about the poll"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(
        default=True,
        help_text="Whether poll accepts new votes"
    )
    is_public = models.BooleanField(
        default=False,
        help_text="Whether poll is visible on homepage"
    )
    is_deleted = models.BooleanField(
        default=False,
        help_text="Soft delete flag (poll hidden but not removed from DB)"
    )
    creator_code = models.CharField(
        max_length=12,
        unique=True,
        null=True,
        blank=True,
        editable=False,
        help_text="Unique code to manage this poll as creator"
    )
    tiebreaker_method = models.CharField(
        max_length=20,
        choices=[
            ('schulze', 'Schulze Method'),
            ('borda', 'Borda Count'),
            ('random', 'Random Selection'),
        ],
        default='schulze',
        help_text="Method for resolving Condorcet paradox"
    )

    requires_auth = models.BooleanField(
        default=False,
        help_text="Whether poll requires a unique one-time password to vote"
    )

    max_votes = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Maximum votes allowed (None = unlimited)"
    )
    results_released = models.BooleanField(
        default=False,
        help_text="Whether results have been released by the creator while poll is active"
    )

    allow_multiple_votes_per_device = models.BooleanField(
        default=False,
        help_text="If True, bypass cookie/fingerprint checks to allow multiple votes from same device"
    )
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['is_active']),
            models.Index(fields=['is_public']),
            models.Index(fields=['is_deleted']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.id})"
    
    def save(self, *args, **kwargs):
        """Generate creator_code if not set."""
        if not self.creator_code:
            # Generate random 12-char alphanumeric code
            chars = string.ascii_letters + string.digits
            self.creator_code = ''.join(random.choice(chars) for _ in range(12))
        super().save(*args, **kwargs)
    
    def get_vote_count(self):
        """Return total number of votes cast."""
        return self.vote_set.count()
    
    def get_candidates(self):
        """Return all candidates for this poll."""
        return self.candidate_set.all().order_by('name')

    def can_accept_votes(self):
        """Check if poll can accept new votes."""
        if not self.is_active:
            return False
        if self.max_votes and self.get_vote_count() >= self.max_votes:
            return False
        return True


class PollToken(models.Model):
    """
    Represents a one-time use token for secure polls.
    
    Attributes:
        poll: The poll this token belongs to
        token_hash: Hashed version of the token (never store plaintext!)
        is_used: Whether the token has been used
        used_at: Timestamp when token was used
    """
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name='tokens')
    token_hash = models.CharField(max_length=128)  # Store SHA256 or similar
    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ('poll', 'token_hash')  # Although hash collision unlikely
        indexes = [
            models.Index(fields=['poll', 'token_hash']),
        ]

    def __str__(self):
        return f"Token for {self.poll.id} ({'Used' if self.is_used else 'Active'})"



class Candidate(models.Model):
    """
    Represents a candidate/option in a poll.
    
    Attributes:
        id: UUID primary key
        poll: Foreign key to parent Poll
        name: Candidate name/title
        description: Optional description
        created_at: Timestamp of creation
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    poll = models.ForeignKey(
        Poll,
        on_delete=models.CASCADE,
        help_text="The poll this candidate belongs to"
    )
    name = models.CharField(
        max_length=100,
        validators=[MaxLengthValidator(100)],
        help_text="Candidate name or option text"
    )
    description = models.TextField(
        blank=True,
        null=True,
        max_length=500,
        help_text="Optional candidate description"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
        unique_together = [['poll', 'name']]  # No duplicate candidate names per poll
        indexes = [
            models.Index(fields=['poll', 'name']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.poll.title})"


class Vote(models.Model):
    """
    Represents a single voter's ranked ballot.
    Stores the ranking order of candidates.
    
    Attributes:
        id: UUID primary key
        poll: Foreign key to Poll
        voter_fingerprint: Hash of voter IP + User-Agent (prevents duplicates)
        ranking: JSON storing candidate order [candidate_id_1, candidate_id_2, ...]
        cast_at: Timestamp when vote was submitted
    
    Security:
        - Voter fingerprint used to prevent duplicate votes without identification
        - No personal data stored (anonymous voting)
        - JSON-based ranking is validated before storage
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    poll = models.ForeignKey(
        Poll,
        on_delete=models.CASCADE,
        help_text="The poll this vote belongs to"
    )
    voter_fingerprint = models.CharField(
        max_length=64,  # SHA256 hash = 64 hex chars
        help_text="Hash of voter IP + User-Agent to prevent duplicates"
    )
    ranking = models.JSONField(
        help_text="List of candidate UUIDs in ranked order [1st_choice, 2nd_choice, ...]"
    )
    cast_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-cast_at']
        unique_together = [['poll', 'voter_fingerprint']]  # One vote per voter
        indexes = [
            models.Index(fields=['poll', 'voter_fingerprint']),
            models.Index(fields=['-cast_at']),
        ]
    
    def __str__(self):
        return f"Vote on {self.poll.title} at {self.cast_at}"
    
    @staticmethod
    def generate_fingerprint(ip_address, user_agent):
        """
        Generate voter fingerprint from IP and User-Agent.
        Uses SHA256 to create irreversible, consistent hash.
        
        Args:
            ip_address: Voter's IP address
            user_agent: Browser User-Agent string
            
        Returns:
            SHA256 hex digest
        """
        data = f"{ip_address}:{user_agent}"
        return hashlib.sha256(data.encode()).hexdigest()


class VoterSession(models.Model):
    """
    Tracks voter sessions to prevent abuse and duplicate voting.
    
    Attributes:
        id: Auto-increment primary key
        poll: Foreign key to Poll
        voter_fingerprint: Hash of IP + User-Agent
        cookie_token: Unique token stored in cookie
        ip_address: Voter's IP address (for logging)
        user_agent: Browser User-Agent
        first_visit: When voter first accessed poll
        last_activity: Last action timestamp
        vote_count: Number of votes from this fingerprint
    
    Security:
        - Tokens are invalidated after vote submission
        - Rate limiting can be implemented using this model
        - Logs provide audit trail for abuse detection
    """
    
    poll = models.ForeignKey(
        Poll,
        on_delete=models.CASCADE,
        help_text="Poll being accessed"
    )
    voter_fingerprint = models.CharField(
        max_length=64,
        help_text="Hash of voter IP + User-Agent"
    )
    cookie_token = models.CharField(
        max_length=64,
        db_index=True,
        default=generate_token,
        help_text="Unique token stored in voter's cookie"
    )
    ip_address = models.GenericIPAddressField(
        help_text="Voter's IP address"
    )
    user_agent = models.TextField(
        help_text="Browser User-Agent string"
    )
    first_visit = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    vote_count = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Number of votes from this session"
    )
    
    class Meta:
        unique_together = [
            ['poll', 'voter_fingerprint'],
            ['poll', 'cookie_token']
        ]
        indexes = [
            models.Index(fields=['poll', 'voter_fingerprint']),
            models.Index(fields=['cookie_token']),
        ]
    
    def __str__(self):
        return f"Session {self.voter_fingerprint} on {self.poll.title}"
