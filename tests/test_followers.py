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
        self.setup_test_environment("followers")
        self.create_test_actor()

    def tearDown(self):
        self.teardown_test_environment()

    def test_followers_endpoint_empty(self):
        """Endpoint returns an empty OrderedCollection when there are no followers."""
        from app import app

        with app.test_client() as client:
            response = client.get('/activitypub/followers',
                                  headers={'Accept': 'application/activity+json'})

            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertEqual(data['type'], 'OrderedCollection')
            self.assertEqual(data['totalItems'], 0)
            self.assertEqual(data['orderedItems'], [])

    def test_followers_endpoint_does_not_create_file(self):
        """Endpoint is render-on-read: hitting it should not materialize followers.json."""
        from app import app

        followers_file = os.path.join(self.config['directories']['data_root'], 'followers.json')
        self.assertFalse(os.path.exists(followers_file))

        with app.test_client() as client:
            response = client.get('/activitypub/followers',
                                  headers={'Accept': 'application/activity+json'})
            self.assertEqual(response.status_code, 200)

        self.assertFalse(os.path.exists(followers_file),
                         "followers.json should not be created merely by reading the endpoint")


if __name__ == '__main__':
    unittest.main()
