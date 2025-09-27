#!/usr/bin/env python3
"""
Unit tests for ActivityPub activity processing system
"""
import unittest
import tempfile
import shutil
import os
import json
import sys
from unittest.mock import patch


class TestActivityProcessor(unittest.TestCase):
    """Test activity processing functionality"""

    def setUp(self):
        """Set up temporary directory for test files"""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        sys.path.insert(0, self.original_cwd)

        # Create test config
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
                "namespace": "activitypub",
                "auto_accept_follow_requests": True
            },
            "security": {
                "public_key_file": "test.pem",
                "private_key_file": "test.pem"
            },
            "directories": {
                "inbox": "static/tests/inbox",
                "inbox_queue": "static/tests/inbox/queue",
                "outbox": "static/tests",
                "posts": "static/tests/posts",
                "activities": "static/tests/activities",
                "followers": "static/tests"
            }
        }
        with open('config.json', 'w') as f:
            json.dump(test_config, f)
        with open('test.pem', 'w') as f:
            f.write('test key')

        # Create required directories from config
        self.config = test_config
        os.makedirs(test_config['directories']['inbox'], exist_ok=True)
        os.makedirs(test_config['directories']['inbox_queue'], exist_ok=True)
        os.makedirs(test_config['directories']['activities'], exist_ok=True)

    def tearDown(self):
        """Clean up temporary directory"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    def test_follow_activity_processor(self):
        """Test Follow activity processing"""
        from activity_processor import FollowActivityProcessor

        processor = FollowActivityProcessor()

        follow_activity = {
            "type": "Follow",
            "actor": "https://mastodon.social/users/alice",
            "object": "https://test.example.com/activitypub/actor",
            "id": "https://mastodon.social/activities/123"
        }

        # Test processing
        result = processor.process(follow_activity, "test-follow.json")
        self.assertTrue(result)

        # TODO: Verify Accept activity was created in static/activities/
        # TODO: Verify follower was added to static/followers.json
        # TODO: Check that Accept activity has correct structure

    def test_undo_follow_activity_processor(self):
        """Test Undo Follow activity processing"""
        from activity_processor import UndoActivityProcessor

        processor = UndoActivityProcessor()

        # First, let's assume there's a follower to remove
        followers_dir = self.config['directories']['followers']
        os.makedirs(followers_dir, exist_ok=True)
        followers_data = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "OrderedCollection",
            "id": "https://test.example.com/activitypub/followers",
            "totalItems": 1,
            "orderedItems": ["https://mastodon.social/users/alice"]
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

        # Test processing
        result = processor.process(undo_activity, "test-undo.json")
        self.assertTrue(result)

        # TODO: Verify follower was removed from followers.json
        # TODO: Check that followers.json totalItems was decremented

    def test_unknown_activity_processor(self):
        """Test handling of unknown activity types"""
        from activity_processor import PROCESSORS

        # Unknown activity type should not have a processor
        self.assertNotIn('Like', PROCESSORS)
        self.assertNotIn('Announce', PROCESSORS)

    def test_activity_processor_registry(self):
        """Test that the processor registry is properly configured"""
        from activity_processor import PROCESSORS, FollowActivityProcessor, UndoActivityProcessor

        # Check that expected processors are registered
        self.assertIn('Follow', PROCESSORS)
        self.assertIn('Undo', PROCESSORS)

        # Check processor types
        self.assertIsInstance(PROCESSORS['Follow'], FollowActivityProcessor)
        self.assertIsInstance(PROCESSORS['Undo'], UndoActivityProcessor)

    def test_queue_directory_creation(self):
        """Test that queue directory is created properly"""
        from activity_processor import ensure_queue_directory

        # Remove queue directory if it exists
        queue_dir = self.config['directories']['inbox_queue']
        if os.path.exists(queue_dir):
            shutil.rmtree(queue_dir)

        # Test directory creation
        result_dir = ensure_queue_directory()
        self.assertTrue(os.path.exists(result_dir))
        self.assertEqual(result_dir, queue_dir)

    def test_main_processor_empty_queue(self):
        """Test main processor with empty queue"""
        from activity_processor import main

        # Capture stdout to check output
        with patch('builtins.print') as mock_print:
            main()
            mock_print.assert_called_with("No activities to process")

    def test_main_processor_with_activities(self):
        """Test main processor with queued activities"""
        from activity_processor import main

        # Create a test activity file
        follow_activity = {
            "type": "Follow",
            "actor": "https://mastodon.social/users/alice",
            "object": "https://test.example.com/activitypub/actor",
            "id": "https://mastodon.social/activities/123"
        }

        # Save activity to inbox using config paths
        inbox_dir = self.config['directories']['inbox']
        activity_file = os.path.join(inbox_dir, 'follow-test.json')
        with open(activity_file, 'w') as f:
            json.dump(follow_activity, f)

        # Create symlink in queue using config paths
        queue_dir = self.config['directories']['inbox_queue']
        queue_file = os.path.join(queue_dir, 'follow-test.json')
        os.symlink(os.path.abspath(activity_file), queue_file)

        # Run processor
        with patch('builtins.print') as mock_print:
            main()

            # Check that processing was attempted
            call_args = [call.args[0] for call in mock_print.call_args_list]
            self.assertTrue(any('Processing 1 queued activities' in arg for arg in call_args))
            self.assertTrue(any('Processing Follow activity' in arg for arg in call_args))

    def test_malformed_activity_handling(self):
        """Test handling of malformed activity files"""
        from activity_processor import main

        # Create a malformed activity file
        inbox_dir = self.config['directories']['inbox']
        malformed_file = os.path.join(inbox_dir, 'malformed.json')
        with open(malformed_file, 'w') as f:
            f.write('{"invalid": json}')  # Invalid JSON

        # Create symlink in queue
        queue_dir = self.config['directories']['inbox_queue']
        queue_file = os.path.join(queue_dir, 'malformed.json')
        os.symlink(os.path.abspath(malformed_file), queue_file)

        # Run processor
        with patch('builtins.print') as mock_print:
            main()

            # Check that error was handled gracefully
            call_args = [call.args[0] for call in mock_print.call_args_list]
            self.assertTrue(any('Error loading activity' in arg for arg in call_args))

    def test_missing_actor_handling(self):
        """Test handling of activities with missing actor"""
        from activity_processor import FollowActivityProcessor

        processor = FollowActivityProcessor()

        # Activity without actor
        bad_activity = {
            "type": "Follow",
            "object": "https://test.example.com/activitypub/actor"
        }

        result = processor.process(bad_activity, "test-no-actor.json")
        self.assertFalse(result)

    def test_undo_non_follow_activity(self):
        """Test Undo processor with non-Follow objects"""
        from activity_processor import UndoActivityProcessor

        processor = UndoActivityProcessor()

        # Undo Like activity (should be ignored)
        undo_like = {
            "type": "Undo",
            "actor": "https://mastodon.social/users/alice",
            "object": {
                "type": "Like",
                "actor": "https://mastodon.social/users/alice",
                "object": "https://test.example.com/activitypub/posts/123"
            }
        }

        result = processor.process(undo_like, "test-undo-like.json")
        self.assertTrue(result)  # Should succeed but be ignored


class TestActivityQueueIntegration(unittest.TestCase):
    """Test integration between inbox endpoint and activity queue"""

    def setUp(self):
        """Set up test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        sys.path.insert(0, self.original_cwd)

        # Create test config
        test_config = {
            "server": {"domain": "test.example.com", "protocol": "https", "host": "0.0.0.0", "port": 5000, "debug": True},
            "activitypub": {"namespace": "activitypub", "username": "test", "actor_name": "Test", "actor_summary": "Test", "auto_accept_follow_requests": True},
            "security": {"public_key_file": "test.pem", "private_key_file": "test.pem"},
            "directories": {
                "inbox": "static/tests/inbox",
                "inbox_queue": "static/tests/inbox/queue",
                "outbox": "static/tests",
                "posts": "static/tests/posts",
                "activities": "static/tests/activities",
                "followers": "static/tests"
            }
        }
        with open('config.json', 'w') as f:
            json.dump(test_config, f)
        with open('test.pem', 'w') as f:
            f.write('test key')

        self.config = test_config

        # Create and clean test directories
        for dir_path in test_config['directories'].values():
            os.makedirs(dir_path, exist_ok=True)
            # Clean any existing files
            for f in os.listdir(dir_path):
                file_path = os.path.join(dir_path, f)
                if os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isfile(file_path):
                    os.remove(file_path)

    def tearDown(self):
        """Clean up"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    def test_inbox_to_queue_workflow(self):
        """Test that inbox endpoint properly queues activities"""
        from app import app, save_inbox_activity, queue_activity_for_processing

        # Test activity
        follow_activity = {
            "type": "Follow",
            "actor": "https://mastodon.social/users/alice",
            "object": "https://test.example.com/activitypub/actor"
        }

        # Save activity and queue it
        filename = save_inbox_activity(follow_activity)
        queue_activity_for_processing(filename)

        inbox_dir = self.config['directories']['inbox']

        # Check that activity was saved to inbox (exclude directories)
        inbox_entries = os.listdir(inbox_dir)
        inbox_files = [f for f in inbox_entries if os.path.isfile(os.path.join(inbox_dir, f))]
        self.assertEqual(len(inbox_files), 1, f"Expected 1 file but found {len(inbox_files)}: {inbox_files}")
        self.assertTrue(inbox_files[0].startswith('follow-'))

        # Check that symlink was created in queue
        queue_dir = self.config['directories']['inbox_queue']
        queue_files = os.listdir(queue_dir)
        self.assertEqual(len(queue_files), 1)
        self.assertEqual(queue_files[0], inbox_files[0])

        # Verify symlink points to correct file
        queue_path = os.path.join(queue_dir, queue_files[0])
        inbox_path = os.path.join(inbox_dir, inbox_files[0])
        self.assertTrue(os.path.islink(queue_path))
        self.assertEqual(os.path.realpath(queue_path), os.path.abspath(inbox_path))

    def test_queue_cleanup_after_processing(self):
        """Test that queue symlinks are removed after successful processing"""
        from activity_processor import main

        # Create and queue a Follow activity
        follow_activity = {
            "type": "Follow",
            "actor": "https://mastodon.social/users/alice",
            "object": "https://test.example.com/activitypub/actor",
            "id": "https://mastodon.social/activities/123"
        }

        # Create directories
        inbox_dir = self.config['directories']['inbox']
        queue_dir = self.config['directories']['inbox_queue']
        os.makedirs(inbox_dir, exist_ok=True)
        os.makedirs(queue_dir, exist_ok=True)

        # Save activity
        activity_file = os.path.join(inbox_dir, 'follow-test.json')
        with open(activity_file, 'w') as f:
            json.dump(follow_activity, f)

        # Create queue symlink
        queue_file = os.path.join(queue_dir, 'follow-test.json')
        os.symlink(os.path.abspath(activity_file), queue_file)

        # Verify queue has the activity
        self.assertEqual(len(os.listdir(queue_dir)), 1)

        # Process activities
        main()

        # Verify queue is empty after processing
        self.assertEqual(len(os.listdir(queue_dir)), 0)

        # Verify original activity file still exists
        self.assertTrue(os.path.exists(activity_file))


if __name__ == '__main__':
    unittest.main()