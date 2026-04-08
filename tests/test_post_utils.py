#!/usr/bin/env python3
"""
Unit tests for post_utils utility functions
"""
import unittest
import os
import json
import sys

sys.path.insert(0, '.')
from tests.test_config import TestConfigMixin
from post_utils import get_local_posts_dir


class TestGenerateActivityId(unittest.TestCase):
    """Test activity ID generation"""

    def test_generate_activity_id(self):
        """Test activity ID generation with timestamp"""
        from post_utils import generate_activity_id

        create_id = generate_activity_id('create')
        accept_id = generate_activity_id('Accept')
        follow_id = generate_activity_id('FOLLOW')

        self.assertTrue(create_id.startswith('create-'))
        self.assertTrue(accept_id.startswith('accept-'))
        self.assertTrue(follow_id.startswith('follow-'))

        import re
        timestamp_pattern = r'-\d{8}-\d{6}-\d{6}$'
        self.assertRegex(create_id, timestamp_pattern)
        self.assertRegex(accept_id, timestamp_pattern)
        self.assertRegex(follow_id, timestamp_pattern)


class TestParseActorUrl(unittest.TestCase):
    """Test actor URL parsing"""

    def test_parse_actor_url(self):
        """Test actor URL parsing for domain and username extraction"""
        from post_utils import parse_actor_url

        test_cases = [
            ('https://mastodon.social/users/alice', ('mastodon.social', 'alice')),
            ('https://pixelfed.social/@bob', ('pixelfed.social', 'bob')),
            ('https://lemmy.world/u/charlie', ('lemmy.world', 'charlie')),
            ('https://example.com/users/dave/profile', ('example.com', 'dave')),
            ('https://micro.blog/users/eve', ('micro.blog', 'eve')),
            ('not-a-url', ('unknown', None)),
            ('', ('unknown', None)),
            (None, ('unknown', None)),
        ]

        for actor_url, expected in test_cases:
            with self.subTest(actor_url=actor_url):
                domain, username = parse_actor_url(actor_url)
                self.assertEqual((domain, username), expected)

    def test_parse_actor_url_edge_cases(self):
        """Test edge cases for actor URL parsing"""
        from post_utils import parse_actor_url

        domain, username = parse_actor_url('https://example.com/some/other/path')
        self.assertEqual(domain, 'example.com')
        self.assertIsNone(username)

        domain, username = parse_actor_url('https://example.com/')
        self.assertEqual(domain, 'example.com')
        self.assertIsNone(username)

        domain, username = parse_actor_url('https://')
        self.assertEqual(domain, 'unknown')
        self.assertIsNone(username)


class TestResolvePostUuid(unittest.TestCase, TestConfigMixin):
    """Test resolve_post_uuid_from_url utility"""

    def setUp(self):
        self.setup_test_environment("resolve_post_uuid")
        self.post_uuid = "550e8400-e29b-41d4-a716-446655440000"
        post_dir = os.path.join(get_local_posts_dir(self.config), self.post_uuid)
        os.makedirs(post_dir, exist_ok=True)
        test_post = {"type": "Article", "id": f"https://test.example.com/activitypub/posts/{self.post_uuid}"}
        with open(os.path.join(post_dir, 'post.json'), 'w') as f:
            json.dump(test_post, f)

    def tearDown(self):
        self.teardown_test_environment()

    def test_resolves_local_post(self):
        """Test that a valid local post URL returns the UUID"""
        from post_utils import resolve_post_uuid_from_url
        result = resolve_post_uuid_from_url(
            f"https://test.example.com/activitypub/posts/{self.post_uuid}", self.config
        )
        self.assertEqual(result, self.post_uuid)

    def test_returns_none_for_non_local_url(self):
        """Test that a non-local URL returns None"""
        from post_utils import resolve_post_uuid_from_url
        result = resolve_post_uuid_from_url(
            "https://other-server.com/posts/123", self.config
        )
        self.assertIsNone(result)

    def test_returns_none_for_nonexistent_post(self):
        """Test that a local URL with unknown UUID returns None"""
        from post_utils import resolve_post_uuid_from_url
        result = resolve_post_uuid_from_url(
            "https://test.example.com/activitypub/posts/nonexistent-uuid", self.config
        )
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
