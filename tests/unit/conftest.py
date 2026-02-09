"""
Unit test configuration.
"""

import pytest
from unittest.mock import patch

from finbot.core.auth.session import session_manager
from finbot.core.data.database import SessionLocal
from finbot.core.data.repositories import VendorRepository
from finbot.core.data.models import UserSession


@pytest.fixture
def fast_client(client):
    """Alias for client fixture for unit tests."""    """
    Unit test configuration.
    """
    
    import pytest
    from unittest.mock import patch
    
    from finbot.core.auth.session import session_manager
    from finbot.core.data.database import SessionLocal
    from finbot.core.data.repositories import VendorRepository
    from finbot.core.data.models import UserSession
    
    
    @pytest.fixture
    def fast_client(client):
        """Alias for client fixture for unit tests."""
        return client
    
    
    @pytest.fixture
    def client():
        """Create a test client with mocked startup tasks.
    
        Patches start_processor_task and load_definitions_on_startup so the
        FastAPI app can boot without Redis or YAML definitions on disk.
        """
        from fastapi.testclient import TestClient
        from finbot.main import app
    
        with patch("finbot.main.start_processor_task"), \
             patch("finbot.main.load_definitions_on_startup"):
            with TestClient(app) as c:
                yield c
    
    
    @pytest.fixture
    def db():
        """Get database session with automatic rollback after each test.
    
        Uses a SAVEPOINT so all inserts/updates within a test are undone
        on teardown. This ensures test isolation without needing manual
        cleanup helpers.
        """
        session = SessionLocal()
        session.begin_nested()
        yield session
        session.rollback()
        session.close()
    
    
    def create_vendor(vendor_repo, company_name: str, contact_name: str, email: str, tin: str):
        """Helper to create a vendor with standard test data."""
        return vendor_repo.create_vendor(
            company_name=company_name,
            vendor_category="Technology",
            industry="Software",
            services="Consulting",
            contact_name=contact_name,
            email=email,
            tin=tin,
            bank_account_number="123456789012",
            bank_name="Test Bank",
            bank_routing_number="021000021",
            bank_account_holder_name=contact_name,
        )
    
    
    @pytest.fixture
    def vendor_pair_setup(db):
        """Create two test vendors with sessions for isolation testing.
    
        Returns dict with:
            - s1, s2: Two sessions for same user email
            - v1, v2: Two vendors created in same namespace
            - db: Database session
        """
        # Create two sessions for the same user (same namespace/user_id)
        s1 = session_manager.create_session(email="isolation_test@example.com")
        s2 = session_manager.create_session(email="isolation_test@example.com")
    
        # Create vendors
        vendor_repo = VendorRepository(db, s1)
        v1 = create_vendor(vendor_repo, "Vendor Alpha", "Alice Smith", "alice@vendor1.com", "11-1111111")
        v2 = create_vendor(vendor_repo, "Vendor Beta", "Bob Johnson", "bob@vendor2.com", "22-2222222")
    
        # Attach vendor contexts to sessions
        us1 = db.query(UserSession).filter(UserSession.session_id == s1.session_id).first()
        us2 = db.query(UserSession).filter(UserSession.session_id == s2.session_id).first()
        us1.current_vendor_id = v1.id
        us2.current_vendor_id = v2.id
        db.commit()
    
        return {
            's1': s1,
            's2': s2,
            'v1': v1,
            'v2': v2,
            'db': db,
        }
    
    
    @pytest.fixture
    def multi_vendor_setup(db):
        """Create multiple test vendors for load/concurrency testing.
    
        Returns dict with:
            - vendors: List of vendor dicts with session_id, vendor_id, invoice_id
            - db: Database session
        """
        vendors = []
    
        for i in range(5):
            session = session_manager.create_session(email=f"vendor_{i}@example.com")
            vendor_repo = VendorRepository(db, session)
            vendor = create_vendor(
                vendor_repo,
                f"Load Test Vendor {i}",
                f"Contact {i}",
                f"contact{i}@example.com",
                f"{i:02d}-{i:07d}"
            )
    
            vendors.append({
                'session_id': session.session_id,
                'vendor_id': vendor.id,
                'invoice_id': None,
                'db': db,
            })
    
        return vendors
    return client


@pytest.fixture
def client():
    """Create a test client with mocked startup tasks.

    Patches start_processor_task and load_definitions_on_startup so the
    FastAPI app can boot without Redis or YAML definitions on disk.
    """
    from fastapi.testclient import TestClient
    from finbot.main import app

    with patch("finbot.main.start_processor_task"), \
         patch("finbot.main.load_definitions_on_startup"):
        with TestClient(app) as c:
            yield c


@pytest.fixture
def db():
    """Get database session with automatic rollback after each test.

    Uses a SAVEPOINT so all inserts/updates within a test are undone
    on teardown. This ensures test isolation without needing manual
    cleanup helpers.
    """
    session = SessionLocal()
    session.begin_nested()
    yield session
    session.rollback()
    session.close()


def create_vendor(vendor_repo, company_name: str, contact_name: str, email: str, tin: str):
    """Helper to create a vendor with standard test data."""
    return vendor_repo.create_vendor(
        company_name=company_name,
        vendor_category="Technology",
        industry="Software",
        services="Consulting",
        contact_name=contact_name,
        email=email,
        tin=tin,
        bank_account_number="123456789012",
        bank_name="Test Bank",
        bank_routing_number="021000021",
        bank_account_holder_name=contact_name,
    )


@pytest.fixture
def vendor_pair_setup(db):
    """Create two test vendors with sessions for isolation testing.

    Returns dict with:
        - s1, s2: Two sessions for same user email
        - v1, v2: Two vendors created in same namespace
        - db: Database session
    """
    # Create two sessions for the same user (same namespace/user_id)
    s1 = session_manager.create_session(email="isolation_test@example.com")
    s2 = session_manager.create_session(email="isolation_test@example.com")

    # Create vendors
    vendor_repo = VendorRepository(db, s1)
    v1 = create_vendor(vendor_repo, "Vendor Alpha", "Alice Smith", "alice@vendor1.com", "11-1111111")
    v2 = create_vendor(vendor_repo, "Vendor Beta", "Bob Johnson", "bob@vendor2.com", "22-2222222")

    # Attach vendor contexts to sessions
    us1 = db.query(UserSession).filter(UserSession.session_id == s1.session_id).first()
    us2 = db.query(UserSession).filter(UserSession.session_id == s2.session_id).first()
    us1.current_vendor_id = v1.id
    us2.current_vendor_id = v2.id
    db.commit()

    return {
        's1': s1,
        's2': s2,
        'v1': v1,
        'v2': v2,
        'db': db,
    }


@pytest.fixture
def multi_vendor_setup(db):
    """Create multiple test vendors for load/concurrency testing.

    Returns dict with:
        - vendors: List of vendor dicts with session_id, vendor_id, invoice_id
        - db: Database session
    """
    vendors = []

    for i in range(5):
        session = session_manager.create_session(email=f"vendor_{i}@example.com")
        vendor_repo = VendorRepository(db, session)
        vendor = create_vendor(
            vendor_repo,
            f"Load Test Vendor {i}",
            f"Contact {i}",
            f"contact{i}@example.com",
            f"{i:02d}-{i:07d}"
        )

        vendors.append({
            'session_id': session.session_id,
            'vendor_id': vendor.id,
            'invoice_id': None,
            'db': db,
        })

    return vendors