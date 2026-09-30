import base64
import hashlib
import secrets
from typing import Any, Dict, Optional
import uuid

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.core.config import settings

_session_serializer = URLSafeTimedSerializer(
    settings.SESSION_SECRET,
    salt="user-session-v1",
)

_oauth_state_serializer = URLSafeTimedSerializer(
    settings.SESSION_SECRET,
    salt="oauth-state-v1",
)


def create_session_token(user_id: uuid.UUID | str) -> str:
    """Generate a tamper-proof signed session token containing user id."""
    return _session_serializer.dumps({"sub": str(user_id)})


def verify_session_token(token: str) -> Optional[str]:
    """Verify and decode a signed session token. Returns user id string if valid."""
    try:
        data = _session_serializer.loads(
            token,
            max_age=settings.SESSION_MAX_AGE_SECONDS,
        )
        return data.get("sub")
    except (BadSignature, SignatureExpired):
        return None


def generate_pkce_pair() -> tuple[str, str]:
    """Generate PKCE code_verifier and S256 code_challenge."""
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return code_verifier, code_challenge


def create_oauth_state_token(state: str, code_verifier: str) -> str:
    """Generate a tamper-proof signed token storing state and code_verifier."""
    payload = {"state": state, "code_verifier": code_verifier}
    return _oauth_state_serializer.dumps(payload)


def verify_oauth_state_token(token: str, max_age: int = 600) -> Optional[Dict[str, Any]]:
    """Verify and decode an OAuth state token. Returns dict or None."""
    try:
        return _oauth_state_serializer.loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
