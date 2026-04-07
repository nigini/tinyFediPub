"""
Announce activity processor

Handles:
- Incoming Announce: add actor to per-post shares collection, update post.json
- Incoming Undo Announce: remove actor from per-post shares collection
"""

import json
import os
from activity_processor import BaseActivityProcessor
from post_utils import generate_base_url, get_post_path, resolve_post_uuid_from_url
from template_utils import templates


def _get_shares_list(post_uuid, config):
    """Load the current shares list for a post, or return empty list."""
    posts_dir = config['directories']['posts']
    shares_path = os.path.join(posts_dir, post_uuid, 'shares.json')

    if os.path.exists(shares_path):
        with open(shares_path, 'r') as f:
            shares_data = json.load(f)
        return shares_data.get('orderedItems', shares_data.get('items', []))

    return []


class AnnounceProcessor(BaseActivityProcessor):
    """Process incoming Announce activities."""

    def _add_share(self, actor_url, post_uuid, config):
        """Add actor to the post's shares collection. Returns True if added, False if duplicate."""
        shares_list = _get_shares_list(post_uuid, config)

        if actor_url in shares_list:
            return False

        shares_list.append(actor_url)

        base_url = generate_base_url(config)
        shares_id = f"{base_url}/posts/{post_uuid}/shares"

        shares_collection = templates.render_ordered_collection(shares_id, shares_list)

        posts_dir = config['directories']['posts']
        shares_path = os.path.join(posts_dir, post_uuid, 'shares.json')
        with open(shares_path, 'w') as f:
            json.dump(shares_collection, f, indent=2)

        return True

    def _update_post_shares_summary(self, post_uuid, shares_count, config):
        """Update the shares collection summary in post.json with current count."""
        post_path = get_post_path(post_uuid, config)

        with open(post_path, 'r') as f:
            post_data = json.load(f)

        base_url = generate_base_url(config)
        post_data['shares'] = {
            "type": "OrderedCollection",
            "id": f"{base_url}/posts/{post_uuid}/shares",
            "totalItems": shares_count
        }

        with open(post_path, 'w') as f:
            json.dump(post_data, f, indent=2)

    def process_inbox(self, activity, filename, config):
        """Process Announce activity - add to post's shares collection"""
        try:
            actor_url = activity.get('actor')
            if not actor_url:
                print(f"Announce activity missing actor: {filename}")
                return False

            object_url = activity.get('object')
            if not object_url:
                print(f"Announce activity missing object: {filename}")
                return False

            post_uuid = resolve_post_uuid_from_url(object_url, config)
            if not post_uuid:
                print(f"Announce targets unknown or non-local post: {object_url}")
                return False

            print(f"Processing Announce from {actor_url} on post {post_uuid}")

            if self._add_share(actor_url, post_uuid, config):
                print(f"Added {actor_url} to shares for post {post_uuid}")
            else:
                print(f"Share from {actor_url} already exists for post {post_uuid}")

            shares_count = len(_get_shares_list(post_uuid, config))
            self._update_post_shares_summary(post_uuid, shares_count, config)

            print(f"Successfully processed Announce from {actor_url}")
            return True

        except Exception as e:
            print(f"Error processing Announce activity {filename}: {e}")
            return False


class UndoAnnounceProcessor(BaseActivityProcessor):
    """Process incoming Undo Announce activities."""

    def _remove_share(self, actor_url, post_uuid, config):
        """Remove actor from shares collection. Returns True if removed."""
        shares_list = _get_shares_list(post_uuid, config)

        if actor_url not in shares_list:
            return False

        shares_list.remove(actor_url)

        base_url = generate_base_url(config)
        shares_id = f"{base_url}/posts/{post_uuid}/shares"
        shares_collection = templates.render_ordered_collection(shares_id, shares_list)

        posts_dir = config['directories']['posts']
        shares_path = os.path.join(posts_dir, post_uuid, 'shares.json')
        with open(shares_path, 'w') as f:
            json.dump(shares_collection, f, indent=2)

        self._update_post_shares_summary(post_uuid, len(shares_list), config)

        return True

    def _update_post_shares_summary(self, post_uuid, shares_count, config):
        """Update the shares collection summary in post.json."""
        post_path = get_post_path(post_uuid, config)

        with open(post_path, 'r') as f:
            post_data = json.load(f)

        base_url = generate_base_url(config)
        post_data['shares'] = {
            "type": "OrderedCollection",
            "id": f"{base_url}/posts/{post_uuid}/shares",
            "totalItems": shares_count
        }

        with open(post_path, 'w') as f:
            json.dump(post_data, f, indent=2)

    def process_inbox(self, activity, filename, config):
        """Process Undo Announce activity - remove from post's shares collection"""
        actor_url = activity.get('actor')
        if not actor_url:
            return False

        object_url = activity.get('object', {}).get('object')
        if not object_url:
            return False

        post_uuid = resolve_post_uuid_from_url(object_url, config)
        if not post_uuid:
            return False

        self._remove_share(actor_url, post_uuid, config)
        return True
