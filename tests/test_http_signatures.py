#!/usr/bin/env python3
"""
Unit tests for HTTP Signatures module

Tests cryptographic signature verification and signing for ActivityPub federation.
This is security-critical code that must be thoroughly tested before deployment.
"""
import unittest
import base64
import hashlib
import json
import sys
import time
from datetime import datetime, timezone, timedelta
from email.utils import formatdate
from unittest.mock import patch, MagicMock
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend

sys.path.insert(0, '.')
from tests.test_config import TestConfigMixin
import http_signatures


class TestDigestComputation(unittest.TestCase):
    """Test digest computation and verification"""

    def test_compute_digest_simple(self):
        """Test computing SHA-256 digest of simple body"""
        body = b'{"type":"Follow","actor":"https://example.com/actor"}'

        digest = http_signatures.compute_digest(body)

        # Verify format
        self.assertTrue(digest.startswith('SHA-256='))

        # Verify it's valid base64
        digest_value = digest.split('=', 1)[1]
        try:
            base64.b64decode(digest_value)
        except Exception:
            self.fail("Digest should be valid base64")

    def test_compute_digest_empty_body(self):
        """Test computing digest of empty body"""
        body = b''

        digest = http_signatures.compute_digest(body)

        # SHA-256 of empty string has a known value
        expected_hash = hashlib.sha256(b'').digest()
        expected_b64 = base64.b64encode(expected_hash).decode('utf-8')
        expected_digest = f"SHA-256={expected_b64}"

        self.assertEqual(digest, expected_digest)

    def test_compute_digest_unicode(self):
        """Test computing digest with Unicode characters"""
        body = '{"content":"Hello 世界 🌍"}'.encode('utf-8')

        digest = http_signatures.compute_digest(body)

        # Should handle Unicode correctly
        self.assertTrue(digest.startswith('SHA-256='))

    def test_verify_digest_valid(self):
        """Test verifying correct digest"""
        body = b'{"type":"Follow"}'
        digest_header = http_signatures.compute_digest(body)

        result = http_signatures.verify_digest(digest_header, body)

        self.assertTrue(result)

    def test_verify_digest_invalid(self):
        """Test rejecting incorrect digest"""
        body = b'{"type":"Follow"}'
        wrong_body = b'{"type":"Like"}'
        digest_header = http_signatures.compute_digest(wrong_body)

        result = http_signatures.verify_digest(digest_header, body)

        self.assertFalse(result)

    def test_verify_digest_malformed(self):
        """Test handling malformed digest header"""
        body = b'{"type":"Follow"}'
        digest_header = "invalid-digest-format"

        result = http_signatures.verify_digest(digest_header, body)

        self.assertFalse(result)


class TestDateValidation(unittest.TestCase):
    """Test date header validation for replay attack prevention"""

    def test_verify_date_current(self):
        """Test accepting current timestamp"""
        # Generate current RFC 2616 date
        date_header = formatdate(timeval=None, localtime=False, usegmt=True)

        result = http_signatures.verify_date(date_header)

        self.assertTrue(result)

    def test_verify_date_within_window(self):
        """Test accepting date within 5-minute window"""
        # Generate date 2 minutes ago
        two_minutes_ago = datetime.now(timezone.utc) - timedelta(minutes=2)
        timestamp = two_minutes_ago.timestamp()
        date_header = formatdate(timeval=timestamp, localtime=False, usegmt=True)

        result = http_signatures.verify_date(date_header)

        self.assertTrue(result)

    def test_verify_date_expired(self):
        """Test rejecting old timestamp (>5 minutes)"""
        # Generate date 10 minutes ago
        ten_minutes_ago = datetime.now(timezone.utc) - timedelta(minutes=10)
        timestamp = ten_minutes_ago.timestamp()
        date_header = formatdate(timeval=timestamp, localtime=False, usegmt=True)

        result = http_signatures.verify_date(date_header, max_age_seconds=300)

        self.assertFalse(result)

    def test_verify_date_future(self):
        """Test rejecting future timestamp (clock skew attack)"""
        # Generate date 10 minutes in future
        ten_minutes_future = datetime.now(timezone.utc) + timedelta(minutes=10)
        timestamp = ten_minutes_future.timestamp()
        date_header = formatdate(timeval=timestamp, localtime=False, usegmt=True)

        result = http_signatures.verify_date(date_header, max_age_seconds=300)

        self.assertFalse(result)

    def test_verify_date_custom_window(self):
        """Test custom time window"""
        # Generate date 8 minutes ago
        eight_minutes_ago = datetime.now(timezone.utc) - timedelta(minutes=8)
        timestamp = eight_minutes_ago.timestamp()
        date_header = formatdate(timeval=timestamp, localtime=False, usegmt=True)

        # Should fail with 5-minute window
        result_strict = http_signatures.verify_date(date_header, max_age_seconds=300)
        self.assertFalse(result_strict)

        # Should pass with 10-minute window
        result_lenient = http_signatures.verify_date(date_header, max_age_seconds=600)
        self.assertTrue(result_lenient)

    def test_verify_date_malformed(self):
        """Test handling malformed date header"""
        date_header = "not-a-valid-date"

        result = http_signatures.verify_date(date_header)

        self.assertFalse(result)


