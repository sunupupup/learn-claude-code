# Implementation Plan: D1 RAG Agent Demo

## Decisions

1. Use real OpenAI Embeddings and Qdrant adapters in production code.
2. Keep provider calls behind protocols so tests can use deterministic fakes.
3. Use document-level ACL metadata from `data/manifest.json`; compile it into Qdrant payload filters before vector search.
4. Use an explicit Harness loop rather than hiding control flow inside a framework.
5. Use OpenAI Responses API function tools for retrieval and JSON Schema structured output for the final answer.
6. Treat `retrieval_status` and `answerable` as different decisions: the former is retrieval policy, the latter is model-level evidence sufficiency.
7. Rebuild the demo collection at startup behind an explicit development flag; document versioned collection/alias swap as the production replacement.

## Components and order

1. Contracts and settings: define identities, chunks, tool requests, final output, RunState and environment configuration.
2. Ingestion: validate manifest paths, parse Markdown, preserve headings, and attach ACL metadata to every chunk.
3. Embeddings and vector store: batch real embeddings, create/rebuild Qdrant collection, upsert payloads, and query with pre-ranking ACL filters.
4. Tool adapter: expose `search_knowledge` with strict input/output contracts and redacted tool results.
5. Model adapter: implement real Responses API calls, tool-call extraction, function-call output continuation, and structured final output.
6. Harness: enforce required retrieval, one-tool-call budget, repair budget, no-evidence branch, output validation, and terminal states.
7. Trace and CLI: expose run stages and safe user-facing messages without leaking document content.
8. Tests and evals: cover ingestion, ACLs, retrieval threshold, tool trajectory, invalid output, no evidence, and tenant isolation.
9. Documentation: explain the stable mental model, production gaps, commands, and each deliberate simplification.

## Risks and mitigations

- Embedding model dimension is discovered at startup; collection creation must happen after the first embedding batch.
- Similarity score is not proof of answerability; preserve scores for diagnosis and let the final model return `answerable=false` when evidence is insufficient.
- Qdrant APIs and model SDKs evolve; isolate them in adapters and pin compatible dependency ranges.
- Rebuilding a live collection is unsafe; mark it as demo-only and explain atomic versioned collection promotion.
- LLM output can be syntactically valid but semantically wrong; validate source IDs and keep offline evals separate from runtime schema checks.
