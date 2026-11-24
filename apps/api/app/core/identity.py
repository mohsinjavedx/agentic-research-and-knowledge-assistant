"""Stable, domain-separated HMAC identities without retaining raw network identifiers."""

import hashlib
import hmac
from dataclasses import dataclass
from ipaddress import ip_address
from uuid import UUID

from app.core.config import Settings


@dataclass(frozen=True)
class RequestIdentity:
    ip_hash: str
    session_hash: str


def private_hash(settings: Settings, kind: str, value: str) -> str:
    # Development inherits a stable existing secret; production requires its own key.
    secret = (
        settings.privacy_hash_key.get_secret_value() or settings.database_url.get_secret_value()
    )
    key = hashlib.sha256(("research-identity-v1:" + secret).encode()).digest()
    return hmac.new(key, f"{kind}:{value}".encode(), hashlib.sha256).hexdigest()


def request_identity(settings: Settings, peer: str, session_id: UUID) -> RequestIdentity:
    try:
        peer = str(ip_address(peer))
    except ValueError:
        # ASGI test transports can supply a named peer. Never read forwarding headers here.
        peer = peer.casefold()
    return RequestIdentity(
        private_hash(settings, "ip", peer), private_hash(settings, "session", str(session_id))
    )
