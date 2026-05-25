"""
data_access.follow — Follow relationships: followers, following, pending.

Public API operates on actor URLs and activity IDs. Storage layout is an
implementation detail.

Current implementation: JSON OrderedCollections for the followers/following
collections, plus a pending-follows directory containing symlinks to the
sent Follow activity for each request awaiting Accept.
"""

import json
import os
from post_utils import generate_base_url
from template_utils import templates


def _followers_path(config):
    return os.path.join(config['directories']['data_root'], 'followers.json')


def _following_path(config):
    return os.path.join(config['directories']['data_root'], 'following.json')


def _pending_dir(config):
    return os.path.join(config['directories']['data_root'], 'following_pending')


def _outbox_dir(config):
    return config['directories']['outbox']


def _load_collection(path):
    """Read an OrderedCollection (or legacy Collection) file. Returns a list."""
    if not os.path.exists(path):
        return []
    with open(path, 'r') as f:
        data = json.load(f)
    return data.get('orderedItems', data.get('items', []))


def _save_collection(path, collection_id, items):
    """Render and write an OrderedCollection file."""
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    collection = templates.render_ordered_collection(collection_id, items)
    with open(path, 'w') as f:
        json.dump(collection, f, indent=2)


def get_followers(config):
    """Return the list of accepted follower actor URLs."""
    return _load_collection(_followers_path(config))


def add_follower(actor_url, config):
    """Add actor to followers. Returns True if added, False if already present."""
    followers = get_followers(config)
    if actor_url in followers:
        return False
    followers.append(actor_url)
    _save_collection(_followers_path(config), f"{generate_base_url(config)}/followers", followers)
    return True


def remove_follower(actor_url, config):
    """Remove actor from followers. Returns True if removed, False if not found."""
    followers = get_followers(config)
    if actor_url not in followers:
        return False
    followers.remove(actor_url)
    _save_collection(_followers_path(config), f"{generate_base_url(config)}/followers", followers)
    return True


def get_following(config):
    """Return the list of accepted following actor URLs."""
    return _load_collection(_following_path(config))


def add_following(actor_url, config):
    """Add actor to following. Returns True if added, False if already present."""
    following = get_following(config)
    if actor_url in following:
        return False
    following.append(actor_url)
    _save_collection(_following_path(config), f"{generate_base_url(config)}/following", following)
    return True


def add_pending_follow(activity_id, config):
    """Register a sent Follow as pending acceptance.

    Returns True if newly registered, False if already pending.
    """
    pending_dir = _pending_dir(config)
    os.makedirs(pending_dir, exist_ok=True)
    activity_file = os.path.join(_outbox_dir(config), f"{activity_id}.json")
    pending_link = os.path.join(pending_dir, f"{activity_id}.json")
    if os.path.lexists(pending_link):
        return False
    os.symlink(os.path.abspath(activity_file), pending_link)
    return True


def is_pending(activity_id, config):
    """Has a Follow with this activity_id been sent and not yet Accepted/Rejected?"""
    pending_link = os.path.join(_pending_dir(config), f"{activity_id}.json")
    return os.path.lexists(pending_link)


def _read_pending_target(pending_link):
    """Read the Follow activity behind a pending link and return its target actor."""
    with open(pending_link, 'r') as f:
        follow = json.load(f)
    target = follow.get('object')
    if isinstance(target, dict):
        target = target.get('id')
    return target


def find_pending_by_target(target_actor, config):
    """Return the activity_id of a pending Follow targeting this actor, or None."""
    pending_dir = _pending_dir(config)
    if not os.path.isdir(pending_dir):
        return None
    for filename in os.listdir(pending_dir):
        link = os.path.join(pending_dir, filename)
        try:
            if _read_pending_target(link) == target_actor:
                return filename.removesuffix('.json')
        except (OSError, json.JSONDecodeError):
            continue
    return None


def accept_pending_follow(activity_id, config):
    """Move a pending Follow into the accepted following list.

    Returns the target_actor that was accepted, or None if no pending follow
    with this activity_id exists (or its activity file is missing/corrupt).
    """
    pending_link = os.path.join(_pending_dir(config), f"{activity_id}.json")
    if not os.path.lexists(pending_link):
        return None
    try:
        target = _read_pending_target(pending_link)
    except (OSError, json.JSONDecodeError):
        target = None
    os.unlink(pending_link)
    if target:
        add_following(target, config)
    return target
