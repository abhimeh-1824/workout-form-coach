import logging
import secrets
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.security import (
    create_oauth_state_token,
    create_session_token,
    generate_pkce_pair,
    verify_oauth_state_token,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserResponse

logger = logging.getLogger("workout_form_coach.auth")

router = APIRouter(tags=["authentication"])


@router.get("/google/login", summary="Initiate Google OAuth Login with PKCE")
def google_login() -> RedirectResponse:
    """Generate Google authorization URL with PKCE and redirect the browser."""
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured on this server.",
        )

    code_verifier, code_challenge = generate_pkce_pair()
    state = secrets.token_urlsafe(32)
    state_cookie_val = create_oauth_state_token(state, code_verifier)

    query_params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "access_type": "online",
        "prompt": "select_account",
    }
    google_auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(query_params)}"
    )

    response = RedirectResponse(
        url=google_auth_url,
        status_code=status.HTTP_302_FOUND,
    )
    response.set_cookie(
        key="oauth_state",
        value=state_cookie_val,
        httponly=True,
        secure=settings.APP_ENV == "production",
        samesite="lax",
        max_age=600,  # 10 minutes
        path="/",
    )
    return response


@router.get("/google/callback", summary="Google OAuth Callback Handler")
async def google_callback(
    request: Request,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Validate Google OAuth callback, exchange code, upsert user, and create session."""
    if error:
        logger.warning("OAuth provider returned error: %s", error)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth authorization failed: {error}",
        )

    if not code or not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing authorization code or state parameter",
        )

    oauth_state_cookie = request.cookies.get("oauth_state")
    if not oauth_state_cookie:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing or expired OAuth state cookie",
        )

    state_data = verify_oauth_state_token(oauth_state_cookie)
    if not state_data or state_data.get("state") != state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state parameter",
        )

    code_verifier = state_data.get("code_verifier")
    if not code_verifier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing PKCE code verifier",
        )

    # Securely exchange authorization code for tokens with PKCE verifier
    token_url = "https://oauth2.googleapis.com/token"
    token_payload = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "code": code,
        "code_verifier": code_verifier,
        "grant_type": "authorization_code",
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            token_response = await client.post(token_url, data=token_payload)
        except httpx.RequestError as exc:
            logger.error("Failed to connect to Google token endpoint: %s", type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to contact OAuth provider",
            )

        if token_response.status_code != 200:
            logger.error(
                "Google token exchange failed with status %d",
                token_response.status_code,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to exchange authorization code with OAuth provider",
            )

        tokens = token_response.json()
        access_token = tokens.get("access_token")
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No access token received from OAuth provider",
            )

        # Retrieve user profile from Google OIDC userinfo endpoint
        userinfo_url = "https://openidconnect.googleapis.com/v1/userinfo"
        try:
            userinfo_response = await client.get(
                userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
        except httpx.RequestError as exc:
            logger.error("Failed to connect to Google userinfo endpoint: %s", type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to fetch user profile from OAuth provider",
            )

        if userinfo_response.status_code != 200:
            logger.error(
                "Google userinfo request failed with status %d",
                userinfo_response.status_code,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to fetch user profile from OAuth provider",
            )

        user_info = userinfo_response.json()

    provider_user_id = str(user_info.get("sub", ""))
    email = user_info.get("email")
    name = user_info.get("name")

    if not provider_user_id or not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incomplete user profile received from OAuth provider",
        )

    # Upsert user record: find existing user by (provider, provider_user_id)
    user = db.execute(
        select(User).where(
            User.provider == "google",
            User.provider_user_id == provider_user_id,
        )
    ).scalar_one_or_none()

    if not user:
        # Check if email is already registered
        existing_email_user = db.execute(
            select(User).where(User.email == email)
        ).scalar_one_or_none()

        if existing_email_user:
            user = existing_email_user
            user.provider = "google"
            user.provider_user_id = provider_user_id
            if name:
                user.name = name
        else:
            user = User(
                provider="google",
                provider_user_id=provider_user_id,
                email=email,
                name=name,
            )
            db.add(user)
    else:
        if name and user.name != name:
            user.name = name
        if user.email != email:
            user.email = email

    db.commit()
    db.refresh(user)

    # Create server-signed session token containing user ID
    session_token = create_session_token(user.id)

    # Secure redirect to the configured frontend application
    response = RedirectResponse(
        url=settings.FRONTEND_URL,
        status_code=status.HTTP_302_FOUND,
    )
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=session_token,
        httponly=True,
        secure=settings.APP_ENV == "production",
        samesite="lax",
        max_age=settings.SESSION_MAX_AGE_SECONDS,
        path="/",
    )
    # Clear one-time OAuth state cookie
    response.delete_cookie(
        key="oauth_state",
        path="/",
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/me", response_model=UserResponse, summary="Get Current Authenticated User")
def get_me(current_user: User = Depends(get_current_user)) -> User:
    """Return profile details for the currently authenticated session."""
    return current_user


@router.post("/logout", summary="Logout Current User Session")
def logout() -> JSONResponse:
    """Invalidate authenticated session by clearing the HttpOnly session cookie."""
    response = JSONResponse(content={"message": "Successfully logged out"})
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
    )
    return response
