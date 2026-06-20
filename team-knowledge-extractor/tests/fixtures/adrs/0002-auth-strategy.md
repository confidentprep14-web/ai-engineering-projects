# Adopt OAuth2 client-credentials for service-to-service auth
Date: 2024-04-05

## Status
Accepted

## Context
Service-to-service calls currently use long-lived, non-expiring API keys stored in plaintext config. A leaked key has an unbounded blast radius and revocation requires a manual deploy.

## Decision
We chose OAuth2 client-credentials flow with 1-hour access tokens and a token-issuance audit log, replacing static API keys for all internal service-to-service authentication.

## Consequences
Services must implement token refresh and handle 401s by re-authenticating. We gain short-lived credentials, per-client revocation, and an audit trail of which client requested which scope.
