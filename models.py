from sqlalchemy import Column, Integer, String, DateTime, Float, JSON, Boolean
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

# ====================== USER ======================
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    email = Column(String, nullable=True)
    role = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    language = Column(String, default="ru")
    is_active = Column(Boolean, default=True)
    
    # Email верификация
    email_verified = Column(Boolean, default=False)
    email_code = Column(String, nullable=True)
    email_code_expires = Column(DateTime, nullable=True)
    
    # Для курьеров - документы
    passport_photo = Column(String, nullable=True)
    selfie_photo = Column(String, nullable=True)
    selfie_with_passport = Column(String, nullable=True)
    is_verified = Column(Boolean, default=False)
    
    # Подписка
    subscription_type = Column(String, default="none")  # none, plus, premium
    subscription_expires = Column(DateTime, nullable=True)
    free_deliveries_used = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)


# ====================== ORDER ======================
class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(Integer, unique=True, index=True, nullable=False)

    customer_phone = Column(String, nullable=False)
    seller_phone = Column(String, nullable=True)
    courier = Column(String, nullable=True)

    status = Column(String, default="создан")

    products = Column(JSON, nullable=False)
    total_price = Column(Float, nullable=True)
    delivery_price = Column(Float, nullable=False)
    price_per_km = Column(Float, nullable=True)
    commission_percent = Column(Integer, nullable=True)
    
    # Доплаты
    time_surcharge = Column(Float, default=0)  # вечер/ночь
    weather_surcharge = Column(Float, default=0)  # дождь/снег
    service_fee = Column(Float, default=5)  # service fee (скрыто)
    
    # Подписка использована
    is_subscription_order = Column(Boolean, default=False)
    discount_applied = Column(Float, default=0)  # 5% или 10%

    from_lat = Column(Float, nullable=True)
    from_lng = Column(Float, nullable=True)
    to_lat = Column(Float, nullable=True)
    to_lng = Column(Float, nullable=True)
    distance_km = Column(Float, nullable=True)

    # 2 КОДА
    pickup_code = Column(Integer, nullable=True)  # Код от ресторана курьеру
    delivery_code = Column(Integer, nullable=True)  # Код от клиента курьеру

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
    seller_type = Column(String, nullable=False)
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
    status = Column(String, default="pending")
    note = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ====================== COURIER BONUS ======================
class CourierBonus(Base):
    __tablename__ = "courier_bonuses"

    id = Column(Integer, primary_key=True, index=True)
    courier_phone = Column(String, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    reason = Column(String, nullable=False)
    deliveries_count = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# ====================== SUBSCRIPTION ======================
class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_phone = Column(String, nullable=False, index=True)
    subscription_type = Column(String, nullable=False)  # plus, premium
    price = Column(Float, nullable=False)
    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)
    free_deliveries_used = Column(Integer, default=0)
    free_deliveries_limit = Column(Integer, nullable=False)  # 5 или 15
    created_at = Column(DateTime, default=datetime.utcnow)