class TestSignatureHeaderParsing(unittest.TestCase):
    """Test parsing HTTP Signature headers"""

    def test_parse_signature_header_complete(self):
        """Test parsing well-formed signature header"""
        header = 'keyId="https://example.com/actor#main-key",algorithm="hs2019",headers="(request-target) host date digest",signature="abcd1234"'

        result = http_signatures.parse_signature_header(header)

        self.assertEqual(result['keyId'], 'https://example.com/actor#main-key')
        self.assertEqual(result['algorithm'], 'hs2019')
        self.assertEqual(result['headers'], '(request-target) host date digest')
        self.assertEqual(result['signature'], 'abcd1234')

    def test_parse_signature_header_minimal(self):
        """Test parsing minimal signature header (keyId and signature only)"""
        header = 'keyId="https://example.com/actor#key",signature="xyz789"'

        result = http_signatures.parse_signature_header(header)

        self.assertEqual(result['keyId'], 'https://example.com/actor#key')
        self.assertEqual(result['signature'], 'xyz789')
        self.assertNotIn('algorithm', result)
        self.assertNotIn('headers', result)

    def test_parse_signature_header_with_spaces(self):
        """Test parsing signature header with various spacing"""
        header = 'keyId="https://example.com/actor", algorithm="hs2019", signature="abc"'

        result = http_signatures.parse_signature_header(header)

        self.assertEqual(result['keyId'], 'https://example.com/actor')
        self.assertEqual(result['algorithm'], 'hs2019')
        self.assertEqual(result['signature'], 'abc')


class TestSigningString(unittest.TestCase):
    """Test building signing strings from request components"""

    def test_build_signing_string_simple(self):
        """Test building signing string with basic headers"""
        headers_to_sign = "(request-target) host date"
        method = "POST"
        path = "/activitypub/inbox"
        headers = {
            "host": "example.com",
            "date": "Tue, 07 Jun 2025 20:51:35 GMT"
        }

        result = http_signatures.build_signing_string(headers_to_sign, method, path, headers)

        expected = "(request-target): post /activitypub/inbox\nhost: example.com\ndate: Tue, 07 Jun 2025 20:51:35 GMT"
        self.assertEqual(result, expected)

    def test_build_signing_string_with_digest(self):
        """Test building signing string including digest"""
        headers_to_sign = "(request-target) host date digest"
        method = "POST"
        path = "/inbox"
        headers = {
            "host": "mastodon.social",
            "date": "Tue, 07 Jun 2025 20:51:35 GMT",
            "digest": "SHA-256=abcd1234"
        }

        result = http_signatures.build_signing_string(headers_to_sign, method, path, headers)

        self.assertIn("(request-target): post /inbox", result)
        self.assertIn("host: mastodon.social", result)
        self.assertIn("date: Tue, 07 Jun 2025 20:51:35 GMT", result)
        self.assertIn("digest: SHA-256=abcd1234", result)

    def test_build_signing_string_case_insensitive(self):
        """Test that header lookup is case-insensitive"""
        headers_to_sign = "host date"
        method = "GET"
        path = "/actor"
        headers = {
            "Host": "example.com",  # Capitalized
            "Date": "Tue, 07 Jun 2025 20:51:35 GMT"
        }

        result = http_signatures.build_signing_string(headers_to_sign, method, path, headers)

        # Should normalize to lowercase in output
        self.assertIn("host: example.com", result)
        self.assertIn("date: Tue, 07 Jun 2025 20:51:35 GMT", result)

    def test_build_signing_string_missing_header(self):
        """Test handling missing header gracefully"""
        headers_to_sign = "host date digest"
        method = "POST"
        path = "/inbox"
        headers = {
            "host": "example.com",
            "date": "Tue, 07 Jun 2025 20:51:35 GMT"
            # digest is missing
        }

        result = http_signatures.build_signing_string(headers_to_sign, method, path, headers)

        # Should include empty value for missing header
        self.assertIn("digest: ", result)


