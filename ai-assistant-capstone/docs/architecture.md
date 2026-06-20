# Architecture: Full AI Assistant

```mermaid
graph TB
    Client["Client (curl / browser)"]
    APIGW["API Gateway HTTP API"]
    Lambda["AWS Lambda\n(FastAPI + Mangum)"]
    SM["Secrets Manager\n(LLM API Key)"]
    S3["S3\n(FAISS index - optional)"]
    LLM["LLM Provider\n(Anthropic / OpenAI)"]

    Client -->|"POST /chat\n(SSE stream)"| APIGW
    Client -->|"POST /documents"| APIGW
    Client -->|"GET /metrics"| APIGW
    APIGW --> Lambda
    Lambda -->|"GetSecretValue"| SM
    Lambda -->|"Stream tokens"| LLM
    Lambda -->|"Tool calls: Wikipedia, calculator, datetime"| External["External APIs\n(Wikipedia REST)"]
    Lambda -->|"/tmp storage"| SQLite["SQLite\n(requests, sessions)"]
    Lambda -->|"FAISS index"| SQLite

    subgraph "Lambda internals"
        Router["FastAPI Router"]
        RAG["RAG Module\n(FAISS + embeddings)"]
        Context["Context Manager\n(sliding window)"]
        Tools["Tool Registry\n(calculator, datetime, wiki)"]
        Router --> RAG
        Router --> Context
        Router --> Tools
    end
```

## Data flow for a /chat request

1. Client sends `{"message": "...", "session_id": "abc"}`
2. Lambda loads last 20 messages for session "abc" from SQLite
3. RAG retrieves top-3 chunks from FAISS index (if use_rag=true)
4. Context manager checks token count, applies sliding window if needed
5. LLM streams response; if tool_call in response → execute tool → inject result → continue
6. Final answer streamed as SSE to client
7. Request logged to SQLite (tokens, cost, latency, retrieval_hit)
