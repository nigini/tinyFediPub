#!/usr/bin/env python3
"""
Unit tests for activity processor infrastructure: registry, queue, error handling
"""
import unittest
import tempfile
import shutil
import os
import json
import sys
from unittest.mock import patch

from tests.test_config import TestConfigMixin


class TestActivityProcessor(unittest.TestCase):
    """Test activity processor registry and queue infrastructure"""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        sys.path.insert(0, self.original_cwd)

        self.config = {
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
                "data_root": "static/tests",
                "outbox": "static/tests/outbox",
                "posts": "static/tests/posts",
                "followers": "static/tests"
            }
        }
        with open('config.json', 'w') as f:
            json.dump(self.config, f)
        with open('test.pem', 'w') as f:
            f.write('test key')

        os.makedirs(self.config['directories']['inbox'], exist_ok=True)
        os.makedirs(self.config['directories']['inbox_queue'], exist_ok=True)
        os.makedirs(self.config['directories']['outbox'], exist_ok=True)

    def tearDown(self):
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    def test_unknown_activity_processor(self):
        """Test handling of unknown activity types"""
        from activity_processor import PROCESSORS

        self.assertNotIn('Announce', PROCESSORS)

    def test_activity_processor_registry(self):
        """Test that the processor registry is properly configured"""
        from activity_processor import PROCESSORS, FollowProcessor, UndoActivityProcessor, UndoFollowProcessor

        self.assertIn('Follow', PROCESSORS)
        self.assertIn('Undo', PROCESSORS)
        self.assertIn('Undo.Follow', PROCESSORS)

        self.assertIsInstance(PROCESSORS['Follow'], FollowProcessor)
        self.assertIsInstance(PROCESSORS['Undo'], UndoActivityProcessor)
        self.assertIsInstance(PROCESSORS['Undo.Follow'], UndoFollowProcessor)

    def test_queue_directory_creation(self):
        """Test that queue directory is created properly"""
        from activity_processor import ensure_queue_directory

        queue_dir = self.config['directories']['inbox_queue']
        if os.path.exists(queue_dir):
            shutil.rmtree(queue_dir)

        result_dir = ensure_queue_directory(self.config)
        self.assertTrue(os.path.exists(result_dir))
        self.assertEqual(result_dir, queue_dir)

    def test_main_processor_empty_queue(self):
        """Test main processor with empty queue"""
        from activity_processor import process_queue

        with patch('builtins.print') as mock_print:
            process_queue(self.config)
            mock_print.assert_called_with("No activities to process")

    def test_main_processor_with_activities(self):
        """Test main processor with queued activities"""
        from activity_processor import process_queue

        follow_activity = {
            "type": "Follow",
            "actor": "https://mastodon.social/users/alice",
            "object": "https://test.example.com/activitypub/actor",
            "id": "https://mastodon.social/activities/123"
        }

        inbox_dir = self.config['directories']['inbox']
        activity_file = os.path.join(inbox_dir, 'follow-test.json')
        with open(activity_file, 'w') as f:
            json.dump(follow_activity, f)

        queue_dir = self.config['directories']['inbox_queue']
        queue_file = os.path.join(queue_dir, 'follow-test.json')
        os.symlink(os.path.abspath(activity_file), queue_file)

        with patch('builtins.print') as mock_print:
            process_queue(self.config)

            call_args = [call.args[0] for call in mock_print.call_args_list]
            self.assertTrue(any('Processing 1 queued activities' in arg for arg in call_args))
            self.assertTrue(any('Processing Follow activity' in arg for arg in call_args))

    def test_malformed_activity_handling(self):
        """Test handling of malformed activity files"""
        from activity_processor import process_queue

        inbox_dir = self.config['directories']['inbox']
        malformed_file = os.path.join(inbox_dir, 'malformed.json')
        with open(malformed_file, 'w') as f:
            f.write('{"invalid": json}')

        queue_dir = self.config['directories']['inbox_queue']
        queue_file = os.path.join(queue_dir, 'malformed.json')
        os.symlink(os.path.abspath(malformed_file), queue_file)

        with patch('builtins.print') as mock_print:
            process_queue(self.config)

            call_args = [call.args[0] for call in mock_print.call_args_list]
            self.assertTrue(any('Error loading activity' in arg for arg in call_args))

    def test_undo_non_follow_activity(self):
        """Test Undo processor with non-Follow objects"""
        from activity_processor import UndoActivityProcessor

        processor = UndoActivityProcessor()

        undo_like = {
            "type": "Undo",
            "actor": "https://mastodon.social/users/alice",
            "object": {
                "type": "Like",
                "actor": "https://mastodon.social/users/alice",
                "object": "https://test.example.com/activitypub/posts/123"
            }
        }

        result = processor.process_inbox(undo_like, "test-undo-like.json", self.config)
        self.assertTrue(result)  # Should succeed but be ignored


class TestActivityQueueIntegration(unittest.TestCase, TestConfigMixin):
    """Test integration between inbox endpoint and activity queue"""

    def setUp(self):
        self.setup_test_environment("queue_integration")

    def tearDown(self):
        self.teardown_test_environment()

    def test_inbox_to_queue_workflow(self):
        """Test that inbox endpoint properly queues activities"""
        from app import app, save_inbox_activity, queue_activity_for_processing

        follow_activity = {
            "type": "Follow",
            "actor": "https://mastodon.social/users/alice",
            "object": "https://test.example.com/activitypub/actor"
        }

        filename = save_inbox_activity(follow_activity)
        queue_activity_for_processing(filename)

        inbox_dir = self.config['directories']['inbox']
        inbox_files = [f for f in os.listdir(inbox_dir) if os.path.isfile(os.path.join(inbox_dir, f))]
        self.assertEqual(len(inbox_files), 1)
        self.assertTrue(inbox_files[0].startswith('follow-'))

        queue_dir = self.config['directories']['inbox_queue']
        queue_files = os.listdir(queue_dir)
        self.assertEqual(len(queue_files), 1)
        self.assertEqual(queue_files[0], inbox_files[0])

        queue_path = os.path.join(queue_dir, queue_files[0])
        inbox_path = os.path.join(inbox_dir, inbox_files[0])
        self.assertTrue(os.path.islink(queue_path))
        self.assertEqual(os.path.realpath(queue_path), os.path.abspath(inbox_path))

    def test_queue_cleanup_after_processing(self):
        """Test that queue symlinks are removed after successful processing"""
        from activity_processor import process_queue

        follow_activity = {
            "type": "Follow",
            "actor": "https://mastodon.social/users/alice",
            "object": "https://test.example.com/activitypub/actor",
            "id": "https://mastodon.social/activities/123"
        }

        inbox_dir = self.config['directories']['inbox']
        queue_dir = self.config['directories']['inbox_queue']

        activity_file = os.path.join(inbox_dir, 'follow-test.json')
        with open(activity_file, 'w') as f:
            json.dump(follow_activity, f)

        queue_file = os.path.join(queue_dir, 'follow-test.json')
        os.symlink(os.path.abspath(activity_file), queue_file)

        self.assertEqual(len(os.listdir(queue_dir)), 1)

        process_queue(self.config)

        self.assertEqual(len(os.listdir(queue_dir)), 0)
        self.assertTrue(os.path.exists(activity_file))


if __name__ == '__main__':
    unittest.main()
