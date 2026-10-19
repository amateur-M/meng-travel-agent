"""Uniform error responses (V4/P1, T1.6).

The endpoints used to hand-roll ``JSONResponse(status_code=404,
content={"detail": ...})`` in several places. That bypasses ``response_model``
and scatters the error shape across modules. Raising ``HTTPException`` instead
lets FastAPI's built-in handler render the identical ``{"detail": ...}`` body,
so the wire contract is unchanged while the 404 shape lives in one place.
"""

from fastapi import HTTPException, status


def not_found(detail: str) -> HTTPException:
    """A 404 with the standard ``{"detail": ...}`` body.

    Returned (not raised) so call sites read ``raise not_found("...")``.
    """
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def bad_request(detail: str) -> HTTPException:
    """A 400 with the standard ``{"detail": ...}`` body."""
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
