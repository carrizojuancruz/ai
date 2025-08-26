


import hashlib


def create_content_hash(content: str) -> str:
    """Create a SHA-256 hash of the given content."""
    return hashlib.sha256(content.encode()).hexdigest()
