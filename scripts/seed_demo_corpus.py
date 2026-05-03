"""
One-shot script: upload demo PDFs as the sentinel "demo_seed" user so all
guest sessions can search them via document_search.

Usage:
    uv run python -m scripts.seed_demo_corpus <path/to/file1.pdf> <path/to/file2.pdf>

Run this once after deploying Phase 3. The demo_seed user is never swept
by the guest cleanup job — see app/services/worker.py for the guard.
"""

import asyncio
import sys
import uuid
from pathlib import Path

from sqlalchemy import select


async def seed(pdf_paths: list[Path]) -> None:
    from app.database import async_session
    from app.models import Document, User
    from app.services.ingestion import ingest_document_background
    from app.services.storage import save_file
    from app.config import settings

    seed_clerk_id = settings.seed_user_id  # "demo_seed" by default

    async with async_session() as db:
        result = await db.execute(select(User).where(User.clerk_id == seed_clerk_id))
        seed_user = result.scalar_one_or_none()
        if not seed_user:
            seed_user = User(clerk_id=seed_clerk_id, is_guest=False)
            db.add(seed_user)
            await db.commit()
            await db.refresh(seed_user)
            print(f"Created seed user: {seed_clerk_id}")
        else:
            print(f"Seed user already exists: {seed_clerk_id}")

    for pdf_path in pdf_paths:
        if not pdf_path.exists():
            print(f"ERROR: file not found: {pdf_path}")
            sys.exit(1)

        doc_id = str(uuid.uuid4())
        storage_path = await save_file(pdf_path.read_bytes(), doc_id, pdf_path.name)

        async with async_session() as db:
            doc = Document(
                id=uuid.UUID(doc_id),
                user_id=seed_clerk_id,
                filename=pdf_path.name,
                storage_path=storage_path,
                status="processing",
            )
            db.add(doc)
            await db.commit()

            await ingest_document_background(db, doc_id, storage_path, pdf_path.name, seed_clerk_id)

        print(f"Seeded: {pdf_path.name} (id={doc_id})")

    print("Done. Demo corpus is ready.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    paths = [Path(p) for p in sys.argv[1:]]
    asyncio.run(seed(paths))
