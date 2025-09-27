#!/usr/bin/env python3
"""
Unit tests for followers collection endpoint
"""
import unittest
import json
import os
import sys
sys.path.insert(0, '.')
from tests.test_config import TestConfigMixin


class TestFollowersEndpoint(unittest.TestCase, TestConfigMixin):
    """Test the followers collection endpoint"""

    def setUp(self):
        """Set up test environment"""
        self.setup_test_environment("followers")
        # Create actor file for this test
        self.create_test_actor()

    def tearDown(self):
        """Clean up test environment"""
        self.teardown_test_environment()

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
        followers_file = self.get_test_file_path('followers', 'followers.json')
        self.assertFalse(os.path.exists(followers_file))

        with app.test_client() as client:
            response = client.get('/activitypub/followers',
                                headers={'Accept': 'application/activity+json'})

            self.assertEqual(response.status_code, 200)
            # Check that file was created
            self.assertTrue(os.path.exists(followers_file))

            # Verify file contents
            with open(followers_file, 'r') as f:
                followers_data = json.load(f)
            self.assertEqual(followers_data['totalItems'], 0)


if __name__ == '__main__':
    unittest.main()