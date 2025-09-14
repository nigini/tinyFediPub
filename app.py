from flask import Flask, jsonify, request
import json
import os
from template_utils import templates

app = Flask(__name__)

# Load configuration
def load_config():
    """Load configuration from config.json"""
    with open('config.json', 'r') as f:
        return json.load(f)

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

@app.route('/.well-known/webfinger')
def webfinger():
    """WebFinger endpoint for actor discovery"""
    resource = request.args.get('resource')
    if resource != ACCOUNT:
        return jsonify({'error': 'Resource not found'}), 404
    
    return jsonify(load_json_file('webfinger.json'))

@app.route(f'/{NAMESPACE}/actor')
def actor():
    """Actor profile endpoint"""
    # Content negotiation for ActivityPub
    accept = request.headers.get('Accept', '')
    if CONTENT_TYPE_AP not in accept and CONTENT_TYPE_LD not in accept:
        return jsonify({'error': 'Not acceptable'}), 406
    
    response = jsonify(load_json_file('actor.json'))
    response.headers['Content-Type'] = CONTENT_TYPE_AP
    return response

@app.route(f'/{NAMESPACE}/outbox')
def outbox():
    """Outbox endpoint - collection of activities"""
    accept = request.headers.get('Accept', '')
    if CONTENT_TYPE_AP not in accept and CONTENT_TYPE_LD not in accept:
        return jsonify({'error': 'Not acceptable'}), 406
    
    response = jsonify(load_json_file('outbox.json'))
    response.headers['Content-Type'] = CONTENT_TYPE_AP
    return response

@app.route(f'/{NAMESPACE}/posts/<post_id>')
def post(post_id):
    """Individual post objects"""
    accept = request.headers.get('Accept', '')
    if CONTENT_TYPE_AP not in accept and CONTENT_TYPE_LD not in accept:
        return jsonify({'error': 'Not acceptable'}), 406
    
    try:
        response = jsonify(load_json_file(f'posts/{post_id}.json'))
        response.headers['Content-Type'] = CONTENT_TYPE_AP
        return response
    except FileNotFoundError:
        return jsonify({'error': 'Post not found'}), 404

@app.route(f'/{NAMESPACE}/activities/<activity_id>')
def activity(activity_id):
    """Individual activity objects"""
    accept = request.headers.get('Accept', '')
    if CONTENT_TYPE_AP not in accept and CONTENT_TYPE_LD not in accept:
        return jsonify({'error': 'Not acceptable'}), 406
    
    try:
        response = jsonify(load_json_file(f'activities/{activity_id}.json'))
        response.headers['Content-Type'] = CONTENT_TYPE_AP
        return response
    except FileNotFoundError:
        return jsonify({'error': 'Activity not found'}), 404

if __name__ == '__main__':
    # Generate actor.json on startup
    write_actor_config()
    app.run(debug=config['server']['debug'], 
            host=config['server']['host'], 
            port=config['server']['port'])
