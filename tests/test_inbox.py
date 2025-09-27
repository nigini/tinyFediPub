#!/usr/bin/env python3
"""
Unit tests for ActivityPub inbox functionality
"""
import unittest
import json
import sys
sys.path.insert(0, '.')
from tests.test_config import TestConfigMixin


class TestInboxFunctionality(unittest.TestCase, TestConfigMixin):
    """Test inbox activity saving and processing"""

    def setUp(self):
        """Set up test environment"""
        self.setup_test_environment("inbox_functionality")

    def tearDown(self):
        """Clean up test environment"""
        self.teardown_test_environment()

    def test_save_follow_activity(self):
        """Test saving Follow activity to inbox folder"""
        from app import save_inbox_activity

        follow_activity = {
            "type": "Follow",
            "actor": "https://mastodon.social/users/alice",
            "object": "https://example.com/actor",
            "id": "https://mastodon.social/activities/123"
        }

        save_inbox_activity(follow_activity)

        # Check file was created with correct pattern
        self.assert_file_count('inbox', 1)

        # Get the single file and verify naming
        filename = self.get_single_file_in_directory('inbox')
        self.assertTrue(filename.startswith('follow-'))
        self.assertTrue(filename.endswith('-mastodon-social.json'))

    def test_save_undo_activity(self):
        """Test saving Undo activity to inbox folder"""
        from app import save_inbox_activity

        undo_activity = {
            "type": "Undo",
            "actor": "https://pixelfed.social/users/bob",
            "object": {"type": "Follow"},
            "id": "https://pixelfed.social/activities/456"
        }

        save_inbox_activity(undo_activity)

        self.assert_file_count('inbox', 1)
        filename = self.get_single_file_in_directory('inbox')
        self.assertTrue(filename.startswith('undo-'))
        self.assertTrue(filename.endswith('-pixelfed-social.json'))

    def test_save_activity_unknown_actor(self):
        """Test saving activity with malformed actor URL"""
        from app import save_inbox_activity

        bad_activity = {
            "type": "Like",
            "actor": "not-a-valid-url",
            "object": "https://example.com/posts/123"
        }

        save_inbox_activity(bad_activity)

        self.assert_file_count('inbox', 1)
        filename = self.get_single_file_in_directory('inbox')
        self.assertTrue(filename.startswith('like-'))
        self.assertTrue(filename.endswith('-unknown.json'))


class TestInboxEndpoint(unittest.TestCase, TestConfigMixin):
    """Test the inbox HTTP endpoint"""

    def setUp(self):
        """Set up test environment"""
        self.setup_test_environment("inbox_endpoint")

    def tearDown(self):
        """Clean up test environment"""
        self.teardown_test_environment()

    def test_inbox_accepts_follow(self):
        """Test that inbox endpoint accepts Follow activities"""
        from app import app

        with app.test_client() as client:
            follow_activity = {
                "type": "Follow",
                "actor": "https://mastodon.social/users/alice",
                "object": "https://test.example.com/activitypub/actor"
            }

            response = client.post('/activitypub/inbox',
                                 json=follow_activity,
                                 content_type='application/activity+json')

            self.assertEqual(response.status_code, 202)

    def test_inbox_rejects_wrong_content_type(self):
        """Test that inbox rejects non-ActivityPub content types"""
        from app import app

        with app.test_client() as client:
            response = client.post('/activitypub/inbox',
                                 json={"type": "Follow"},
                                 content_type='application/json')

            self.assertEqual(response.status_code, 400)
            data = json.loads(response.data)
            self.assertEqual(data['error'], 'Invalid content type')


if __name__ == '__main__':
    unittest.main()