import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import HTTPException, Request, Response

from api.config import settings
from api.db.connection import get_pool


COOKIE_NAME = "ninety_session"


def _token_for(user_id: int) -> str:
    return jwt.encode(
        {
            "sub": str(user_id),
            "exp": datetime.now(timezone.utc) + timedelta(days=settings.auth_session_days),
        },
        settings.auth_secret,
        algorithm="HS256",
    )


async def set_auth_cookie(response: Response, user_id: int) -> None:
    response.set_cookie(
        COOKIE_NAME,
        _token_for(user_id),
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        max_age=settings.auth_session_days * 86400,
        path="/",
    )


async def current_user(request: Request) -> dict:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    try:
        payload = jwt.decode(token, settings.auth_secret, algorithms=["HS256"])
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Your session has expired.") from exc

    pool = await get_pool()
    user = await pool.fetchrow(
        "SELECT id, email, display_name, avatar_url FROM users WHERE id = $1",
        user_id,
    )
    if not user:
        raise HTTPException(status_code=401, detail="Account not found.")
    return dict(user)


def hash_otp(code: str) -> str:
    return hashlib.sha256(f"{settings.auth_secret}:{code}".encode()).hexdigest()


async def create_or_update_user(email: str, display_name: str | None = None, avatar_url: str | None = None) -> dict:
    pool = await get_pool()
    return dict(await pool.fetchrow(
        """
        INSERT INTO users (email, display_name, avatar_url)
        VALUES ($1, $2, $3)
        ON CONFLICT (email) DO UPDATE SET
          display_name = COALESCE(EXCLUDED.display_name, users.display_name),
          avatar_url = COALESCE(EXCLUDED.avatar_url, users.avatar_url),
          updated_at = NOW()
        RETURNING id, email, display_name, avatar_url
        """,
        email.lower().strip(),
        display_name,
        avatar_url,
    ))


async def send_otp_email(email: str, code: str) -> None:
    if not settings.smtp_host or not settings.smtp_username or not settings.smtp_password:
        raise HTTPException(
            status_code=503,
            detail="Email OTP is not configured. Add the SMTP settings from the setup guide.",
        )
    import smtplib
    from email.message import EmailMessage

    message = EmailMessage()
    message["Subject"] = "Your Ninety sign-in code"
    message["From"] = settings.smtp_from or settings.smtp_username
    message["To"] = email
    message.set_content(f"Your Ninety sign-in code is {code}. It expires in 10 minutes.")

    def deliver() -> None:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.starttls()
            server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)

    import asyncio
    await asyncio.to_thread(deliver)


async def google_authorization_url(state: str) -> str:
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "select_account",
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


async def exchange_google_code(code: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        token_response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        token_response.raise_for_status()
        token = token_response.json()["access_token"]
        profile_response = await client.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {token}"},
        )
        profile_response.raise_for_status()
        return profile_response.json()


def oauth_state() -> str:
    return secrets.token_urlsafe(32)
