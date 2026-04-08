from flask import Flask, jsonify, request
import glob
import json
import os
from template_utils import templates

app = Flask(__name__)

# Load configuration
def load_config():
    """Load configuration from config.json"""
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ Error: config.json not found!")
        print("Please copy the example configuration file and customize it:")
        print("  cp config.json.example config.json")
        print("Then edit config.json with your domain and settings.")
        exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: config.json is not valid JSON: {e}")
        print("Please check the file format and try again.")
        exit(1)

def load_key_file(filename):
    """Load key from file"""
    try:
        with open(filename, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"Warning: Key file {filename} not found. Please generate keys first.")
        return None

config = load_config()

# Configuration
DOMAIN = config['server']['domain']
USERNAME = config['activitypub']['username']
ACCOUNT = f'acct:{USERNAME}@{DOMAIN}'
ACTOR_NAME = config['activitypub']['actor_name']
ACTOR_SUMMARY = config['activitypub']['actor_summary']
PUBLIC_KEY_PEM = load_key_file(config['security']['public_key_file'])
PRIVATE_KEY_PEM = load_key_file(config['security']['private_key_file'])
PROTOCOL = config['server'].get('protocol', 'https')
WEBSITE_URL = f'{PROTOCOL}://{DOMAIN}'

NAMESPACE = config['activitypub']['namespace']
CONTENT_TYPE_AP = 'application/activity+json'
CONTENT_TYPE_LD = 'application/ld+json; profile="https://www.w3.org/ns/activitystreams"'
CORS_ORIGINS = config['security'].get('cors_origins', [])

@app.after_request
def add_cors_headers(response):
    """Add CORS headers for configured origins (tinyHome browser access)"""
    origin = request.headers.get('Origin')
    if origin and origin in CORS_ORIGINS:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Headers'] = 'Authorization, Content-Type, Accept'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response

def load_json_file(filename):
    """Load JSON data from data_root or followers directory"""
    if filename == 'followers.json':
        base_dir = config['directories']['followers']
    else:
        base_dir = config['directories']['data_root']

    filepath = os.path.join(base_dir, filename)
    with open(filepath, 'r') as f:
        return json.load(f)

def write_actor_config():
    """Write actor configuration to actor.json"""
    actor_config = templates.render_actor(config, PUBLIC_KEY_PEM)
    data_root = config['directories']['data_root']
    filepath = os.path.join(data_root, 'actor.json')
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w') as f:
        json.dump(actor_config, f, indent=2)
    print(f"Generated actor.json with domain: {DOMAIN}, username: {USERNAME}")

def require_activitypub_accept(f):
    """Decorator to validate Accept header for ActivityPub content negotiation"""
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        accept = request.headers.get('Accept', '')
        if CONTENT_TYPE_AP not in accept and CONTENT_TYPE_LD not in accept:
            return jsonify({'error': 'Not acceptable'}), 406
        return f(*args, **kwargs)
    return decorated_function

def require_c2s_auth(f):
    """Decorator to validate Bearer token for C2S endpoints"""
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        token = config['security'].get('c2s_token')
        if not token or token == 'REPLACE_ME':
            return jsonify({'error': 'C2S token not configured'}), 500
        if auth != f'Bearer {token}':
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/.well-known/webfinger')
def webfinger():
    """WebFinger endpoint for actor discovery"""
    resource = request.args.get('resource')
    if resource != ACCOUNT:
        return jsonify({'error': 'Resource not found'}), 404
    
    return jsonify(load_json_file('webfinger.json'))

@app.route(f'/{NAMESPACE}/actor')
@require_activitypub_accept
def actor():
    """Actor profile endpoint"""
    response = jsonify(load_json_file('actor.json'))
    response.headers['Content-Type'] = CONTENT_TYPE_AP
    return response

