"""The single slowapi Limiter instance (V4/P1).

Created here rather than in ``main.py`` so route modules can decorate their
endpoints with ``@limiter.limit(...)`` without importing the app. ``main``
still attaches it to ``app.state.limiter`` (slowapi reads it from there) and
mounts ``SlowAPIMiddleware``.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from config.settings import settings

# The middleware is always mounted; ``enabled`` follows the env so tests and
# local dev do not trip 429s, while production can turn limiting on.
limiter = Limiter(key_func=get_remote_address, enabled=settings.rate_limit_enabled)
