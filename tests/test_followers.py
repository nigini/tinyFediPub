#!/usr/bin/env python3
"""
Unit tests for followers collection endpoint
"""
import unittest
import tempfile
import shutil
import os
import json
import sys


class TestFollowersEndpoint(unittest.TestCase):
    """Test the followers collection endpoint"""

    def setUp(self):
        """Set up Flask test client"""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        sys.path.insert(0, self.original_cwd)

        # Create test config
        test_config = {
            "server": {"domain": "test.example.com", "protocol": "https", "host": "0.0.0.0", "port": 5000, "debug": True},
            "activitypub": {"namespace": "activitypub", "username": "test", "actor_name": "Test", "actor_summary": "Test"},
            "security": {"public_key_file": "test.pem", "private_key_file": "test.pem"}
        }
        with open('config.json', 'w') as f:
            json.dump(test_config, f)
        with open('test.pem', 'w') as f:
            f.write('test key')

        # Create actor.json
        os.makedirs('static', exist_ok=True)
        test_actor = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Person",
            "id": "https://test.example.com/activitypub/actor"
        }
        with open('static/actor.json', 'w') as f:
            json.dump(test_actor, f)

    def tearDown(self):
        """Clean up"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    def test_followers_endpoint_empty(self):
        """Test followers endpoint returns empty collection when file doesn't exist"""
        from app import app

        with app.test_client() as client:
            response = client.get('/activitypub/followers',
                                headers={'Accept': 'application/activity+json'})

            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertEqual(data['type'], 'Collection')
            self.assertEqual(data['totalItems'], 0)
            self.assertEqual(data['items'], [])

    def test_followers_endpoint_creates_file(self):
        """Test that followers endpoint creates followers.json if it doesn't exist"""
        from app import app

        # Ensure file doesn't exist initially
        self.assertFalse(os.path.exists('static/followers.json'))

        with app.test_client() as client:
            response = client.get('/activitypub/followers',
                                headers={'Accept': 'application/activity+json'})

            self.assertEqual(response.status_code, 200)
            # Check that file was created
            self.assertTrue(os.path.exists('static/followers.json'))

            # Verify file contents
            with open('static/followers.json', 'r') as f:
                followers_data = json.load(f)
            self.assertEqual(followers_data['totalItems'], 0)


if __name__ == '__main__':
    unittest.main()