"""
Activity Processor module for TinyFedi ActivityPub Server

Processes queued activities using strategy pattern.
Run as: python -m activity_processor

Processors are auto-discovered from .py files in this package.
Naming convention:
  - FollowProcessor       -> registry key 'Follow'
  - UndoFollowProcessor   -> registry key 'Undo.Follow'
"""

import json
import os
import importlib
import pkgutil
import sys
from abc import ABC


class BaseActivityProcessor(ABC):
    """Base class for all activity processors.

    Subclasses implement process_inbox and/or process_outbox.
    Config is passed as a parameter, not stored as module state.
    """

    def process_inbox(self, activity: dict, filename: str, config: dict) -> bool:
        """Process an incoming activity. Return True if successful."""
        raise NotImplementedError(f"{self.__class__.__name__} does not handle inbox activities")

    def process_outbox(self, activity: dict, filename: str, config: dict) -> bool:
        """Process an outgoing activity. Return True if successful."""
        raise NotImplementedError(f"{self.__class__.__name__} does not handle outbox activities")


def _discover_processors():
    """Auto-discover processor classes from files in this package.

    Scans all .py files, finds BaseActivityProcessor subclasses,
    and builds a registry mapping activity types to processor instances.

    Naming convention:
      - FollowProcessor       -> 'Follow'
      - UndoFollowProcessor   -> 'Undo.Follow'
    """
    registry = {}
    package_dir = os.path.dirname(__file__)

    for _, module_name, _ in pkgutil.iter_modules([package_dir]):
        if module_name.startswith('__'):
            continue
        module = importlib.import_module(f".{module_name}", package=__name__)
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type)
                    and issubclass(attr, BaseActivityProcessor)
                    and attr is not BaseActivityProcessor):
                key = attr_name.replace('Processor', '')
                if key.startswith('Undo') and len(key) > 4:
                    key = f"Undo.{key[4:]}"
                registry[key] = attr()

    return registry


# Build the processor registry from discovered classes
PROCESSORS = _discover_processors()

# Re-export discovered processor classes at package level
_this_module = sys.modules[__name__]
for _proc in PROCESSORS.values():
    setattr(_this_module, type(_proc).__name__, type(_proc))


class UndoActivityProcessor(BaseActivityProcessor):
    """Delegates Undo activities to specific Undo.{type} processors."""

    def process_inbox(self, activity: dict, filename: str, config: dict) -> bool:
        try:
            actor_url = activity.get('actor')
            undo_object = activity.get('object', {})

            if not actor_url:
                print(f"Undo activity missing actor: {filename}")
                return False

            object_type = undo_object.get('type', 'unknown')
            composite_key = f"Undo.{object_type}"

            processor = PROCESSORS.get(composite_key)
            if processor:
                print(f"Processing {composite_key} from {actor_url}")
                return processor.process_inbox(activity, filename, config)
            else:
                print(f"No processor for {composite_key} from {actor_url} - ignoring")
                return True

        except Exception as e:
            print(f"Error processing Undo activity {filename}: {e}")
            return False


PROCESSORS['Undo'] = UndoActivityProcessor()
setattr(_this_module, 'UndoActivityProcessor', UndoActivityProcessor)


def ensure_queue_directory(config):
    """Ensure the queue directory exists"""
    queue_dir = os.path.join(config['directories']['inbox'], 'queue')
    os.makedirs(queue_dir, exist_ok=True)
    return queue_dir


def process_queue(config):
    """Process all queued activities"""
    queue_dir = ensure_queue_directory(config)

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
            real_filepath = os.path.realpath(filepath)
            with open(real_filepath) as f:
                activity = json.load(f)

            activity_type = activity.get('type')
            processor = PROCESSORS.get(activity_type)

            if processor:
                print(f"Processing {activity_type} activity: {filename}")
                success = processor.process_inbox(activity, filename, config)

                if success:
                    os.unlink(filepath)
                    processed_count += 1
                    print(f"✓ Successfully processed {filename}")
                else:
                    failed_count += 1
                    print(f"✗ Failed to process {filename}")
            else:
                print(f"No processor for activity type '{activity_type}' in {filename}")
                failed_count += 1

        except Exception as e:
            print(f"Error loading activity {filename}: {e}")
            failed_count += 1

    print(f"\nProcessing complete: {processed_count} processed, {failed_count} failed")
