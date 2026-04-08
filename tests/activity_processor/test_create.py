#!/usr/bin/env python3
"""
Unit tests for Create activity processing
"""
import unittest
import os
import json

from tests.test_config import TestConfigMixin


class TestCreateProcessor(unittest.TestCase, TestConfigMixin):
    """Test Create activity processing functionality"""

    def setUp(self):
        self.setup_test_environment("create_processor")

        # We follow alice
        following = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Collection",
            "id": "https://test.example.com/activitypub/following",
            "totalItems": 1,
            "items": ["https://mastodon.social/users/alice"]
        }
        following_path = os.path.join(self.config['directories']['data_root'], 'following.json')
        with open(following_path, 'w') as f:
            json.dump(following, f)

        # Save a Create activity + metadata in inbox (simulating what app.py does)
        self.activity = {
            "type": "Create",
            "actor": "https://mastodon.social/users/alice",
            "object": {
                "type": "Note",
                "id": "https://mastodon.social/users/alice/statuses/12345",
                "content": "Hello from Alice!",
                "attributedTo": "https://mastodon.social/users/alice"
            }
        }
        self.filename = "create-20260407-120000-000000-mastodon-social.json"

        inbox_dir = self.config['directories']['inbox']
        with open(os.path.join(inbox_dir, self.filename), 'w') as f:
            json.dump(self.activity, f)
        with open(os.path.join(inbox_dir, self.filename.replace('.json', '.meta.json')), 'w') as f:
            json.dump({"signed_by": "https://mastodon.social/users/alice#main-key", "received_at": "2026-04-07T12:00:00+00:00"}, f)

    def tearDown(self):
        self.teardown_test_environment()

    def test_create_from_followed_stores_post(self):
        """Create(Note) from followed actor stores object.json and metadata.json"""
        from activity_processor.create import CreateProcessor

        processor = CreateProcessor()
        result = processor.process_inbox(self.activity, self.filename, self.config)
        self.assertTrue(result)

        # Verify object.json stored at URL-derived path
        remote_dir = os.path.join(
            self.config['directories']['posts_remote'],
            'mastodon.social', 'users', 'alice', 'statuses', '12345'
        )
        object_path = os.path.join(remote_dir, 'object.json')
        self.assertTrue(os.path.exists(object_path))

        with open(object_path) as f:
            stored = json.load(f)
        self.assertEqual(stored['type'], 'Note')
        self.assertEqual(stored['content'], 'Hello from Alice!')

        # Verify metadata.json
        metadata_path = os.path.join(remote_dir, 'metadata.json')
        self.assertTrue(os.path.exists(metadata_path))

        with open(metadata_path) as f:
            metadata = json.load(f)
        self.assertEqual(metadata['signed_by'], 'https://mastodon.social/users/alice#main-key')
        self.assertEqual(metadata['accepted_by_rule'], 'following')
        self.assertIn('received_at', metadata)


    def test_create_from_stranger_rejected(self):
        """Create from unknown actor is rejected and not stored"""
        from activity_processor.create import CreateProcessor

        activity = {
            "type": "Create",
            "actor": "https://random.server/users/nobody",
            "object": {
                "type": "Note",
                "id": "https://random.server/users/nobody/statuses/999",
                "content": "Unsolicited content"
            }
        }
        stranger_filename = "create-20260407-130000-000000-random-server.json"

        inbox_dir = self.config['directories']['inbox']
        with open(os.path.join(inbox_dir, stranger_filename), 'w') as f:
            json.dump(activity, f)
        with open(os.path.join(inbox_dir, stranger_filename.replace('.json', '.meta.json')), 'w') as f:
            json.dump({"signed_by": None, "received_at": "2026-04-07T13:00:00+00:00"}, f)

        processor = CreateProcessor()
        result = processor.process_inbox(activity, stranger_filename, self.config)
        self.assertFalse(result)

        # Verify nothing was stored in posts_remote
        remote_dir = os.path.join(
            self.config['directories']['posts_remote'],
            'random.server', 'users', 'nobody', 'statuses', '999'
        )
        self.assertFalse(os.path.exists(remote_dir))


    def test_create_from_trusted_forwarder_stores_post(self):
        """Create from stranger but signed by followed actor is accepted"""
        from activity_processor.create import CreateProcessor

        activity = {
            "type": "Create",
            "actor": "https://other.server/users/bob",
            "object": {
                "type": "Note",
                "id": "https://other.server/users/bob/statuses/777",
                "content": "Forwarded by alice",
                "attributedTo": "https://other.server/users/bob"
            }
        }
        fwd_filename = "create-20260407-140000-000000-other-server.json"

        inbox_dir = self.config['directories']['inbox']
        with open(os.path.join(inbox_dir, fwd_filename), 'w') as f:
            json.dump(activity, f)
        with open(os.path.join(inbox_dir, fwd_filename.replace('.json', '.meta.json')), 'w') as f:
            json.dump({"signed_by": "https://mastodon.social/users/alice#main-key", "received_at": "2026-04-07T14:00:00+00:00"}, f)

        processor = CreateProcessor()
        result = processor.process_inbox(activity, fwd_filename, self.config)
        self.assertTrue(result)

        remote_dir = os.path.join(
            self.config['directories']['posts_remote'],
            'other.server', 'users', 'bob', 'statuses', '777'
        )
        with open(os.path.join(remote_dir, 'metadata.json')) as f:
            metadata = json.load(f)
        self.assertEqual(metadata['accepted_by_rule'], 'trusted_signer')

    def test_create_preserves_integrity_proof(self):
        """Object with FEP-8b32 proof is stored untouched"""
        from activity_processor.create import CreateProcessor

        obj_with_proof = {
            "type": "Note",
            "id": "https://mastodon.social/users/alice/statuses/99999",
            "content": "Signed post",
            "attributedTo": "https://mastodon.social/users/alice",
            "proof": {
                "type": "DataIntegrityProof",
                "cryptosuite": "eddsa-jcs-2022",
                "verificationMethod": "https://mastodon.social/users/alice#ed25519-key",
                "proofPurpose": "assertionMethod",
                "proofValue": "z3hx9MsF..."
            }
        }
        activity = {
            "type": "Create",
            "actor": "https://mastodon.social/users/alice",
            "object": obj_with_proof
        }
        proof_filename = "create-20260407-150000-000000-mastodon-social.json"

        inbox_dir = self.config['directories']['inbox']
        with open(os.path.join(inbox_dir, proof_filename), 'w') as f:
            json.dump(activity, f)
        with open(os.path.join(inbox_dir, proof_filename.replace('.json', '.meta.json')), 'w') as f:
            json.dump({"signed_by": "https://mastodon.social/users/alice#main-key", "received_at": "2026-04-07T15:00:00+00:00"}, f)

        processor = CreateProcessor()
        result = processor.process_inbox(activity, proof_filename, self.config)
        self.assertTrue(result)

        remote_dir = os.path.join(
            self.config['directories']['posts_remote'],
            'mastodon.social', 'users', 'alice', 'statuses', '99999'
        )
        with open(os.path.join(remote_dir, 'object.json')) as f:
            stored = json.load(f)

        # Proof must be preserved exactly
        self.assertIn('proof', stored)
        self.assertEqual(stored['proof']['type'], 'DataIntegrityProof')
        self.assertEqual(stored['proof']['proofValue'], 'z3hx9MsF...')

    def test_create_article_stores_post(self):
        """Create(Article) is also stored correctly"""
        from activity_processor.create import CreateProcessor

        activity = {
            "type": "Create",
            "actor": "https://mastodon.social/users/alice",
            "object": {
                "type": "Article",
                "id": "https://mastodon.social/users/alice/articles/42",
                "name": "My Blog Post",
                "content": "<p>Long form content</p>",
                "attributedTo": "https://mastodon.social/users/alice"
            }
        }
        article_filename = "create-20260407-160000-000000-mastodon-social.json"

        inbox_dir = self.config['directories']['inbox']
        with open(os.path.join(inbox_dir, article_filename), 'w') as f:
            json.dump(activity, f)
        with open(os.path.join(inbox_dir, article_filename.replace('.json', '.meta.json')), 'w') as f:
            json.dump({"signed_by": "https://mastodon.social/users/alice#main-key", "received_at": "2026-04-07T16:00:00+00:00"}, f)

        processor = CreateProcessor()
        result = processor.process_inbox(activity, article_filename, self.config)
        self.assertTrue(result)

        remote_dir = os.path.join(
            self.config['directories']['posts_remote'],
            'mastodon.social', 'users', 'alice', 'articles', '42'
        )
        with open(os.path.join(remote_dir, 'object.json')) as f:
            stored = json.load(f)
        self.assertEqual(stored['type'], 'Article')
        self.assertEqual(stored['name'], 'My Blog Post')

    def test_create_no_metadata_file(self):
        """Create still works if .meta.json is missing (unsigned)"""
        from activity_processor.create import CreateProcessor

        activity = {
            "type": "Create",
            "actor": "https://mastodon.social/users/alice",
            "object": {
                "type": "Note",
                "id": "https://mastodon.social/users/alice/statuses/55555",
                "content": "No metadata file"
            }
        }
        no_meta_filename = "create-20260407-170000-000000-mastodon-social.json"

        inbox_dir = self.config['directories']['inbox']
        with open(os.path.join(inbox_dir, no_meta_filename), 'w') as f:
            json.dump(activity, f)
        # No .meta.json created

        processor = CreateProcessor()
        result = processor.process_inbox(activity, no_meta_filename, self.config)
        self.assertTrue(result)

        remote_dir = os.path.join(
            self.config['directories']['posts_remote'],
            'mastodon.social', 'users', 'alice', 'statuses', '55555'
        )
        self.assertTrue(os.path.exists(os.path.join(remote_dir, 'object.json')))


    def test_duplicate_create_overwrites(self):
        """Receiving the same object URL twice overwrites the stored post"""
        from activity_processor.create import CreateProcessor

        processor = CreateProcessor()
        result1 = processor.process_inbox(self.activity, self.filename, self.config)
        self.assertTrue(result1)

        # Send again with updated content
        updated_activity = json.loads(json.dumps(self.activity))
        updated_activity['object']['content'] = 'Updated content!'

        result2 = processor.process_inbox(updated_activity, self.filename, self.config)
        self.assertTrue(result2)

        remote_dir = os.path.join(
            self.config['directories']['posts_remote'],
            'mastodon.social', 'users', 'alice', 'statuses', '12345'
        )
        with open(os.path.join(remote_dir, 'object.json')) as f:
            stored = json.load(f)
        self.assertEqual(stored['content'], 'Updated content!')

    def test_create_missing_object_id(self):
        """Create with object missing id returns False"""
        from activity_processor.create import CreateProcessor

        activity = {
            "type": "Create",
            "actor": "https://mastodon.social/users/alice",
            "object": {
                "type": "Note",
                "content": "No id field"
            }
        }
        no_id_filename = "create-20260407-180000-000000-mastodon-social.json"

        inbox_dir = self.config['directories']['inbox']
        with open(os.path.join(inbox_dir, no_id_filename), 'w') as f:
            json.dump(activity, f)
        with open(os.path.join(inbox_dir, no_id_filename.replace('.json', '.meta.json')), 'w') as f:
            json.dump({"signed_by": "https://mastodon.social/users/alice#main-key", "received_at": "2026-04-07T18:00:00+00:00"}, f)

        processor = CreateProcessor()
        result = processor.process_inbox(activity, no_id_filename, self.config)
        self.assertFalse(result)

    def test_create_addressed_to_us(self):
        """Create from stranger addressed to us is accepted"""
        from activity_processor.create import CreateProcessor

        activity = {
            "type": "Create",
            "actor": "https://other.server/users/bob",
            "to": ["https://test.example.com/activitypub/actor"],
            "object": {
                "type": "Note",
                "id": "https://other.server/users/bob/statuses/888",
                "content": "Hey, check this out!"
            }
        }
        dm_filename = "create-20260407-190000-000000-other-server.json"

        inbox_dir = self.config['directories']['inbox']
        with open(os.path.join(inbox_dir, dm_filename), 'w') as f:
            json.dump(activity, f)
        with open(os.path.join(inbox_dir, dm_filename.replace('.json', '.meta.json')), 'w') as f:
            json.dump({"signed_by": "https://other.server/users/bob#main-key", "received_at": "2026-04-07T19:00:00+00:00"}, f)

        processor = CreateProcessor()
        result = processor.process_inbox(activity, dm_filename, self.config)
        self.assertTrue(result)

        remote_dir = os.path.join(
            self.config['directories']['posts_remote'],
            'other.server', 'users', 'bob', 'statuses', '888'
        )
        with open(os.path.join(remote_dir, 'metadata.json')) as f:
            metadata = json.load(f)
        self.assertEqual(metadata['accepted_by_rule'], 'addressed_to_us')

    def test_create_reply_to_local_post(self):
        """Create replying to a local post from stranger is accepted"""
        from activity_processor.create import CreateProcessor
        from post_utils import get_local_posts_dir

        # Create a local post to reply to
        local_uuid = "660e8400-e29b-41d4-a716-446655440000"
        local_dir = os.path.join(get_local_posts_dir(self.config), local_uuid)
        os.makedirs(local_dir, exist_ok=True)
        with open(os.path.join(local_dir, 'post.json'), 'w') as f:
            json.dump({"type": "Article", "id": f"https://test.example.com/activitypub/posts/{local_uuid}"}, f)

        activity = {
            "type": "Create",
            "actor": "https://other.server/users/carol",
            "object": {
                "type": "Note",
                "id": "https://other.server/users/carol/statuses/333",
                "content": "Great post!",
                "inReplyTo": f"https://test.example.com/activitypub/posts/{local_uuid}"
            }
        }
        reply_filename = "create-20260407-200000-000000-other-server.json"

        inbox_dir = self.config['directories']['inbox']
        with open(os.path.join(inbox_dir, reply_filename), 'w') as f:
            json.dump(activity, f)
        with open(os.path.join(inbox_dir, reply_filename.replace('.json', '.meta.json')), 'w') as f:
            json.dump({"signed_by": None, "received_at": "2026-04-07T20:00:00+00:00"}, f)

        processor = CreateProcessor()
        result = processor.process_inbox(activity, reply_filename, self.config)
        self.assertTrue(result)

        remote_dir = os.path.join(
            self.config['directories']['posts_remote'],
            'other.server', 'users', 'carol', 'statuses', '333'
        )
        with open(os.path.join(remote_dir, 'metadata.json')) as f:
            metadata = json.load(f)
        self.assertEqual(metadata['accepted_by_rule'], 'reply_to_known_post')

    def test_create_in_registry(self):
        """CreateProcessor is auto-discovered in the processor registry"""
        from activity_processor import PROCESSORS
        from activity_processor.create import CreateProcessor

        self.assertIn('Create', PROCESSORS)
        self.assertIsInstance(PROCESSORS['Create'], CreateProcessor)


if __name__ == '__main__':
    unittest.main()
