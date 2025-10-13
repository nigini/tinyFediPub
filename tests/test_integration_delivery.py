"""
Integration tests for activity delivery with mocked remote instance

Tests the complete delivery workflow by:
- Running one real Flask instance (Bob)
- Mocking the remote instance (Alice) with controlled responses
- Verifying the full Follow -> Accept workflow
"""
import unittest
import json
import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.test_config import TestConfigMixin
import activity_processor


class TestDeliveryIntegration(TestConfigMixin, unittest.TestCase):
    """
    Integration test for complete activity delivery workflow

    Scenario: Alice (mocked) follows Bob (real Flask app)
    1. Alice sends Follow activity to Bob's inbox
    2. Bob processes Follow, adds Alice to followers
    3. Bob generates Accept activity
    4. Bob delivers Accept to Alice's inbox (mocked)
    5. Verify all steps completed correctly
    """

    def setUp(self):
        """Set up Bob's instance"""
        self.setup_test_environment("bob_integration")

        # Generate RSA keys for signing
        self.private_key, self.public_key = self.generate_test_rsa_keys()

        # Write keys to files
        with open(self.config['security']['private_key_file'], 'w') as f:
            f.write(self.private_key)
        with open(self.config['security']['public_key_file'], 'w') as f:
            f.write(self.public_key)

        # Create Bob's actor with public key
        self._create_bob_actor()

        # Import Flask app AFTER setup (to get fresh config)
        import importlib
        if 'app' in sys.modules:
            importlib.reload(sys.modules['app'])
        import app as flask_app
        self.app = flask_app.app
        self.client = self.app.test_client()

    def tearDown(self):
        """Clean up test environment"""
        self.teardown_test_environment()

    def _create_bob_actor(self):
        """Create Bob's actor.json with public key"""
        from post_utils import generate_base_url
        base_url = generate_base_url(self.config)

        actor = {
            "@context": [
                "https://www.w3.org/ns/activitystreams",
                "https://w3id.org/security/v1"
            ],
            "type": "Person",
            "id": f"{base_url}/actor",
            "preferredUsername": "bob",
            "name": "Bob Test",
            "inbox": f"{base_url}/inbox",
            "outbox": f"{base_url}/outbox",
            "followers": f"{base_url}/followers",
            "publicKey": {
                "id": f"{base_url}/actor#main-key",
                "owner": f"{base_url}/actor",
                "publicKeyPem": self.public_key
            }
        }

        actor_path = os.path.join(self.config['directories']['outbox'], 'actor.json')
        with open(actor_path, 'w') as f:
            json.dump(actor, f, indent=2)

    def test_complete_follow_workflow_with_mocked_remote(self):
        """
        Test complete Follow -> Accept workflow

        Steps:
        1. Alice (mocked) sends Follow to Bob's inbox
        2. Bob saves Follow to inbox
        3. Activity processor runs
        4. Bob adds Alice to followers
        5. Bob generates Accept activity
        6. Bob delivers Accept to Alice's inbox (mocked HTTP request)
        7. Verify all state changes
        """
        alice_actor_url = "https://mastodon.example/users/alice"
        alice_inbox_url = "https://mastodon.example/users/alice/inbox"

        # Create Follow activity from Alice
        follow_activity = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Follow",
            "id": "https://mastodon.example/activities/follow-123",
            "actor": alice_actor_url,
            "object": "https://test.example.com/activitypub/actor"
        }

        # Step 1: Alice sends Follow to Bob's inbox
        response = self.client.post(
            '/activitypub/inbox',
            data=json.dumps(follow_activity),
            content_type='application/activity+json'
        )

        self.assertEqual(response.status_code, 202)

        # Verify Follow was saved to inbox
        inbox_dir = self.config['directories']['inbox']
        inbox_files = [f for f in os.listdir(inbox_dir) if f.startswith('follow-') and f.endswith('.json')]
        self.assertEqual(len(inbox_files), 1, "Follow activity should be saved in inbox")

        # Verify symlink was created in queue (app does this automatically)
        queue_dir = self.config['directories']['inbox_queue']
        queue_files = os.listdir(queue_dir)
        self.assertEqual(len(queue_files), 1, "Follow should be queued for processing")

        # Step 2 & 3: Process the activity with mocked delivery
        # Mock the remote actor fetch, signing, and Accept delivery
        with patch('activity_delivery.requests.get') as mock_get, \
             patch('activity_delivery.requests.post') as mock_post, \
             patch('http_signatures.sign_request') as mock_sign:

            # Mock fetching Alice's actor (for inbox URL)
            mock_actor_response = MagicMock()
            mock_actor_response.json.return_value = {
                "id": alice_actor_url,
                "type": "Person",
                "inbox": alice_inbox_url,
                "publicKey": {
                    "id": f"{alice_actor_url}#main-key",
                    "publicKeyPem": self.public_key  # Use same key for simplicity
                }
            }
            mock_actor_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_actor_response

            # Mock signing (return fake signature)
            mock_sign.return_value = "fake_signature_string"

            # Mock Accept delivery to Alice's inbox
            mock_delivery_response = MagicMock()
            mock_delivery_response.raise_for_status = MagicMock()
            mock_post.return_value = mock_delivery_response

            # Run activity processor
            import importlib
            importlib.reload(activity_processor)
            activity_processor.main()

        # Step 4: Verify Alice is in Bob's followers
        followers_file = os.path.join(
            self.config['directories']['followers'],
            'followers.json'
        )
        self.assertTrue(os.path.exists(followers_file), "Followers file should exist")

        with open(followers_file, 'r') as f:
            followers_data = json.load(f)

        # Check for either 'items' or 'orderedItems' (both are valid in ActivityStreams)
        items_key = 'items' if 'items' in followers_data else 'orderedItems'
        self.assertIn(items_key, followers_data)
        self.assertIn(alice_actor_url, followers_data[items_key])

        # Step 5: Verify Accept activity was generated
        activities_dir = self.config['directories']['activities']
        accept_files = [f for f in os.listdir(activities_dir) if f.startswith('accept-')]
        self.assertGreater(len(accept_files), 0, "Accept activity should be generated")

        # Verify Accept activity content
        accept_file = os.path.join(activities_dir, accept_files[0])
        with open(accept_file, 'r') as f:
            accept_activity = json.load(f)

        self.assertEqual(accept_activity['type'], 'Accept')
        self.assertEqual(accept_activity['object'], follow_activity)

        # Step 6: Verify Accept was delivered to Alice
        mock_post.assert_called_once()
        delivery_call = mock_post.call_args

        # Verify delivery URL
        self.assertEqual(delivery_call[0][0], alice_inbox_url)

        # Verify Accept was in the request body
        delivered_body = json.loads(delivery_call[1]['data'])
        self.assertEqual(delivered_body['type'], 'Accept')

        # Verify HTTP signature was included
        self.assertIn('Signature', delivery_call[1]['headers'])

        # Verify queue was cleaned up
        queue_files = os.listdir(queue_dir)
        self.assertEqual(len(queue_files), 0, "Queue should be empty after processing")

    def test_follow_then_unfollow_workflow(self):
        """
        Test Follow followed by Undo Follow workflow

        Steps:
        1. Alice follows Bob (adds to followers)
        2. Alice unfollows Bob (removes from followers)
        3. Verify final state
        """
        alice_actor_url = "https://mastodon.example/users/alice"
        alice_inbox_url = "https://mastodon.example/users/alice/inbox"

        # Follow activity
        follow_activity = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Follow",
            "id": "https://mastodon.example/activities/follow-456",
            "actor": alice_actor_url,
            "object": "https://test.example.com/activitypub/actor"
        }

        # Send Follow
        self.client.post(
            '/activitypub/inbox',
            data=json.dumps(follow_activity),
            content_type='application/activity+json'
        )

        # Verify Follow was queued (app does this automatically)
        inbox_dir = self.config['directories']['inbox']
        queue_dir = self.config['directories']['inbox_queue']

        with patch('activity_delivery.requests.get') as mock_get, \
             patch('activity_delivery.requests.post') as mock_post, \
             patch('http_signatures.sign_request') as mock_sign:

            mock_actor_response = MagicMock()
            mock_actor_response.json.return_value = {
                "inbox": alice_inbox_url,
                "publicKey": {"id": f"{alice_actor_url}#main-key"}
            }
            mock_actor_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_actor_response

            mock_sign.return_value = "fake_signature_string"
            mock_post.return_value = MagicMock(raise_for_status=MagicMock())

            import importlib
            importlib.reload(activity_processor)
            activity_processor.main()

        # Verify Alice is in followers
        followers_file = os.path.join(
            self.config['directories']['followers'],
            'followers.json'
        )
        with open(followers_file, 'r') as f:
            followers_data = json.load(f)

        items_key = 'items' if 'items' in followers_data else 'orderedItems'
        self.assertIn(alice_actor_url, followers_data[items_key])

        # Now send Undo Follow
        undo_activity = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Undo",
            "id": "https://mastodon.example/activities/undo-456",
            "actor": alice_actor_url,
            "object": follow_activity
        }

        self.client.post(
            '/activitypub/inbox',
            data=json.dumps(undo_activity),
            content_type='application/activity+json'
        )

        # Undo is automatically queued by the app

        importlib.reload(activity_processor)
        activity_processor.main()

        # Verify Alice is no longer in followers
        with open(followers_file, 'r') as f:
            followers_data = json.load(f)

        items_key = 'items' if 'items' in followers_data else 'orderedItems'
        self.assertNotIn(alice_actor_url, followers_data[items_key])


if __name__ == '__main__':
    unittest.main()
