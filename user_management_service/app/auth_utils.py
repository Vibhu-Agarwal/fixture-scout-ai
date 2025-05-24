# user_management_service/app/auth_utils.py
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt  # PyJWT library
from jwt import PyJWTError
from pydantic import BaseModel

from .config import settings

logger = logging.getLogger(__name__)

from .models import TokenData


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})

    try:
        encoded_jwt = jwt.encode(
            to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
        )
        return encoded_jwt
    except PyJWTError as e:
        logger.error(f"Error encoding JWT: {e}", exc_info=True)
        raise  # Re-raise the error to be handled by the caller


def decode_access_token(token: str) -> Optional[TokenData]:
    """
    Decodes an access token. Returns TokenData if valid, None otherwise.
    This function would be used if the service itself validates tokens,
    rather than fully relying on an API Gateway.
    """
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        user_id: Optional[str] = payload.get(
            "sub"
        )  # Assuming you store user_id in 'sub' claim
        if user_id is None:
            # Try 'user_id' if you used that as the claim key
            user_id = payload.get("user_id")

        # You might want to add more validation here, e.g., check 'iss' (issuer), 'aud' (audience)
        # For now, just extracting user_id based on 'sub' or 'user_id' claim
        return TokenData(user_id=user_id)
    except PyJWTError as e:
        logger.warning(f"JWT decoding/validation error: {e}")
        return None