class TestSignatureSigning(unittest.TestCase):
    """Test signing outgoing requests with private keys"""

    def setUp(self):
        """Generate test RSA key pair using mixin"""
        self.private_key_pem, self.public_key_pem = TestConfigMixin().generate_test_rsa_keys()

    def test_sign_request_basic(self):
        """Test signing a basic request"""
        method = "POST"
        path = "/inbox"
        body = b'{"type":"Follow","actor":"https://example.com/actor"}'
        headers = {
            "host": "mastodon.social",
            "date": formatdate(timeval=None, localtime=False, usegmt=True),
            "content-type": "application/activity+json"
        }
        key_id = "https://example.com/actor#main-key"

        signature_header = http_signatures.sign_request(
            method, path, headers, body, self.private_key_pem, key_id
        )

        # Verify header format
        self.assertIn('keyId=', signature_header)
        self.assertIn('algorithm=', signature_header)
        self.assertIn('headers=', signature_header)
        self.assertIn('signature=', signature_header)

        # Verify key ID is correct
        self.assertIn(f'keyId="{key_id}"', signature_header)

        # Verify algorithm is hs2019
        self.assertIn('algorithm="hs2019"', signature_header)

    def test_sign_request_adds_digest(self):
        """Test that signing adds Digest header"""
        method = "POST"
        path = "/inbox"
        body = b'{"type":"Follow"}'
        headers = {
            "host": "example.com",
            "date": formatdate(timeval=None, localtime=False, usegmt=True),
            "content-type": "application/activity+json"
        }
        key_id = "https://example.com/actor#main-key"

        # Digest should not be in headers initially
        self.assertNotIn('digest', headers)

        signature_header = http_signatures.sign_request(
            method, path, headers, body, self.private_key_pem, key_id
        )

        # Digest should now be added
        self.assertIn('digest', headers)
        self.assertTrue(headers['digest'].startswith('SHA-256='))

    def test_sign_request_signature_is_valid(self):
        """Test that generated signature can be verified"""
        method = "POST"
        path = "/inbox"
        body = b'{"type":"Follow"}'
        headers = {
            "host": "example.com",
            "date": formatdate(timeval=None, localtime=False, usegmt=True),
            "content-type": "application/activity+json"
        }
        key_id = "https://example.com/actor#main-key"

        # Sign the request
        signature_header = http_signatures.sign_request(
            method, path, headers, body, self.private_key_pem, key_id
        )

        # Parse the signature
        sig_components = http_signatures.parse_signature_header(signature_header)

        # Build signing string
        signing_string = http_signatures.build_signing_string(
            sig_components['headers'], method, path, headers
        )

        # Verify signature manually
        signature_bytes = base64.b64decode(sig_components['signature'])

        # Load public key for verification
        public_key = serialization.load_pem_public_key(
            self.public_key_pem.encode('utf-8'),
            backend=default_backend()
        )

        try:
            public_key.verify(
                signature_bytes,
                signing_string.encode('utf-8'),
                padding.PKCS1v15(),
                hashes.SHA256()
            )
            # If no exception, signature is valid
            signature_valid = True
        except Exception:
            signature_valid = False

        self.assertTrue(signature_valid)

    def test_sign_request_includes_all_required_headers(self):
        """Test that signature includes all required headers"""
        method = "POST"
        path = "/inbox"
        body = b'{"type":"Follow"}'
        headers = {
            "host": "example.com",
            "date": formatdate(timeval=None, localtime=False, usegmt=True),
            "content-type": "application/activity+json"
        }
        key_id = "https://example.com/actor#main-key"

        signature_header = http_signatures.sign_request(
            method, path, headers, body, self.private_key_pem, key_id
        )

        # Parse headers field
        sig_components = http_signatures.parse_signature_header(signature_header)
        headers_signed = sig_components['headers']

        # Should include all required headers per ActivityPub spec
        self.assertIn('(request-target)', headers_signed)
        self.assertIn('host', headers_signed)
        self.assertIn('date', headers_signed)
        self.assertIn('digest', headers_signed)
        self.assertIn('content-type', headers_signed)


