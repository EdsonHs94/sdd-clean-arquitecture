"""JWT access-token adapter with signature and claim verification enabled."""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

import jwt

from app.application.dto import TokenResult
from app.application.errors import DependencyUnavailable, NotAuthenticated

ACCESS_TOKEN_LIFETIME = 3600
SIGNING_ALGORITHM = "HS256"
REQUIRED_CLAIMS = ["sub", "exp", "iat", "iss", "aud"]


class JwtTokenService:
    def __init__(
        self,
        secret: str,
        *,
        issuer: str = "user-architecture-model",
        audience: str = "user-architecture-model-api",
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if not isinstance(secret, str) or len(secret.encode()) < 32:
            raise ValueError("Signing secret must contain at least 32 bytes")
        if (
            not isinstance(issuer, str)
            or not issuer
            or not isinstance(audience, str)
            or not audience
        ):
            raise ValueError("Issuer and audience must be nonempty strings")
        self._secret = secret
        self._issuer = issuer
        self._audience = audience
        self._clock = clock

    async def issue(self, user_id: UUID) -> TokenResult:
        if not isinstance(user_id, UUID):
            raise ValueError("Token subject must be a UUID")
        issued_at = int(self._clock().timestamp())
        claims = {
            "sub": str(user_id),
            "iat": issued_at,
            "exp": issued_at + ACCESS_TOKEN_LIFETIME,
            "iss": self._issuer,
            "aud": self._audience,
        }
        try:
            token = jwt.encode(claims, self._secret, algorithm=SIGNING_ALGORITHM)
        except jwt.PyJWTError:
            raise DependencyUnavailable() from None
        return TokenResult(access_token=token, expires_in=ACCESS_TOKEN_LIFETIME)

    async def verify(self, token: str) -> UUID:
        if not isinstance(token, str) or not token:
            raise NotAuthenticated()
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=[SIGNING_ALGORITHM],
                issuer=self._issuer,
                audience=self._audience,
                leeway=0,
                options={"require": REQUIRED_CLAIMS, "strict_aud": True},
            )
            # PyJWT accepts coercible numeric dates; the application requires integers.
            if type(claims["iat"]) is not int or type(claims["exp"]) is not int:
                raise NotAuthenticated()
            return UUID(claims["sub"])
        except (jwt.InvalidTokenError, ValueError, TypeError):
            raise NotAuthenticated() from None
        except jwt.PyJWTError:
            raise DependencyUnavailable() from None
