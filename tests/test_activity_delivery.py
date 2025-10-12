"""
Tests for activity_delivery module
"""
import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import activity_delivery
from tests.test_config import TestConfigMixin


class TestFetchActorInbox(unittest.TestCase):
    """Test fetching actor inbox URLs"""

    def test_fetch_inbox_success(self):
        """Test successfully fetching inbox from actor document"""
        actor_url = "https://mastodon.social/users/alice"
        expected_inbox = "https://mastodon.social/users/alice/inbox"

        mock_actor = {
            "id": actor_url,
            "type": "Person",
            "inbox": expected_inbox
        }

        config = {"server": {}}

        with patch('activity_delivery.requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_actor
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            result = activity_delivery.fetch_actor_inbox(actor_url, config)

            self.assertEqual(result, expected_inbox)
            mock_get.assert_called_once()

            # Verify headers
            call_args = mock_get.call_args
            headers = call_args[1]['headers']
            self.assertIn('Accept', headers)
            self.assertIn('application/activity+json', headers['Accept'])

    def test_fetch_inbox_missing(self):
        """Test actor document without inbox"""
        actor_url = "https://mastodon.social/users/alice"

        mock_actor = {
            "id": actor_url,
            "type": "Person"
            # No inbox field
        }

        config = {"server": {}}

        with patch('activity_delivery.requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_actor
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            result = activity_delivery.fetch_actor_inbox(actor_url, config)

            self.assertIsNone(result)

    def test_fetch_inbox_network_error(self):
        """Test handling network errors when fetching inbox"""
        actor_url = "https://mastodon.social/users/alice"
        config = {"server": {}}

        with patch('activity_delivery.requests.get') as mock_get:
            mock_get.side_effect = Exception("Network error")

            result = activity_delivery.fetch_actor_inbox(actor_url, config)

            self.assertIsNone(result)

    def test_fetch_inbox_with_user_agent(self):
        """Test that custom User-Agent is used"""
        actor_url = "https://mastodon.social/users/alice"
        custom_ua = "MyFedi/2.0"

        mock_actor = {
            "id": actor_url,
            "inbox": "https://mastodon.social/users/alice/inbox"
        }

        config = {"server": {"user_agent": custom_ua}}

        with patch('activity_delivery.requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = mock_actor
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            activity_delivery.fetch_actor_inbox(actor_url, config)

            # Verify User-Agent header
            call_args = mock_get.call_args
            headers = call_args[1]['headers']
            self.assertEqual(headers['User-Agent'], custom_ua)


class TestDeliverActivity(TestConfigMixin, unittest.TestCase):
    """Test delivering activities to remote inboxes"""

    def setUp(self):
        self.setup_test_environment("delivery_test")
        self.activity = {
            "type": "Accept",
            "actor": "https://example.com/actor",
            "object": {"type": "Follow"}
        }
        self.inbox_url = "https://mastodon.social/users/alice/inbox"

    def tearDown(self):
        self.teardown_test_environment()

    def test_deliver_activity_success(self):
        """Test successful activity delivery"""
        with patch('activity_delivery.requests.post') as mock_post, \
             patch('activity_delivery.load_private_key') as mock_load_key, \
             patch('post_utils.get_actor_info') as mock_actor_info:

            # Setup mocks
            mock_load_key.return_value = "fake-private-key"
            mock_actor_info.return_value = {
                "publicKey": {
                    "id": "https://example.com/actor#main-key"
                }
            }

            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_response

            # Mock sign_request to avoid actual signing
            with patch('activity_delivery.http_signatures.sign_request') as mock_sign:
                mock_sign.return_value = "signature_string"

                result = activity_delivery.deliver_activity(
                    self.activity,
                    self.inbox_url,
                    self.config
                )

            self.assertTrue(result)
            mock_post.assert_called_once()

    def test_deliver_activity_network_error(self):
        """Test handling network errors during delivery"""
        with patch('activity_delivery.requests.post') as mock_post, \
             patch('activity_delivery.load_private_key') as mock_load_key, \
             patch('post_utils.get_actor_info') as mock_actor_info:

            # Setup mocks
            mock_load_key.return_value = "fake-private-key"
            mock_actor_info.return_value = {
                "publicKey": {
                    "id": "https://example.com/actor#main-key"
                }
            }

            mock_post.side_effect = Exception("Network error")

            with patch('activity_delivery.http_signatures.sign_request') as mock_sign:
                mock_sign.return_value = "signature_string"

                result = activity_delivery.deliver_activity(
                    self.activity,
                    self.inbox_url,
                    self.config
                )

            self.assertFalse(result)

    def test_deliver_activity_missing_actor_key(self):
        """Test handling missing actor public key"""
        with patch('activity_delivery.load_private_key') as mock_load_key, \
             patch('post_utils.get_actor_info') as mock_actor_info:

            mock_load_key.return_value = "fake-private-key"
            mock_actor_info.return_value = {}  # No publicKey field

            result = activity_delivery.deliver_activity(
                self.activity,
                self.inbox_url,
                self.config
            )

            self.assertFalse(result)


class TestDeliverToActor(TestConfigMixin, unittest.TestCase):
    """Test delivering to a single actor"""

    def setUp(self):
        self.setup_test_environment("deliver_to_actor_test")
        self.activity = {
            "type": "Accept",
            "actor": "https://example.com/actor",
            "object": {"type": "Follow"}
        }
        self.actor_url = "https://mastodon.social/users/alice"

    def tearDown(self):
        self.teardown_test_environment()

    def test_deliver_to_actor_success(self):
        """Test successful delivery to actor"""
        with patch('activity_delivery.fetch_actor_inbox') as mock_fetch, \
             patch('activity_delivery.deliver_activity') as mock_deliver:

            mock_fetch.return_value = "https://mastodon.social/users/alice/inbox"
            mock_deliver.return_value = True

            result = activity_delivery.deliver_to_actor(
                self.activity,
                self.actor_url,
                self.config
            )

            self.assertTrue(result)
            mock_fetch.assert_called_once_with(self.actor_url, self.config)
            mock_deliver.assert_called_once()

    def test_deliver_to_actor_no_inbox(self):
        """Test handling when actor has no inbox"""
        with patch('activity_delivery.fetch_actor_inbox') as mock_fetch:
            mock_fetch.return_value = None

            result = activity_delivery.deliver_to_actor(
                self.activity,
                self.actor_url,
                self.config
            )

            self.assertFalse(result)


class TestDeliverToFollowers(TestConfigMixin, unittest.TestCase):
    """Test broadcasting to all followers"""

    def setUp(self):
        self.setup_test_environment("deliver_to_followers_test")
        self.activity = {
            "type": "Create",
            "actor": "https://example.com/actor",
            "object": {"type": "Note"}
        }

    def tearDown(self):
        self.teardown_test_environment()

    def test_deliver_to_followers_success(self):
        """Test successful delivery to multiple followers"""
        followers = [
            "https://mastodon.social/users/alice",
            "https://mastodon.social/users/bob"
        ]

        with patch('post_utils.get_followers_list') as mock_followers, \
             patch('activity_delivery.deliver_to_actor') as mock_deliver:

            mock_followers.return_value = followers
            mock_deliver.return_value = True

            results = activity_delivery.deliver_to_followers(
                self.activity,
                self.config
            )

            self.assertEqual(len(results), 2)
            self.assertTrue(all(results.values()))
            self.assertEqual(mock_deliver.call_count, 2)

    def test_deliver_to_followers_partial_failure(self):
        """Test handling partial delivery failures"""
        followers = [
            "https://mastodon.social/users/alice",
            "https://mastodon.social/users/bob",
            "https://mastodon.social/users/charlie"
        ]

        with patch('post_utils.get_followers_list') as mock_followers, \
             patch('activity_delivery.deliver_to_actor') as mock_deliver:

            mock_followers.return_value = followers
            # Second delivery fails
            mock_deliver.side_effect = [True, False, True]

            results = activity_delivery.deliver_to_followers(
                self.activity,
                self.config
            )

            self.assertEqual(len(results), 3)
            self.assertEqual(sum(results.values()), 2)  # 2 successes
            self.assertEqual(mock_deliver.call_count, 3)

    def test_deliver_to_followers_empty_list(self):
        """Test delivery with no followers"""
        with patch('post_utils.get_followers_list') as mock_followers:
            mock_followers.return_value = []

            results = activity_delivery.deliver_to_followers(
                self.activity,
                self.config
            )

            self.assertEqual(len(results), 0)


if __name__ == '__main__':
    unittest.main()
