"""
Condorcet Algorithm & Utility Functions
========================================

Core voting logic implementing the Condorcet method:
- Pairwise comparison of all candidates
- Condorcet winner determination (candidate that beats all others in head-to-head)
- Fallback for cyclic preferences (Schulze method)
- Vote ranking validation

The Condorcet Method:
- Compare each candidate against every other candidate
- Count head-to-head votes (who would win in a one-on-one matchup)
- Candidate is Condorcet winner if they beat all others in pairwise comparisons
- If no Condorcet winner exists, use Schulze or Borda tiebreaker

References:
- https://en.wikipedia.org/wiki/Condorcet_method
- https://en.wikipedia.org/wiki/Schulze_method
"""

from collections import defaultdict
from typing import List, Dict, Set, Tuple, Optional
import logging
import random
import urllib.parse
from django.urls import reverse

logger = logging.getLogger(__name__)


def calculate_condorcet_winner(votes_list: List[List[str]], tiebreaker_method: str = 'schulze', expected_candidates: Set[str] = None) -> Tuple[Optional[str], Optional[str]]:
    """
    Calculate Condorcet winner from a list of ranked votes.
    
    Args:
        votes_list: List of votes, each vote is list of candidate IDs in order
        tiebreaker_method: Method to use if no Condorcet winner ('schulze', 'borda', 'random')
        expected_candidates: Optional set of valid candidate IDs to filter votes
    
    Returns:
        Tuple (winner_id, method_used)
        method_used will be 'condorcet', 'schulze', 'borda', 'random', or None
    """
    
    if not votes_list:
        raise ValueError("Cannot calculate winner from empty votes list.")
    
    # Filter votes if expected_candidates provided
    if expected_candidates:
        cleaned_votes = []
        for vote in votes_list:
            # Keep only candidates that are in expected_candidates, preserving order
            cleaned_vote = [c for c in vote if c in expected_candidates]
            if cleaned_vote:
                cleaned_votes.append(cleaned_vote)
        votes_list = cleaned_votes
        
        if not votes_list:
             raise ValueError("No valid votes remaining after filtering candidates.")

        # Update all_candidates to be expected_candidates (or intersection)
        all_candidates = expected_candidates
    else:
        # Validate all votes have same length (same candidates)
        vote_lengths = set(len(vote) for vote in votes_list)
        if len(vote_lengths) > 1:
            raise ValueError("All votes must have same number of candidates.")
            
        # Get all unique candidates
        all_candidates = set()
        for vote in votes_list:
            all_candidates.update(vote)
    
    if not votes_list[0]:
        raise ValueError("Votes cannot be empty.")
    
    if len(all_candidates) < 2:
        # If only 1 candidate, they are the winner
        if len(all_candidates) == 1:
            return list(all_candidates)[0], 'condorcet'
        raise ValueError("Need at least 2 candidates.")
    
    logger.info(f"Calculating winner for {len(votes_list)} votes with {len(all_candidates)} candidates")
    
    # Calculate pairwise results
    pairwise_results = calculate_pairwise_results(votes_list, all_candidates)
    
    # Log pairwise matrix for debugging
    logger.info("Pairwise Matrix:")
    for cand_a in all_candidates:
        for cand_b in all_candidates:
            if cand_a != cand_b:
                wins = pairwise_results.get((cand_a, cand_b), 0)
                losses = pairwise_results.get((cand_b, cand_a), 0)
                logger.info(f"{cand_a} vs {cand_b}: {wins}-{losses}")

    # Check for Condorcet winner
    condorcet_winner = find_condorcet_winner(pairwise_results, all_candidates)
    
    if condorcet_winner:
        logger.info(f"Condorcet winner found: {condorcet_winner}")
        return condorcet_winner, 'condorcet'
    
    # No Condorcet winner - use tiebreaker
    logger.warning(f"No Condorcet winner found. Using {tiebreaker_method} tiebreaker.")
    
    if tiebreaker_method == 'borda':
        return borda_count_tiebreaker(votes_list), 'borda'
    elif tiebreaker_method == 'random':
        return random_tiebreaker(all_candidates), 'random'
    else:
        # Default to Schulze
        return schulze_method(pairwise_results, all_candidates), 'schulze'


