import datetime
import logging
import os
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

AUTH_SECRET = os.getenv("AUTH_SECRET")
if not AUTH_SECRET:
    raise RuntimeError("AUTH_SECRET is not set. Add AUTH_SECRET to backend/.env.")

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    FastAPI dependency that validates the NextAuth JWT (signed with AUTH_SECRET).
    Returns the decoded token payload if valid, or raises HTTP 401.
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            AUTH_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False},  # NextAuth doesn't set aud by default
            leeway=datetime.timedelta(seconds=30),  # tolerate host↔container clock skew
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("JWT auth failed: token has expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        logger.warning("JWT auth failed: %s (secret length: %d)", e, len(AUTH_SECRET) if AUTH_SECRET else 0)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
