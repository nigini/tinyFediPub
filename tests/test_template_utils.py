#!/usr/bin/env python3
"""Tests for template_utils render methods."""

import unittest


class TestRenderFollowActivity(unittest.TestCase):
    """Cover the Follow activity render method."""

    def test_render_follow_activity_basic_shape(self):
        from template_utils import templates

        activity = templates.render_follow_activity(
            activity_id="https://test.example.com/activitypub/activities/follow-abc",
            actor_id="https://test.example.com/activitypub/actor",
            published="2026-05-25T12:00:00Z",
            target_actor="https://mastodon.social/users/alice",
        )

        self.assertEqual(activity["type"], "Follow")
        self.assertEqual(activity["@context"], "https://www.w3.org/ns/activitystreams")
        self.assertEqual(activity["id"], "https://test.example.com/activitypub/activities/follow-abc")
        self.assertEqual(activity["actor"], "https://test.example.com/activitypub/actor")
        self.assertEqual(activity["object"], "https://mastodon.social/users/alice")
        self.assertEqual(activity["published"], "2026-05-25T12:00:00Z")


if __name__ == '__main__':
    unittest.main()
