"""Bearer token authentication middleware for HTTP transport."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def create_auth_middleware(expected_key: str):
    """Create a bearer token authentication middleware function.

    For FastMCP HTTP transport, we use an auth dependency that validates
    the Authorization header on incoming requests.

    Args:
        expected_key: The expected bearer token value

    Returns:
        An async middleware function
    """

    async def auth_middleware(request):
        """Validate Bearer token on HTTP requests."""
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            logger.warning("Missing or malformed Authorization header")
            raise PermissionError("Missing Bearer token")

        token = auth_header.split(" ", 1)[1]
        if token != expected_key:
            logger.warning("Invalid Bearer token")
            raise PermissionError("Invalid Bearer token")

        return True

    return auth_middleware
