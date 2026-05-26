"""
Accept activity processors

Accept is a generic activity in AS2 — it can accept Follows, Invites, Joins,
Offers, etc. This module ships:

- AcceptProcessor: generic dispatcher (registry key 'Accept'). Inspects the
  inner object's type and delegates to Accept.<innertype> processors.
- AcceptFollowProcessor: handler for Accept(Follow) (registry key 'Accept.Follow').
  Matches the inner Follow against our pending follows and, on a hit, moves
  the target actor from pending to the accepted following list.

When Accept.object is a bare URL string (Mastodon-style — no inner type
available), the dispatcher defaults to Accept.Follow because that is by far
the dominant Accept use case in current fediverse traffic.
"""

from activity_processor import BaseActivityProcessor
from data_access import follow as follow_store


class AcceptProcessor(BaseActivityProcessor):
    """Generic dispatcher: delegate to Accept.<innertype> based on Accept.object."""

    def process_inbox(self, activity, filename, config):
        try:
            actor = activity.get('actor')
            if not actor:
                print(f"Accept activity missing actor: {filename}")
                return False

            obj = activity.get('object')
            inner_type = obj.get('type') if isinstance(obj, dict) else None

            # Bare URL object -> default to Follow (the dominant case)
            composite_key = f"Accept.{inner_type or 'Follow'}"

            from activity_processor import PROCESSORS  # runtime: registry built at import time
            processor = PROCESSORS.get(composite_key)

            if processor:
                print(f"Processing {composite_key} from {actor}")
                return processor.process_inbox(activity, filename, config)

            print(f"No processor for {composite_key} from {actor} — ignoring")
            return True

        except Exception as e:
            print(f"Error processing Accept activity {filename}: {e}")
            return False


class AcceptFollowProcessor(BaseActivityProcessor):
    """Handle Accept(Follow): if it matches a pending Follow we sent, accept it.

    Match strategy (per AP §5.2):
      A) Match Accept.object (or its .id) against our pending Follow activity IDs.
      B) Fall back to Accept.actor against pending targets — handles remotes
         that echo a different/embedded object reference.
    Unmatched Accepts return True so they don't loop in the queue; a log line
    records the miss for inspection.
    """

    def _follow_id_from_object(self, accept_object):
        if isinstance(accept_object, str):
            return accept_object
        if isinstance(accept_object, dict):
            return accept_object.get('id')
        return None

    def _activity_id_from_url(self, url):
        if not url:
            return None
        if '/' in url:
            return url.rsplit('/', 1)[-1]
        return url

    def process_inbox(self, activity, filename, config):
        try:
            accepter = activity.get('actor')

            follow_url = self._follow_id_from_object(activity.get('object'))
            candidate_id = self._activity_id_from_url(follow_url)
            if candidate_id and follow_store.is_pending(candidate_id, config):
                target = follow_store.accept_pending_follow(candidate_id, config)
                print(f"✓ Follow accepted by {accepter}; now following {target}")
                return True

            fallback_id = follow_store.find_pending_by_target(accepter, config)
            if fallback_id:
                target = follow_store.accept_pending_follow(fallback_id, config)
                print(f"✓ Follow accepted by {accepter} (matched by actor); now following {target}")
                return True

            print(f"Accept(Follow) from {accepter} did not match any pending Follow — ignoring")
            return True

        except Exception as e:
            print(f"Error processing Accept(Follow) activity {filename}: {e}")
            return False
