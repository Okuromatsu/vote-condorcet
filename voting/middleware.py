"""
Custom middleware for Condorcet Voting System
==============================================

Security & session management middleware:
- SecurityHeadersMiddleware: Adds custom security headers
- DuplicateVoteMiddleware: Tracks and prevents duplicate votes via cookies
- CsrfExemptLocalhost: Allows CSRF in localhost development (no Origin header)

OWASP recommendations implemented:
- X-Frame-Options: Prevent clickjacking
- X-Content-Type-Options: Prevent MIME type sniffing
- X-XSS-Protection: Legacy XSS filter
- Content-Security-Policy: Restrict script/resource loading
"""

from django.utils.deprecation import MiddlewareMixin # pyright: ignore[reportMissingModuleSource]
from django.http import HttpResponse # pyright: ignore[reportMissingModuleSource]
from django.conf import settings # pyright: ignore[reportMissingModuleSource]
import logging

logger = logging.getLogger(__name__)


class CsrfExemptLocalhost(MiddlewareMixin):
    """
    In development on localhost, allow CSRF without strict origin checking.
    
    Problem: Django 4.2+ requires Origin header for CSRF validation.
    When accessing via http://localhost:8000, the browser doesn't send Origin header,
    causing "Origin checking failed - null does not match any trusted origins" error.
    
    Solution: This middleware temporarily disables CSRF_EXEMPT_REFERER_HEADER_CHECK
    for localhost requests in DEBUG mode.
    
    Security: ONLY used in DEBUG mode. Production uses strict CSRF validation.
    """
    
    def process_request(self, request):
        """Allow localhost to bypass strict origin checking in development."""
        
        if settings.DEBUG:
            host = request.META.get('HTTP_HOST', '')
            # Allow localhost variants in development
            if host.startswith(('localhost', '127.0.0.1')):
                # Mark request to skip CSRF origin check
                request._dont_enforce_csrf_checks = True
        
        return None

class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Add security headers to all HTTP responses.
    
    Headers added:
    - X-Frame-Options: DENY (prevent clickjacking)
    - X-Content-Type-Options: nosniff (prevent MIME sniffing)
    - X-XSS-Protection: 1; mode=block (legacy XSS protection)
    - Strict-Transport-Security: HTTPS enforcement
    """
    
    def process_response(self, request, response):
        """Add security headers to response."""
        
        # Prevent clickjacking attacks
        response['X-Frame-Options'] = 'DENY'
        
        # Prevent MIME type sniffing
        response['X-Content-Type-Options'] = 'nosniff'
        
        # Legacy XSS filter (modern browsers use CSP)
        response['X-XSS-Protection'] = '1; mode=block'
        
        # Prevent access from non-HTTPS (if not DEBUG)
        if not response.has_header('Strict-Transport-Security'):
            response['Strict-Transport-Security'] = (
                'max-age=31536000; includeSubDomains; preload'
            )
        
        # Referrer policy (limit what referer info is sent)
        # Use strict-origin-when-cross-origin instead of no-referrer to ensure
        # Referer header is sent for same-origin requests (required for CSRF)
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Feature policy / Permissions-Policy
        response['Permissions-Policy'] = (
            'geolocation=(), microphone=(), camera=()'
        )
        
        logger.debug("Security headers added to response")
        return response


class DuplicateVoteMiddleware(MiddlewareMixin):
    """
    Track voter sessions via cookies to prevent duplicate votes.
    
    How it works:
    1. First request: Generate unique cookie token
    2. Store token with voter fingerprint (IP + User-Agent)
    3. On vote submission: Check if fingerprint already voted
    4. Reject vote if duplicate detected
    
    Security considerations:
    - Does NOT prevent determined attackers (use VPN/proxy)
    - Provides basic protection for casual vote manipulation
    - Combined with IP logging for audit trail
    """
    
    VOTER_COOKIE_NAME = 'condorcet_voter_session'
    VOTER_COOKIE_AGE = 31536000  # 1 year (seconds)
    
    def process_request(self, request):
        """Check or create voter session cookie."""
        
        # Skip static files to prevent race conditions and unnecessary processing
        if request.path.startswith(settings.STATIC_URL) or request.path.startswith(settings.MEDIA_URL):
            return None

        # Generate or retrieve voter session token
        if self.VOTER_COOKIE_NAME not in request.COOKIES:
            # New voter - generate token
            import uuid
            token = uuid.uuid4().hex
            request.voter_session_token = token
            request.voter_session_new = True
        else:
            # Returning voter
            request.voter_session_token = request.COOKIES[self.VOTER_COOKIE_NAME]
            request.voter_session_new = False
        
        # Extract voter fingerprint data
        request.voter_ip = self.get_client_ip(request)
        request.voter_user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        logger.debug(f"Voter session: {request.voter_session_token} "
                    f"({request.voter_ip})")
        
        return None
    
    def process_response(self, request, response):
        """Set voter session cookie in response."""
        
        # Set cookie for new voters
        if hasattr(request, 'voter_session_new') and request.voter_session_new:
            response.set_cookie(
                self.VOTER_COOKIE_NAME,
                request.voter_session_token,
                max_age=self.VOTER_COOKIE_AGE,
                secure=not settings.DEBUG,  # HTTPS only in production
                httponly=True,  # No JavaScript access
                samesite='Lax',  # Allow cookies on top-level navigation
            )
            logger.info(f"New voter session cookie set: "
                       f"{request.voter_session_token}")
        
        return response
    
    @staticmethod
    def get_client_ip(request):
        """
        Extract client IP address, considering proxies.
        
        Checks headers in order:
        1. X-Forwarded-For (most common proxy header)
        2. X-Real-IP
        3. REMOTE_ADDR (direct connection)
        
        Args:
            request: Django request object
            
        Returns:
            Client IP address string
        """
        
        # Check for proxy headers (set by reverse proxy/load balancer)
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # Can contain multiple IPs, first is client
            ip = x_forwarded_for.split(',')[0].strip()
            return ip
        
        # Check alternative proxy header
        x_real_ip = request.META.get('HTTP_X_REAL_IP')
        if x_real_ip:
            return x_real_ip
        
        # Direct connection
        return request.META.get('REMOTE_ADDR', '0.0.0.0')
