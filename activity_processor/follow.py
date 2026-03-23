"""
Follow activity processors

Handles:
- Incoming Follow: add follower, generate and deliver Accept
- Incoming Undo Follow: remove follower
"""

import json
import os
from datetime import datetime
from activity_processor import BaseActivityProcessor
from template_utils import templates


class FollowProcessor(BaseActivityProcessor):
    """Process incoming Follow activities."""

    def _add_follower(self, actor_url, config):
        """Add follower to followers.json collection. Returns True if added, False if already exists."""
        from post_utils import get_followers_list, generate_base_url
        followers_list = get_followers_list(config)

        if actor_url in followers_list:
            return False

        followers_list.append(actor_url)

        base_url = generate_base_url(config)
        followers_collection = templates.render_followers_collection(
            followers_id=f"{base_url}/followers",
            followers_list=followers_list
        )

        followers_dir = config['directories']['followers']
        followers_path = os.path.join(followers_dir, 'followers.json')
        with open(followers_path, 'w') as f:
            json.dump(followers_collection, f, indent=2)

        return True

    def _generate_accept_activity(self, original_follow, actor_url, config):
        """Generate Accept activity for the Follow request using template system"""
        from post_utils import generate_activity_id, generate_base_url

        activity_id = generate_activity_id('accept')
        base_url = generate_base_url(config)

        accept_activity = templates.render_accept_activity(
            activity_id=f"{base_url}/activities/{activity_id}",
            actor_id=f"{base_url}/actor",
            published=datetime.now().isoformat() + "Z",
            follow_object=original_follow
        )

        # Save Accept activity to outbox
        outbox_dir = config['directories']['outbox']
        os.makedirs(outbox_dir, exist_ok=True)
        activity_path = os.path.join(outbox_dir, f"{activity_id}.json")

        with open(activity_path, 'w') as f:
            json.dump(accept_activity, f, indent=2)

        print(f"Saved Accept activity to {activity_path}")

        # Deliver Accept activity to follower's inbox
        import activity_delivery
        success = activity_delivery.deliver_to_actor(accept_activity, actor_url, config)
        if success:
            print(f"✓ Delivered Accept activity to {actor_url}")
        else:
            print(f"✗ Failed to deliver Accept activity to {actor_url}")

        return accept_activity

    def process_inbox(self, activity, filename, config):
        """Process Follow activity - auto-accept and add to followers"""
        try:
            actor_url = activity.get('actor')
            if not actor_url:
                print(f"Follow activity missing actor: {filename}")
                return False

            print(f"Processing Follow from {actor_url}")

            if config['activitypub'].get('auto_accept_follow_requests', True):
                if self._add_follower(actor_url, config):
                    print(f"Added {actor_url} to followers collection")
                else:
                    print(f"Follower {actor_url} already exists")

                self._generate_accept_activity(activity, actor_url, config)
                print(f"Generated and delivered Accept activity for {actor_url}")
            else:
                print(f"Follow request from {actor_url} saved for manual review (auto-accept disabled)")

            print(f"Successfully processed Follow from {actor_url}")
            return True

        except Exception as e:
            print(f"Error processing Follow activity {filename}: {e}")
            return False


class UndoFollowProcessor(BaseActivityProcessor):
    """Process incoming Undo Follow activities."""

    def _remove_follower(self, actor_url, config):
        """Remove follower from followers.json collection. Returns True if removed, False if not found."""
        from post_utils import get_followers_list, generate_base_url
        followers_list = get_followers_list(config)

        if actor_url not in followers_list:
            return False

        followers_list.remove(actor_url)

        base_url = generate_base_url(config)
        followers_collection = templates.render_followers_collection(
            followers_id=f"{base_url}/followers",
            followers_list=followers_list
        )

        followers_dir = config['directories']['followers']
        followers_path = os.path.join(followers_dir, 'followers.json')
        with open(followers_path, 'w') as f:
            json.dump(followers_collection, f, indent=2)

        return True

    def process_inbox(self, activity, filename, config):
        """Process Undo Follow activity - remove follower"""
        try:
            actor_url = activity.get('actor')

            if not actor_url:
                print(f"Undo Follow activity missing actor: {filename}")
                return False

            print(f"Processing Undo Follow from {actor_url}")

            if self._remove_follower(actor_url, config):
                print(f"Removed {actor_url} from followers collection")
            else:
                print(f"Follower {actor_url} was not found in collection")

            print(f"Successfully processed Undo Follow from {actor_url}")
            return True

        except Exception as e:
            print(f"Error processing Undo Follow activity {filename}: {e}")
            return False
