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


def calculate_condorcet_winner(votes_list: List[List[str]], tiebreaker_method: str = 'schulze', expected_candidates: Set[str] = None) -> Tuple[Optional[str], Optional[str], bool]:
    """
    Calculate Condorcet winner from a list of ranked votes.
    
    Returns:
        Tuple (winner_id, method_used, was_randomly_picked)
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
            return list(all_candidates)[0], 'condorcet', False
        raise ValueError("Need at least 2 candidates.")
    
    logger.info(f"Calculating winner for {len(votes_list)} votes with {len(all_candidates)} candidates")
    
    # Calculate pairwise results
    pairwise_results = calculate_pairwise_results(votes_list, all_candidates)
    
    condorcet_winner = find_condorcet_winner(pairwise_results, all_candidates)
    
    if condorcet_winner:
        logger.info(f"Condorcet winner found: {condorcet_winner}")
        return condorcet_winner, 'condorcet', False
    
    # Tiebreakers
    if tiebreaker_method == 'borda':
        winner_id, was_random = borda_count_tiebreaker(votes_list)
        return winner_id, 'borda', was_random
    elif tiebreaker_method == 'random':
        return random_tiebreaker(all_candidates), 'random', True
    else:
        winner_id, was_random = schulze_method(pairwise_results, all_candidates)
        return winner_id, 'schulze', was_random


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
) -> Tuple[str, bool]:
    """
    Schulze method for breaking ties when no Condorcet winner exists.
    
    Returns:
        Tuple (winner_id, was_randomly_picked)
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
    schulze_winners = []
    for i in candidates_list:
        is_winner = True
        for j in candidates_list:
            if i != j:
                if d[(j, i)] > d[(i, j)]:
                    is_winner = False
                    break
        if is_winner:
            schulze_winners.append(i)
    
    if schulze_winners:
        if len(schulze_winners) > 1:
            logger.warning(f"Multiple Schulze winners found: {schulze_winners}. Picking random.")
            return random.choice(schulze_winners), True
        
        logger.info(f"Schulze winner determined: {schulze_winners[0]}")
        return schulze_winners[0], False
    
    return random.choice(candidates_list), True


def borda_count_tiebreaker(votes_list: List[List[str]]) -> Tuple[str, bool]:
    """
    Simple Borda count as secondary tiebreaker.
    
    Returns:
        Tuple (winner_id, was_randomly_picked)
    """
    
    scores = defaultdict(int)
    n_candidates = len(votes_list[0]) if votes_list else 0
    
    for vote in votes_list:
        for position, candidate in enumerate(vote):
            points = n_candidates - position
            scores[candidate] += points
    
    if not scores:
        all_cands = list(set(c for v in votes_list for c in v))
        return random.choice(all_cands), True

    max_score = max(scores.values())
    winners = [c for c, s in scores.items() if s == max_score]
    
    if len(winners) > 1:
        return random.choice(winners), True
    
    return winners[0], False


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


