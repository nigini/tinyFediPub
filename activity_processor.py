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
    def process(self, activity: dict, filename: str) -> bool:
        """Process Follow activity - auto-accept and add to followers"""
        try:
            actor_url = activity.get('actor')
            if not actor_url:
                print(f"Follow activity missing actor: {filename}")
                return False

            print(f"Processing Follow from {actor_url}")

            # TODO: Add follower to followers.json
            # TODO: Generate Accept activity
            # TODO: Send Accept activity to follower's inbox

            print(f"Successfully processed Follow from {actor_url}")
            return True

        except Exception as e:
            print(f"Error processing Follow activity {filename}: {e}")
            return False


class UndoActivityProcessor(BaseActivityProcessor):
    def process(self, activity: dict, filename: str) -> bool:
        """Process Undo activity - remove follower if it's undoing a Follow"""
        try:
            actor_url = activity.get('actor')
            undo_object = activity.get('object', {})

            if not actor_url:
                print(f"Undo activity missing actor: {filename}")
                return False

            if undo_object.get('type') == 'Follow':
                print(f"Processing Undo Follow from {actor_url}")

                # TODO: Remove follower from followers.json

                print(f"Successfully processed Undo Follow from {actor_url}")
                return True
            else:
                print(f"Ignoring Undo of {undo_object.get('type', 'unknown')} from {actor_url}")
                return True

        except Exception as e:
            print(f"Error processing Undo activity {filename}: {e}")
            return False


# Registry mapping activity types to processors
PROCESSORS = {
    'Follow': FollowActivityProcessor(),
    'Undo': UndoActivityProcessor(),
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