"""
Embedding Service
=================
Generates OpenAI embeddings for text and syncs business/service data
into the vector store (core.embeddings table).
"""

from openai import AsyncOpenAI
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.embedding import Embedding
from app.models.business import Business
from app.models.service import Service

_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

EMBEDDING_MODEL = "text-embedding-3-small"  # 1536 dims, cheap


async def create_embedding(text: str) -> list[float]:
    """Call OpenAI and return a 1536-dim vector for the given text."""
    if not text or not text.strip():
        return None
    response = await _client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text.strip(),
    )
    return response.data[0].embedding


def _build_business_chunks(business: Business) -> list[str]:
    """Break a business into searchable text chunks."""
    chunks = []
    if business.business_name:
        chunks.append(f"Business name: {business.business_name}")
    if business.description:
        chunks.append(f"About the business: {business.description}")
    industry = getattr(business, "industry_label", None)
    if industry:
        chunks.append(f"Industry: {industry}")
    location_parts = [p for p in [business.street_address, business.city, business.state, business.zip_code, business.country] if p]
    if location_parts:
        chunks.append(f"Location: {', '.join(location_parts)}")
    contact_parts = []
    if business.phone:
        contact_parts.append(f"phone {business.phone}")
    if business.email:
        contact_parts.append(f"email {business.email}")
    if business.website:
        contact_parts.append(f"website {business.website}")
    if contact_parts:
        chunks.append(f"Contact: {', '.join(contact_parts)}")
    return chunks


def _build_service_chunks(service: Service, business_name: str = "") -> list[str]:
    """Break a service into searchable text chunks."""
    chunks = []
    prefix = f"{business_name} - " if business_name else ""
    if service.service_name:
        chunks.append(f"{prefix}Service offered: {service.service_name}")
    if service.description:
        chunks.append(f"{prefix}{service.service_name} details: {service.description}")
    if service.base_price is not None:
        currency = service.currency or ""
        chunks.append(f"{prefix}{service.service_name} price: {service.base_price} {currency}".strip())
    if service.duration_minutes:
        chunks.append(f"{prefix}{service.service_name} duration: {service.duration_minutes} minutes")
    if getattr(service, "location", None):
        chunks.append(f"{prefix}{service.service_name} location: {service.location}")
    return chunks


async def sync_business_embeddings(db: AsyncSession, business: Business) -> int:
    """Delete old embeddings for a business and generate fresh ones."""
    # Remove existing business-level embeddings
    await db.execute(
        delete(Embedding).where(
            Embedding.business_id == business.id,
            Embedding.source_type == "business",
        )
    )

    chunks = _build_business_chunks(business)
    count = 0
    for chunk in chunks:
        vector = await create_embedding(chunk)
        if vector is None:
            continue
        db.add(Embedding(
            business_id=business.id,
            source_type="business",
            source_id=business.id,
            content=chunk,
            embedding=vector,
        ))
        count += 1

    await db.commit()
    return count


async def sync_service_embeddings(db: AsyncSession, service: Service) -> int:
    """Delete old embeddings for a service and generate fresh ones."""
    await db.execute(
        delete(Embedding).where(
            Embedding.source_type == "service",
            Embedding.source_id == service.id,
        )
    )

    # Get business name for richer context
    biz_result = await db.execute(select(Business).where(Business.id == service.business_id))
    business = biz_result.scalar_one_or_none()
    business_name = business.business_name if business else ""

    chunks = _build_service_chunks(service, business_name)
    count = 0
    for chunk in chunks:
        vector = await create_embedding(chunk)
        if vector is None:
            continue
        db.add(Embedding(
            business_id=service.business_id,
            source_type="service",
            source_id=service.id,
            content=chunk,
            embedding=vector,
        ))
        count += 1

    await db.commit()
    return count


async def search_knowledge(
    db: AsyncSession,
    business_id,
    query: str,
    top_k: int = 5,
) -> list[dict]:
    """Semantic search — find the top_k most relevant chunks for a query."""
    query_vector = await create_embedding(query)
    if query_vector is None:
        return []

    # pgvector cosine distance: smaller = more similar
    stmt = (
        select(
            Embedding.content,
            Embedding.source_type,
            Embedding.source_id,
            Embedding.embedding.cosine_distance(query_vector).label("distance"),
        )
        .where(Embedding.business_id == business_id)
        .order_by(Embedding.embedding.cosine_distance(query_vector))
        .limit(top_k)
    )
    result = await db.execute(stmt)
    return [
        {
            "content": row.content,
            "source_type": row.source_type,
            "source_id": str(row.source_id) if row.source_id else None,
            "similarity": round(1 - float(row.distance), 4),
        }
        for row in result.all()
    ]