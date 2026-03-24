"""
Like activity processor

Handles:
- Incoming Like: add actor to per-post likes collection, update post.json
"""

import json
import os
from activity_processor import BaseActivityProcessor
from post_utils import generate_base_url, get_post_path
from template_utils import templates


class LikeProcessor(BaseActivityProcessor):
    """Process incoming Like activities."""

    def _resolve_post_uuid(self, object_url, config):
        """Extract post UUID from object URL if it's a local post.

        Returns the UUID string, or None if not a local post or not found.
        """
        base_url = generate_base_url(config)
        posts_prefix = f"{base_url}/posts/"

        if not object_url.startswith(posts_prefix):
            return None

        post_uuid = object_url[len(posts_prefix):].strip('/')
        post_path = get_post_path(post_uuid, config)

        if not os.path.exists(post_path):
            return None

        return post_uuid

    def _get_likes_list(self, post_uuid, config):
        """Load the current likes list for a post, or return empty list."""
        posts_dir = config['directories']['posts']
        likes_path = os.path.join(posts_dir, post_uuid, 'likes.json')

        if os.path.exists(likes_path):
            with open(likes_path, 'r') as f:
                likes_data = json.load(f)
            return likes_data.get('items', [])

        return []

    def _add_like(self, actor_url, post_uuid, config):
        """Add actor to the post's likes collection. Returns True if added, False if duplicate."""
        likes_list = self._get_likes_list(post_uuid, config)

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

    def _update_post_likes_field(self, post_uuid, config):
        """Add likes collection URL to post.json if not already present."""
        post_path = get_post_path(post_uuid, config)

        with open(post_path, 'r') as f:
            post_data = json.load(f)

        base_url = generate_base_url(config)
        likes_url = f"{base_url}/posts/{post_uuid}/likes"

        if post_data.get('likes') != likes_url:
            post_data['likes'] = likes_url
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

            post_uuid = self._resolve_post_uuid(object_url, config)
            if not post_uuid:
                print(f"Like targets unknown or non-local post: {object_url}")
                return False

            print(f"Processing Like from {actor_url} on post {post_uuid}")

            if self._add_like(actor_url, post_uuid, config):
                print(f"Added {actor_url} to likes for post {post_uuid}")
            else:
                print(f"Like from {actor_url} already exists for post {post_uuid}")

            self._update_post_likes_field(post_uuid, config)

            print(f"Successfully processed Like from {actor_url}")
            return True

        except Exception as e:
            print(f"Error processing Like activity {filename}: {e}")
            return False
