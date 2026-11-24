from uuid import uuid4

from app.core.config import load_settings
from app.core.identity import request_identity


def test_identity_hashes_are_stable_domain_separated_and_not_raw_values():
    config = load_settings()
    owner = uuid4()
    first = request_identity(config, "203.0.113.4", owner)
    assert first == request_identity(config, "203.0.113.4", owner)
    assert len(first.ip_hash) == 64 and len(first.session_hash) == 64
    assert "203.0.113.4" not in str(first) and str(owner) not in str(first)
    assert first.ip_hash != first.session_hash
