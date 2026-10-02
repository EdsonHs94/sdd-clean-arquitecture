# Create Behavioral Specification

Read:

- `AGENTS.md`
- `docs/requirements.md`

Do not implement code.

Create:

`docs/spec.md`

The specification must translate the requirements into precise, testable behavior.

## Include

### User registration

Specify:

- required fields
- valid email expectations
- duplicate email behavior
- password handling
- expected successful result
- failure scenarios

### Login

Specify:

- accepted credentials
- invalid credential behavior
- JWT access token response
- authentication failures

### Authentication

Specify:

- Bearer token usage
- invalid token behavior
- expired token behavior
- missing token behavior

### Current user

Specify behavior for:

`GET /me`

### File upload

Specify:

- authenticated ownership
- storage behavior
- metadata persistence
- expected successful result
- failure scenarios

### File listing

Specify that users only see their own files.

### File retrieval

Specify ownership enforcement.

### File deletion

Specify:

- authorization
- metadata deletion
- storage deletion
- failure scenarios

## Security rules

Explicitly define:

- user isolation
- password protection
- JWT authentication
- authorization boundaries

## Acceptance criteria

Provide acceptance criteria that can later be translated directly into tests.

Prefer Given / When / Then style where appropriate.

Example:

Given an existing user
When they authenticate using the correct email and password
Then the API returns a valid access token.

## Important

This document describes observable behavior.

Avoid premature implementation details.

Do not define concrete repository classes or framework wiring.

Do not implement code.

At the end document:

- assumptions
- ambiguities
- unresolved decisions
