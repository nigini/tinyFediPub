"""
Create activity processor

Handles:
- Incoming Create: evaluate trust, store remote post with metadata
"""

import json
import os
from activity_processor import BaseActivityProcessor
from post_utils import generate_base_url
from trust import evaluate_create


class CreateProcessor(BaseActivityProcessor):
    """Process incoming Create activities."""

    def _load_inbox_metadata(self, filename, config):
        """Load the sibling .meta.json for an inbox activity."""
        inbox_dir = config['directories']['inbox']
        meta_path = os.path.join(inbox_dir, filename.replace('.json', '.meta.json'))

        if os.path.exists(meta_path):
            with open(meta_path, 'r') as f:
                return json.load(f)

        return {}

    def _store_remote_post(self, obj, metadata, config):
        """Store a remote post's object.json and metadata.json."""
        object_id = obj.get('id', '')
        url_path = object_id.split('://', 1)[-1]

        remote_dir = os.path.join(config['directories']['posts_remote'], url_path)
        os.makedirs(remote_dir, exist_ok=True)

        with open(os.path.join(remote_dir, 'object.json'), 'w') as f:
            json.dump(obj, f, indent=2)

        with open(os.path.join(remote_dir, 'metadata.json'), 'w') as f:
            json.dump(metadata, f, indent=2)

    def process_inbox(self, activity, filename, config):
        """Process Create activity - evaluate trust and store remote post"""
        inbox_meta = self._load_inbox_metadata(filename, config)

        base_url = generate_base_url(config)
        context = {
            "signed_by": inbox_meta.get('signed_by'),
            "our_actor": f"{base_url}/actor"
        }

        decision = evaluate_create(activity, context, config)

        if not decision.accepted:
            print(f"Rejected Create from {activity.get('actor')}: {decision.rule}")
            return False

        obj = activity.get('object', {})
        if not obj.get('id'):
            return False

        metadata = {
            "signed_by": inbox_meta.get('signed_by'),
            "received_at": inbox_meta.get('received_at'),
            "accepted_by_rule": decision.rule
        }

        self._store_remote_post(obj, metadata, config)
        print(f"Stored remote post: {obj.get('id')}")
        return True