def list_json_files(pattern, sort_key='name', reverse=True):
    """List JSON files matching a glob pattern, sorted. Does NOT load them.

    Args:
        pattern: Glob pattern (e.g., 'data/outbox/*.json' or 'data/posts/*/post.json')
        sort_key: 'name' for filename sort, 'mtime' for modification time
        reverse: True for reverse (most recent first)

    Returns:
        list of file paths, sorted
    """
    paths = glob.glob(pattern)
    if sort_key == 'mtime':
        paths.sort(key=os.path.getmtime, reverse=reverse)
    else:
        paths.sort(reverse=reverse)
    return paths

def load_json_files(filepaths):
    """Load JSON from a list of file paths. Skips files that fail to parse."""
    items = []
    for filepath in filepaths:
        try:
            with open(filepath, 'r') as f:
                items.append(json.load(f))
        except (json.JSONDecodeError, FileNotFoundError):
            continue
    return items

def paginate_collection(all_paths, collection_url):
    """Paginate a sorted list of file paths: slice first, then load only the page.

    Reads ?page= and ?limit= from Flask request context.
    Returns an OrderedCollection dict with pagination links.
    """
    max_page_size = config['activitypub'].get('max_page_size', 20)
    page_size = request.args.get('limit', max_page_size, type=int)
    page_size = max(1, min(page_size, max_page_size))

    total_items = len(all_paths)

    page = request.args.get('page', 1, type=int)
    page = max(1, page)
    start = (page - 1) * page_size
    page_paths = all_paths[start:start + page_size]

    items = load_json_files(page_paths)

    next_page = f"{collection_url}?page={page + 1}" if start + page_size < total_items else None
    prev_page = f"{collection_url}?page={page - 1}" if page > 1 else None

    return templates.render_outbox_collection(
        outbox_id=collection_url,
        total_items=total_items,
        items=items,
        next_page=next_page,
        prev_page=prev_page
    )

@app.route(f'/{NAMESPACE}/outbox', methods=['GET', 'POST'])
def outbox():
    """Outbox endpoint - GET returns activities, POST creates new content (C2S)"""
    if request.method == 'GET':
        return outbox_get()
    else:
        return outbox_post()

@require_activitypub_accept
def outbox_get():
    """GET outbox - paginated collection of activities (public, for S2S)"""
    outbox_dir = config['directories']['outbox']
    os.makedirs(outbox_dir, exist_ok=True)
    paths = list_json_files(os.path.join(outbox_dir, '*.json'))
    base_url = f"{PROTOCOL}://{DOMAIN}/{NAMESPACE}/outbox"

    response = jsonify(paginate_collection(paths, base_url))
    response.headers['Content-Type'] = CONTENT_TYPE_AP
    return response

@require_c2s_auth
def outbox_post():
    """POST outbox - accept AS2 object, wrap in Create activity (C2S, authenticated)"""
    from post_utils import create_post, create_activity, generate_base_url

    data = request.get_json(silent=True)
    if not data or 'type' not in data:
        return jsonify({'error': 'Invalid object: missing type'}), 400

    obj_type = data['type'].lower()
    content = data.get('content', '')
    title = data.get('name')
    url = data.get('url', '')
    summary = data.get('summary')

    post_type = 'article' if obj_type == 'article' else 'note'
    post_obj, post_id = create_post(post_type, title, content, url, summary)
    activity_obj, activity_id = create_activity(post_obj, post_id)

    base_url = generate_base_url(config)
    activity_url = f"{base_url}/activities/{activity_id}"

    response = jsonify(activity_obj)
    response.status_code = 201
    response.headers['Location'] = activity_url
    response.headers['Content-Type'] = CONTENT_TYPE_AP
    return response

@app.route(f'/{NAMESPACE}/posts/<post_id>')
@require_activitypub_accept
def post(post_id):
    """Individual post objects"""
    try:
        from post_utils import get_post_path, load_config as load_post_config
        post_path = get_post_path(post_id, load_post_config())
        with open(post_path, 'r') as f:
            post_data = json.load(f)
        response = jsonify(post_data)
        response.headers['Content-Type'] = CONTENT_TYPE_AP
        return response
    except FileNotFoundError:
        return jsonify({'error': 'Post not found'}), 404

