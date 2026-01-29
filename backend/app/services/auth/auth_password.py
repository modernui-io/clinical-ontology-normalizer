"""Password hashing and verification utilities.

This module provides password-related operations:
- Password hashing using bcrypt
- Password verification against stored hashes

Security considerations:
- Uses bcrypt with 12 rounds of salt
- Timing-safe password comparison
"""

import bcrypt


def hash_password(password: str) -> str:
    """Hash a password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        Bcrypt hashed password string
    """
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a password against its hash.

    Args:
        password: Plain text password to verify
        hashed_password: Stored bcrypt hash

    Returns:
        True if password matches, False otherwise
    """
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False
