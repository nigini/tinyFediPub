# tinyFedi.pub

A minimalist ActivityPub server designed for easy integration with personal websites.

## Overview

Simple file-based ActivityPub implementation that serves federated content from static JSON files. Perfect for personal blogs and small websites wanting to join the fediverse without complex infrastructure.

## Tech Stack

- **Flask** - Lightweight web framework
- **Jinja2** - Template engine for ActivityPub entities
- **File-based storage** - All content served from static JSON files
- **Zero dependencies** - Minimal external requirements

## Setup

### 1. Generate Cryptographic Keys

ActivityPub requires public/private key pairs for secure federation:

```bash
mkdir keys
openssl genrsa -out keys/private_key.pem 2048
openssl rsa -in keys/private_key.pem -pubout -out keys/public_key.pem
```

### 2. Configuration

All settings are externalized in `config.json`:

```json
{
  "server": {
    "domain": "yourdomain.com",
    "host": "0.0.0.0", 
    "port": 5000,
    "debug": false
  },
  "activitypub": {
    "username": "blog",
    "actor_name": "Your Blog Name",
    "actor_summary": "Description of your blog",
    "namespace": "activitypub"
  },
  "security": {
    "public_key_file": "keys/public_key.pem",
    "private_key_file": "keys/private_key.pem"
  }
}
```

**Security Note:** Keys are automatically excluded from version control via `.gitignore`.

## Deployment

Designed to run behind a reverse proxy alongside existing websites:

```nginx
location /activitypub/ {
    proxy_pass http://localhost:5000/activitypub/;
}
```

## Usage

1. Update `config.json` with your domain and actor details
2. Run `python app.py` 
3. Actor profile auto-generates from config on startup
4. Add posts using the CLI: `./new_post.py --title "Post Title" --content "Content" --url "https://yourblog.com/post"`

## Development

### Running Tests

Install dependencies and run the test suite:

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

### Creating Posts

Use the CLI tool to create new ActivityPub posts:

```bash
./new_post.py --title "My Post" --content "Post content" --url "https://myblog.com/my-post" --summary "Optional summary"
```

This automatically:
- Creates the post JSON in `static/posts/`
- Generates the Create activity in `static/activities/`
- Regenerates the outbox collection

## Template System

ActivityPub entities are generated using Jinja2 templates for maintainability and extensibility:

```
templates/
├── objects/          # ActivityStreams Object types
│   ├── actor.json.j2      # Person/Service actors
│   ├── article.json.j2    # Blog posts, articles
│   └── note.json.j2       # Short messages (future)
├── activities/       # ActivityStreams Activity types
│   ├── create.json.j2     # Create activities
│   └── update.json.j2     # Update activities (future)
└── collections/      # ActivityStreams Collections
    └── outbox.json.j2     # Outbox collections (future)
```

**Design Philosophy:**
- **Type-specific templates** - Each ActivityStreams type has its own template
- **Extensible** - Easy to add new object types (Note, Image, Event) and activity types (Like, Follow, Announce)
- **Spec-compliant** - Templates ensure proper ActivityPub/ActivityStreams structure
- **Configurable** - All values injected from `config.json` and runtime data

Current implementation supports `Article` objects and `Create` activities, with template structure ready for future ActivityStreams types.