# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a minimal ActivityPub server implementation using Flask. It serves static JSON files to provide basic ActivityPub federation capabilities for publishing blog posts to the fediverse.

## Commands

**Development:**
```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python3 app.py
```

**Testing:**
```bash
# Test webfinger endpoint
curl "http://localhost:5000/.well-known/webfinger?resource=acct:blog@nigini.me"

# Test ActivityPub endpoints (require proper headers)
curl -H "Accept: application/activity+json" http://localhost:5000/activitypub/actor
curl -H "Accept: application/activity+json" http://localhost:5000/activitypub/outbox
curl -H "Accept: application/activity+json" http://localhost:5000/activitypub/posts/hello-world
curl -H "Accept: application/activity+json" http://localhost:5000/activitypub/activities/create-1
```

## Architecture

**URL Structure:**
- All ActivityPub endpoints use the `/activitypub/` namespace (defined by `NAMESPACE` constant)
- WebFinger discovery at `/.well-known/webfinger` (protocol requirement)

**Data Model:**
- **Activities** (`/activitypub/activities/<id>`) - Actions that happened (e.g., Create, Update)
- **Objects** (`/activitypub/posts/<id>`) - The content being acted upon (blog posts)
- **Actor** (`/activitypub/actor`) - The blog identity/profile
- **Outbox** (`/activitypub/outbox`) - Collection of all activities published

**Static Content:**
All responses are served from static JSON files in the `static/` directory:
- `static/webfinger.json` - WebFinger response
- `static/actor.json` - Actor profile 
- `static/outbox.json` - Activity collection (references individual activities)
- `static/activities/` - Individual activity files
- `static/posts/` - Individual post objects

**Content Negotiation:**
ActivityPub endpoints require `application/activity+json` or `application/ld+json` Accept headers. The server returns 406 for other content types.

**Current Limitations:**
- Single hardcoded actor (`acct:blog@nigini.me`)
- No HTTP signature support (placeholder public key)
- No inbox functionality
- Static JSON files only (no database)