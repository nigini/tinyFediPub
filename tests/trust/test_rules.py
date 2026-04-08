#!/usr/bin/env python3
"""
Unit tests for trust rules
"""
import unittest
import os
import json

from tests.test_config import TestConfigMixin


class TestIsBlocked(unittest.TestCase, TestConfigMixin):
    """Test is_blocked rule"""

    def setUp(self):
        self.setup_test_environment("trust_block_list")

        # Create blocked.json with one actor and one domain
        blocked = {
            "actors": ["https://spam.server/users/spammer"],
            "domains": ["evil.instance"]
        }
        blocked_path = os.path.join(self.config['directories']['data_root'], 'blocked.json')
        with open(blocked_path, 'w') as f:
            json.dump(blocked, f)

    def tearDown(self):
        self.teardown_test_environment()

    def test_blocked_actor(self):
        """Blocked actor returns True"""
        from trust.rules import is_blocked

        result = is_blocked("https://spam.server/users/spammer", "spam.server", self.config)
        self.assertTrue(result)

    def test_blocked_domain(self):
        """Actor from blocked domain returns True"""
        from trust.rules import is_blocked

        result = is_blocked("https://evil.instance/users/anyone", "evil.instance", self.config)
        self.assertTrue(result)

    def test_not_blocked(self):
        """Non-blocked actor returns False"""
        from trust.rules import is_blocked

        result = is_blocked("https://friendly.server/users/alice", "friendly.server", self.config)
        self.assertFalse(result)

    def test_no_blocked_file(self):
        """Missing blocked.json returns False (nothing is blocked)"""
        from trust.rules import is_blocked

        blocked_path = os.path.join(self.config['directories']['data_root'], 'blocked.json')
        os.remove(blocked_path)

        result = is_blocked("https://anyone.server/users/bob", "anyone.server", self.config)
        self.assertFalse(result)


class TestIsFollowing(unittest.TestCase, TestConfigMixin):
    """Test is_following rule"""

    def setUp(self):
        self.setup_test_environment("trust_following")

        # Create following.json with one actor
        following = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Collection",
            "id": "https://test.example.com/activitypub/following",
            "totalItems": 1,
            "items": ["https://mastodon.social/users/alice"]
        }
        following_path = os.path.join(self.config['directories']['data_root'], 'following.json')
        with open(following_path, 'w') as f:
            json.dump(following, f)

    def tearDown(self):
        self.teardown_test_environment()

    def test_followed_actor(self):
        """Followed actor returns True"""
        from trust.rules import is_following

        result = is_following("https://mastodon.social/users/alice", self.config)
        self.assertTrue(result)

    def test_not_followed_actor(self):
        """Non-followed actor returns False"""
        from trust.rules import is_following

        result = is_following("https://other.server/users/bob", self.config)
        self.assertFalse(result)

    def test_no_following_file(self):
        """Missing following.json returns False"""
        from trust.rules import is_following

        following_path = os.path.join(self.config['directories']['data_root'], 'following.json')
        os.remove(following_path)

        result = is_following("https://mastodon.social/users/alice", self.config)
        self.assertFalse(result)


class TestIsAddressedToUs(unittest.TestCase):
    """Test is_addressed_to_us rule"""

    def test_in_to_field(self):
        """Our actor in 'to' returns True"""
        from trust.rules import is_addressed_to_us

        activity = {
            "type": "Create",
            "actor": "https://mastodon.social/users/alice",
            "to": ["https://nigini.me/activitypub/actor"],
            "object": {"type": "Note", "content": "Hello!"}
        }
        result = is_addressed_to_us(activity, "https://nigini.me/activitypub/actor")
        self.assertTrue(result)

    def test_in_cc_field(self):
        """Our actor in 'cc' returns True"""
        from trust.rules import is_addressed_to_us

        activity = {
            "type": "Create",
            "actor": "https://mastodon.social/users/alice",
            "to": ["https://www.w3.org/ns/activitystreams#Public"],
            "cc": ["https://nigini.me/activitypub/actor"],
            "object": {"type": "Note", "content": "Hello!"}
        }
        result = is_addressed_to_us(activity, "https://nigini.me/activitypub/actor")
        self.assertTrue(result)

    def test_not_addressed(self):
        """Our actor not in to/cc returns False"""
        from trust.rules import is_addressed_to_us

        activity = {
            "type": "Create",
            "actor": "https://mastodon.social/users/alice",
            "to": ["https://www.w3.org/ns/activitystreams#Public"],
            "cc": ["https://mastodon.social/users/alice/followers"],
            "object": {"type": "Note", "content": "Hello!"}
        }
        result = is_addressed_to_us(activity, "https://nigini.me/activitypub/actor")
        self.assertFalse(result)

    def test_no_to_or_cc(self):
        """Activity with no to/cc returns False"""
        from trust.rules import is_addressed_to_us

        activity = {
            "type": "Create",
            "actor": "https://mastodon.social/users/alice",
            "object": {"type": "Note", "content": "Hello!"}
        }
        result = is_addressed_to_us(activity, "https://nigini.me/activitypub/actor")
        self.assertFalse(result)


