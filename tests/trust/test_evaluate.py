#!/usr/bin/env python3
"""
Integration tests for evaluate_create
"""
import unittest
import os
import json

from tests.test_config import TestConfigMixin
from post_utils import get_local_posts_dir


class TestEvaluateCreate(unittest.TestCase, TestConfigMixin):
    """Test evaluate_create composes rules correctly"""

    def setUp(self):
        self.setup_test_environment("trust_evaluate")

        # We follow alice
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

        # Block spammer and evil domain
        blocked = {
            "actors": ["https://mastodon.social/users/spammer"],
            "domains": ["evil.instance"]
        }
        blocked_path = os.path.join(self.config['directories']['data_root'], 'blocked.json')
        with open(blocked_path, 'w') as f:
            json.dump(blocked, f)

        # Create a local post for reply tests
        self.local_post_uuid = "550e8400-e29b-41d4-a716-446655440000"
        local_dir = os.path.join(get_local_posts_dir(self.config), self.local_post_uuid)
        os.makedirs(local_dir, exist_ok=True)
        with open(os.path.join(local_dir, 'post.json'), 'w') as f:
            json.dump({"type": "Article", "id": f"https://test.example.com/activitypub/posts/{self.local_post_uuid}"}, f)

        self.our_actor = "https://test.example.com/activitypub/actor"

    def tearDown(self):
        self.teardown_test_environment()

    def test_blocked_actor_rejected(self):
        """Blocked actor is rejected even if we follow them"""
        from trust import evaluate_create

        activity = {
            "type": "Create",
            "actor": "https://mastodon.social/users/spammer",
            "object": {"type": "Note", "content": "Buy my stuff!"}
        }
        context = {"signed_by": None, "our_actor": self.our_actor}
        decision = evaluate_create(activity, context, self.config)
        self.assertFalse(decision.accepted)
        self.assertEqual(decision.rule, "blocked")

    def test_blocked_domain_rejected(self):
        """Actor from blocked domain is rejected"""
        from trust import evaluate_create

        activity = {
            "type": "Create",
            "actor": "https://evil.instance/users/anyone",
            "object": {"type": "Note", "content": "Evil content"}
        }
        context = {"signed_by": None, "our_actor": self.our_actor}
        decision = evaluate_create(activity, context, self.config)
        self.assertFalse(decision.accepted)
        self.assertEqual(decision.rule, "blocked")

    def test_followed_actor_accepted(self):
        """Activity from followed actor is accepted"""
        from trust import evaluate_create

        activity = {
            "type": "Create",
            "actor": "https://mastodon.social/users/alice",
            "object": {"type": "Note", "content": "Hello!"}
        }
        context = {"signed_by": None, "our_actor": self.our_actor}
        decision = evaluate_create(activity, context, self.config)
        self.assertTrue(decision.accepted)
        self.assertEqual(decision.rule, "following")

    def test_addressed_to_us_accepted(self):
        """Activity addressed to us from stranger is accepted"""
        from trust import evaluate_create

        activity = {
            "type": "Create",
            "actor": "https://other.server/users/bob",
            "to": [self.our_actor],
            "object": {"type": "Note", "content": "Hey!"}
        }
        context = {"signed_by": None, "our_actor": self.our_actor}
        decision = evaluate_create(activity, context, self.config)
        self.assertTrue(decision.accepted)
        self.assertEqual(decision.rule, "addressed_to_us")

    def test_reply_to_local_post_accepted(self):
        """Reply to our post from stranger is accepted"""
        from trust import evaluate_create

        activity = {
            "type": "Create",
            "actor": "https://other.server/users/bob",
            "object": {
                "type": "Note",
                "inReplyTo": f"https://test.example.com/activitypub/posts/{self.local_post_uuid}"
            }
        }
        context = {"signed_by": None, "our_actor": self.our_actor}
        decision = evaluate_create(activity, context, self.config)
        self.assertTrue(decision.accepted)
        self.assertEqual(decision.rule, "reply_to_known_post")

    def test_reply_to_remote_post_accepted(self):
        """Reply to a stored remote post from stranger is accepted"""
        from trust import evaluate_create

        # Create a remote post
        remote_dir = os.path.join(self.config['directories']['posts_remote'], 'pixelfed.social', 'users', 'carol', 'p', '99')
        os.makedirs(remote_dir, exist_ok=True)
        with open(os.path.join(remote_dir, 'object.json'), 'w') as f:
            json.dump({"type": "Note", "id": "https://pixelfed.social/users/carol/p/99"}, f)

        activity = {
            "type": "Create",
            "actor": "https://other.server/users/bob",
            "object": {
                "type": "Note",
                "inReplyTo": "https://pixelfed.social/users/carol/p/99"
            }
        }
        context = {"signed_by": None, "our_actor": self.our_actor}
        decision = evaluate_create(activity, context, self.config)
        self.assertTrue(decision.accepted)
        self.assertEqual(decision.rule, "reply_to_known_post")

    def test_trusted_signer_accepted(self):
        """Activity from stranger but signed by followed actor is accepted"""
        from trust import evaluate_create

        activity = {
            "type": "Create",
            "actor": "https://other.server/users/bob",
            "object": {"type": "Note", "content": "Forwarded post"}
        }
        context = {"signed_by": "https://mastodon.social/users/alice#main-key", "our_actor": self.our_actor}
        decision = evaluate_create(activity, context, self.config)
        self.assertTrue(decision.accepted)
        self.assertEqual(decision.rule, "trusted_signer")

    def test_default_reject(self):
        """Unknown actor with no matching rule is rejected"""
        from trust import evaluate_create

        activity = {
            "type": "Create",
            "actor": "https://random.server/users/nobody",
            "object": {"type": "Note", "content": "Who am I?"}
        }
        context = {"signed_by": None, "our_actor": self.our_actor}
        decision = evaluate_create(activity, context, self.config)
        self.assertFalse(decision.accepted)
        self.assertEqual(decision.rule, "default_reject")


if __name__ == '__main__':
    unittest.main()
