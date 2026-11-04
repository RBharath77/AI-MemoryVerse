# AI-MemoryVerse — Testing Strategy & Evaluation Framework

## 1. Testing Pyramid Overview

AI-MemoryVerse employs an automated testing strategy ensuring every core layer is validated before production deployment:

```
           / \
          / E2E \        Playwright / Automated E2E Workflows (12 Scenarios)
         /-------\
        /  Integ  \      FastAPI TestClient + PostgreSQL Integration Tests
       /-----------\
      / AI / RAG Eval\   Groundedness, Citation Accuracy, Precision@K
     /-----------------\
    /     Unit Tests    \ Pytest (Backend services/models) & Vitest (Frontend components)
   /---------------------\
```

---

## 2. 12 Mandatory End-to-End Scenarios

| Scenario | Objective | Validation Check |
|---|---|---|
| **Scenario 1** | Register, log in, create a workspace and add a memory. | User profile created, workspace membership set as Owner, memory saved with status `APPROVED`. |
| **Scenario 2** | Restart the application and verify memory persistence. | Querying the database returns the exact memory with timestamp and metadata intact. |
| **Scenario 3** | Start a new conversation and retrieve a saved fact. | AI chat invokes retrieval and incorporates the saved memory into the prompt. |
| **Scenario 4** | Upload multiple documents and query information across them. | Worker chunks documents; hybrid search retrieves relevant chunks from across both files. |
| **Scenario 5** | Check that answers cite the correct document sources. | Response returns verifiable citation tags matching chunk IDs and page references. |
| **Scenario 6** | Edit a memory and inspect version history. | Old version archived in `memory_versions`; current memory points to updated text. |
| **Scenario 7** | Create a contradictory memory and verify conflict handling. | Conflict detector flags candidate memory with `CONTRADICTION` warning before approval. |
| **Scenario 8** | Explore project relationships in the knowledge graph. | Entities extracted from memories and documents form nodes and edges in `/api/v1/graph`. |
| **Scenario 9** | Verify another user cannot access private information. | User B querying User A's workspace receives HTTP 403 / 404 with zero data leakage. |
| **Scenario 10** | Delete a source and verify dependent data handling. | Deleting a document cascades chunk and embedding deletions cleanly. |
| **Scenario 11** | Process a document through a background worker. | Celery job transitions status from `PENDING` -> `PROCESSING` -> `COMPLETED`. |
| **Scenario 12** | Verify the deployed application and database work together. | Health check endpoint reports database and queue readiness. |

---

## 3. AI Evaluation Metrics
- **Retrieval Precision@K & Recall@K**: Validates whether the top $K$ retrieved chunks contain the ground-truth answers.
- **Answer Groundedness**: Verifies that every assertion made by the LLM is directly supported by retrieved context.
- **Citation Precision**: Ensures every citation tag links to an actually retrieved and relevant chunk.

