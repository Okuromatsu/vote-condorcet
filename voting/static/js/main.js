// Condorcet Vote - Main JavaScript

/**
 * DOM Ready Handler
 * Initialize all interactive components when page loads
 */
document.addEventListener('DOMContentLoaded', function() {
    initializeTooltips();
    initializePopovers();
    initializeFormValidation();
    initializePolls();
});

/**
 * Initialize Bootstrap tooltips
 */
function initializeTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

/**
 * Initialize Bootstrap popovers
 */
function initializePopovers() {
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function(popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
}

/**
 * Initialize form validation (Bootstrap)
 */
function initializeFormValidation() {
    const forms = document.querySelectorAll('.needs-validation');
    Array.from(forms).forEach(function(form) {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        }, false);
    });
}

/**
 * Initialize poll interactions
 */
function initializePolls() {
    // Add click handlers to poll cards
    document.querySelectorAll('.hover-card').forEach(card => {
        const voteBtn = card.querySelector('a[href*="/vote/"]');
        if (voteBtn) {
            card.addEventListener('click', function(e) {
                if (e.target.tagName !== 'A' && e.target.tagName !== 'BUTTON') {
                    voteBtn.click();
                }
            });
        }
    });
}

/**
 * Utility: Show toast notification
 * @param {string} message - Message to display
 * @param {string} type - Type: success, danger, warning, info
 * @param {number} duration - Duration in milliseconds
 */
function showToast(message, type = 'info', duration = 3000) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show fixed-top mt-3`;
    alertDiv.style.zIndex = '9999';
    
    // Create message text node (safe - treated as text, not HTML)
    const messageSpan = document.createElement('span');
    messageSpan.textContent = message;
    
    // Create close button (safe - no user data)
    const closeButton = document.createElement('button');
    closeButton.type = 'button';
    closeButton.className = 'btn-close';
    closeButton.setAttribute('data-bs-dismiss', 'alert');
    
    alertDiv.appendChild(messageSpan);
    alertDiv.appendChild(closeButton);
    
    document.body.insertBefore(alertDiv, document.body.firstChild);
    
    setTimeout(() => {
        alertDiv.remove();
    }, duration);
}

/**
 * Utility: Copy text to clipboard
 * @param {string} text - Text to copy
 * @param {string} feedbackElement - Element to show feedback on
 */
function copyToClipboard(text, feedbackElement = null) {
    navigator.clipboard.writeText(text).then(() => {
        if (feedbackElement) {
            const originalText = feedbackElement.textContent;
            feedbackElement.textContent = '✅ Copied!';
            setTimeout(() => {
                feedbackElement.textContent = originalText;
            }, 2000);
        }
        showToast('Link copied to clipboard!', 'success');
    }).catch(() => {
        showToast('Failed to copy to clipboard', 'danger');
    });
}

/**
 * Utility: Format date
 * @param {Date} date - Date to format
 * @return {string} Formatted date string
 */
function formatDate(date) {
    return new Date(date).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

/**
 * Utility: Debounce function calls
 * @param {Function} func - Function to debounce
 * @param {number} delay - Delay in milliseconds
 * @return {Function} Debounced function
 */
function debounce(func, delay) {
    let timeoutId;
    return function(...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => func.apply(this, args), delay);
    };
}

/**
 * Utility: Throttle function calls
 * @param {Function} func - Function to throttle
 * @param {number} limit - Time limit in milliseconds
 * @return {Function} Throttled function
 */
function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

/**
 * Fetch poll data via AJAX
 * @param {string} pollId - Poll UUID
 * @return {Promise} Poll data
 */
async function fetchPollResults(pollId) {
    try {
        const response = await fetch(`/api/results/${pollId}/`);
        if (!response.ok) throw new Error('Failed to fetch results');
        return await response.json();
    } catch (error) {
        console.error('Error fetching poll results:', error);
        showToast('Error loading poll results', 'danger');
        return null;
    }
}

/**
 * Submit vote via AJAX (optional, for no-reload voting)
 * @param {string} pollId - Poll UUID
 * @param {Array} ranking - Candidate IDs in ranked order
 * @param {string} csrfToken - CSRF token
 * @return {Promise} Vote response
 */
async function submitVoteAjax(pollId, ranking, csrfToken) {
    try {
        const response = await fetch(`/vote/${pollId}/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({ ranking: ranking })
        });
        
        if (!response.ok) throw new Error('Failed to submit vote');
        return await response.json();
    } catch (error) {
        console.error('Error submitting vote:', error);
        showToast('Error submitting vote', 'danger');
        return null;
    }
}

/**
 * Analytics tracking (Google Analytics compatible)
 * @param {string} category - Event category
 * @param {string} action - Event action
 * @param {string} label - Event label
 */
function trackEvent(category, action, label = '') {
    if (typeof gtag !== 'undefined') {
        gtag('event', action, {
            'event_category': category,
            'event_label': label
        });
    }
}

// Export functions for use in other scripts
window.CondorcetVote = {
    showToast,
    copyToClipboard,
    formatDate,
    debounce,
    throttle,
    fetchPollResults,
    submitVoteAjax,
    trackEvent
};
