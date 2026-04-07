#!/usr/bin/env python3
"""
Unit tests for Follow activity processing
"""
import unittest
import os
import json
from unittest.mock import patch

from tests.test_config import TestConfigMixin


class TestFollowProcessor(unittest.TestCase, TestConfigMixin):
    """Test Follow activity processing functionality"""

    def setUp(self):
        self.setup_test_environment("follow_processor")

    def tearDown(self):
        self.teardown_test_environment()

    def test_follow_activity_processor(self):
        """Test Follow activity processing"""
        from activity_processor import FollowProcessor

        processor = FollowProcessor()

        follow_activity = {
            "type": "Follow",
            "actor": "https://mastodon.social/users/alice",
            "object": "https://test.example.com/activitypub/actor",
            "id": "https://mastodon.social/activities/123"
        }

        result = processor.process_inbox(follow_activity, "test-follow.json", self.config)
        self.assertTrue(result)

        # Verify Accept activity was created
        activities_dir = self.config['directories']['outbox']
        activity_files = [f for f in os.listdir(activities_dir) if f.startswith('accept-')]
        self.assertEqual(len(activity_files), 1, "Should have created exactly one Accept activity")

        # Load and verify Accept activity structure
        with open(os.path.join(activities_dir, activity_files[0])) as f:
            accept_activity = json.load(f)

        self.assertEqual(accept_activity['type'], 'Accept')
        self.assertEqual(accept_activity['actor'], 'https://test.example.com/activitypub/actor')
        self.assertEqual(accept_activity['object'], follow_activity)
        self.assertTrue(accept_activity['id'].startswith('https://test.example.com/activitypub/activities/accept-'))

        # Verify follower was added
        followers_dir = self.config['directories']['followers']
        followers_file = os.path.join(followers_dir, 'followers.json')
        self.assertTrue(os.path.exists(followers_file), "followers.json should be created")

        with open(followers_file) as f:
            followers_data = json.load(f)

        self.assertEqual(followers_data['type'], 'Collection')
        self.assertEqual(followers_data['totalItems'], 1)
        self.assertIn('https://mastodon.social/users/alice', followers_data['items'])

    def test_duplicate_follow_processing(self):
        """Test that duplicate follows don't create duplicate followers"""
        from activity_processor import FollowProcessor

        processor = FollowProcessor()

        follow_activity = {
            "type": "Follow",
            "actor": "https://mastodon.social/users/alice",
            "object": "https://test.example.com/activitypub/actor",
            "id": "https://mastodon.social/activities/123"
        }

        result1 = processor.process_inbox(follow_activity, "test-follow-1.json", self.config)
        result2 = processor.process_inbox(follow_activity, "test-follow-2.json", self.config)

        self.assertTrue(result1)
        self.assertTrue(result2)

        # Verify only one follower exists
        followers_dir = self.config['directories']['followers']
        followers_file = os.path.join(followers_dir, 'followers.json')

        with open(followers_file) as f:
            followers_data = json.load(f)

        self.assertEqual(followers_data['totalItems'], 1)
        self.assertEqual(len(followers_data['items']), 1)
        self.assertIn('https://mastodon.social/users/alice', followers_data['items'])

        # Verify two Accept activities were created (one for each follow)
        activities_dir = self.config['directories']['outbox']
        activity_files = [f for f in os.listdir(activities_dir) if f.startswith('accept-')]
        self.assertEqual(len(activity_files), 2, "Should have created two Accept activities")

    def test_follow_processing_with_auto_accept_disabled(self):
        """Test Follow processing when auto_accept_follow_requests is false"""
        from activity_processor import FollowProcessor

        config = json.loads(json.dumps(self.config))
        config['activitypub']['auto_accept_follow_requests'] = False

        processor = FollowProcessor()

        follow_activity = {
            "type": "Follow",
            "actor": "https://mastodon.social/users/bob",
            "object": "https://test.example.com/activitypub/actor",
            "id": "https://mastodon.social/activities/456"
        }

        result = processor.process_inbox(follow_activity, "test-follow-no-auto.json", config)
        self.assertTrue(result)

        # Verify NO follower was added when auto-accept is disabled
        followers_dir = self.config['directories']['followers']
        followers_file = os.path.join(followers_dir, 'followers.json')

        if os.path.exists(followers_file):
            with open(followers_file) as f:
                followers_data = json.load(f)
            self.assertNotIn('https://mastodon.social/users/bob', followers_data.get('items', []))

        # Verify NO Accept activity was created
        activities_dir = self.config['directories']['outbox']
        activity_files = [f for f in os.listdir(activities_dir) if f.startswith('accept-')]
        self.assertEqual(len(activity_files), 0, "Should not have created Accept activities when auto-accept is disabled")

    def test_missing_actor_handling(self):
        """Test handling of activities with missing actor"""
        from activity_processor import FollowProcessor

        processor = FollowProcessor()

        bad_activity = {
            "type": "Follow",
            "object": "https://test.example.com/activitypub/actor"
        }

        result = processor.process_inbox(bad_activity, "test-no-actor.json", self.config)
        self.assertFalse(result)

    def test_undo_follow_activity_processor(self):
        """Test Undo Follow activity processing"""
        from activity_processor import UndoFollowProcessor

        processor = UndoFollowProcessor()

        # Set up existing follower
        followers_dir = self.config['directories']['followers']
        os.makedirs(followers_dir, exist_ok=True)
        followers_data = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Collection",
            "id": "https://test.example.com/activitypub/followers",
            "totalItems": 1,
            "items": ["https://mastodon.social/users/alice"]
        }
        followers_file = os.path.join(followers_dir, 'followers.json')
        with open(followers_file, 'w') as f:
            json.dump(followers_data, f)

        undo_activity = {
            "type": "Undo",
            "actor": "https://mastodon.social/users/alice",
            "object": {
                "type": "Follow",
                "actor": "https://mastodon.social/users/alice",
                "object": "https://test.example.com/activitypub/actor"
            },
            "id": "https://mastodon.social/activities/456"
        }

        result = processor.process_inbox(undo_activity, "test-undo.json", self.config)
        self.assertTrue(result)

        with open(followers_file) as f:
            updated_followers_data = json.load(f)

        self.assertEqual(updated_followers_data['type'], 'Collection')
        self.assertEqual(updated_followers_data['totalItems'], 0)
        self.assertEqual(len(updated_followers_data['items']), 0)

    def test_undo_follow_nonexistent_follower(self):
        """Test Undo Follow when follower doesn't exist"""
        from activity_processor import UndoFollowProcessor

        processor = UndoFollowProcessor()

        followers_dir = self.config['directories']['followers']
        os.makedirs(followers_dir, exist_ok=True)
        followers_data = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Collection",
            "id": "https://test.example.com/activitypub/followers",
            "totalItems": 0,
            "items": []
        }
        followers_file = os.path.join(followers_dir, 'followers.json')
        with open(followers_file, 'w') as f:
            json.dump(followers_data, f)

        undo_activity = {
            "type": "Undo",
            "actor": "https://mastodon.social/users/bob",
            "object": {
                "type": "Follow",
                "actor": "https://mastodon.social/users/bob",
                "object": "https://test.example.com/activitypub/actor"
            },
            "id": "https://mastodon.social/activities/789"
        }

        result = processor.process_inbox(undo_activity, "test-undo-nonexistent.json", self.config)
        self.assertTrue(result)

        with open(followers_file) as f:
            updated_followers_data = json.load(f)

        self.assertEqual(updated_followers_data['totalItems'], 0)
        self.assertEqual(len(updated_followers_data['items']), 0)

    def test_undo_delegation_mechanism(self):
        """Test that UndoActivityProcessor properly delegates to specific processors"""
        from activity_processor import UndoActivityProcessor, FollowProcessor

        follow_processor = FollowProcessor()
        follow_activity = {
            "type": "Follow",
            "actor": "https://mastodon.social/users/alice",
            "object": "https://test.example.com/activitypub/actor",
            "id": "https://mastodon.social/activities/123"
        }
        follow_processor.process_inbox(follow_activity, "test-follow.json", self.config)

        followers_dir = self.config['directories']['followers']
        followers_file = os.path.join(followers_dir, 'followers.json')
        with open(followers_file) as f:
            followers_data = json.load(f)
        self.assertIn('https://mastodon.social/users/alice', followers_data['items'])

        undo_processor = UndoActivityProcessor()
        undo_activity = {
            "type": "Undo",
            "actor": "https://mastodon.social/users/alice",
            "object": {
                "type": "Follow",
                "actor": "https://mastodon.social/users/alice",
                "object": "https://test.example.com/activitypub/actor"
            },
            "id": "https://mastodon.social/activities/456"
        }

        result = undo_processor.process_inbox(undo_activity, "test-undo-delegation.json", self.config)
        self.assertTrue(result)

        with open(followers_file) as f:
            followers_data = json.load(f)
        self.assertNotIn('https://mastodon.social/users/alice', followers_data['items'])
        self.assertEqual(followers_data['totalItems'], 0)