class TestIsReplyToKnownPost(unittest.TestCase, TestConfigMixin):
    """Test is_reply_to_known_post rule"""

    def setUp(self):
        self.setup_test_environment("trust_reply")
        self.local_post_uuid = "550e8400-e29b-41d4-a716-446655440000"

        # Create a local post
        from post_utils import get_local_posts_dir
        local_dir = os.path.join(get_local_posts_dir(self.config), self.local_post_uuid)
        os.makedirs(local_dir, exist_ok=True)
        with open(os.path.join(local_dir, 'post.json'), 'w') as f:
            json.dump({"type": "Article", "id": f"https://test.example.com/activitypub/posts/{self.local_post_uuid}"}, f)

        # Create a remote post — path mirrors the URL structure
        remote_dir = os.path.join(self.config['directories']['posts_remote'], 'mastodon.social', 'users', 'alice', 'statuses', '12345')
        os.makedirs(remote_dir, exist_ok=True)
        with open(os.path.join(remote_dir, 'object.json'), 'w') as f:
            json.dump({"type": "Note", "id": "https://mastodon.social/users/alice/statuses/12345"}, f)

    def tearDown(self):
        self.teardown_test_environment()

    def test_reply_to_local_post(self):
        """inReplyTo pointing to a local post returns True"""
        from trust.rules import is_reply_to_known_post

        activity = {
            "type": "Create",
            "object": {
                "type": "Note",
                "inReplyTo": f"https://test.example.com/activitypub/posts/{self.local_post_uuid}"
            }
        }
        result = is_reply_to_known_post(activity, self.config)
        self.assertTrue(result)

    def test_reply_to_remote_post(self):
        """inReplyTo pointing to a stored remote post returns True"""
        from trust.rules import is_reply_to_known_post

        activity = {
            "type": "Create",
            "object": {
                "type": "Note",
                "inReplyTo": "https://mastodon.social/users/alice/statuses/12345"
            }
        }
        result = is_reply_to_known_post(activity, self.config)
        self.assertTrue(result)

    def test_reply_to_unknown_post(self):
        """inReplyTo pointing to unknown post returns False"""
        from trust.rules import is_reply_to_known_post

        activity = {
            "type": "Create",
            "object": {
                "type": "Note",
                "inReplyTo": "https://other.server/users/bob/statuses/99999"
            }
        }
        result = is_reply_to_known_post(activity, self.config)
        self.assertFalse(result)

    def test_no_in_reply_to(self):
        """Activity with no inReplyTo returns False"""
        from trust.rules import is_reply_to_known_post

        activity = {
            "type": "Create",
            "object": {
                "type": "Note",
                "content": "Just a standalone post"
            }
        }
        result = is_reply_to_known_post(activity, self.config)
        self.assertFalse(result)


class TestIsTrustedSigner(unittest.TestCase, TestConfigMixin):
    """Test is_trusted_signer rule"""

    def setUp(self):
        self.setup_test_environment("trust_signer")

        # Create following.json — we follow alice
        following = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Collection",
            "id": "https://test.example.com/activitypub/following",
            "totalItems": 1,
            "items": ["https://social.coop/users/alice"]
        }
        following_path = os.path.join(self.config['directories']['data_root'], 'following.json')
        with open(following_path, 'w') as f:
            json.dump(following, f)

    def tearDown(self):
        self.teardown_test_environment()

    def test_signed_by_followed_actor(self):
        """Signed by someone we follow → True"""
        from trust.rules import is_trusted_signer

        result = is_trusted_signer("https://social.coop/users/alice", self.config)
        self.assertTrue(result)

    def test_signed_by_stranger(self):
        """Signed by someone we don't follow → False"""
        from trust.rules import is_trusted_signer

        result = is_trusted_signer("https://unknown.server/users/dave", self.config)
        self.assertFalse(result)

    def test_no_signer(self):
        """No signature info → False"""
        from trust.rules import is_trusted_signer

        result = is_trusted_signer(None, self.config)
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
