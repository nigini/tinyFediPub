#!/usr/bin/env python3
"""
Unit tests for following collection endpoint
"""
import unittest
import json
import os
import sys
sys.path.insert(0, '.')
from tests.test_config import TestConfigMixin


class TestFollowingEndpoint(unittest.TestCase, TestConfigMixin):
    """Test the following collection endpoint"""

    def setUp(self):
        self.setup_test_environment("following")
        self.create_test_actor()

    def tearDown(self):
        self.teardown_test_environment()

    def test_following_endpoint_empty(self):
        """Endpoint returns an empty OrderedCollection when not following anyone."""
        from app import app

        with app.test_client() as client:
            response = client.get('/activitypub/following',
                                  headers={'Accept': 'application/activity+json'})

            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertEqual(data['type'], 'OrderedCollection')
            self.assertEqual(data['totalItems'], 0)
            self.assertEqual(data['orderedItems'], [])

    def test_following_endpoint_with_entries(self):
        """Endpoint returns followed actors when following list has entries."""
        from data_access.follow import add_following
        from app import app

        add_following("https://mastodon.social/users/alice", self.config)
        add_following("https://social.coop/users/bob", self.config)

        with app.test_client() as client:
            response = client.get('/activitypub/following',
                                  headers={'Accept': 'application/activity+json'})

            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertEqual(data['type'], 'OrderedCollection')
            self.assertEqual(data['totalItems'], 2)
            self.assertEqual(data['orderedItems'], [
                'https://mastodon.social/users/alice',
                'https://social.coop/users/bob'
            ])

    def test_following_endpoint_does_not_create_file(self):
        """Endpoint is render-on-read: hitting it should not materialize following.json."""
        from app import app

        following_file = os.path.join(self.config['directories']['data_root'], 'following.json')
        self.assertFalse(os.path.exists(following_file))

        with app.test_client() as client:
            response = client.get('/activitypub/following',
                                  headers={'Accept': 'application/activity+json'})
            self.assertEqual(response.status_code, 200)

        self.assertFalse(os.path.exists(following_file),
                         "following.json should not be created merely by reading the endpoint")

    def test_following_endpoint_requires_ap_content_type(self):
        """Endpoint requires application/activity+json Accept header."""
        from app import app

        with app.test_client() as client:
            response = client.get('/activitypub/following',
                                  headers={'Accept': 'text/html'})

            self.assertEqual(response.status_code, 406)
            data = json.loads(response.data)
            self.assertEqual(data['error'], 'Not acceptable')


if __name__ == '__main__':
    unittest.main()
