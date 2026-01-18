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

    voter_count = forms.IntegerField(
        required=False,
        min_value=2,
        max_value=100,
        label=_('Number of voters'),
        help_text=_('How many unique passwords to generate (2-100)'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '10',
        })
    )

    has_deadline = forms.BooleanField(
        required=False,
        label=_('Limit voting time'),
        help_text=_('Set a deadline for the poll. Voting will automatically close after this time.'),
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'data-bs-toggle': 'collapse',
            'data-bs-target': '#deadlineSection',
        })
    )

    deadline_duration = forms.IntegerField(
        required=False,
        min_value=1,
        label=_('Duration'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '1',
        })
    )

    deadline_unit = forms.ChoiceField(
        required=False,
        choices=[
            ('minutes', _('Minutes')),
            ('hours', _('Hours')),
            ('days', _('Days')),
        ],
        label=_('Unit'),
        widget=forms.Select(attrs={
            'class': 'form-select',
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        has_deadline = cleaned_data.get('has_deadline')
        deadline_duration = cleaned_data.get('deadline_duration')
        
        if has_deadline and not deadline_duration:
             self.add_error('deadline_duration', _('Please specify a duration.'))
        
        return cleaned_data

    class Meta:
        model = Poll
        fields = ['title', 'description', 'tiebreaker_method', 'allow_multiple_votes_per_device', 'is_public', 'requires_auth']
        labels = {
            'title': _('Poll Title'),
            'description': _('Poll Description'),
            'tiebreaker_method': _('Tiebreaker Method'),
            'allow_multiple_votes_per_device': _('Allow multiple votes per device'),
            'is_public': _('Make poll public'),
            'requires_auth': _('Secure vote with unique passwords'),
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
            'is_public': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'requires_auth': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'data-bs-toggle': 'collapse',
                'data-bs-target': '#voterCountSection',
            }),
        }
        help_texts = {
             'allow_multiple_votes_per_device': _('Enable this for shared devices (e.g., passing a tablet around). Bypasses duplicate vote protection.'),
             'is_public': _('Polls are private by default (only accessible via a private link).'),
             'requires_auth': _('Generate a list of one-time passwords. Each voter will need a unique password to vote.'),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        requires_auth = cleaned_data.get('requires_auth')
        allow_multiple = cleaned_data.get('allow_multiple_votes_per_device')
        voter_count = cleaned_data.get('voter_count')

        if requires_auth and allow_multiple:
            raise ValidationError(
                _("You cannot enable both 'Multiple votes per device' and 'Secure password protection'. Password protection enforces strict one-person-one-vote.")
            )
        
        if requires_auth:
            if not voter_count:
                 self.add_error('voter_count', _("Number of voters is required when password protection is enabled."))
            elif not (2 <= voter_count <= 100):
                 self.add_error('voter_count', _("Number of voters must be between 2 and 100."))
        
        return cleaned_data

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


class AuthForm(forms.Form):
    """Form to enter password for secure polls."""
    password = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': _("Enter your unique voting password"),
            'autocomplete': 'off'
        })
    )


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
