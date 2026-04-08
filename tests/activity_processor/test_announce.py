#!/usr/bin/env python3
"""
Unit tests for Announce activity processing
"""
import unittest
import os
import json

from tests.test_config import TestConfigMixin
from post_utils import get_local_posts_dir


class TestAnnounceRegistry(unittest.TestCase, TestConfigMixin):
    """Test that Announce processors are auto-discovered in the registry"""

    def setUp(self):
        self.setup_test_environment("announce_registry")

    def tearDown(self):
        self.teardown_test_environment()

    def test_announce_in_registry(self):
        """Test that PROCESSORS contains Announce and Undo.Announce"""
        from activity_processor import PROCESSORS
        from activity_processor.announce import AnnounceProcessor, UndoAnnounceProcessor

        self.assertIn('Announce', PROCESSORS)
        self.assertIn('Undo.Announce', PROCESSORS)
        self.assertIsInstance(PROCESSORS['Announce'], AnnounceProcessor)
        self.assertIsInstance(PROCESSORS['Undo.Announce'], UndoAnnounceProcessor)


class TestAnnounceProcessor(unittest.TestCase, TestConfigMixin):
    """Test Announce activity processing functionality"""

    def setUp(self):
        self.setup_test_environment("announce_processor")
        self.post_uuid = "550e8400-e29b-41d4-a716-446655440000"

        # Create a test post with empty reaction collections
        post_dir = os.path.join(get_local_posts_dir(self.config), self.post_uuid)
        os.makedirs(post_dir, exist_ok=True)
        post_base = f"https://test.example.com/activitypub/posts/{self.post_uuid}"
        test_post = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Article",
            "id": post_base,
            "name": "Test Post",
            "content": "Hello world",
            "likes": {"type": "OrderedCollection", "id": f"{post_base}/likes", "totalItems": 0},
            "shares": {"type": "OrderedCollection", "id": f"{post_base}/shares", "totalItems": 0},
            "replies": {"type": "OrderedCollection", "id": f"{post_base}/replies", "totalItems": 0}
        }
        with open(os.path.join(post_dir, 'post.json'), 'w') as f:
            json.dump(test_post, f)

        # Create empty shares.json
        empty_shares = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "OrderedCollection",
            "id": f"{post_base}/shares",
            "totalItems": 0,
            "orderedItems": []
        }
        with open(os.path.join(post_dir, 'shares.json'), 'w') as f:
            json.dump(empty_shares, f)

    def tearDown(self):
        self.teardown_test_environment()

    def test_announce_adds_actor_to_shares(self):
        """Test that an Announce activity adds the actor to shares.json"""
        from activity_processor.announce import AnnounceProcessor

        processor = AnnounceProcessor()

        announce_activity = {
            "type": "Announce",
            "actor": "https://mastodon.social/users/alice",
            "object": f"https://test.example.com/activitypub/posts/{self.post_uuid}",
            "id": "https://mastodon.social/activities/announce-123"
        }

        result = processor.process_inbox(announce_activity, "announce-test.json", self.config)
        self.assertTrue(result)

        # Verify shares.json was updated
        shares_path = os.path.join(
            get_local_posts_dir(self.config), self.post_uuid, 'shares.json'
        )
        self.assertTrue(os.path.exists(shares_path))

        with open(shares_path) as f:
            shares_data = json.load(f)

        self.assertEqual(shares_data['type'], 'OrderedCollection')
        self.assertEqual(shares_data['totalItems'], 1)
        self.assertIn('https://mastodon.social/users/alice', shares_data['orderedItems'])

        # Second announce from a different actor
        announce_bob = {
            "type": "Announce",
            "actor": "https://pixelfed.social/users/bob",
            "object": f"https://test.example.com/activitypub/posts/{self.post_uuid}",
            "id": "https://pixelfed.social/activities/announce-456"
        }

        result2 = processor.process_inbox(announce_bob, "announce-bob.json", self.config)
        self.assertTrue(result2)

        with open(shares_path) as f:
            shares_data = json.load(f)

        self.assertEqual(shares_data['totalItems'], 2)
        self.assertIn('https://mastodon.social/users/alice', shares_data['orderedItems'])
        self.assertIn('https://pixelfed.social/users/bob', shares_data['orderedItems'])


    def test_announce_missing_actor(self):
        """Test that an Announce with no actor returns False"""
        from activity_processor.announce import AnnounceProcessor

        processor = AnnounceProcessor()
        activity = {
            "type": "Announce",
            "object": f"https://test.example.com/activitypub/posts/{self.post_uuid}",
            "id": "https://mastodon.social/activities/announce-123"
        }
        result = processor.process_inbox(activity, "announce-no-actor.json", self.config)
        self.assertFalse(result)

    def test_announce_missing_object(self):
        """Test that an Announce with no object returns False"""
        from activity_processor.announce import AnnounceProcessor

        processor = AnnounceProcessor()
        activity = {
            "type": "Announce",
            "actor": "https://mastodon.social/users/alice",
            "id": "https://mastodon.social/activities/announce-123"
        }
        result = processor.process_inbox(activity, "announce-no-object.json", self.config)
        self.assertFalse(result)

    def test_announce_non_local_object(self):
        """Test that an Announce targeting a non-local URL returns False"""
        from activity_processor.announce import AnnounceProcessor

        processor = AnnounceProcessor()
        activity = {
            "type": "Announce",
            "actor": "https://mastodon.social/users/alice",
            "object": "https://other-server.com/posts/123",
            "id": "https://mastodon.social/activities/announce-123"
        }
        result = processor.process_inbox(activity, "announce-non-local.json", self.config)
        self.assertFalse(result)

    def test_announce_nonexistent_post(self):
        """Test that an Announce targeting an unknown post returns False"""
        from activity_processor.announce import AnnounceProcessor

        processor = AnnounceProcessor()
        activity = {
            "type": "Announce",
            "actor": "https://mastodon.social/users/alice",
            "object": "https://test.example.com/activitypub/posts/nonexistent-uuid",
            "id": "https://mastodon.social/activities/announce-123"
        }
        result = processor.process_inbox(activity, "announce-bad-post.json", self.config)
        self.assertFalse(result)


    def test_announce_updates_post_shares_summary(self):
        """Test that processing an Announce updates post.json shares summary"""
        from activity_processor.announce import AnnounceProcessor

        processor = AnnounceProcessor()

        announce_activity = {
            "type": "Announce",
            "actor": "https://mastodon.social/users/alice",
            "object": f"https://test.example.com/activitypub/posts/{self.post_uuid}",
            "id": "https://mastodon.social/activities/announce-123"
        }

        processor.process_inbox(announce_activity, "announce-test.json", self.config)

        post_dir = os.path.join(get_local_posts_dir(self.config), self.post_uuid)
        with open(os.path.join(post_dir, 'post.json')) as f:
            post_data = json.load(f)

        self.assertEqual(post_data['shares']['type'], 'OrderedCollection')
        self.assertEqual(post_data['shares']['totalItems'], 1)
        # likes and replies should be unchanged
        self.assertEqual(post_data['likes']['totalItems'], 0)
        self.assertEqual(post_data['replies']['totalItems'], 0)

    def test_duplicate_announce_ignored(self):
        """Test that the same actor announcing the same post twice doesn't duplicate"""
        from activity_processor.announce import AnnounceProcessor

        processor = AnnounceProcessor()

        announce_activity = {
            "type": "Announce",
            "actor": "https://mastodon.social/users/alice",
            "object": f"https://test.example.com/activitypub/posts/{self.post_uuid}",
            "id": "https://mastodon.social/activities/announce-123"
        }

        result1 = processor.process_inbox(announce_activity, "announce-1.json", self.config)
        result2 = processor.process_inbox(announce_activity, "announce-2.json", self.config)

        self.assertTrue(result1)
        self.assertTrue(result2)

        shares_path = os.path.join(
            get_local_posts_dir(self.config), self.post_uuid, 'shares.json'
        )
        with open(shares_path) as f:
            shares_data = json.load(f)

        self.assertEqual(shares_data['totalItems'], 1)
        self.assertEqual(len(shares_data['orderedItems']), 1)


