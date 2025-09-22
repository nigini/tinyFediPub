#!/usr/bin/env python3
"""
Unit tests for ActivityPub inbox functionality
"""
import unittest
import tempfile
import shutil
import os
import json
import sys


class TestInboxFunctionality(unittest.TestCase):
    """Test inbox activity saving and processing"""

    def setUp(self):
        """Set up temporary directory for test files"""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        sys.path.insert(0, self.original_cwd)

        # Create test config (copy from example)
        test_config = {
            "server": {
                "domain": "test.example.com",
                "protocol": "https",
                "host": "0.0.0.0",
                "port": 5000,
                "debug": True
            },
            "activitypub": {
                "username": "test",
                "actor_name": "Test Actor",
                "actor_summary": "A test actor",
                "namespace": "activitypub"
            },
            "security": {
                "public_key_file": "test.pem",
                "private_key_file": "test.pem"
            }
        }
        with open('config.json', 'w') as f:
            json.dump(test_config, f)
        with open('test.pem', 'w') as f:
            f.write('test key')

    def tearDown(self):
        """Clean up temporary directory"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

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
        inbox_files = os.listdir('static/inbox')
        self.assertEqual(len(inbox_files), 1)

        filename = inbox_files[0]
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

        inbox_files = os.listdir('static/inbox')
        filename = inbox_files[0]
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

        inbox_files = os.listdir('static/inbox')
        filename = inbox_files[0]
        self.assertTrue(filename.startswith('like-'))
        self.assertTrue(filename.endswith('-unknown.json'))


class TestInboxEndpoint(unittest.TestCase):
    """Test the inbox HTTP endpoint"""

    def setUp(self):
        """Set up Flask test client"""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        sys.path.insert(0, self.original_cwd)

        # Create test config and keys
        test_config = {
            "server": {"domain": "test.example.com", "protocol": "https", "host": "0.0.0.0", "port": 5000, "debug": True},
            "activitypub": {"namespace": "activitypub", "username": "test", "actor_name": "Test", "actor_summary": "Test"},
            "security": {"public_key_file": "test.pem", "private_key_file": "test.pem"}
        }
        with open('config.json', 'w') as f:
            json.dump(test_config, f)
        with open('test.pem', 'w') as f:
            f.write('test key')

    def tearDown(self):
        """Clean up"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

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