#!/usr/bin/env python3
"""
HTTP Signatures for ActivityPub

Implements draft-cavage-http-signatures-12 for ActivityPub:
- Verifying incoming ActivityPub requests
- Signing outgoing ActivityPub requests

References:
- https://swicg.github.io/activitypub-http-signature/
- https://datatracker.ietf.org/doc/html/draft-cavage-http-signatures-12
"""

import base64
import hashlib
import json
import re
import requests
from datetime import datetime, timezone
from typing import Optional, Dict, Tuple
from urllib.parse import urlparse
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend


# Cache for fetched actor public keys (simple in-memory cache)
# In production, consider using Redis or similar
_ACTOR_KEY_CACHE: Dict[str, Tuple[str, float]] = {}
CACHE_TTL = 3600  # 1 hour


def parse_signature_header(signature_header: str) -> Dict[str, str]:
    """
    Parse HTTP Signature header into components

    Args:
        signature_header: Raw Signature header value
            Example: 'keyId="https://example.com/actor#main-key",headers="(request-target) host date",signature="..."'

    Returns:
        dict: Parsed signature components (keyId, headers, signature, algorithm)
    """
    components = {}

    # Parse header format: keyId="...",headers="...",signature="..."
    pattern = r'(\w+)="([^"]*)"'
    matches = re.findall(pattern, signature_header)

    for key, value in matches:
        components[key] = value

    return components


def fetch_actor_public_key(key_id: str) -> Optional[str]:
    """
    Fetch actor's public key from keyId following ActivityPub spec

    Per spec: https://swicg.github.io/activitypub-http-signature/#how-to-obtain-a-signature-s-public-key
    1. Strip fragment from keyId before fetching
    2. Fetch actor document
    3. Find publicKey object whose id matches original keyId (with fragment)
    4. Extract publicKeyPem

    Args:
        key_id: Full keyId URL (may include fragment, e.g., 'https://example.com/actor#main-key')

    Returns:
        str: PEM-formatted public key, or None if fetch fails
    """
    # Check cache first
    if key_id in _ACTOR_KEY_CACHE:
        cached_key, cached_time = _ACTOR_KEY_CACHE[key_id]
        if datetime.now().timestamp() - cached_time < CACHE_TTL:
            return cached_key

    try:
        # Strip fragment identifier for fetching
        parsed = urlparse(key_id)
        fetch_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if parsed.query:
            fetch_url += f"?{parsed.query}"

        # Fetch actor document with ActivityPub headers
        headers = {
            'Accept': 'application/activity+json, application/ld+json',
            'User-Agent': 'TinyFedi/1.0'
        }

        response = requests.get(fetch_url, headers=headers, timeout=10)
        response.raise_for_status()
        actor_data = response.json()

        # Extract public key - can be object or array
        public_key_data = actor_data.get('publicKey')
        if not public_key_data:
            print(f"Warning: No publicKey in actor document for {key_id}")
            return None

        # Handle both single object and array formats
        keys_to_check = public_key_data if isinstance(public_key_data, list) else [public_key_data]

        # Find key whose id matches original keyId (including fragment)
        for key_obj in keys_to_check:
            # Handle both expanded objects and compacted IDs
            if isinstance(key_obj, dict):
                if key_obj.get('id') == key_id:
                    public_key_pem = key_obj.get('publicKeyPem')
                    if public_key_pem:
                        # Cache the key
                        _ACTOR_KEY_CACHE[key_id] = (public_key_pem, datetime.now().timestamp())
                        return public_key_pem

        print(f"Warning: No matching publicKey found for {key_id}")
        return None

    except Exception as e:
        print(f"Error fetching public key for {key_id}: {e}")
        return None


def build_signing_string(headers_to_sign: str, method: str, path: str, headers: Dict[str, str]) -> str:
    """
    Build the signing string from request components

    Per spec: https://swicg.github.io/activitypub-http-signature/#signing-string
    Format: "header-name: header-value\nheader-name: header-value\n..."

    Args:
        headers_to_sign: Space-separated list of headers (e.g., "(request-target) host date digest")
        method: HTTP method (e.g., "POST")
        path: Request path (e.g., "/activitypub/inbox")
        headers: Dict of HTTP headers from the request

    Returns:
        str: Signing string ready for signature verification
    """
    header_list = headers_to_sign.split()
    signing_parts = []

    for header_name in header_list:
        if header_name == '(request-target)':
            # Special pseudo-header: "post /activitypub/inbox"
            target = f"{method.lower()} {path}"
            signing_parts.append(f"(request-target): {target}")
        else:
            # Regular header - use lowercase name
            header_value = headers.get(header_name) or headers.get(header_name.lower()) or headers.get(header_name.title())
            if header_value:
                signing_parts.append(f"{header_name.lower()}: {header_value}")
            else:
                # Header not found - signature will fail
                print(f"Warning: Header '{header_name}' not found in request")
                signing_parts.append(f"{header_name.lower()}: ")

    return '\n'.join(signing_parts)


def compute_digest(body: bytes) -> str:
    """
    Compute SHA-256 digest of request body

    Per spec: Digest header format is "SHA-256=base64(sha256(body))"

    Args:
        body: Request body as bytes

    Returns:
        str: Digest header value (e.g., "SHA-256=abc123...")
    """
    hash_obj = hashlib.sha256(body)
    digest_b64 = base64.b64encode(hash_obj.digest()).decode('utf-8')
    return f"SHA-256={digest_b64}"


