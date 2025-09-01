from flask import Flask, jsonify, request
import json
import os

app = Flask(__name__)

NAMESPACE = 'activitypub'
CONTENT_TYPE_AP = 'application/activity+json'
CONTENT_TYPE_LD = 'application/ld+json; profile="https://www.w3.org/ns/activitystreams"'

def load_json_file(filename):
    """Load JSON data from static files"""
    filepath = os.path.join('static', filename)
    with open(filepath, 'r') as f:
        return json.load(f)

@app.route('/.well-known/webfinger')
def webfinger():
    """WebFinger endpoint for actor discovery"""
    resource = request.args.get('resource')
    if resource != 'acct:blog@nigini.me':
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
    app.run(debug=True, host='0.0.0.0', port=5000)