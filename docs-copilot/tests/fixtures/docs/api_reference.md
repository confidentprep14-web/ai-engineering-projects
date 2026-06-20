# API Reference

This document describes the public HTTP API exposed by the service.

## Authentication

All API calls require a Bearer token in the Authorization header. Obtain a token by sending a POST request to `/auth/token` with your client credentials. Tokens expire after one hour and must be refreshed using the `/auth/refresh` endpoint.

## Rate Limits

Each API key is limited to 100 requests per minute. Exceeding this limit returns an HTTP 429 response with a `Retry-After` header indicating how many seconds to wait before retrying. Sustained abuse may result in the key being revoked.

## Error Codes

The API returns standard HTTP status codes. A 400 response indicates a malformed request body. A 401 response means the Bearer token is missing or invalid. A 404 response means the requested resource does not exist. A 500 response indicates an unexpected server error and should be reported.
