"""
Like activity processor

Handles:
- Incoming Like: add actor to per-post likes collection, update post.json
- Incoming Undo Like: remove actor from per-post likes collection
"""

import json
import os
from activity_processor import BaseActivityProcessor
from post_utils import generate_base_url, get_post_path, resolve_post_uuid_from_url
from template_utils import templates


def _get_likes_list(post_uuid, config):
    """Load the current likes list for a post, or return empty list."""
    posts_dir = config['directories']['posts']
    likes_path = os.path.join(posts_dir, post_uuid, 'likes.json')

    if os.path.exists(likes_path):
        with open(likes_path, 'r') as f:
            likes_data = json.load(f)
        return likes_data.get('orderedItems', likes_data.get('items', []))

    return []


class LikeProcessor(BaseActivityProcessor):
    """Process incoming Like activities."""

    def _add_like(self, actor_url, post_uuid, config):
        """Add actor to the post's likes collection. Returns True if added, False if duplicate."""
        likes_list = _get_likes_list(post_uuid, config)

        if actor_url in likes_list:
            return False

        likes_list.append(actor_url)

        base_url = generate_base_url(config)
        likes_id = f"{base_url}/posts/{post_uuid}/likes"

        likes_collection = templates.render_likes_collection(
            likes_id=likes_id,
            actors_list=likes_list
        )

        posts_dir = config['directories']['posts']
        likes_path = os.path.join(posts_dir, post_uuid, 'likes.json')
        with open(likes_path, 'w') as f:
            json.dump(likes_collection, f, indent=2)

        return True

    def _update_post_likes_summary(self, post_uuid, likes_count, config):
        """Update the likes collection summary in post.json with current count."""
        post_path = get_post_path(post_uuid, config)

        with open(post_path, 'r') as f:
            post_data = json.load(f)

        base_url = generate_base_url(config)
        post_data['likes'] = {
            "type": "OrderedCollection",
            "id": f"{base_url}/posts/{post_uuid}/likes",
            "totalItems": likes_count
        }

        with open(post_path, 'w') as f:
            json.dump(post_data, f, indent=2)

    def process_inbox(self, activity, filename, config):
        """Process Like activity - add to post's likes collection"""
        try:
            actor_url = activity.get('actor')
            if not actor_url:
                print(f"Like activity missing actor: {filename}")
                return False

            object_url = activity.get('object')
            if not object_url:
                print(f"Like activity missing object: {filename}")
                return False

            post_uuid = resolve_post_uuid_from_url(object_url, config)
            if not post_uuid:
                print(f"Like targets unknown or non-local post: {object_url}")
                return False

            print(f"Processing Like from {actor_url} on post {post_uuid}")

            if self._add_like(actor_url, post_uuid, config):
                print(f"Added {actor_url} to likes for post {post_uuid}")
            else:
                print(f"Like from {actor_url} already exists for post {post_uuid}")

            likes_count = len(_get_likes_list(post_uuid, config))
            self._update_post_likes_summary(post_uuid, likes_count, config)

            print(f"Successfully processed Like from {actor_url}")
            return True

        except Exception as e:
            print(f"Error processing Like activity {filename}: {e}")
            return False


class UndoLikeProcessor(BaseActivityProcessor):
    """Process incoming Undo Like activities."""

    def _remove_like(self, actor_url, post_uuid, config):
        """Remove actor from likes collection. Returns True if removed, False if not found."""
        likes_list = _get_likes_list(post_uuid, config)

        if actor_url not in likes_list:
            return False

        likes_list.remove(actor_url)

        base_url = generate_base_url(config)
        likes_id = f"{base_url}/posts/{post_uuid}/likes"
        likes_collection = templates.render_likes_collection(
            likes_id=likes_id,
            actors_list=likes_list
        )

        posts_dir = config['directories']['posts']
        likes_path = os.path.join(posts_dir, post_uuid, 'likes.json')
        with open(likes_path, 'w') as f:
            json.dump(likes_collection, f, indent=2)

        self._update_post_likes_summary(post_uuid, len(likes_list), config)

        return True

    def _update_post_likes_summary(self, post_uuid, likes_count, config):
        """Update the likes collection summary in post.json."""
        post_path = get_post_path(post_uuid, config)

        with open(post_path, 'r') as f:
            post_data = json.load(f)

        base_url = generate_base_url(config)
        post_data['likes'] = {
            "type": "OrderedCollection",
            "id": f"{base_url}/posts/{post_uuid}/likes",
            "totalItems": likes_count
        }

        with open(post_path, 'w') as f:
            json.dump(post_data, f, indent=2)

    def process_inbox(self, activity, filename, config):
        """Process Undo Like activity - remove from post's likes collection"""
        try:
            actor_url = activity.get('actor')
            if not actor_url:
                print(f"Undo Like activity missing actor: {filename}")
                return False

            object_url = activity.get('object', {}).get('object')
            if not object_url:
                print(f"Undo Like activity missing object: {filename}")
                return False

            post_uuid = resolve_post_uuid_from_url(object_url, config)
            if not post_uuid:
                print(f"Undo Like targets unknown or non-local post: {object_url}")
                return False

            print(f"Processing Undo Like from {actor_url} on post {post_uuid}")

            if self._remove_like(actor_url, post_uuid, config):
                print(f"Removed {actor_url} from likes for post {post_uuid}")
            else:
                print(f"Like from {actor_url} was not found for post {post_uuid}")

            print(f"Successfully processed Undo Like from {actor_url}")
            return True

        except Exception as e:
            print(f"Error processing Undo Like activity {filename}: {e}")
            return False
