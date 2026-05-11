import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint,
    DateTime, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


def _uuid():
    return str(uuid.uuid4())


class Retailer(Base):
    __tablename__ = "retailers"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    name = Column(String(100), nullable=False)
    domain = Column(String(255), nullable=False, unique=True)
    is_supported = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    products = relationship("Product", back_populates="retailer")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("retailer_id", "retailer_product_id", name="uq_product_retailer_id"),
    )

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    retailer_id = Column(UUID(as_uuid=False), ForeignKey("retailers.id"), nullable=False)
    retailer_product_id = Column(String(255), nullable=True)
    canonical_url = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    brand = Column(String(255), nullable=True)
    category = Column(String(100), nullable=True)
    image_url = Column(Text, nullable=True)
    normalized_title = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    retailer = relationship("Retailer", back_populates="products")
    price_history = relationship("PriceHistory", back_populates="product")


class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    product_id = Column(UUID(as_uuid=False), ForeignKey("products.id"), nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(10), nullable=False, default="USD")
    availability = Column(String(50), nullable=True)
    observed_at = Column(DateTime(timezone=True), nullable=False)
    source = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    product = relationship("Product", back_populates="price_history")