class TestFollowersEndpointIntegration(unittest.TestCase, TestConfigMixin):
    """Integration test: followers endpoint reflects processed Follow activities"""

    def setUp(self):
        self.setup_test_environment("followers_endpoint",
                                    server={"domain": "test.example.com"},
                                    activitypub={"username": "test", "actor_name": "Test Actor"})

        from app import app
        self.app = app
        self.client = app.test_client()
        app.config['TESTING'] = True

    def tearDown(self):
        self.teardown_test_environment()

    def test_followers_endpoint_after_follow_processed(self):
        """Test that /followers reflects a newly processed Follow activity"""
        from activity_processor import FollowProcessor

        processor = FollowProcessor()

        follow_activity = {
            "type": "Follow",
            "actor": "https://mastodon.social/users/alice",
            "object": "https://test.example.com/activitypub/actor",
            "id": "https://mastodon.social/activities/123"
        }

        processor.process_inbox(follow_activity, "follow-test.json", self.config)

        response = self.client.get(
            '/activitypub/followers',
            headers={'Accept': 'application/activity+json'}
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['type'], 'Collection')
        self.assertEqual(data['totalItems'], 1)
        self.assertIn('https://mastodon.social/users/alice', data['items'])

    def test_followers_endpoint_after_undo_follow(self):
        """Test that /followers reflects an UndoFollow removing a follower"""
        from activity_processor import UndoFollowProcessor

        # Pre-populate followers.json with an existing follower
        followers_dir = self.config['directories']['followers']
        followers_data = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Collection",
            "id": "https://test.example.com/activitypub/followers",
            "totalItems": 1,
            "items": ["https://mastodon.social/users/alice"]
        }
        with open(os.path.join(followers_dir, 'followers.json'), 'w') as f:
            json.dump(followers_data, f)

        undo_processor = UndoFollowProcessor()
        undo_activity = {
            "type": "Undo",
            "actor": "https://mastodon.social/users/alice",
            "object": {
                "type": "Follow",
                "actor": "https://mastodon.social/users/alice",
                "object": "https://test.example.com/activitypub/actor"
            },
            "id": "https://mastodon.social/activities/456"
        }
        undo_processor.process_inbox(undo_activity, "undo-follow-test.json", self.config)

        response = self.client.get(
            '/activitypub/followers',
            headers={'Accept': 'application/activity+json'}
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['totalItems'], 0)
        self.assertNotIn('https://mastodon.social/users/alice', data['items'])


if __name__ == '__main__':
    unittest.main()