class TestPublicKeyFetching(unittest.TestCase):
    """Test fetching actor public keys from remote servers"""

    def setUp(self):
        """Clear the cache before each test"""
        http_signatures._ACTOR_KEY_CACHE.clear()

    def test_fetch_actor_public_key_success(self):
        """Test successfully fetching public key from actor document"""
        key_id = "https://mastodon.social/users/alice#main-key"
        expected_pem = "-----BEGIN PUBLIC KEY-----\nMIIBIjANBg...\n-----END PUBLIC KEY-----"

        mock_actor = {
            "id": "https://mastodon.social/users/alice",
            "type": "Person",
            "publicKey": {
                "id": "https://mastodon.social/users/alice#main-key",
                "owner": "https://mastodon.social/users/alice",
                "publicKeyPem": expected_pem
            }
        }

        with patch('http_signatures.requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_actor
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            result = http_signatures.fetch_actor_public_key(key_id)

            self.assertEqual(result, expected_pem)

            # Verify correct URL was fetched (without fragment)
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            self.assertEqual(call_args[0][0], "https://mastodon.social/users/alice")

    def test_fetch_actor_public_key_strips_fragment(self):
        """Test that fragment is stripped before fetching"""
        key_id = "https://example.com/actor#main-key"

        with patch('http_signatures.requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "publicKey": {
                    "id": key_id,
                    "publicKeyPem": "test-key"
                }
            }
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            http_signatures.fetch_actor_public_key(key_id)

            # Should fetch without fragment
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            self.assertEqual(call_args[0][0], "https://example.com/actor")

    def test_fetch_actor_public_key_no_fragment(self):
        """Test fetching key when keyId has no fragment"""
        key_id = "https://example.com/actor"  # No fragment

        mock_actor = {
            "id": "https://example.com/actor",
            "type": "Person",
            "publicKey": {
                "id": "https://example.com/actor",  # Same as actor ID
                "publicKeyPem": "no-fragment-key"
            }
        }

        with patch('http_signatures.requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_actor
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            result = http_signatures.fetch_actor_public_key(key_id)

            self.assertEqual(result, "no-fragment-key")

            # Should fetch the same URL
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            self.assertEqual(call_args[0][0], "https://example.com/actor")

    def test_fetch_actor_public_key_array_format(self):
        """Test handling publicKey as array"""
        key_id = "https://example.com/actor#key-2"

        mock_actor = {
            "publicKey": [
                {
                    "id": "https://example.com/actor#key-1",
                    "publicKeyPem": "wrong-key"
                },
                {
                    "id": "https://example.com/actor#key-2",
                    "publicKeyPem": "correct-key"
                }
            ]
        }

        with patch('http_signatures.requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_actor
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            result = http_signatures.fetch_actor_public_key(key_id)

            # Should find the correct key
            self.assertEqual(result, "correct-key")

    def test_fetch_actor_public_key_not_found(self):
        """Test handling missing publicKey"""
        key_id = "https://example.com/actor#main-key"

        with patch('http_signatures.requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "type": "Person",
                "id": "https://example.com/actor"
                # No publicKey field
            }
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            result = http_signatures.fetch_actor_public_key(key_id)

            self.assertIsNone(result)

    def test_fetch_actor_public_key_wrong_key_id(self):
        """Test handling key ID mismatch"""
        key_id = "https://example.com/actor#key-2"

        mock_actor = {
            "publicKey": {
                "id": "https://example.com/actor#key-1",  # Wrong ID
                "publicKeyPem": "test-key"
            }
        }

        with patch('http_signatures.requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_actor
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            result = http_signatures.fetch_actor_public_key(key_id)

            # Should return None when ID doesn't match
            self.assertIsNone(result)

    def test_fetch_actor_public_key_caching(self):
        """Test that fetched keys are cached"""
        key_id = "https://example.com/actor#main-key"

        mock_actor = {
            "publicKey": {
                "id": key_id,
                "publicKeyPem": "cached-key"
            }
        }

        with patch('http_signatures.requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_actor
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            # First fetch
            result1 = http_signatures.fetch_actor_public_key(key_id)
            self.assertEqual(result1, "cached-key")
            self.assertEqual(mock_get.call_count, 1)

            # Second fetch should use cache
            result2 = http_signatures.fetch_actor_public_key(key_id)
            self.assertEqual(result2, "cached-key")
            self.assertEqual(mock_get.call_count, 1)  # Still 1, not 2

    def test_fetch_actor_public_key_network_error(self):
        """Test handling network errors gracefully"""
        key_id = "https://example.com/actor#main-key"

        with patch('http_signatures.requests.get') as mock_get:
            mock_get.side_effect = Exception("Network error")

            result = http_signatures.fetch_actor_public_key(key_id)

            self.assertIsNone(result)


class TestSignatureVerification(unittest.TestCase):
    """Test complete signature verification workflow"""

    def setUp(self):
        """Generate test RSA key pair and clear cache"""
        http_signatures._ACTOR_KEY_CACHE.clear()
        self.private_key_pem, self.public_key_pem = TestConfigMixin().generate_test_rsa_keys()

    def test_verify_signature_valid(self):
        """Test verifying a valid signature end-to-end"""
        key_id = "https://example.com/actor#main-key"
        method = "POST"
        path = "/inbox"
        body = b'{"type":"Follow"}'
        headers = {
            "host": "mastodon.social",
            "date": formatdate(timeval=None, localtime=False, usegmt=True),
            "content-type": "application/activity+json"
        }

        # Sign the request
        signature_header = http_signatures.sign_request(
            method, path, headers, body, self.private_key_pem, key_id
        )

        # Mock fetching the public key
        mock_actor = {
            "publicKey": {
                "id": key_id,
                "publicKeyPem": self.public_key_pem
            }
        }

        with patch('http_signatures.requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_actor
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            # Verify the signature
            result = http_signatures.verify_signature(
                signature_header, method, path, headers, body
            )

            self.assertTrue(result)

    def test_verify_signature_invalid_signature(self):
        """Test rejecting invalid signature"""
        key_id = "https://example.com/actor#main-key"
        method = "POST"
        path = "/inbox"
        body = b'{"type":"Follow"}'
        wrong_body = b'{"type":"Like"}'
        headers = {
            "host": "example.com",
            "date": formatdate(timeval=None, localtime=False, usegmt=True),
            "content-type": "application/activity+json"
        }

        # Sign with wrong body - this creates a signature for wrong_body
        # but we'll verify it against the correct body
        temp_headers = headers.copy()
        signature_header = http_signatures.sign_request(
            method, path, temp_headers, wrong_body, self.private_key_pem, key_id
        )

        # Now set up headers for correct body
        headers['digest'] = http_signatures.compute_digest(body)

        # Mock fetching the public key
        mock_actor = {
            "publicKey": {
                "id": key_id,
                "publicKeyPem": self.public_key_pem
            }
        }

        with patch('http_signatures.requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_actor
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            # Should fail - signature was for wrong_body, but we're verifying with body
            result = http_signatures.verify_signature(
                signature_header, method, path, headers, body
            )

            self.assertFalse(result)

    def test_verify_signature_missing_key_id(self):
        """Test handling missing keyId in signature"""
        signature_header = 'algorithm="hs2019",signature="abc123"'  # No keyId
        method = "POST"
        path = "/inbox"
        headers = {"host": "example.com"}
        body = b'{"type":"Follow"}'

        result = http_signatures.verify_signature(
            signature_header, method, path, headers, body
        )

        self.assertFalse(result)

    def test_verify_signature_key_fetch_fails(self):
        """Test handling failure to fetch public key"""
        key_id = "https://example.com/actor#main-key"
        signature_header = f'keyId="{key_id}",signature="abc123"'
        method = "POST"
        path = "/inbox"
        headers = {"host": "example.com"}
        body = b'{"type":"Follow"}'

        with patch('http_signatures.requests.get') as mock_get:
            mock_get.side_effect = Exception("Network error")

            result = http_signatures.verify_signature(
                signature_header, method, path, headers, body
            )

            self.assertFalse(result)


class TestCompleteRequestVerification(unittest.TestCase):
    """Test complete request verification (digest + date + signature)"""

    def setUp(self):
        """Generate test RSA key pair and clear cache"""
        http_signatures._ACTOR_KEY_CACHE.clear()
        self.private_key_pem, self.public_key_pem = TestConfigMixin().generate_test_rsa_keys()

    def test_verify_request_complete_success(self):
        """Test complete request verification with all checks passing"""
        key_id = "https://example.com/actor#main-key"
        method = "POST"
        path = "/inbox"
        body = b'{"type":"Follow"}'
        headers = {
            "host": "example.com",
            "date": formatdate(timeval=None, localtime=False, usegmt=True),
            "content-type": "application/activity+json"
        }

        signature_header = http_signatures.sign_request(
            method, path, headers, body, self.private_key_pem, key_id
        )

        mock_actor = {
            "publicKey": {"id": key_id, "publicKeyPem": self.public_key_pem}
        }

        with patch('http_signatures.requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_actor
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            result = http_signatures.verify_request(
                signature_header, method, path, headers, body
            )

            self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()