def calculate_pairwise_results(
    votes_list: List[List[str]], 
    candidates: Set[str]
) -> Dict[Tuple[str, str], int]:
    """
    Calculate pairwise comparison results.
    
    For each pair of candidates (A, B), count how many voters prefer A over B.
    
    Args:
        votes_list: List of ranked votes
        candidates: Set of all candidate IDs
    
    Returns:
        Dictionary: {(candidate_a_id, candidate_b_id): vote_count, ...}
        Example: {('A', 'B'): 5, ('B', 'A'): 3} means 5 voters prefer A over B
    """
    
    pairwise = defaultdict(int)
    
    # For each vote
    for vote in votes_list:
        # Compare each pair of candidates in this vote
        for i, candidate_a in enumerate(vote):
            for candidate_b in vote[i+1:]:
                # Voter ranks candidate_a higher than candidate_b
                pairwise[(candidate_a, candidate_b)] += 1
    
    return dict(pairwise)


def find_condorcet_winner(
    pairwise_results: Dict[Tuple[str, str], int],
    candidates: Set[str]
) -> Optional[str]:
    """
    Find Condorcet winner if one exists.
    
    A Condorcet winner beats every other candidate in pairwise comparison.
    
    Args:
        pairwise_results: Dictionary from calculate_pairwise_results()
        candidates: Set of all candidate IDs
    
    Returns:
        Candidate ID if Condorcet winner exists, None otherwise
    """
    
    for candidate in candidates:
        is_winner = True
        
        # Check if this candidate beats all others
        for opponent in candidates:
            if candidate == opponent:
                continue
            
            # Count votes: candidate vs opponent
            votes_for = pairwise_results.get((candidate, opponent), 0)
            votes_against = pairwise_results.get((opponent, candidate), 0)
            
            # Candidate must have more votes than opponent
            if votes_for <= votes_against:
                is_winner = False
                break
        
        if is_winner:
            return candidate
    
    return None


def schulze_method(
    pairwise_results: Dict[Tuple[str, str], int],
    candidates: Set[str]
) -> str:
    """
    Schulze method for breaking ties when no Condorcet winner exists.
    
    Finds the candidate with strongest support when no clear winner exists.
    This is more complex than simple Borda count and handles cycles well.
    
    Algorithm:
    1. Build strongest path from each candidate to every other
    2. For each candidate, find weakest link in their strongest path
    3. Winner is candidate with strongest weakest link
    
    Args:
        pairwise_results: Dictionary from calculate_pairwise_results()
        candidates: Set of all candidate IDs
    
    Returns:
        Winning candidate ID
    """
    
    # Initialize distance matrix (strongest path strengths)
    candidates_list = list(candidates)
    n = len(candidates_list)
    
    # d[i][j] = strongest path strength from i to j
    d = {}
    
    # Initialize: direct pairwise results
    for i, cand_i in enumerate(candidates_list):
        for j, cand_j in enumerate(candidates_list):
            if i != j:
                strength = pairwise_results.get((cand_i, cand_j), 0)
                d[(cand_i, cand_j)] = strength
            else:
                d[(cand_i, cand_j)] = 0
    
    # Floyd-Warshall: find strongest paths through intermediates
    for k in candidates_list:
        for i in candidates_list:
            for j in candidates_list:
                if i != j:
                    # Path i -> k -> j might be stronger than i -> j
                    current = d[(i, j)]
                    via_k = min(d[(i, k)], d[(k, j)])
                    d[(i, j)] = max(current, via_k)
    
    # Find winner: candidate who beats all others in path strength
    # Candidate X wins if p[X,Y] >= p[Y,X] for all other candidates Y
    
    schulze_winners = []
    for i in candidates_list:
        is_winner = True
        for j in candidates_list:
            if i != j:
                # If any other candidate has a stronger path to i than i has to them, i loses
                if d[(j, i)] > d[(i, j)]:
                    is_winner = False
                    break
        if is_winner:
            schulze_winners.append(i)
    
    if schulze_winners:
        if len(schulze_winners) > 1:
            logger.warning(f"Multiple Schulze winners found: {schulze_winners}. Picking random.")
            return random.choice(schulze_winners)
        
        logger.info(f"Schulze winner determined: {schulze_winners[0]}")
        return schulze_winners[0]
    
    # Fallback (should theoretically not happen)
    logger.error("No Schulze winner found (unexpected). Returning random.")
    return random.choice(candidates_list)


