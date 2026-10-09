# Behavioral specification

## API contracts and validation

All timestamps are UTC ISO 8601. User and file identifiers are UUIDs. JSON inputs
reject unknown fields. Validation errors return 422 with `detail` entries containing
`loc`, `msg`, and `type`; never echo submitted password values. Other errors use
`{"detail": "message"}`. Dependency failures return 503 with `Service unavailable`;
unexpected failures return 500 with `Internal server error`, without internal details.

User profile: `id`, `name`, `email`, `created_at`. File metadata: `id`, `filename`,
`content_type`, `size_bytes`, `created_at`. No password data, storage key, bucket,
or owner identifier appears in either file responses or profile password fields.

## Registration (R01, R02)

`POST /users` accepts JSON `name`, `email`, `password`, all required strings.
Trim name and email; name must contain 1–100 characters after trimming. Email
must be a syntactically valid mailbox of at most 254 characters; lowercase the
entire trimmed address for uniqueness, storage, and login. Password is 8–128
characters, used exactly as supplied without trimming; do not impose complexity rules.

Success returns 201 and the user profile. Store only a secure, salted password
hash. Registration does not return a token. Invalid input returns 422 and creates
no user. A duplicate normalized email returns 409 with `Email already registered`,
including concurrent attempts: at most one user can be created for that address.
Hashing or persistence failure returns 503 and no successful registration response.

## Login (R03)

`POST /auth/login` accepts JSON `email` and `password` with the same validation
and normalization rules. Valid credentials return 200 with `access_token` (JWT),
`token_type` (`bearer`), and `expires_in` (3600 seconds). Unknown email and wrong
password both return 401 with `Invalid credentials` and `WWW-Authenticate: Bearer`.
Malformed input returns 422. Credential or token dependencies failing return 503.

## Authentication (R04)

Protected endpoints require `Authorization: Bearer <access_token>` (scheme is
case-insensitive). The token identifies one registered user and expires one hour
after issuance. Signature, expiry, expected issuer and audience must be verified;
required subject and expiry claims must be present and valid. A token's subject
must be a user UUID belonging to an existing user. Tokens must not contain password data.

Missing, malformed, tampered, expired, incorrectly signed, wrong issuer/audience,
missing/invalid claims, or unknown-user tokens all return 401 with `Not authenticated`
and `WWW-Authenticate: Bearer`. Expiry is exclusive: at or after expiry the token
is invalid. Authentication runs before file lookup or storage operations. Dependency
failure while resolving the user returns 503 rather than misreporting bad credentials.

## Current user (R05)

`GET /me` returns 200 and the authenticated user's profile. No caller-supplied
user identifier can select another profile. Authentication failures follow the
authentication contract.

## File upload (R06, R07, R12)

`POST /files` accepts multipart form data containing one required `file` field.
The authenticated user becomes the owner; clients cannot supply an owner. Accept
arbitrary content types, defaulting to `application/octet-stream` when absent.
Filename is required, 1–255 characters, with no slash, backslash, or control
characters. Empty content is allowed. Limit content to 10 MiB (10,485,760 bytes),
including streamed uploads without a declared content length. Invalid filename or
missing file returns 422; oversized content returns 413 with `File too large`.

On success, content exists privately in S3 and PostgreSQL metadata records the
file ID, owner ID, storage locator, filename, content type, byte size, and creation
time. Return 201 with file metadata only after both operations succeed. Repeated
filenames create separate files; client filenames must not select storage locations.

If storage upload fails, return 503 and create no metadata. If metadata persistence
fails after storage succeeds, return 503, leave no committed metadata, and attempt
to remove uploaded content. If cleanup also fails, still return 503 and record a
sanitized diagnostic for operator cleanup; an orphan may remain. This API does not
promise atomicity between PostgreSQL and S3 or automatic orphan reconciliation.

## File listing (R08, R11)

`GET /files` returns 200 with a JSON array of only the authenticated user's file
metadata, ordered by `created_at` ascending then ID ascending. An empty list is
`[]`. No pagination or owner selector is supported. Persistence failure returns 503.

## File retrieval (R09, R11)

`GET /files/{file_id}` returns 200 with owned file metadata. It does not return
file content or a storage URL. Missing and other-user UUIDs both return 404 with
`File not found`. A malformed UUID returns 422 after successful authentication.
Persistence failure returns 503. No storage read is necessary for metadata retrieval.