class TestUndoAnnounceProcessor(unittest.TestCase, TestConfigMixin):
    """Test Undo Announce activity processing"""

    def setUp(self):
        self.setup_test_environment("undo_announce")
        self.post_uuid = "550e8400-e29b-41d4-a716-446655440000"

        # Create a test post with two existing shares
        post_dir = os.path.join(get_local_posts_dir(self.config), self.post_uuid)
        os.makedirs(post_dir, exist_ok=True)
        post_base = f"https://test.example.com/activitypub/posts/{self.post_uuid}"
        test_post = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Article",
            "id": post_base,
            "name": "Test Post",
            "content": "Hello world",
            "likes": {"type": "OrderedCollection", "id": f"{post_base}/likes", "totalItems": 0},
            "shares": {"type": "OrderedCollection", "id": f"{post_base}/shares", "totalItems": 2},
            "replies": {"type": "OrderedCollection", "id": f"{post_base}/replies", "totalItems": 0}
        }
        with open(os.path.join(post_dir, 'post.json'), 'w') as f:
            json.dump(test_post, f)

        # Pre-populate shares.json with two shares
        shares_data = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "OrderedCollection",
            "id": f"{post_base}/shares",
            "totalItems": 2,
            "orderedItems": [
                "https://mastodon.social/users/alice",
                "https://pixelfed.social/users/bob"
            ]
        }
        with open(os.path.join(post_dir, 'shares.json'), 'w') as f:
            json.dump(shares_data, f)

    def tearDown(self):
        self.teardown_test_environment()

    def _make_undo_announce(self, actor_url):
        return {
            "type": "Undo",
            "actor": actor_url,
            "object": {
                "type": "Announce",
                "actor": actor_url,
                "object": f"https://test.example.com/activitypub/posts/{self.post_uuid}"
            },
            "id": f"{actor_url}/activities/undo-announce-123"
        }

    def test_undo_announce_removes_actor_and_updates_summary(self):
        """Test that Undo Announce removes one actor, then the other"""
        from activity_processor.announce import UndoAnnounceProcessor

        processor = UndoAnnounceProcessor()
        post_dir = os.path.join(get_local_posts_dir(self.config), self.post_uuid)

        # Remove alice
        result = processor.process_inbox(
            self._make_undo_announce("https://mastodon.social/users/alice"),
            "undo-announce-alice.json", self.config
        )
        self.assertTrue(result)

        with open(os.path.join(post_dir, 'shares.json')) as f:
            shares_data = json.load(f)
        self.assertEqual(shares_data['totalItems'], 1)
        self.assertNotIn('https://mastodon.social/users/alice', shares_data['orderedItems'])
        self.assertIn('https://pixelfed.social/users/bob', shares_data['orderedItems'])

        with open(os.path.join(post_dir, 'post.json')) as f:
            post_data = json.load(f)
        self.assertEqual(post_data['shares']['totalItems'], 1)

        # Remove bob
        result = processor.process_inbox(
            self._make_undo_announce("https://pixelfed.social/users/bob"),
            "undo-announce-bob.json", self.config
        )
        self.assertTrue(result)

        with open(os.path.join(post_dir, 'shares.json')) as f:
            shares_data = json.load(f)
        self.assertEqual(shares_data['totalItems'], 0)
        self.assertEqual(shares_data['orderedItems'], [])

        with open(os.path.join(post_dir, 'post.json')) as f:
            post_data = json.load(f)
        self.assertEqual(post_data['shares']['totalItems'], 0)


    def test_undo_announce_missing_actor(self):
        """Test that Undo Announce with no actor returns False"""
        from activity_processor.announce import UndoAnnounceProcessor

        processor = UndoAnnounceProcessor()
        activity = {
            "type": "Undo",
            "object": {
                "type": "Announce",
                "object": f"https://test.example.com/activitypub/posts/{self.post_uuid}"
            }
        }
        result = processor.process_inbox(activity, "undo-no-actor.json", self.config)
        self.assertFalse(result)

    def test_undo_announce_nonexistent_share(self):
        """Test Undo Announce when actor hasn't shared the post"""
        from activity_processor.announce import UndoAnnounceProcessor

        processor = UndoAnnounceProcessor()
        result = processor.process_inbox(
            self._make_undo_announce("https://other.server/users/charlie"),
            "undo-announce-nonexistent.json", self.config
        )
        self.assertTrue(result)

        # Alice and bob should still be there
        post_dir = os.path.join(get_local_posts_dir(self.config), self.post_uuid)
        with open(os.path.join(post_dir, 'shares.json')) as f:
            shares_data = json.load(f)
        self.assertEqual(shares_data['totalItems'], 2)

    def test_undo_announce_no_shares_file(self):
        """Test Undo Announce when no shares.json exists"""
        from activity_processor.announce import UndoAnnounceProcessor

        # Remove the pre-populated shares.json
        post_dir = os.path.join(get_local_posts_dir(self.config), self.post_uuid)
        os.remove(os.path.join(post_dir, 'shares.json'))

        processor = UndoAnnounceProcessor()
        result = processor.process_inbox(
            self._make_undo_announce("https://mastodon.social/users/alice"),
            "undo-announce-no-file.json", self.config
        )
        self.assertTrue(result)


    def test_undo_announce_missing_object(self):
        """Test that Undo Announce with no object returns False"""
        from activity_processor.announce import UndoAnnounceProcessor

        processor = UndoAnnounceProcessor()
        activity = {
            "type": "Undo",
            "actor": "https://mastodon.social/users/alice",
            "object": {
                "type": "Announce"
            }
        }
        result = processor.process_inbox(activity, "undo-no-object.json", self.config)
        self.assertFalse(result)

    def test_undo_announce_non_local_object(self):
        """Test that Undo Announce targeting a non-local URL returns False"""
        from activity_processor.announce import UndoAnnounceProcessor

        processor = UndoAnnounceProcessor()
        activity = {
            "type": "Undo",
            "actor": "https://mastodon.social/users/alice",
            "object": {
                "type": "Announce",
                "actor": "https://mastodon.social/users/alice",
                "object": "https://other-server.com/posts/123"
            },
            "id": "https://mastodon.social/activities/undo-123"
        }
        result = processor.process_inbox(activity, "undo-non-local.json", self.config)
        self.assertFalse(result)

    def test_undo_delegation_to_announce(self):
        """Test that UndoActivityProcessor delegates to UndoAnnounceProcessor"""
        from activity_processor import UndoActivityProcessor

        processor = UndoActivityProcessor()
        result = processor.process_inbox(
            self._make_undo_announce("https://mastodon.social/users/alice"),
            "undo-announce-delegation.json", self.config
        )
        self.assertTrue(result)

        post_dir = os.path.join(get_local_posts_dir(self.config), self.post_uuid)
        with open(os.path.join(post_dir, 'shares.json')) as f:
            shares_data = json.load(f)
        self.assertEqual(shares_data['totalItems'], 1)
        self.assertNotIn('https://mastodon.social/users/alice', shares_data['orderedItems'])


