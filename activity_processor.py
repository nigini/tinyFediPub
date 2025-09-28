#!/usr/bin/env python3
"""
Activity Processor for TinyFedi ActivityPub Server

Processes queued activities from the inbox using strategy pattern.
Run as: python activity_processor.py

Queue Structure:
- static/inbox/ - saved activities
- static/inbox/queue/ - symlinks to activities that need processing
"""

import json
import os
from abc import ABC, abstractmethod
from datetime import datetime
from template_utils import templates

# Load configuration
def load_config():
    """Load configuration from config.json"""
    with open('config.json') as f:
        return json.load(f)

config = load_config()


class BaseActivityProcessor(ABC):
    @abstractmethod
    def process(self, activity: dict, filename: str) -> bool:
        """Process the activity. Return True if successful"""
        pass


class FollowActivityProcessor(BaseActivityProcessor):
    def _add_follower(self, actor_url: str) -> bool:
        """Add follower to followers.json collection. Returns True if added, False if already exists."""
        from post_utils import get_followers_list
        followers_list = get_followers_list(config)

        # Check if follower already exists
        if actor_url in followers_list:
            return False

        # Add new follower
        followers_list.append(actor_url)

        # Generate updated followers collection
        from post_utils import generate_base_url
        base_url = generate_base_url(config)
        followers_collection = templates.render_followers_collection(
            followers_id=f"{base_url}/followers",
            followers_list=followers_list
        )

        # Save updated collection
        followers_dir = config['directories']['followers']
        followers_path = os.path.join(followers_dir, 'followers.json')
        with open(followers_path, 'w') as f:
            json.dump(followers_collection, f, indent=2)

        return True

    def _generate_accept_activity(self, original_follow: dict, actor_url: str):
        """Generate Accept activity for the Follow request using template system"""
        from post_utils import generate_activity_id, generate_base_url

        # Generate activity ID using existing pattern
        activity_id = generate_activity_id('accept')
        base_url = generate_base_url(config)

        # Generate Accept activity using template
        accept_activity = templates.render_accept_activity(
            activity_id=f"{base_url}/activities/{activity_id}",
            actor_id=f"{base_url}/actor",
            published=datetime.now().isoformat() + "Z",
            follow_object=original_follow
        )

        # Save Accept activity to activities directory
        activities_dir = config['directories']['activities']
        os.makedirs(activities_dir, exist_ok=True)
        activity_path = os.path.join(activities_dir, f"{activity_id}.json")

        with open(activity_path, 'w') as f:
            json.dump(accept_activity, f, indent=2)

        print(f"Saved Accept activity to {activity_path}")

        # TODO: Send Accept activity to follower's inbox (future implementation)
        # This would involve HTTP POST to actor_url's inbox endpoint

    def process(self, activity: dict, filename: str) -> bool:
        """Process Follow activity - auto-accept and add to followers"""
        try:
            actor_url = activity.get('actor')
            if not actor_url:
                print(f"Follow activity missing actor: {filename}")
                return False

            print(f"Processing Follow from {actor_url}")

            # Only add follower and generate Accept if auto-accept is enabled
            if config['activitypub'].get('auto_accept_follow_requests', True):
                # Add follower to followers.json
                if self._add_follower(actor_url):
                    print(f"Added {actor_url} to followers collection")
                else:
                    print(f"Follower {actor_url} already exists")

                # Generate Accept activity
                self._generate_accept_activity(activity, actor_url)
                print(f"Generated Accept activity for {actor_url}")

                # TODO: Send Accept activity to follower's inbox (future implementation)
            else:
                print(f"Follow request from {actor_url} saved for manual review (auto-accept disabled)")

            print(f"Successfully processed Follow from {actor_url}")
            return True

        except Exception as e:
            print(f"Error processing Follow activity {filename}: {e}")
            return False


