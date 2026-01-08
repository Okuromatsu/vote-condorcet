"""
Django Forms for Condorcet Voting System
=========================================

Handles form validation and rendering for:
- Creating new polls
- Submitting votes with ranking validation

Security features:
- CSRF token protection (built-in)
- XSS prevention via template escaping
- Input validation and sanitization
- Rate limiting can be added
"""

from django import forms # pyright: ignore[reportMissingModuleSource]
from django.core.exceptions import ValidationError # pyright: ignore[reportMissingModuleSource]
from django.utils.translation import gettext_lazy as _ # pyright: ignore[reportMissingModuleSource]
from .models import Poll, Candidate, Vote


class CreatePollForm(forms.ModelForm):
    """
    Form for creating a new poll.
    
    Validates:
    - Poll title (required, max 200 chars)
    - Description (optional)
    - Candidates (minimum 2, maximum 50)
    
    Security:
    - HTML escaping for all text fields
    - Length validation prevents buffer overflow
    """
    
    candidates = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'placeholder': _('Enter one candidate per line'),
            'required': True,
        }),
        help_text=_('Enter one candidate per line (minimum 2, maximum 50)'),
        label=_('Candidates')
    )
    
    class Meta:
        model = Poll
        fields = ['title', 'description', 'tiebreaker_method', 'allow_multiple_votes_per_device']
        labels = {
            'title': _('Poll Title'),
            'description': _('Poll Description'),
            'tiebreaker_method': _('Tiebreaker Method'),
            'allow_multiple_votes_per_device': _('Allow multiple votes per device'),
        }
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('e.g., Best Programming Language?'),
                'maxlength': '200',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Optional details about this poll...'),
                'maxlength': '1000',
            }),
            'tiebreaker_method': forms.Select(attrs={
                'class': 'form-select',
            }),
            'allow_multiple_votes_per_device': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }
        help_texts = {
             'allow_multiple_votes_per_device': _('Enable this for shared devices (e.g., passing a tablet around). Bypasses duplicate vote protection.'),
        }
    
    def clean_candidates(self):
        """Validate candidate list."""
        candidates_text = self.cleaned_data.get('candidates', '').strip()
        
        if not candidates_text:
            raise ValidationError('Please enter at least one candidate.')
        
        # Split by newlines and clean
        candidates_list = [
            c.strip() for c in candidates_text.split('\n') if c.strip()
        ]
        
        # Validation rules
        if len(candidates_list) < 2:
            raise ValidationError('Please enter at least 2 candidates.')
        
        if len(candidates_list) > 50:
            raise ValidationError('Maximum 50 candidates allowed.')
        
        # Check for duplicates
        if len(candidates_list) != len(set(candidates_list)):
            raise ValidationError('Duplicate candidate names are not allowed.')
        
        # Check individual candidate name length
        for candidate in candidates_list:
            if len(candidate) > 100:
                raise ValidationError(
                    f'Candidate name too long: "{candidate[:50]}..." (max 100 chars)'
                )
        
        return candidates_list
    
    def clean_title(self):
        """Validate poll title."""
        title = self.cleaned_data.get('title', '').strip()
        
        if not title:
            raise ValidationError('Poll title is required.')
        
        if len(title) < 5:
            raise ValidationError('Poll title must be at least 5 characters.')
        
        return title


class VoteForm(forms.Form):
    """
    Form for submitting a ranked vote.
    
    Dynamically validates that voter has ranked all candidates exactly once.
    
    Security:
    - CSRF token validation (automatic)
    - Prevents vote manipulation via hidden field validation
    """
    
    def __init__(self, candidates, *args, **kwargs):
        """
        Initialize form with poll's candidates.
        
        Args:
            candidates: QuerySet of Candidate objects for this poll
        """
        super().__init__(*args, **kwargs)
        self.candidates = candidates
        
        # Create a dropdown for each candidate
        # Voter must rank them from 1 to n
        choices = [(i, f"Position {i}") for i in range(1, len(candidates) + 1)]
        
        for candidate in candidates:
            self.fields[f'rank_{candidate.id}'] = forms.ChoiceField(
                choices=choices,
                widget=forms.Select(attrs={
                    'class': 'form-select candidate-rank',
                    'data-candidate-id': str(candidate.id),
                }),
                label=candidate.name,
                required=True,
            )
    
    def clean(self):
        """
        Validate that each candidate has been ranked exactly once.
        Prevents duplicate rankings and skipped positions.
        """
        cleaned_data = super().clean()
        
        rankings = []
        candidate_ids = []
        
        # Extract rankings
        for candidate in self.candidates:
            field_name = f'rank_{candidate.id}'
            if field_name in cleaned_data:
                try:
                    rank = int(cleaned_data[field_name])
                    rankings.append(rank)
                    candidate_ids.append(str(candidate.id))
                except (ValueError, TypeError):
                    raise ValidationError('Invalid ranking value.')
        
        # Check for duplicates
        if len(rankings) != len(set(rankings)):
            raise ValidationError('Each candidate must have a unique ranking.')
        
        # Check for consecutive rankings from 1 to n
        expected_rankings = set(range(1, len(self.candidates) + 1))
        if set(rankings) != expected_rankings:
            raise ValidationError('Rankings must be consecutive from 1 to ' 
                                 f'{len(self.candidates)}.')
        
        return cleaned_data