class TestSharesEndpoint(unittest.TestCase, TestConfigMixin):
    """Integration test: shares collection endpoint on posts"""

    def setUp(self):
        self.setup_test_environment("shares_endpoint",
                                    server={"domain": "test.example.com"},
                                    activitypub={"username": "test", "actor_name": "Test Actor"})

        self.post_uuid = "550e8400-e29b-41d4-a716-446655440000"

        # Create a test post with one share
        post_dir = os.path.join(get_local_posts_dir(self.config), self.post_uuid)
        os.makedirs(post_dir, exist_ok=True)
        post_base = f"https://test.example.com/activitypub/posts/{self.post_uuid}"
        test_post = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Article",
            "id": post_base,
            "name": "Test Post",
            "content": "Hello world",
            "likes": {"type": "OrderedCollection", "id": f"{post_base}/likes", "totalItems": 0},
            "shares": {"type": "OrderedCollection", "id": f"{post_base}/shares", "totalItems": 1},
            "replies": {"type": "OrderedCollection", "id": f"{post_base}/replies", "totalItems": 0}
        }
        with open(os.path.join(post_dir, 'post.json'), 'w') as f:
            json.dump(test_post, f)

        shares_data = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "OrderedCollection",
            "id": f"{post_base}/shares",
            "totalItems": 1,
            "orderedItems": ["https://mastodon.social/users/alice"]
        }
        with open(os.path.join(post_dir, 'shares.json'), 'w') as f:
            json.dump(shares_data, f)

        from app import app
        self.app = app
        self.client = app.test_client()
        app.config['TESTING'] = True

    def tearDown(self):
        self.teardown_test_environment()

    def test_shares_endpoint_returns_collection(self):
        """Test that /posts/{uuid}/shares returns the shares collection"""
        response = self.client.get(
            f'/activitypub/posts/{self.post_uuid}/shares',
            headers={'Accept': 'application/activity+json'}
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['type'], 'OrderedCollection')
        self.assertEqual(data['totalItems'], 1)
        self.assertIn('https://mastodon.social/users/alice', data['orderedItems'])

    def test_shares_endpoint_no_shares_file(self):
        """Test that /posts/{uuid}/shares returns 404 when post exists but no shares.json"""
        # Remove shares.json but keep the post
        post_dir = os.path.join(get_local_posts_dir(self.config), self.post_uuid)
        os.remove(os.path.join(post_dir, 'shares.json'))

        response = self.client.get(
            f'/activitypub/posts/{self.post_uuid}/shares',
            headers={'Accept': 'application/activity+json'}
        )
        self.assertEqual(response.status_code, 404)

    def test_shares_endpoint_nonexistent_post(self):
        """Test that /posts/{uuid}/shares returns 404 for unknown post"""
        response = self.client.get(
            '/activitypub/posts/nonexistent-uuid/shares',
            headers={'Accept': 'application/activity+json'}
        )
        self.assertEqual(response.status_code, 404)


if __name__ == '__main__':
    unittest.main()
