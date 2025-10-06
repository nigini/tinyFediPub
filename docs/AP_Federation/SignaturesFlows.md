# ActivityPub and HTTP Signatures

- SOURCE: https://swicg.github.io/activitypub-http-signature/
- VERSION: 03 August 2025

## Flow Chart - HTTP Signature Process

 ```mermaid
  sequenceDiagram
      participant M as Fediverse Server
      participant Y as TinyFedi
      participant MA as Fediverse Actor Endpoint

      Note over M,Y: INCOMING REQUEST (Verification)

      M->>M: 1. Create Follow activity
      M->>M: 2. Compute SHA-256 digest of body
      M->>M: 3. Build signing string:<br/>"(request-target): post /inbox<br/>host: yourserver.com<br/>date: Mon, 01 Jan 2025...<br/>digest: SHA-256=abc123...<br/>content-type: application/activity+json"
      M->>M: 4. Sign with private key
      M->>M: 5. Add Signature header
      M->>Y: POST /inbox with Signature header

      Y->>Y: 6. Parse Signature header<br/>(extract keyId, signature, headers)
      Y->>MA: 7. Fetch public key from keyId URL
      MA->>Y: 8. Return actor document with publicKeyPem
      Y->>Y: 9. Rebuild same signing string from request
      Y->>Y: 10. Verify signature using public key

      alt Signature Valid
          Y->>Y: 11. Process activity
          Y->>M: 202 Accepted
      else Signature Invalid
          Y->>M: 401 Unauthorized
      end

      Note over M,Y: OUTGOING REQUEST (Signing)

      Y->>Y: 1. Generate Accept activity
      Y->>Y: 2. Compute SHA-256 digest of body
      Y->>Y: 3. Build signing string
      Y->>Y: 4. Sign with YOUR private key
      Y->>Y: 5. Add Signature header
      Y->>M: POST to follower's inbox with Signature

      M->>Y: 6. Fetch YOUR public key
      Y->>M: 7. Return your actor with publicKeyPem
      M->>M: 8. Verify signature
      M->>Y: 202 Accepted
```

## Step-by-Step Breakdown

### Incoming: Someone sends YOU an activity

 ```mermaid
  flowchart TD
      A[Receive POST to /inbox] --> B{Has Signature header?}
      B -->|No| Z1[Reject: 401]
      B -->|Yes| C[Parse Signature header]

      C --> D[Extract keyId from Signature]
      D --> E[Fetch actor document from keyId URL]
      E --> F[Extract publicKeyPem from actor]

      F --> G[Get request components:<br/>- Method: POST<br/>- Path: /inbox<br/>- Headers: host, date, digest<br/>- Body: raw bytes]

      G --> H[Build signing string:<br/>Join headers in specific order]

      H --> I[Decode signature from base64]

      I --> J[Verify signature:<br/>public_key.verify signature, signing_string]

      J -->|Valid| K{Digest matches body?}
      J -->|Invalid| Z2[Reject: 401]

      K -->|Yes| L{Date is recent?}
      K -->|No| Z3[Reject: 401]

      L -->|Yes| M[✓ Accept and process activity]
      L -->|No| Z4[Reject: 401 replay attack]
  ```

### Outgoing: YOU send an activity to someone

 ```mermaid
  flowchart TD
      A[Generate Accept activity] --> B[Convert to JSON bytes]
      B --> C[Compute SHA-256 digest of body]
      C --> D[Build headers:<br/>- host: mastodon.social<br/>- date: current time<br/>- digest: SHA-256=...<br/>- content-type: application/json]

      D --> E[Build signing string from headers]
      E --> F[Sign with YOUR private key]
      F --> G[Encode signature as base64]
      G --> H[Create Signature header:<br/>keyId, algorithm, headers, signature]

      H --> I[POST to follower's inbox]
      I --> J[They verify using YOUR public key]
      J --> K[✓ Activity delivered]
  ```

### The "Why" - Security Benefits

  1. Authentication: Proves the request came from the claimed actor
  2. Integrity: Body can't be modified in transit (digest check)
  3. Anti-replay: Old requests can't be reused (date check)
  4. Non-repudiation: Can't deny sending it (cryptographic proof)

  The Magic Ingredient: Asymmetric Cryptography

  Private Key (secret)  →  Signs messages
  Public Key (published) →  Verifies signatures

  - Only YOU can create signatures with your private key
  - ANYONE can verify with your public key
  - Can't derive private key from public key (RSA math magic)