def borda_count_tiebreaker(votes_list: List[List[str]]) -> str:
    """
    Simple Borda count as secondary tiebreaker (if needed).
    
    Points awarded based on ranking position:
    - 1st choice: n points
    - 2nd choice: n-1 points
    - etc.
    
    Args:
        votes_list: List of ranked votes
    
    Returns:
        Winning candidate ID
    """
    
    scores = defaultdict(int)
    n_candidates = len(votes_list[0]) if votes_list else 0
    
    for vote in votes_list:
        for position, candidate in enumerate(vote):
            points = n_candidates - position
            scores[candidate] += points
    
    return max(scores.items(), key=lambda x: x[1])[0]


def validate_ranking(ranking: List[str], expected_candidates: Set[str]) -> bool:
    """
    Validate that a ranking contains all expected candidates exactly once.
    
    Args:
        ranking: List of candidate IDs in ranked order
        expected_candidates: Set of valid candidate IDs
    
    Returns:
        True if ranking is valid, False otherwise
    """
    
    if len(ranking) != len(expected_candidates):
        logger.warning(f"Ranking length {len(ranking)} "
                      f"!= expected {len(expected_candidates)}")
        return False
    
    if set(ranking) != expected_candidates:
        logger.warning("Ranking candidates don't match expected set")
        return False
    
    if len(ranking) != len(set(ranking)):
        logger.warning("Ranking contains duplicate candidates")
        return False
    
    return True


def get_ranking_statistics(votes_list: List[List[str]]) -> Dict:
    """
    Calculate statistics about voting results.
    
    Args:
        votes_list: List of ranked votes
    
    Returns:
        Dictionary with statistics:
        {
            'total_votes': int,
            'candidates_count': int,
            'first_choice_votes': {'cand_id': count, ...},
            'pairwise_results': {...},
        }
    """
    
    candidates = set()
    for vote in votes_list:
        candidates.update(vote)
    
    first_choices = defaultdict(int)
    for vote in votes_list:
        if vote:
            first_choices[vote[0]] += 1
    
    return {
        'total_votes': len(votes_list),
        'candidates_count': len(candidates),
        'first_choice_votes': dict(first_choices),
        'pairwise_results': calculate_pairwise_results(votes_list, candidates),
    }


def random_tiebreaker(candidates: Set[str]) -> str:
    """
    Random tiebreaker method.
    
    Args:
        candidates: Set of candidate IDs
    
    Returns:
        Randomly selected candidate ID
    """
    return random.choice(list(candidates))


def generate_qr_code(request, poll_uuid):
    """
    Generate the QR code URL for a poll.
    """
    poll_url = request.build_absolute_uri(
        reverse('vote', kwargs={'poll_uuid': poll_uuid})
    )
    # Using a public QR code generator API (e.g., goqr.me)
    # In a real production environment, you might want to generate this locally
    # using a library like `qrcode` or `segno` to avoid leaking URLs to third parties.
    # For this simple example, we construct a Google Charts API or similar URL.
    
    # Let's use `qrcode` python library approach if we wanted to do it server side, 
    # but to send a string to the template, we can just send the target URL 
    # and let a JS library handle it, OR use an external image service.
    
    # Using quickchart.io as it is simple and reliable for free tier
    encoded_url = urllib.parse.quote(poll_url)
    return f"https://quickchart.io/qr?text={encoded_url}&size=200"