@app.route(f'/{NAMESPACE}/posts/<post_id>/likes')
@require_activitypub_accept
def post_likes(post_id):
    """Likes collection for a post"""
    from post_utils import get_post_path, load_config as load_post_config

    post_path = get_post_path(post_id, load_post_config())

    if not os.path.exists(post_path):
        return jsonify({'error': 'Post not found'}), 404

    likes_path = os.path.join(os.path.dirname(post_path), 'likes.json')
    if not os.path.exists(likes_path):
        return jsonify({'error': 'No likes collection'}), 404

    with open(likes_path, 'r') as f:
        likes_data = json.load(f)

    response = jsonify(likes_data)
    response.headers['Content-Type'] = CONTENT_TYPE_AP
    return response

@app.route(f'/{NAMESPACE}/posts/<post_id>/shares')
@require_activitypub_accept
def post_shares(post_id):
    """Shares collection for a post"""
    from post_utils import get_post_path, load_config as load_post_config

    post_path = get_post_path(post_id, load_post_config())

    if not os.path.exists(post_path):
        return jsonify({'error': 'Post not found'}), 404

    shares_path = os.path.join(os.path.dirname(post_path), 'shares.json')
    if not os.path.exists(shares_path):
        return jsonify({'error': 'No shares collection'}), 404

    with open(shares_path, 'r') as f:
        shares_data = json.load(f)

    response = jsonify(shares_data)
    response.headers['Content-Type'] = CONTENT_TYPE_AP
    return response

@app.route(f'/{NAMESPACE}/activities/<activity_id>')
@require_activitypub_accept
def activity(activity_id):
    """Individual activity objects"""
    try:
        outbox_dir = config['directories']['outbox']
        filepath = os.path.join(outbox_dir, f'{activity_id}.json')
        with open(filepath, 'r') as f:
            activity_data = json.load(f)
        response = jsonify(activity_data)
        response.headers['Content-Type'] = CONTENT_TYPE_AP
        return response
    except FileNotFoundError:
        return jsonify({'error': 'Activity not found'}), 404

