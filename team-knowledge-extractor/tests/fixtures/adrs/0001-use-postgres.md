# Use PostgreSQL
Date: 2024-03-10

## Status
Accepted

## Context
We need a primary datastore that supports both relational integrity for billing records and flexible JSON storage for event payloads that change shape frequently.

## Decision
We chose PostgreSQL over MySQL because it offers native JSONB columns with GIN indexing, mature support for partial and expression indexes, and we already operate Postgres for two other internal services, which reduces operational overhead.

## Consequences
Engineers need to learn JSONB query syntax. We gain indexed semi-structured storage without standing up a separate document database.
