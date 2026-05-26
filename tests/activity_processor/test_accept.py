#!/usr/bin/env python3
"""Tests for AcceptProcessor (dispatcher) and AcceptFollowProcessor (Follow handler)."""

import json
import os
import unittest
from unittest.mock import patch

from tests.test_config import TestConfigMixin


class TestAcceptProcessorDispatcher(unittest.TestCase, TestConfigMixin):
    """AcceptProcessor delegates to Accept.<innertype> processors."""

    def setUp(self):
        self.setup_test_environment("accept_dispatcher")

    def tearDown(self):
        self.teardown_test_environment()

    def test_processors_registered(self):
        from activity_processor import PROCESSORS, AcceptProcessor, AcceptFollowProcessor
        self.assertIn('Accept', PROCESSORS)
        self.assertIn('Accept.Follow', PROCESSORS)
        self.assertIsInstance(PROCESSORS['Accept'], AcceptProcessor)
        self.assertIsInstance(PROCESSORS['Accept.Follow'], AcceptFollowProcessor)

    def test_dispatches_to_follow_when_inner_type_is_follow(self):
        from activity_processor import AcceptProcessor

        accept = {
            "type": "Accept",
            "actor": "https://example.com/alice",
            "object": {"type": "Follow", "id": "https://test.example.com/activitypub/activities/follow-xyz"},
        }
        with patch.dict('activity_processor.PROCESSORS', {}, clear=False) as procs:
            # Replace the Accept.Follow with a sentinel to detect dispatch
            from activity_processor import AcceptFollowProcessor
            sentinel = AcceptFollowProcessor()
            with patch.object(sentinel, 'process_inbox', return_value=True) as spy:
                procs['Accept.Follow'] = sentinel
                result = AcceptProcessor().process_inbox(accept, "accept.json", self.config)
                self.assertTrue(result)
                spy.assert_called_once()

    def test_defaults_to_follow_when_object_is_bare_url(self):
        """Bare-URL Accept (Mastodon-style) defaults to Accept.Follow."""
        from activity_processor import AcceptProcessor, AcceptFollowProcessor

        accept = {
            "type": "Accept",
            "actor": "https://example.com/alice",
            "object": "https://test.example.com/activitypub/activities/follow-xyz",
        }
        with patch.dict('activity_processor.PROCESSORS', {}, clear=False) as procs:
            sentinel = AcceptFollowProcessor()
            with patch.object(sentinel, 'process_inbox', return_value=True) as spy:
                procs['Accept.Follow'] = sentinel
                AcceptProcessor().process_inbox(accept, "accept.json", self.config)
                spy.assert_called_once()

    def test_unhandled_inner_type_returns_true_with_log(self):
        from activity_processor import AcceptProcessor

        accept = {
            "type": "Accept",
            "actor": "https://example.com/alice",
            "object": {"type": "Invite", "id": "https://example.com/invites/123"},
        }
        with patch('builtins.print') as mock_print:
            result = AcceptProcessor().process_inbox(accept, "accept.json", self.config)
            self.assertTrue(result)
            call_args = [c.args[0] for c in mock_print.call_args_list]
            self.assertTrue(any('No processor for Accept.Invite' in a for a in call_args))

    def test_missing_actor_returns_false(self):
        from activity_processor import AcceptProcessor

        result = AcceptProcessor().process_inbox(
            {"type": "Accept", "object": "x"}, "accept.json", self.config
        )
        self.assertFalse(result)


class TestAcceptFollowProcessor(unittest.TestCase, TestConfigMixin):
    """AcceptFollowProcessor matches Accepts against pending follows we sent."""

    def setUp(self):
        self.setup_test_environment("accept_follow")

    def tearDown(self):
        self.teardown_test_environment()

    def _write_pending_follow(self, activity_id, target_actor):
        outbox = self.config['directories']['outbox']
        activity = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Follow",
            "id": f"https://test.example.com/activitypub/activities/{activity_id}",
            "actor": "https://test.example.com/activitypub/actor",
            "object": target_actor,
        }
        with open(os.path.join(outbox, f"{activity_id}.json"), 'w') as f:
            json.dump(activity, f)
        from data_access.follow import add_pending_follow
        add_pending_follow(activity_id, self.config)
        return activity

    def test_matched_by_string_id(self):
        from activity_processor import AcceptFollowProcessor
        from data_access.follow import get_following, is_pending

        self._write_pending_follow("follow-aaa", "https://example.com/alice")
        accept = {
            "type": "Accept",
            "actor": "https://example.com/alice",
            "object": "https://test.example.com/activitypub/activities/follow-aaa",
        }
        result = AcceptFollowProcessor().process_inbox(accept, "accept.json", self.config)
        self.assertTrue(result)
        self.assertFalse(is_pending("follow-aaa", self.config))
        self.assertEqual(get_following(self.config), ["https://example.com/alice"])

    def test_matched_by_embedded_object(self):
        from activity_processor import AcceptFollowProcessor
        from data_access.follow import get_following, is_pending

        follow = self._write_pending_follow("follow-bbb", "https://example.com/bob")
        accept = {"type": "Accept", "actor": "https://example.com/bob", "object": follow}
        result = AcceptFollowProcessor().process_inbox(accept, "accept.json", self.config)
        self.assertTrue(result)
        self.assertFalse(is_pending("follow-bbb", self.config))
        self.assertEqual(get_following(self.config), ["https://example.com/bob"])

    def test_fallback_to_actor_pair_when_id_unknown(self):
        from activity_processor import AcceptFollowProcessor
        from data_access.follow import get_following, is_pending

        self._write_pending_follow("follow-ccc", "https://example.com/carol")
        accept = {
            "type": "Accept",
            "actor": "https://example.com/carol",
            "object": "https://other.example/activities/something-unknown",
        }
        result = AcceptFollowProcessor().process_inbox(accept, "accept.json", self.config)
        self.assertTrue(result)
        self.assertFalse(is_pending("follow-ccc", self.config))
        self.assertEqual(get_following(self.config), ["https://example.com/carol"])

    def test_unmatched_accept_returns_true_changes_nothing(self):
        from activity_processor import AcceptFollowProcessor
        from data_access.follow import get_following

        accept = {
            "type": "Accept",
            "actor": "https://example.com/eve",
            "object": "https://example.com/activities/unknown",
        }
        result = AcceptFollowProcessor().process_inbox(accept, "accept.json", self.config)
        self.assertTrue(result)
        self.assertEqual(get_following(self.config), [])


if __name__ == '__main__':
    unittest.main()