@app.route(f'/{NAMESPACE}/inbox', methods=['POST'])
def inbox():
    """Inbox endpoint - receive activities from other servers"""
    from http_signatures import verify_request

    content_type = request.headers.get('Content-Type', '')

    # Basic content type validation
    if CONTENT_TYPE_AP not in content_type and CONTENT_TYPE_LD not in content_type:
        return jsonify({'error': 'Invalid content type'}), 400

    try:
        # Get raw request body and headers
        body = request.get_data()
        headers_dict = dict(request.headers)

        # Check for signature header
        signature_header = headers_dict.get('Signature')
        require_signatures = config['security'].get('require_http_signatures', False)
        signed_by = None

        if signature_header:
            # Signature present - verify it
            if not verify_request(signature_header, request.method, request.path, headers_dict, body):
                print("✗ Invalid signature - rejecting request")
                return jsonify({'error': 'Invalid signature'}), 401
            print("✓ Signature verified")
            # Extract signer identity for metadata
            from http_signatures import parse_signature_header
            sig_components = parse_signature_header(signature_header)
            signed_by = sig_components.get('keyId')
        elif require_signatures:
            # No signature but required - reject
            print("⚠️  No signature and signatures required - rejecting request")
            return jsonify({'error': 'Signature required'}), 401
        else:
            # No signature but not required - accept with warning
            print("⚠️  Accepting unsigned request (signature verification disabled)")

        # Parse activity (we already have the body)
        activity = request.get_json()
        if not activity or 'type' not in activity:
            return jsonify({'error': 'Invalid activity'}), 400

        # Save incoming activity to inbox folder
        filename = save_inbox_activity(activity, signed_by=signed_by)

        # Queue activity for processing by creating symlink
        queue_activity_for_processing(filename)

        actor = activity.get('actor', 'unknown')
        verified_status = "✓ verified" if signature_header else "⚠️  unverified"
        print(f"Received {verified_status} {activity['type']} activity from {actor}")
        return '', 202  # Accepted

    except Exception as e:
        print(f"Inbox error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route(f'/{NAMESPACE}/followers')
@require_activitypub_accept
def followers():
    """Followers collection endpoint"""
    ensure_followers_file_exists()

    response = jsonify(load_json_file('followers.json'))
    response.headers['Content-Type'] = CONTENT_TYPE_AP
    return response

@app.route(f'/{NAMESPACE}/streams/posts')
@require_c2s_auth
@require_activitypub_accept
def streams_posts():
    """Streams/posts endpoint - paginated collection of post objects (not activities)"""
    from post_utils import get_local_posts_dir
    posts_dir = get_local_posts_dir(config)
    os.makedirs(posts_dir, exist_ok=True)
    paths = list_json_files(os.path.join(posts_dir, '*/post.json'), sort_key='mtime')
    base_url = f"{PROTOCOL}://{DOMAIN}/{NAMESPACE}/streams/posts"

    response = jsonify(paginate_collection(paths, base_url))
    response.headers['Content-Type'] = CONTENT_TYPE_AP
    return response

def ensure_followers_file_exists():
    """Create followers.json if it doesn't exist using template"""
    import os
    from post_utils import get_actor_info

    followers_dir = config['directories']['followers']
    filepath = os.path.join(followers_dir, 'followers.json')
    if not os.path.exists(filepath):
        actor = get_actor_info()
        if actor:
            base_url = actor['id'].rsplit('/actor', 1)[0]
            followers_collection = templates.render_followers_collection(
                followers_id=f"{base_url}/followers"
            )
            os.makedirs(followers_dir, exist_ok=True)
            with open(filepath, 'w') as f:
                json.dump(followers_collection, f, indent=2)

def save_inbox_activity(activity, signed_by=None):
    """Save incoming activity to inbox folder with sibling metadata file"""
    from datetime import datetime, timezone
    from post_utils import generate_activity_id, parse_actor_url

    # Generate filename using utility functions
    activity_type = activity['type']
    actor_url = activity.get('actor', '')
    domain, username = parse_actor_url(actor_url)

    # Create filename: activity-type-timestamp-domain.json
    base_id = generate_activity_id(activity_type)
    filename = f"{base_id}-{domain.replace('.', '-')}.json"

    # Save to inbox folder
    inbox_dir = config['directories']['inbox']
    os.makedirs(inbox_dir, exist_ok=True)
    filepath = os.path.join(inbox_dir, filename)

    with open(filepath, 'w') as f:
        json.dump(activity, f, indent=2)

    # Save metadata alongside
    meta_path = filepath.replace('.json', '.meta.json')
    metadata = {
        "signed_by": signed_by,
        "received_at": datetime.now(timezone.utc).isoformat()
    }
    with open(meta_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"✓ Saved inbox activity: {filepath}")
    return filename

def queue_activity_for_processing(filename):
    """Queue activity for processing by creating symlink in queue directory"""
    queue_dir = os.path.join(config['directories']['inbox'], 'queue')
    inbox_dir = config['directories']['inbox']

    os.makedirs(queue_dir, exist_ok=True)

    source_path = os.path.join(inbox_dir, filename)
    queue_path = os.path.join(queue_dir, filename)

    # Create symlink if it doesn't exist
    if not os.path.exists(queue_path):
        os.symlink(os.path.abspath(source_path), queue_path)
        print(f"✓ Queued activity for processing: {filename}")

if __name__ == '__main__':
    # Generate actor.json on startup
    write_actor_config()
    app.run(debug=config['server']['debug'], 
            host=config['server']['host'], 
            port=config['server']['port'])
