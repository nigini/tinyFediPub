"""
Trust rules for evaluating incoming activities.

Each rule answers its own semantic question (e.g., is_blocked, is_following)
and returns True/False. The evaluator in __init__.py interprets the answers.
"""

import json
import os


def is_blocked(actor_url, domain, config):
    """Is this actor or domain in the block list?"""
    blocked_path = os.path.join(config['directories']['data_root'], 'blocked.json')

    if not os.path.exists(blocked_path):
        return False

    with open(blocked_path, 'r') as f:
        blocked = json.load(f)

    if actor_url in blocked.get('actors', []):
        return True

    if domain in blocked.get('domains', []):
        return True

    return False


def is_following(actor_url, config):
    """Are we following this actor?"""
    following_path = os.path.join(config['directories']['data_root'], 'following.json')

    if not os.path.exists(following_path):
        return False

    with open(following_path, 'r') as f:
        following = json.load(f)

    return actor_url in following.get('items', [])


def is_addressed_to_us(activity, our_actor):
    """Is our actor in the activity's to or cc fields?"""
    to = activity.get('to', [])
    cc = activity.get('cc', [])
    return our_actor in to or our_actor in cc


def is_reply_to_known_post(activity, config):
    """Is this a reply to a post we already have (local or remote)?"""
    obj = activity.get('object', {})
    in_reply_to = obj.get('inReplyTo')

    if not in_reply_to:
        return False

    # Check local posts
    from post_utils import resolve_post_uuid_from_url
    if resolve_post_uuid_from_url(in_reply_to, config):
        return True

    # Check remote posts — path derived from URL
    url_path = in_reply_to.split('://', 1)[-1]
    object_path = os.path.join(config['directories']['posts_remote'], url_path, 'object.json')
    if os.path.exists(object_path):
        return True

    return False


def is_trusted_signer(signed_by, config):
    """Is the HTTP signature from someone we trust (follow)?

    Particularly useful for forwarded activities (AP §7.1.2), where the HTTP
    signer differs from the activity's actor. If we trust the signer, we accept
    the activity even though we don't follow the author.
    """
    if not signed_by:
        return False

    actor_url = signed_by.split('#')[0]
    return is_following(actor_url, config)
