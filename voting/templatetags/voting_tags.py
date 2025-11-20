"""
Django template tags and filters for Condorcet Voting System

Custom filters for:
- Dictionary access in templates
- String splitting
- Pairwise display formatting
"""

from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """
    Get item from dictionary by key in templates.
    Usage: {{ my_dict|get_item:my_key }}
    
    Args:
        dictionary: Dictionary to access
        key: Key to retrieve
    
    Returns:
        Value at key or empty string if not found
    """
    if isinstance(dictionary, dict):
        return dictionary.get(str(key), '')
    return ''


@register.filter
def split(value, arg):
    """
    Split string by delimiter in templates.
    Usage: {{ "a_b_c"|split:"_" }}
    
    Args:
        value: String to split
        arg: Delimiter
    
    Returns:
        List of split strings
    """
    return str(value).split(str(arg))
