"""
View functions for Condorcet Voting System
===========================================

HTTP request handlers for:
- Creating new polls
- Displaying voting interface
- Submitting votes with validation
- Calculating and displaying results
- Generating shareable poll links

Security implemented:
- CSRF protection (built-in Django)
- Input validation (no SQL injection, XSS)
- Vote deduplication (cookie + IP fingerprinting)
- Rate limiting (can be added)
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from django.conf import settings
from django.utils.translation import gettext as _
import json
import logging

from .models import Poll, Candidate, Vote, VoterSession, PollToken
from .forms import CreatePollForm, VoteForm, AuthForm
from .utils import (
    calculate_condorcet_winner, validate_ranking, get_ranking_statistics,
    generate_qr_code
)
from django.contrib.auth.hashers import make_password, check_password
import secrets

from django.utils import timezone

logger = logging.getLogger(__name__)


@require_http_methods(["GET", "POST"])
@csrf_protect
def create_poll(request):
    """
    Create a new voting poll.
    
    GET: Display poll creation form
    POST: Process form submission and create poll + candidates
    
    Validation:
    - Poll title: 5-200 characters
    - Candidates: 2-50 unique names
    - Description: optional, max 1000 chars
    - Tiebreaker method selection (Schulze, Borda, Random)
    
    Returns:
        GET: Rendered create_poll.html with form
        POST: Redirect to confirmation page with creator code + QR
    """
    
    if request.method == 'POST':
        form = CreatePollForm(request.POST)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Create poll from form (is_public=False by default)
                    poll = form.save(commit=False)
                    poll.save()
                    
                    # Create candidates
                    candidates_list = form.cleaned_data['candidates']
                    for candidate_name in candidates_list:
                        Candidate.objects.create(
                            poll=poll,
                            name=candidate_name
                        )

                    # Handle Secure Tokens
                    if poll.requires_auth:
                        voter_count = form.cleaned_data.get('voter_count', 0)
                        tokens = []
                        tokens_objects = []
                        for _ in range(voter_count):
                            # Generate a strong 20-char random token (alphanumeric)
                            token = secrets.token_urlsafe(15) # 15 bytes -> approx 20 chars
                            tokens.append(token)
                            
                            # Hash it for storage
                            token_hash = make_password(token)
                            tokens_objects.append(PollToken(poll=poll, token_hash=token_hash))
                        
                        PollToken.objects.bulk_create(tokens_objects)
                        
                        # Store tokens in session to display ONE TIME on confirmation page
                        request.session['created_tokens'] = tokens
                    
                    logger.info(f"Poll created: {poll.id} with "
                               f"{len(candidates_list)} candidates, "
                               f"creator_code: {poll.creator_code}")
                    messages.success(request, 
                                   'Poll created successfully!')
                    
                    # Redirect to confirmation page
                    return redirect('voting:poll_confirmation', poll_id=poll.id, 
                                  creator_code=poll.creator_code)
                    
            except Exception as e:
                logger.error(f"Error creating poll: {str(e)}")
                messages.error(request, 
                             'Error creating poll. Please try again.')
        else:
            # Form validation failed
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    
    else:  # GET request
        form = CreatePollForm()
    
    return render(request, 'voting/create_poll.html', {'form': form})


@require_http_methods(["GET"])
def about_condorcet(request):
    """
    Educational page explaining the Condorcet voting method.
    
    Covers:
    - What is Condorcet voting
    - How it works (step by step)
    - Real examples
    - Advantages vs first-past-the-post and runoff
    - The Condorcet paradox
    - Tiebreaker methods
    
    Returns:
        Rendered about_condorcet.html with educational content
    """
    return render(request, 'voting/about_condorcet.html')


@require_http_methods(["GET"])
def index(request):
    """
    Home page / poll list view.
    
    Displays:
    - Recent PUBLIC polls only
    - Link to create new poll
    - Information about Condorcet voting
    
    Returns:
        Rendered index.html with poll list
    """
    
    # Get recent public polls (not deleted, is_public=True)
    recent_polls = Poll.objects.filter(
        is_active=True,
        is_public=True,
        is_deleted=False
    ).order_by('-created_at')[:10]
    
    context = {
        'polls': recent_polls,
    }
    
    return render(request, 'voting/index.html', context)


@require_http_methods(["GET", "POST"])
@csrf_protect
def vote_poll(request, poll_id):
    """
    Voting interface for a poll.
    
    GET: Display voting form with candidates
    POST: Process vote submission
    
    Security:
    - Check poll is active and not deleted
    - Validate voter hasn't already voted (cookie + fingerprint)
    - CSRF token validation (automatic)
    - Input validation for ranking
    
    Args:
        poll_id: UUID of poll to vote on
    
    Returns:
        GET: Rendered vote.html with voting form
        POST: Redirect to results if successful, re-render on error
    """
    
    # Get poll and check it exists (and not deleted)
    poll = get_object_or_404(Poll, id=poll_id, is_deleted=False)
    
    # Check poll is active OR results are released (allow viewing if results released)
    if not poll.is_active and not poll.results_released:
        messages.error(request, _('This poll is closed and results have not been released.'))
        return redirect('voting:index')
    
    # If poll is closed but results are released, redirect to results view
    if not poll.is_active and poll.results_released:
        messages.info(request, _('This poll is closed. You can only view results.'))
        return redirect('voting:results_poll', poll_id=poll.id)
    
    # If poll is closed (and results not released), prevent voting
    if not poll.is_active:
        messages.error(request, _('This poll is closed and results have not been released.'))
        return redirect('voting:index')
    
    # Check vote limit not reached
    if not poll.can_accept_votes():
        messages.error(request, 
                      _('This poll has reached maximum votes.'))
        return redirect('index')

    # AUTHENTICATION CHECK
    if poll.requires_auth:
        auth_session_key = f'auth_token_id_{poll.id}'
        
        # If user is not authenticated yet
        if auth_session_key not in request.session:
            # Handle Auth Form Submission
            if request.method == 'POST' and 'password' in request.POST:
                auth_form = AuthForm(request.POST)
                if auth_form.is_valid():
                    password = auth_form.cleaned_data['password']
                    # Verify password against unused tokens
                    # We iterate because we only have hashes
                    unused_tokens = PollToken.objects.filter(poll=poll, is_used=False)
                    found_token = None
                    for t in unused_tokens:
                        if check_password(password, t.token_hash):
                            found_token = t
                            break
                    
                    if found_token:
                        # Success: Store token ID in session
                        request.session[auth_session_key] = found_token.id
                        messages.success(request, _('Authentication successful. You can now vote.'))
                        return redirect('voting:vote_poll', poll_id=poll.id)
                    else:
                        messages.error(request, _('Invalid or already used password.'))
            else:
                auth_form = AuthForm()
            
            # Show Auth Page (blocking access to vote form)
            return render(request, 'voting/auth.html', {
                'poll': poll, 
                'form': auth_form
            })
    
    # Get candidates for this poll
    candidates = poll.get_candidates()
    
    if not candidates.exists():
        messages.error(request, _('Poll has no candidates.'))
        return redirect('index')
    
    if request.method == 'POST':
        # Process vote submission
        
        # Check for duplicate votes
        # First, generate stable device fingerprint (used for session tracking and duplicate checks)
        device_fingerprint = Vote.generate_fingerprint(
            request.voter_ip,
            request.voter_user_agent
        )
        
        # Determine fingerprint for the Vote record (may be randomized if multiple votes allowed)
        vote_fingerprint = device_fingerprint

        # Only perform checks if multiple votes per device is NOT allowed
        # EXCEPTION: If the poll requires authentication (Secure Poll), we allow multiple votes
        # from the same device because each vote is authenticated by a unique token.
        if not poll.allow_multiple_votes_per_device and not poll.requires_auth:
            cookie_token = getattr(request, 'voter_session_token', 'MISSING')
            
            logger.info(f"Vote attempt on poll {poll.id} | IP: {request.voter_ip} | "
                        f"Fingerprint: {device_fingerprint} | Cookie: {cookie_token}")

            # Check if this voter already voted on this poll (by fingerprint)
            existing_vote_fingerprint = Vote.objects.filter(
                poll=poll,
                voter_fingerprint=device_fingerprint
            ).exists()

            # Check if this voter already voted on this poll (by cookie session)
            existing_vote_session = False
            if hasattr(request, 'voter_session_token'):
                existing_vote_session = VoterSession.objects.filter(
                    poll=poll,
                    cookie_token=request.voter_session_token,
                    vote_count__gt=0
                ).exists()
            
            if existing_vote_fingerprint or existing_vote_session:
                logger.warning(f"Duplicate vote blocked: {device_fingerprint} | "
                            f"Fingerprint match: {existing_vote_fingerprint} | "
                            f"Cookie match: {existing_vote_session} | "
                            f"Poll: {poll.id}")
                messages.error(request, 
                            _('You have already voted on this poll.'))
                return redirect('voting:vote_poll', poll_id=poll.id)
        else:
            # If multiple votes are allowed, we randomize the fingerprint for the Vote record
            # to bypass the unique_together constraint in the database.
            import uuid
            vote_fingerprint = Vote.generate_fingerprint(
                request.voter_ip + str(uuid.uuid4()),
                request.voter_user_agent
            )
            logger.info(f"Vote attempt on MULTI-VOTE poll {poll.id} | IP: {request.voter_ip}")
        
        # Validate form
        form = VoteForm(candidates, request.POST)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Check Secure Token if required
                    if poll.requires_auth:
                        auth_session_key = f'auth_token_id_{poll.id}'
                        token_id = request.session.get(auth_session_key)
                        
                        if not token_id:
                            messages.error(request, _('Session expired. Please authenticate again.'))
                            return redirect('voting:vote_poll', poll_id=poll.id)
                        
                        try:
                            # Lock the row to prevent race conditions
                            token_obj = PollToken.objects.select_for_update().get(id=token_id, poll=poll, is_used=False)
                            token_obj.is_used = True
                            token_obj.used_at = timezone.now()
                            token_obj.save()
                            
                            # Clean up session
                            if auth_session_key in request.session:
                                del request.session[auth_session_key]
                            
                        except PollToken.DoesNotExist:
                            messages.error(request, _('This password has already been used.'))
                            # Clear invalid session
                            if auth_session_key in request.session:
                                del request.session[auth_session_key]
                            return redirect('voting:vote_poll', poll_id=poll.id)

                    # Build ranking from form data
                    ranking = [''] * len(candidates)
                    
                    for candidate in candidates:
                        field_name = f'rank_{candidate.id}'
                        rank_position = int(form.cleaned_data[field_name]) - 1
                        ranking[rank_position] = str(candidate.id)
                    
                    # Validate ranking
                    if not validate_ranking(ranking, {str(c.id) for c in candidates}):
                        raise ValidationError("Invalid vote ranking.")
                    
                    # Create vote record
                    vote = Vote.objects.create(
                        poll=poll,
                        voter_fingerprint=vote_fingerprint,
                        ranking=ranking
                    )
                    
                    # Update voter session
                    defaults = {
                        'ip_address': request.voter_ip,
                        'user_agent': request.voter_user_agent,
                    }
                    if hasattr(request, 'voter_session_token'):
                        defaults['cookie_token'] = request.voter_session_token

                    # Try to get existing session by fingerprint (always use stable device fingerprint)
                    voter_session, created = VoterSession.objects.get_or_create(
                        poll=poll,
                        voter_fingerprint=device_fingerprint,
                        defaults=defaults
                    )
                    
                    if not created:
                        # If multi-vote is disabled, this implies a race condition or inconsistency 
                        # because we checked for existence earlier.
                        # If multi-vote is enabled, this is normal behavior (same user voting again).
                        if not poll.allow_multiple_votes_per_device and not poll.requires_auth:
                             logger.warning(f"VoterSession existed but Vote didn't? Fingerprint: {device_fingerprint}")
                        
                        if hasattr(request, 'voter_session_token') and voter_session.cookie_token != request.voter_session_token:
                             logger.info(f"Updating session token from {voter_session.cookie_token} to {request.voter_session_token}")
                             voter_session.cookie_token = request.voter_session_token
                        if hasattr(request, 'voter_session_token') and voter_session.cookie_token != request.voter_session_token:
                             logger.info(f"Updating session token from {voter_session.cookie_token} to {request.voter_session_token}")
                             voter_session.cookie_token = request.voter_session_token
                             # Note: This update might fail if new token is already used by another session (IntegrityError)
                             # which is good! It means this cookie already voted.

                    voter_session.vote_count += 1
                    voter_session.save()
                    
                    logger.info(f"Vote recorded: {vote.id} on poll {poll.id} | "
                                f"Session Token: {voter_session.cookie_token}")
                    messages.success(request, _('Your vote has been recorded!'))
                    
                    return redirect('voting:results_poll', poll_id=poll.id)
            
            except IntegrityError as e:
                # Catch unique constraint violation (likely cookie_token collision)
                logger.warning(f"IntegrityError during vote (likely duplicate cookie): {str(e)}")
                messages.error(request, _('You have already voted on this poll.'))
                return redirect('voting:vote_poll', poll_id=poll.id)

            except Exception as e:
                logger.error(f"Error recording vote: {str(e)}")
                messages.error(request, 
                             _('Error recording vote. Please try again.'))
        else:
            # Form validation failed
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    
    else:  # GET request
        form = VoteForm(candidates)
    
    context = {
        'poll': poll,
        'form': form,
        'candidates': candidates,
    }
    
    return render(request, 'voting/vote.html', context)


@require_http_methods(["GET"])
def results_poll(request, poll_id):
    """
    Display voting results and Condorcet winner.
    
    Calculates:
    - Pairwise comparison matrix
    - Condorcet winner (or Schulze tiebreaker)
    - Voting statistics
    
    Results visibility:
    - Public if poll is closed
    - Only for creator (with code) if poll is open
    
    Args:
        poll_id: UUID of poll to show results for
    
    Returns:
        Rendered results.html with results and winner
    """
    
    # Get poll (not deleted)
    poll = get_object_or_404(Poll, id=poll_id, is_deleted=False)
    
    # Check access control
    creator_code = request.GET.get('creator_code')
    is_creator = creator_code and creator_code == poll.creator_code

    # Allow viewing if any of:
    # 1. Poll is closed (results are public), OR
    # 2. User is the creator, OR
    # 3. Creator has explicitly released results while poll is active
    if poll.is_active and not (is_creator or poll.results_released):
        messages.error(request, _('Results are only available after the poll is closed or when released by the creator.'))
        return redirect('voting:index')
    
    # Get all votes for this poll
    votes_queryset = Vote.objects.filter(poll=poll).values_list('ranking', flat=True)
    votes_list = list(votes_queryset)
    
    # Count unique voters (based on fingerprint)
    unique_voters_count = Vote.objects.filter(poll=poll).values('voter_fingerprint').distinct().count()
    
    # Build candidate lookup
    candidates = list(poll.get_candidates())
    candidate_dict = {str(c.id): c for c in candidates}
    
    # Calculate results
    winner_method = None
    if votes_list:
        try:
            # Calculate winner
            valid_candidate_ids = set(candidate_dict.keys())
            winner_id, winner_method = calculate_condorcet_winner(votes_list, poll.tiebreaker_method, expected_candidates=valid_candidate_ids)
            winner = candidate_dict.get(winner_id)
            
            if winner:
                logger.info(f"Winner object found: {winner.name} ({winner.id})")
            else:
                logger.warning(f"Winner ID {winner_id} returned but not found in candidate_dict keys: {list(candidate_dict.keys())}")
            
            # Get statistics
            stats = get_ranking_statistics(votes_list)
            
            # Prepare first choice votes data for template
            first_choice_data = []
            for cand_id, count in stats['first_choice_votes'].items():
                cand = candidate_dict.get(cand_id)
                if cand:
                    first_choice_data.append({
                        'candidate': cand,
                        'count': count,
                        'percentage': round(100 * count / len(votes_list), 1) if votes_list else 0
                    })
            
            # Sort by count descending
            first_choice_data.sort(key=lambda x: x['count'], reverse=True)
            
            # Process pairwise results for template
            raw_pairwise = stats.get('pairwise_results', {})
            pairwise_list = []
            processed_pairs = set()
            
            for (cand_a_id, cand_b_id), votes_a in raw_pairwise.items():
                # Skip if we already processed this pair (in reverse)
                pair_key = tuple(sorted([cand_a_id, cand_b_id]))
                if pair_key in processed_pairs:
                    continue
                
                processed_pairs.add(pair_key)
                
                cand_a = candidate_dict.get(cand_a_id)
                cand_b = candidate_dict.get(cand_b_id)
                
                if cand_a and cand_b:
                    votes_b = raw_pairwise.get((cand_b_id, cand_a_id), 0)
                    
                    matchup_winner = None
                    if votes_a > votes_b:
                        matchup_winner = cand_a
                    elif votes_b > votes_a:
                        matchup_winner = cand_b
                        
                    pairwise_list.append({
                        'candidate_a': cand_a,
                        'candidate_b': cand_b,
                        'votes_a': votes_a,
                        'votes_b': votes_b,
                        'winner': matchup_winner,
                        'is_tie': votes_a == votes_b
                    })

        except Exception as e:
            logger.error(f"Error calculating results: {str(e)}")
            winner = None
            stats = {}
            first_choice_data = []
            pairwise_list = []
            messages.error(request, _('Error calculating results.'))
    else:
        winner = None
        stats = {}
        first_choice_data = []
        pairwise_list = []
    
    context = {
        'poll': poll,
        'winner': winner,
        'winner_method': winner_method,
        'total_votes': len(votes_list),
        'unique_voters_count': unique_voters_count,
        'num_candidates': len(candidates),
        'candidates': candidate_dict,
        'first_choice_votes': first_choice_data,
        'pairwise_results': pairwise_list,
    }
    
    return render(request, 'voting/results.html', context)


@require_http_methods(["GET"])
def poll_confirmation(request, poll_id, creator_code):
    """
    Confirmation page after creating a poll.
    
    Displays:
    - Creator code
    - Voting link
    - QR code for voting link
    - Options to make poll public/start voting
    
    Args:
        poll_id: UUID of newly created poll
        creator_code: Creator's secret code to manage poll
    
    Returns:
        Rendered confirmation page with poll details
    """
    
    # Get poll and verify it exists
    poll = get_object_or_404(Poll, id=poll_id, is_deleted=False)
    
    # Verify creator code matches (simple security check)
    if poll.creator_code != creator_code:
        messages.error(request, _('Invalid creator code.'))
        return redirect('voting:index')
    
    # Build voting URL using SITE_URL from settings
    vote_url = f"{settings.SITE_URL}/vote/{poll.id}/"
    
    # Generate QR code URL using external service (qr-server)
    import urllib.parse
    qr_code_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={urllib.parse.quote(vote_url)}"
    
    context = {
        'poll': poll,
        'creator_code': creator_code,
        'vote_url': vote_url,
        'qr_code_url': qr_code_url,
    }

    # If this is the just-created redirect, display the tokens ONE TIME
    if 'created_tokens' in request.session:
        context['tokens'] = request.session.pop('created_tokens')
    
    return render(request, 'voting/poll_confirmation.html', context)


@require_http_methods(["GET"])
def creator_dashboard(request, creator_code):
    """
    Creator dashboard to manage owned polls.
    
    Displays:
    - All polls created with this code
    - Vote count and live results
    - Options to: make public, close, delete, view results
    
    Also handles POST for actions via GET params (make_public, close, delete)
    
    Args:
        creator_code: Creator's secret code
    
    Returns:
        Rendered dashboard with creator's polls
    """
    
    # Get all polls managed by this creator code
    polls = Poll.objects.filter(
        creator_code=creator_code,
        is_deleted=False
    ).order_by('-created_at')
    
    if not polls.exists():
        messages.error(request, _('No polls found for this creator code.'))
        return redirect('voting:index')
    
    # Handle actions (make_public, close, delete)
    action = request.GET.get('action')
    poll_id = request.GET.get('poll_id')
    
    if action and poll_id:
        try:
            poll = polls.get(id=poll_id)
            
            if action == 'make_public':
                poll.is_public = True
                poll.save()
                messages.success(request, f'Poll "{poll.title}" is now public!')
                
            elif action == 'make_private':
                poll.is_public = False
                poll.save()
                messages.success(request, f'Poll "{poll.title}" is now private!')
                
            elif action == 'close':
                poll.is_active = False
                poll.save()
                messages.success(request, f'Poll "{poll.title}" closed!')
                
            elif action == 'reopen':
                poll.is_active = True
                poll.save()
                messages.success(request, _('Poll "%(title)s" reopened!') % {'title': poll.title})
                
            elif action == 'delete':
                # Permanently delete poll from DB (admin should not see it)
                poll.delete()
                messages.success(request, _('Poll "%(title)s" permanently deleted!') % {'title': poll.title})
            elif action == 'release_results':
                # Release results - poll stays open for viewing, voting is disabled when results are released
                poll.results_released = True
                poll.save()
                messages.success(request, _('Results for "%(title)s" released! Voters can now view results.') % {'title': poll.title})
            elif action == 'hide_results':
                poll.results_released = False
                poll.save()
                messages.success(request, _('Results for "%(title)s" are now hidden.') % {'title': poll.title})
        except Poll.DoesNotExist:
            messages.error(request, _('Poll not found.'))
        except Exception as e:
            logger.error(f"Error performing action: {str(e)}")
            messages.error(request, _('Error performing action.'))
        
        return redirect('voting:creator_dashboard', creator_code=creator_code)
    
    # Build rich context for each poll
    polls_data = []
    for poll in polls:
        vote_count = poll.get_vote_count()
        
        # Calculate winner if votes exist
        winner = None
        if vote_count > 0:
            votes_queryset = Vote.objects.filter(poll=poll).values_list('ranking', flat=True)
            votes_list = list(votes_queryset)
            try:
                valid_candidate_ids = set(str(c.id) for c in poll.candidate_set.all())
                winner_id, _ignored_method = calculate_condorcet_winner(votes_list, poll.tiebreaker_method, expected_candidates=valid_candidate_ids)
                winner = poll.candidate_set.get(id=winner_id) if winner_id else None
            except Exception:
                pass
        
        polls_data.append({
            'poll': poll,
            'vote_count': vote_count,
            'winner': winner,
            'candidates_count': poll.candidate_set.count(),
        })
    
    context = {
        'creator_code': creator_code,
        'polls_data': polls_data,
        'site_url': settings.SITE_URL,  # For generating share URLs in template
    }
    
    return render(request, 'voting/creator_dashboard.html', context)


@require_http_methods(["GET"])
def poll_share_link(request, poll_id):
    """
    Generate shareable link for a poll.
    
    Returns JSON with voting URL that can be shared via:
    - Email
    - Chat/Slack
    - QR code
    - Social media
    
    Args:
        poll_id: UUID of poll
    
    Returns:
        JSON: {'url': 'https://example.com/vote/poll_id/'}
    """
    
    poll = get_object_or_404(Poll, id=poll_id)
    
    # Build full URL using SITE_URL from settings
    share_url = f"{settings.SITE_URL}/vote/{poll.id}/"
    
    return JsonResponse({
        'url': share_url,
        'poll_id': str(poll.id),
    })


@require_http_methods(["GET"])
def poll_api_results(request, poll_id):
    """
    API endpoint for poll results (JSON).
    
    Used by:
    - Frontend JavaScript for live updates
    - External dashboards
    - Mobile apps
    
    Returns:
        JSON with:
        - Poll details
        - Vote count
        - Pairwise results
        - Condorcet winner (if available)
    """
    
    poll = get_object_or_404(Poll, id=poll_id)
    
    votes_queryset = Vote.objects.filter(poll=poll).values_list('ranking', flat=True)
    votes_list = list(votes_queryset)
    
    # Calculate results
    winner_id = None
    winner_method = None
    if votes_list:
        try:
            valid_candidate_ids = set(str(c.id) for c in poll.get_candidates())
            winner_id, winner_method = calculate_condorcet_winner(votes_list, poll.tiebreaker_method, expected_candidates=valid_candidate_ids)
        except Exception as e:
            logger.error(f"Error calculating winner: {str(e)}")
    
    # Get candidates
    candidates_dict = {
        str(c.id): {'id': str(c.id), 'name': c.name}
        for c in poll.get_candidates()
    }
    
    return JsonResponse({
        'poll': {
            'id': str(poll.id),
            'title': poll.title,
            'description': poll.description,
            'is_active': poll.is_active,
        },
        'votes': {
            'total': len(votes_list),
            'max': poll.max_votes,
        },
        'candidates': candidates_dict,
        'winner': winner_id,
        'winner_method': winner_method,
    })


@require_http_methods(["GET", "POST"])
@csrf_protect
def dashboard_login(request):
    """
    Allow creators to access their dashboard by entering their creator code.
    """
    if request.method == 'POST':
        creator_code = request.POST.get('creator_code')
        if creator_code:
            # Check if any poll exists with this code
            if Poll.objects.filter(creator_code=creator_code, is_deleted=False).exists():
                return redirect('voting:creator_dashboard', creator_code=creator_code)
            else:
                messages.error(request, _('Invalid creator code. No polls found.'))
        else:
            messages.error(request, _('Please enter a creator code.'))
            
    return render(request, 'voting/dashboard_login.html')
