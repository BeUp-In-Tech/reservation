import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models import Business, Service, BusinessAISettings
import uuid
from datetime import datetime

DATABASE_URL = "postgresql+asyncpg://postgres:123456@localhost:5432/reservation_dev"

def slugify(text):
    """Simple slugify function"""
    return text.lower().replace(" ", "-")

async def create_test_business():
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Create business
        business = Business(
            id=uuid.uuid4(),
            business_name="Test Salon",
            slug="test-salon",
            email="test@salon.com",
            phone="+1234567890",
            is_active=True,
            created_at=datetime.utcnow()
        )
        session.add(business)
        await session.flush()
        
        print(f"✅ Created business: {business.slug}")
        
        # Create AI settings
        ai_settings = BusinessAISettings(
            business_id=business.id,
            agent_name="Salon Assistant",
            tone_of_voice="friendly and professional"
        )
        session.add(ai_settings)
        print(f"✅ Created AI settings")
        
        # Create test services
        services = [
            {
                "service_name": "Haircut",
                "description": "Professional haircut service",
                "base_price": 50.00,
            },
            {
                "service_name": "Hair Coloring",
                "description": "Full hair coloring service",
                "base_price": 120.00,
            },
            {
                "service_name": "Manicure",
                "description": "Professional manicure",
                "base_price": 30.00,
            }
        ]
        
        for svc in services:
            service = Service(
                id=uuid.uuid4(),
                business_id=business.id,
                slug=slugify(svc["service_name"]),  # ✅ ADD SLUG
                service_name=svc["service_name"],
                description=svc["description"],
                base_price=svc["base_price"],
                currency="USD",
                duration_minutes=60,
                is_active=True,
                created_at=datetime.utcnow()
            )
            session.add(service)
            print(f"✅ Created service: {service.service_name} (slug: {service.slug})")
        
        await session.commit()
        print(f"\n🎉 Success! Use business slug: 'test-salon'")

if __name__ == "__main__":
    asyncio.run(create_test_business())