class UndoActivityProcessor(BaseActivityProcessor):
    def process(self, activity: dict, filename: str) -> bool:
        """Process Undo activity by delegating to specific undo processors"""
        try:
            actor_url = activity.get('actor')
            undo_object = activity.get('object', {})

            if not actor_url:
                print(f"Undo activity missing actor: {filename}")
                return False

            object_type = undo_object.get('type', 'unknown')
            composite_key = f"Undo.{object_type}"

            # Look for specific undo processor
            processor = PROCESSORS.get(composite_key)
            if processor:
                print(f"Processing {composite_key} from {actor_url}")
                return processor.process(activity, filename)
            else:
                print(f"No processor for {composite_key} from {actor_url} - ignoring")
                return True

        except Exception as e:
            print(f"Error processing Undo activity {filename}: {e}")
            return False


class UndoFollowActivityProcessor(BaseActivityProcessor):
    def _remove_follower(self, actor_url: str) -> bool:
        """Remove follower from followers.json collection. Returns True if removed, False if not found."""
        from post_utils import get_followers_list, generate_base_url
        followers_list = get_followers_list(config)

        # Check if follower exists
        if actor_url not in followers_list:
            return False

        # Remove follower
        followers_list.remove(actor_url)

        # Generate updated followers collection
        base_url = generate_base_url(config)
        followers_collection = templates.render_followers_collection(
            followers_id=f"{base_url}/followers",
            followers_list=followers_list
        )

        # Save updated collection
        followers_dir = config['directories']['followers']
        followers_path = os.path.join(followers_dir, 'followers.json')
        with open(followers_path, 'w') as f:
            json.dump(followers_collection, f, indent=2)

        return True

    def process(self, activity: dict, filename: str) -> bool:
        """Process Undo Follow activity - remove follower"""
        try:
            actor_url = activity.get('actor')

            if not actor_url:
                print(f"Undo Follow activity missing actor: {filename}")
                return False

            print(f"Processing Undo Follow from {actor_url}")

            # Remove follower from followers.json
            if self._remove_follower(actor_url):
                print(f"Removed {actor_url} from followers collection")
            else:
                print(f"Follower {actor_url} was not found in collection")

            print(f"Successfully processed Undo Follow from {actor_url}")
            return True

        except Exception as e:
            print(f"Error processing Undo Follow activity {filename}: {e}")
            return False


# Registry mapping activity types to processors
PROCESSORS = {
    'Follow': FollowActivityProcessor(),
    'Undo': UndoActivityProcessor(),
    'Undo.Follow': UndoFollowActivityProcessor(),
}


def ensure_queue_directory():
    """Ensure the queue directory exists"""
    queue_dir = config['directories']['inbox_queue']
    os.makedirs(queue_dir, exist_ok=True)
    return queue_dir


def main():
    """Process all queued activities"""
    queue_dir = ensure_queue_directory()

    if not os.path.exists(queue_dir):
        print("No queue directory found")
        return

    queue_files = os.listdir(queue_dir)
    if not queue_files:
        print("No activities to process")
        return

    print(f"Processing {len(queue_files)} queued activities...")

    processed_count = 0
    failed_count = 0

    for filename in queue_files:
        filepath = os.path.join(queue_dir, filename)

        try:
            # Load activity from the original file (symlink target)
            real_filepath = os.path.realpath(filepath)
            with open(real_filepath) as f:
                activity = json.load(f)

            activity_type = activity.get('type')
            processor = PROCESSORS.get(activity_type)

            if processor:
                print(f"Processing {activity_type} activity: {filename}")
                success = processor.process(activity, filename)

                if success:
                    # Remove from queue on successful processing
                    os.unlink(filepath)
                    processed_count += 1
                    print(f"✓ Successfully processed {filename}")
                else:
                    failed_count += 1
                    print(f"✗ Failed to process {filename}")
            else:
                print(f"No processor for activity type '{activity_type}' in {filename}")
                # Don't remove unknown activity types from queue
                failed_count += 1

        except Exception as e:
            print(f"Error loading activity {filename}: {e}")
            failed_count += 1

    print(f"\nProcessing complete: {processed_count} processed, {failed_count} failed")


if __name__ == '__main__':
    main()