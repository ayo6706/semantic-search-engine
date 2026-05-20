import os
import sys
import asyncio
from sqlalchemy import select

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Set standard output to UTF-8 to avoid console encoding issues
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from app.core.database import async_session_factory
from app.models.document import Document
from app.models.chunk import Chunk

async def main():
    async with async_session_factory() as session:
        result = await session.execute(select(Document))
        docs = result.scalars().all()
        for doc in docs:
            # Only print for our test documents to keep it clean
            if doc.filename not in ["payment_agreement.pdf", "employment_contract.pdf", "terms_of_service.pdf"]:
                continue
            print(f"\nDocument: {doc.filename} (ID: {doc.id})")
            chunk_result = await session.execute(
                select(Chunk).where(Chunk.doc_id == doc.id).order_by(Chunk.chunk_index)
            )
            chunks = chunk_result.scalars().all()
            for chunk in chunks:
                print(f"  Chunk {chunk.chunk_index}:")
                print(f"    {repr(chunk.text)}")

if __name__ == "__main__":
    asyncio.run(main())
