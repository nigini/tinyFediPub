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


COMPOUND_PREFIXES = ('Undo', 'Accept', 'Reject')


def _discover_processors():
    """Auto-discover processor classes from files in this package.

    Scans all .py files, finds BaseActivityProcessor subclasses,
    and builds a registry mapping activity types to processor instances.

    Naming convention:
      - FollowProcessor       -> 'Follow'
      - UndoFollowProcessor   -> 'Undo.Follow'
      - AcceptFollowProcessor -> 'Accept.Follow'

    Compound activity types (Undo/Accept/Reject) get split into <prefix>.<innertype>
    keys so a generic dispatcher (e.g. UndoActivityProcessor) can route to them.
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
                for prefix in COMPOUND_PREFIXES:
                    if key.startswith(prefix) and len(key) > len(prefix):
                        key = f"{prefix}.{key[len(prefix):]}"
                        break
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


def ensure_inbox_queue_directory(config):
    """Ensure the inbox queue directory exists."""
    queue_dir = os.path.join(config['directories']['inbox'], 'queue')
    os.makedirs(queue_dir, exist_ok=True)
    return queue_dir


def ensure_outbox_queue_directory(config):
    """Ensure the outbox queue directory exists."""
    queue_dir = os.path.join(config['directories']['outbox'], 'queue')
    os.makedirs(queue_dir, exist_ok=True)
    return queue_dir


def _queue_activity(source_dir, filename):
    """Symlink <source_dir>/queue/<filename> -> <source_dir>/<filename>."""
    queue_dir = os.path.join(source_dir, 'queue')
    os.makedirs(queue_dir, exist_ok=True)
    source_path = os.path.join(source_dir, filename)
    queue_path = os.path.join(queue_dir, filename)
    if not os.path.lexists(queue_path):
        os.symlink(os.path.abspath(source_path), queue_path)
        print(f"✓ Queued activity for processing: {filename}")


def queue_inbox_activity(filename, config):
    """Queue an inbox activity for processing."""
    _queue_activity(config['directories']['inbox'], filename)


def queue_outbox_activity(filename, config):
    """Queue an outbox activity for processing (delivery + side-effects)."""
    _queue_activity(config['directories']['outbox'], filename)


def _process_queue(queue_dir, dispatch_method, label, config):
    """Walk queue_dir; dispatch each activity to processor.<dispatch_method>."""
    if not os.path.exists(queue_dir):
        print(f"No {label} queue directory found")
        return

    queue_files = os.listdir(queue_dir)
    if not queue_files:
        print(f"No {label} activities to process")
        return

    print(f"Processing {len(queue_files)} queued {label} activities...")

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
                try:
                    method = getattr(processor, dispatch_method)
                    success = method(activity, filename, config)
                except NotImplementedError:
                    print(f"Processor for {activity_type} does not handle {label} activities")
                    failed_count += 1
                    continue

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

    print(f"\n{label.capitalize()} processing complete: {processed_count} processed, {failed_count} failed")


def process_inbox_queue(config):
    """Process all queued inbox activities."""
    queue_dir = ensure_inbox_queue_directory(config)
    _process_queue(queue_dir, 'process_inbox', 'inbox', config)


def process_outbox_queue(config):
    """Process all queued outbox activities."""
    queue_dir = ensure_outbox_queue_directory(config)
    _process_queue(queue_dir, 'process_outbox', 'outbox', config)
