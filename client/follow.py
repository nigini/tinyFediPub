#!/usr/bin/env python3
"""
CLI tool to send a Follow activity to a remote actor.

Builds the Follow, saves it to the outbox, and queues it for the activity
processor to deliver. Idempotent: short-circuits if already following or
if a Follow to this actor is already pending.
"""

import argparse
import json
import os
import sys
from datetime import datetime, UTC

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from activity_processor import queue_outbox_activity
from data_access import follow as follow_store
from post_utils import generate_activity_id, generate_base_url, load_config
from template_utils import templates


def main():
    parser = argparse.ArgumentParser(description='Send a Follow activity to a remote actor.')
    parser.add_argument('--actor', required=True,
                        help='Target actor URL (e.g., https://mastodon.social/users/alice)')
    args = parser.parse_args()

    config = load_config()
    target_actor = args.actor

    if target_actor in follow_store.get_following(config):
        print(f"⚠ Already following {target_actor}")
        return 0

    existing_pending = follow_store.find_pending_by_target(target_actor, config)
    if existing_pending:
        print(f"⚠ Follow to {target_actor} already pending (activity {existing_pending})")
        return 0

    activity_id = generate_activity_id('follow')
    base_url = generate_base_url(config)
    published = datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')

    activity = templates.render_follow_activity(
        activity_id=f"{base_url}/activities/{activity_id}",
        actor_id=f"{base_url}/actor",
        published=published,
        target_actor=target_actor,
    )

    outbox = config['directories']['outbox']
    os.makedirs(outbox, exist_ok=True)
    filename = f"{activity_id}.json"
    with open(os.path.join(outbox, filename), 'w') as f:
        json.dump(activity, f, indent=2)

    queue_outbox_activity(filename, config)

    print(f"✅ Follow queued for delivery")
    print(f"   Target:      {target_actor}")
    print(f"   Activity ID: {activity_id}")
    print()
    print(f"Run `python -m activity_processor` to deliver pending follows.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
