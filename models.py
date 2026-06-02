from sqlalchemy import Column, Integer, String, DateTime, Float, JSON, Boolean
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

# ====================== USER ======================
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String, unique=True, index=True, nullable=False)
    role = Column(String, nullable=False)  # customer, seller, courier, admin
    full_name = Column(String, nullable=True)
    language = Column(String, default="ru")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# ====================== ORDER ======================
class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(Integer, unique=True, index=True, nullable=False)

    customer_phone = Column(String, nullable=False)
    seller_phone = Column(String, nullable=True)
    courier = Column(String, nullable=True)  # ← ИСПРАВИЛ: было courier_phone

    status = Column(String, default="создан")

    products = Column(JSON, nullable=False)
    total_price = Column(Float, nullable=True)  # ← ДОБАВИЛ
    delivery_price = Column(Float, nullable=False)
    price_per_km = Column(Float, nullable=True)  # ← ДОБАВИЛ
    commission_percent = Column(Integer, nullable=True)  # ← ДОБАВИЛ

    from_lat = Column(Float, nullable=True)
    from_lng = Column(Float, nullable=True)
    to_lat = Column(Float, nullable=True)
    to_lng = Column(Float, nullable=True)
    distance_km = Column(Float, nullable=True)

    delivery_code = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    courier_rating = Column(Integer, nullable=True)
    courier_review = Column(String, nullable=True)

    product_rating = Column(Integer, nullable=True)
    product_review = Column(String, nullable=True)

    rizq_fee = Column(Float, nullable=True)
    courier_earn = Column(Float, nullable=True)

# ====================== PRODUCT ======================
class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    seller_phone = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    description = Column(String, nullable=True)
    category = Column(String, nullable=True)
    image_url = Column(String, nullable=True)
    is_available = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# ====================== SELLER ======================
class Seller(Base):
    __tablename__ = "sellers"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    seller_type = Column(String, nullable=False)   # restaurant or market
    address = Column(String, nullable=True)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# ====================== COURIER PAYOUT ======================
class CourierPayout(Base):
    __tablename__ = "courier_payouts"

    id = Column(Integer, primary_key=True, index=True)
    courier_phone = Column(String, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    status = Column(String, default="pending")  # pending, paid, rejected
    note = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    # ====================== COURIER BONUS ======================
class CourierBonus(Base):
    __tablename__ = "courier_bonuses"

    id = Column(Integer, primary_key=True, index=True)
    courier_phone = Column(String, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    reason = Column(String, nullable=False)  # "100_deliveries" or "500_deliveries"
    deliveries_count = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)