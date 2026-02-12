# Podium — Personal AI Assistant Platform

A cloud-native, model-agnostic AI assistant platform with long-term memory,
semantic search, and document ingestion.

## Current Status: v0 — Core RAG Pipeline

Upload documents, ask questions, get grounded answers.

## Quick Start

1. Clone the repo
2. Copy `.env.example` to `.env` and add your OpenAI API key
3. Run:
```bash
   docker compose up --build
```
4. Visit http://localhost:8000/docs

## API Endpoints

- `POST /documents/upload` — Upload a PDF
- `GET /documents/` — List documents
- `POST /chat/` — Ask a question
- `GET /chat/{id}` — Get conversation history

## Architecture

- **Backend:** FastAPI (Python)
- **Database:** PostgreSQL + pgvector
- **LLM:** Model-agnostic via litellm (currently OpenAI)
- **Embeddings:** text-embedding-3-small

## What's Next

- [ ] Streaming responses
- [ ] Conversation memory (multi-turn context)
- [ ] Frontend dashboard
- [ ] Cloud deployment (Terraform + AWS/GCP)
- [ ] Background job processing
- [ ] Multi-model support