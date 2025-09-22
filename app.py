from flask import Flask, jsonify, request
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

def load_json_file(filename):
    """Load JSON data from static files"""
    filepath = os.path.join('static', filename)
    with open(filepath, 'r') as f:
        return json.load(f)

def write_actor_config():
    """Write actor configuration to static/actor.json"""
    actor_config = templates.render_actor(config, PUBLIC_KEY_PEM)
    filepath = os.path.join('static', 'actor.json')
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

@app.route(f'/{NAMESPACE}/outbox')
@require_activitypub_accept
def outbox():
    """Outbox endpoint - collection of activities"""
    response = jsonify(load_json_file('outbox.json'))
    response.headers['Content-Type'] = CONTENT_TYPE_AP
    return response

@app.route(f'/{NAMESPACE}/posts/<post_id>')
@require_activitypub_accept
def post(post_id):
    """Individual post objects"""
    try:
        response = jsonify(load_json_file(f'posts/{post_id}.json'))
        response.headers['Content-Type'] = CONTENT_TYPE_AP
        return response
    except FileNotFoundError:
        return jsonify({'error': 'Post not found'}), 404

@app.route(f'/{NAMESPACE}/activities/<activity_id>')
@require_activitypub_accept
def activity(activity_id):
    """Individual activity objects"""
    try:
        response = jsonify(load_json_file(f'activities/{activity_id}.json'))
        response.headers['Content-Type'] = CONTENT_TYPE_AP
        return response
    except FileNotFoundError:
        return jsonify({'error': 'Activity not found'}), 404

@app.route(f'/{NAMESPACE}/inbox', methods=['POST'])
def inbox():
    """Inbox endpoint - receive activities from other servers"""
    content_type = request.headers.get('Content-Type', '')

    # Basic content type validation
    if CONTENT_TYPE_AP not in content_type and CONTENT_TYPE_LD not in content_type:
        return jsonify({'error': 'Invalid content type'}), 400

    try:
        activity = request.get_json()
        if not activity or 'type' not in activity:
            return jsonify({'error': 'Invalid activity'}), 400

        # Save incoming activity to inbox folder
        save_inbox_activity(activity)

        print(f"Received {activity['type']} activity from {activity.get('actor', 'unknown')}")
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

def ensure_followers_file_exists():
    """Create followers.json if it doesn't exist using template"""
    import os
    from post_utils import get_actor_info

    filepath = 'static/followers.json'
    if not os.path.exists(filepath):
        actor = get_actor_info()
        if actor:
            base_url = actor['id'].rsplit('/actor', 1)[0]
            followers_collection = templates.render_followers_collection(
                followers_id=f"{base_url}/followers"
            )
            os.makedirs('static', exist_ok=True)
            with open(filepath, 'w') as f:
                json.dump(followers_collection, f, indent=2)

def save_inbox_activity(activity):
    """Save incoming activity to inbox folder"""
    from post_utils import generate_activity_id, parse_actor_url

    # Generate filename using utility functions
    activity_type = activity['type']
    actor_url = activity.get('actor', '')
    domain, username = parse_actor_url(actor_url)

    # Create filename: activity-type-timestamp-domain.json
    base_id = generate_activity_id(activity_type)
    filename = f"{base_id}-{domain.replace('.', '-')}.json"

    # Save to inbox folder
    inbox_dir = 'static/inbox'
    os.makedirs(inbox_dir, exist_ok=True)
    filepath = os.path.join(inbox_dir, filename)

    with open(filepath, 'w') as f:
        json.dump(activity, f, indent=2)

    print(f"✓ Saved inbox activity: {filepath}")

if __name__ == '__main__':
    # Generate actor.json on startup
    write_actor_config()
    app.run(debug=config['server']['debug'], 
            host=config['server']['host'], 
            port=config['server']['port'])
