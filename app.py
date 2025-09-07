from flask import Flask, jsonify, request
import json
import os

app = Flask(__name__)

# Configuration
DOMAIN = '127.0.0.1:5000'
USERNAME = 'blog'
ACCOUNT = f'acct:{USERNAME}@{DOMAIN}'
ACTOR_NAME = "localhost's blog"
ACTOR_SUMMARY = "A personal blog with federated posts"
PUBLIC_KEY_PEM = "-----BEGIN PUBLIC KEY-----\n(your public key here)\n-----END PUBLIC KEY-----"
WEBSITE_URL = f'http://{DOMAIN}'

NAMESPACE = 'activitypub'
CONTENT_TYPE_AP = 'application/activity+json'
CONTENT_TYPE_LD = 'application/ld+json; profile="https://www.w3.org/ns/activitystreams"'

def load_json_file(filename):
    """Load JSON data from static files"""
    filepath = os.path.join('static', filename)
    with open(filepath, 'r') as f:
        return json.load(f)

def generate_actor_config():
    """Generate actor.json content from configuration"""
    actor_template = {
        "@context": "https://www.w3.org/ns/activitystreams",
        "type": "Person",
        "id": f"{WEBSITE_URL}/{NAMESPACE}/actor",
        "preferredUsername": USERNAME,
        "name": ACTOR_NAME,
        "summary": ACTOR_SUMMARY,
        "inbox": f"{WEBSITE_URL}/{NAMESPACE}/inbox",
        "outbox": f"{WEBSITE_URL}/{NAMESPACE}/outbox",
        "followers": f"{WEBSITE_URL}/{NAMESPACE}/followers",
        "following": f"{WEBSITE_URL}/{NAMESPACE}/following",
        "url": WEBSITE_URL,
        "publicKey": {
            "id": f"{WEBSITE_URL}/{NAMESPACE}/actor#main-key",
            "owner": f"{WEBSITE_URL}/{NAMESPACE}/actor",
            "publicKeyPem": PUBLIC_KEY_PEM
        }
    }
    return actor_template

def write_actor_config():
    """Write actor configuration to static/actor.json"""
    actor_config = generate_actor_config()
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
    app.run(debug=True, host='0.0.0.0', port=5000)
