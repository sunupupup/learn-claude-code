# Implementation Tasks: D1 RAG Agent Demo

- [x] Task: Update the specification for real Embeddings and Qdrant
  - Acceptance: SPEC.md names real dependencies, interfaces, ACL contract, and production caveats.
  - Verify: Read the Data, Tech Stack, Control Flow, and Boundaries sections.
  - Files: SPEC.md

- [x] Task: Add package metadata and configuration
  - Acceptance: pyproject.toml declares Python, OpenAI, Qdrant, and Pydantic dependencies; settings are environment-driven.
  - Verify: Inspect package metadata and run a syntax check.
  - Files: pyproject.toml, rag_agent_demo/config.py

- [x] Task: Implement contracts and document ingestion
  - Acceptance: Manifest paths are contained, Markdown chunks have stable IDs/content hashes, and ACL metadata is copied to chunks.
  - Verify: Unit tests cover malformed manifest, path escape, chunk IDs, and metadata.
  - Files: contracts.py, ingest.py, data/manifest.json, data/documents/*.md, tests/test_ingest.py

- [x] Task: Implement real Embedding and Qdrant adapters
  - Acceptance: Batch embeddings, collection creation, payload upsert, pre-ranking tenant/group filter, top-k and score threshold are explicit.
  - Verify: Adapter imports are isolated; offline tests cover authorization policy and threshold propagation.
  - Files: embeddings.py, vector_store.py, tests/test_permissions.py, tests/test_retrieval.py

- [x] Task: Implement Tool and model contracts
  - Acceptance: Strict search input, Responses function-tool schema, real OpenAI Responses adapter, and deterministic test doubles exist.
  - Verify: Contract tests cover tool-call parsing and function-call output continuation shape.
  - Files: tools.py, model.py, tests/test_model_contracts.py

- [x] Task: Implement Harness, output validation, and tracing
  - Acceptance: Required retrieval, one-call budget, one repair, no-evidence, valid final schema, source allow-list, and terminal states are enforced.
  - Verify: Agent-loop tests cover success, direct-text repair, no evidence, invalid source, repeated tool call, and failure states.
  - Files: agent.py, output_validation.py, tracing.py, contracts.py, tests/test_agent_loop.py, tests/test_output_validation.py

- [x] Task: Add CLI, evals, README, and final verification
  - Acceptance: Commands and production caveats are documented; 10 eval cases cover quality/safety/trajectory basics.
  - Verify: Run unittest and eval commands when dependencies/services are available; otherwise run compile-only verification and report the limitation.
  - Files: cli.py, evals/cases.json, evals/run_evals.py, README.md