## File deletion (R10, R11, R12)

`DELETE /files/{file_id}` first requires authentication and ownership. Missing and
other-user files both return 404 with `File not found`; perform no storage deletion.
Malformed UUIDs return 422 after authentication. On success remove stored content
and then metadata; return 204 with no body only when both operations succeed.

Storage failure returns 503 and preserves metadata. An already absent storage
object counts as successful storage deletion, enabling retry. If metadata deletion
fails after storage succeeds, return 503 and preserve metadata; content may already
be absent. A retry can remove that metadata and return 204. After complete deletion,
a subsequent request returns 404. Concurrent owned deletes may return 204 or 404;
they must never delete another object's content or report success with metadata remaining.

## Security boundaries

Registration and login are public; `/me` and all file routes require authentication.
Derive ownership solely from verified authentication. List queries and single-file
operations must enforce ownership before returning data or modifying storage.
Missing/foreign file responses must be indistinguishable. Passwords and hashes
must never appear in responses, logs, tokens, or validation input echoes. Never log
access tokens or secrets. Storage objects are private and have opaque unique keys.

## Acceptance criteria

| ID | Given / When / Then | Requirements |
| --- | --- | --- |
| AC01 | Given valid registration data, when submitted, then return 201 with normalized email and profile; persist a hash and no plain password. | R01 |
| AC02 | Given invalid/missing fields or unknown JSON fields, when registered, then return 422 and persist nothing; boundary lengths follow the limits above. | R01 |
| AC03 | Given an existing email, when the same normalized email is registered (including concurrently), then return 409 and retain a single account. | R02 |
| AC04 | Given valid credentials, when logged in, then return 200 and a verifiable token with a 3600-second lifetime and bearer token type. | R03 |
| AC05 | Given wrong password or unknown email, when logged in, then return identical 401 responses and challenge headers; malformed input returns 422. | R03 |
| AC06 | Given each missing/invalid/expired/unknown-user token variant above, when a protected route is called, then return 401 with challenge and perform no file operation; test the expiry instant. | R04 |
| AC07 | Given two users, when either calls `/me`, then only their own profile is returned without password data. | R05 |
| AC08 | Given an authenticated user and valid upload, when uploaded, then return 201 with matching bytes/metadata, private content, and authenticated ownership. | R06, R07 |
| AC09 | Given invalid filename/missing file or content over 10 MiB, when uploaded, then return 422/413 without persistence; exactly 10 MiB and zero bytes succeed. | R06 |
| AC10 | Given storage failure, when uploading, then return 503 with no metadata; given metadata failure, attempt content cleanup and return 503 even if cleanup fails. | R12 |
| AC11 | Given files of two users, when one lists files, then return only their files in specified order; a user with no files receives an empty array. | R08, R11 |
| AC12 | Given owned metadata, when retrieved, then return 200; missing/foreign IDs return identical 404, malformed IDs return 422, and no storage read occurs. | R09, R11 |
| AC13 | Given an owned file, when deleted, then remove content and metadata and return empty 204; a repeat returns 404. | R10 |
| AC14 | Given another user's file or missing ID, when deletion is attempted, then return identical 404 without storage mutation. | R11 |
| AC15 | Given storage deletion failure, then return 503 retaining metadata; given metadata deletion failure, return 503 and allow retry when content is already absent. | R12 |
| AC16 | Given dependency failures in registration, login, authentication, list, or retrieval, then return sanitized 503; unexpected failures return sanitized 500. | R12 |
| AC17 | Given any response, validation failure, token, or captured log, then no password/hash, token log, AWS credential, signing secret, or private storage locator is exposed. | Security |

## Assumptions

- Endpoint names, lengths, upload limit, ordering, status codes, and one-hour token
  lifetime above are explicit defaults selected for this learning project.
- Email validation checks syntax only; deliverability is not verified.
- Token issuer/audience values and cryptographic implementation are plan decisions;
  their verification behavior is fixed here.
- Operators can inspect diagnostics and manually clean orphaned objects.

## Ambiguities

- Cross-system failure behavior is resolved by compensating upload cleanup and
  retryable storage-first deletion; partial failure states are explicitly permitted.
- Email case handling and repeated filenames are resolved as specified above.

## Unresolved decisions

No blocking behavioral decisions remain. Adapter choices, configuration names,
and test tooling details belong to the implementation plan.