def verify_signature(signature_header: str, method: str, path: str, headers: Dict[str, str], body: bytes) -> bool:
    """
    Verify HTTP signature on incoming request

    Args:
        signature_header: Value of the Signature header
        method: HTTP method (e.g., "POST")
        path: Request path (e.g., "/activitypub/inbox")
        headers: Dict of request headers
        body: Request body as bytes

    Returns:
        bool: True if signature is valid, False otherwise
    """
    try:
        # Parse signature header
        sig_components = parse_signature_header(signature_header)

        key_id = sig_components.get('keyId')
        signature_b64 = sig_components.get('signature')
        headers_to_sign = sig_components.get('headers', '(request-target) host date')

        if not key_id or not signature_b64:
            print("Error: Missing keyId or signature in Signature header")
            return False

        # Fetch the public key
        public_key_pem = fetch_actor_public_key(key_id)
        if not public_key_pem:
            print(f"Error: Could not fetch public key for {key_id}")
            return False

        # Build signing string
        signing_string = build_signing_string(headers_to_sign, method, path, headers)

        # Decode signature
        signature_bytes = base64.b64decode(signature_b64)

        # Load public key
        public_key = serialization.load_pem_public_key(
            public_key_pem.encode('utf-8'),
            backend=default_backend()
        )

        # Verify signature using RSA-SHA256
        public_key.verify(
            signature_bytes,
            signing_string.encode('utf-8'),
            padding.PKCS1v15(),
            hashes.SHA256()
        )

        # If we get here, signature is valid
        print(f"✓ Signature verified for {key_id}")
        return True

    except Exception as e:
        print(f"Signature verification failed: {e}")
        return False


def sign_request(method: str, path: str, headers: Dict[str, str], body: bytes, private_key_pem: str, key_id: str) -> str:
    """
    Generate HTTP signature for outgoing request

    Args:
        method: HTTP method (e.g., "POST")
        path: Request path (e.g., "/inbox")
        headers: Dict of headers to include in request
        body: Request body as bytes
        private_key_pem: Your private key (PEM format)
        key_id: Your public key ID URL (e.g., "https://yourdomain.com/activitypub/actor#main-key")

    Returns:
        str: Signature header value to add to request
    """
    try:
        # Compute digest of body
        digest = compute_digest(body)
        headers['digest'] = digest

        # Headers to sign (per ActivityPub spec)
        headers_to_sign = '(request-target) host date digest content-type'

        # Build signing string
        signing_string = build_signing_string(headers_to_sign, method, path, headers)

        # Load private key
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode('utf-8'),
            password=None,
            backend=default_backend()
        )

        # Sign the string using RSA-SHA256
        signature_bytes = private_key.sign(
            signing_string.encode('utf-8'),
            padding.PKCS1v15(),
            hashes.SHA256()
        )

        # Encode signature as base64
        signature_b64 = base64.b64encode(signature_bytes).decode('utf-8')

        # Build Signature header
        signature_header = f'keyId="{key_id}",algorithm="hs2019",headers="{headers_to_sign}",signature="{signature_b64}"'

        return signature_header

    except Exception as e:
        print(f"Error signing request: {e}")
        raise


def verify_digest(digest_header: str, body: bytes) -> bool:
    """
    Verify that Digest header matches the request body

    Args:
        digest_header: Value of Digest header (e.g., "SHA-256=abc123...")
        body: Request body as bytes

    Returns:
        bool: True if digest matches, False otherwise
    """
    try:
        # Compute expected digest
        expected_digest = compute_digest(body)

        # Compare (case-sensitive)
        if digest_header == expected_digest:
            return True
        else:
            print(f"Digest mismatch: expected {expected_digest}, got {digest_header}")
            return False

    except Exception as e:
        print(f"Error verifying digest: {e}")
        return False


def verify_date(date_header: str, max_age_seconds: int = 300) -> bool:
    """
    Verify that Date header is within acceptable time window

    Prevents replay attacks by rejecting old requests

    Args:
        date_header: Value of Date header (RFC 2616 format)
        max_age_seconds: Maximum age in seconds (default 5 minutes)

    Returns:
        bool: True if date is valid, False otherwise
    """
    try:
        from email.utils import parsedate_to_datetime

        request_time = parsedate_to_datetime(date_header)
        current_time = datetime.now(timezone.utc)

        # Calculate age
        age = (current_time - request_time).total_seconds()

        # Check if within acceptable range (allow some clock skew in both directions)
        if abs(age) <= max_age_seconds:
            return True
        else:
            print(f"Date too old/new: {age} seconds (max {max_age_seconds})")
            return False

    except Exception as e:
        print(f"Error parsing date header: {e}")
        return False


def verify_request(signature_header: str, method: str, path: str, headers: Dict[str, str], body: bytes) -> bool:
    """
    Complete verification of incoming ActivityPub request

    Performs:
    1. Digest verification (body matches Digest header)
    2. Date verification (request is recent)
    3. Signature verification (cryptographic validation)

    Args:
        signature_header: Value of the Signature header
        method: HTTP method (e.g., "POST")
        path: Request path (e.g., "/activitypub/inbox")
        headers: Dict of request headers
        body: Request body as bytes

    Returns:
        bool: True if all checks pass, False otherwise
    """
    # Step 1: Verify digest
    digest_header = headers.get('digest') or headers.get('Digest')
    if digest_header:
        if not verify_digest(digest_header, body):
            print("✗ Digest verification failed")
            return False
    else:
        print("Warning: No Digest header present")

    # Step 2: Verify date
    date_header = headers.get('date') or headers.get('Date')
    if date_header:
        if not verify_date(date_header):
            print("✗ Date verification failed")
            return False
    else:
        print("Warning: No Date header present")

    # Step 3: Verify signature
    if not verify_signature(signature_header, method, path, headers, body):
        print("✗ Signature verification failed")
        return False

    print("✓ Request verification passed")
    return True
