#!/usr/bin/env python3
"""Tests for data_access.follow — followers, following, pending."""

import json
import os
import unittest

from tests.test_config import TestConfigMixin


class TestFollowersFollowing(unittest.TestCase, TestConfigMixin):
    """Tests for the followers and following helpers."""

    def setUp(self):
        self.setup_test_environment("data_access_follow")

    def tearDown(self):
        self.teardown_test_environment()

    def _write_followers_file(self, payload):
        path = os.path.join(self.config['directories']['data_root'], 'followers.json')
        with open(path, 'w') as f:
            json.dump(payload, f)

    def test_get_followers_empty_when_no_file(self):
        from data_access.follow import get_followers
        self.assertEqual(get_followers(self.config), [])

    def test_add_follower_creates_collection_and_returns_true(self):
        from data_access.follow import add_follower, get_followers
        self.assertTrue(add_follower("https://example.com/alice", self.config))
        self.assertEqual(get_followers(self.config), ["https://example.com/alice"])
        self.assert_file_exists("data_root", "followers.json")

    def test_add_follower_writes_orderedcollection_shape(self):
        from data_access.follow import add_follower
        add_follower("https://example.com/alice", self.config)
        path = os.path.join(self.config['directories']['data_root'], 'followers.json')
        with open(path) as f:
            data = json.load(f)
        self.assertEqual(data['type'], 'OrderedCollection')
        self.assertEqual(data['orderedItems'], ["https://example.com/alice"])
        self.assertEqual(data['totalItems'], 1)

    def test_add_follower_duplicate_returns_false(self):
        from data_access.follow import add_follower, get_followers
        add_follower("https://example.com/alice", self.config)
        self.assertFalse(add_follower("https://example.com/alice", self.config))
        self.assertEqual(get_followers(self.config), ["https://example.com/alice"])

    def test_remove_follower_removes_and_returns_true(self):
        from data_access.follow import add_follower, remove_follower, get_followers
        add_follower("https://example.com/alice", self.config)
        self.assertTrue(remove_follower("https://example.com/alice", self.config))
        self.assertEqual(get_followers(self.config), [])

    def test_remove_follower_not_found_returns_false(self):
        from data_access.follow import remove_follower
        self.assertFalse(remove_follower("https://example.com/ghost", self.config))

    def test_get_followers_reads_legacy_items_fallback(self):
        from data_access.follow import get_followers
        self._write_followers_file({
            "type": "Collection",
            "items": ["https://example.com/legacy"],
            "totalItems": 1,
        })
        self.assertEqual(get_followers(self.config), ["https://example.com/legacy"])

    def test_following_helpers_mirror_followers(self):
        from data_access.follow import add_following, get_following
        self.assertTrue(add_following("https://example.com/bob", self.config))
        self.assertFalse(add_following("https://example.com/bob", self.config))
        self.assertEqual(get_following(self.config), ["https://example.com/bob"])
        path = os.path.join(self.config['directories']['data_root'], 'following.json')
        with open(path) as f:
            data = json.load(f)
        self.assertEqual(data['type'], 'OrderedCollection')
        self.assertTrue(data['id'].endswith('/following'))


class TestPendingFollows(unittest.TestCase, TestConfigMixin):
    """Tests for pending-follow helpers (add/is/find/accept)."""

    def setUp(self):
        self.setup_test_environment("data_access_follow_pending")

    def tearDown(self):
        self.teardown_test_environment()

    def _write_follow_in_outbox(self, activity_id, target_actor, object_as_dict=False):
        """Create a fake Follow activity file in the outbox."""
        target = {"id": target_actor, "type": "Person"} if object_as_dict else target_actor
        activity = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Follow",
            "id": f"https://test.example.com/activitypub/activities/{activity_id}",
            "actor": "https://test.example.com/activitypub/actor",
            "object": target,
        }
        path = os.path.join(self.config['directories']['outbox'], f"{activity_id}.json")
        with open(path, 'w') as f:
            json.dump(activity, f)
        return path

    def test_add_pending_follow_creates_symlink(self):
        from data_access.follow import add_pending_follow, is_pending
        self._write_follow_in_outbox("follow-aaa", "https://example.com/alice")
        self.assertTrue(add_pending_follow("follow-aaa", self.config))
        self.assertTrue(is_pending("follow-aaa", self.config))

    def test_add_pending_follow_duplicate_returns_false(self):
        from data_access.follow import add_pending_follow
        self._write_follow_in_outbox("follow-bbb", "https://example.com/bob")
        self.assertTrue(add_pending_follow("follow-bbb", self.config))
        self.assertFalse(add_pending_follow("follow-bbb", self.config))

    def test_is_pending_false_when_no_pending_dir(self):
        from data_access.follow import is_pending
        self.assertFalse(is_pending("follow-never", self.config))

    def test_find_pending_by_target_finds_match(self):
        from data_access.follow import add_pending_follow, find_pending_by_target
        self._write_follow_in_outbox("follow-ccc", "https://example.com/carol")
        add_pending_follow("follow-ccc", self.config)
        self.assertEqual(
            find_pending_by_target("https://example.com/carol", self.config),
            "follow-ccc",
        )

    def test_find_pending_by_target_handles_embedded_object(self):
        """target may be passed as an embedded {id, type, ...} dict in the Follow."""
        from data_access.follow import add_pending_follow, find_pending_by_target
        self._write_follow_in_outbox("follow-ddd", "https://example.com/dan", object_as_dict=True)
        add_pending_follow("follow-ddd", self.config)
        self.assertEqual(
            find_pending_by_target("https://example.com/dan", self.config),
            "follow-ddd",
        )

    def test_find_pending_by_target_returns_none_when_no_match(self):
        from data_access.follow import find_pending_by_target
        self.assertIsNone(find_pending_by_target("https://example.com/ghost", self.config))

    def test_accept_pending_follow_moves_to_following(self):
        from data_access.follow import accept_pending_follow, add_pending_follow, get_following, is_pending
        self._write_follow_in_outbox("follow-eee", "https://example.com/eve")
        add_pending_follow("follow-eee", self.config)

        target = accept_pending_follow("follow-eee", self.config)

        self.assertEqual(target, "https://example.com/eve")
        self.assertFalse(is_pending("follow-eee", self.config))
        self.assertEqual(get_following(self.config), ["https://example.com/eve"])

    def test_accept_pending_follow_unknown_returns_none(self):
        from data_access.follow import accept_pending_follow
        self.assertIsNone(accept_pending_follow("follow-nope", self.config))

    def test_accept_pending_follow_dangling_symlink_cleans_up(self):
        from data_access.follow import accept_pending_follow, add_pending_follow, is_pending
        outbox_path = self._write_follow_in_outbox("follow-fff", "https://example.com/frank")
        add_pending_follow("follow-fff", self.config)
        os.unlink(outbox_path)  # break the symlink

        self.assertIsNone(accept_pending_follow("follow-fff", self.config))
        self.assertFalse(is_pending("follow-fff", self.config))


if __name__ == '__main__':
    unittest.main()
