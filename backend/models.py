from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Garage(Base):
    __tablename__ = "garages"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    address = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    floors = relationship(
        "Floor",
        back_populates="garage",
        cascade="all, delete-orphan",
    )

    pricing = relationship(
        "PricingConfig",
        back_populates="garage",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Floor(Base):
    __tablename__ = "floors"

    id = Column(Integer, primary_key=True)
    garage_id = Column(Integer, ForeignKey("garages.id"), nullable=False)
    floor_number = Column(Integer, nullable=False)

    garage = relationship("Garage", back_populates="floors")

    spots = relationship(
        "ParkingSpot",
        back_populates="floor",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "garage_id",
            "floor_number",
            name="uq_garage_floor",
        ),
    )


class ParkingSpot(Base):
    __tablename__ = "parking_spots"

    id = Column(Integer, primary_key=True)
    floor_id = Column(Integer, ForeignKey("floors.id"), nullable=False)
    spot_number = Column(String, nullable=False)
    spot_type = Column(String, nullable=False)
    is_occupied = Column(Boolean, default=False, nullable=False)

    floor = relationship("Floor", back_populates="spots")

    sessions = relationship(
        "ParkingSession",
        back_populates="spot",
    )

    __table_args__ = (
        UniqueConstraint(
            "floor_id",
            "spot_number",
            name="uq_floor_spot",
        ),
    )


class ParkingSession(Base):
    __tablename__ = "parking_sessions"

    id = Column(Integer, primary_key=True)

    garage_id = Column(
        Integer,
        ForeignKey("garages.id"),
        nullable=False,
    )

    vehicle_plate = Column(
        String,
        index=True,
        nullable=False,
    )

    vehicle_type = Column(
        String,
        nullable=False,
    )

    spot_id = Column(
        Integer,
        ForeignKey("parking_spots.id"),
        nullable=False,
    )

    check_in_time = Column(
        DateTime,
        nullable=False,
    )

    check_out_time = Column(
        DateTime,
        nullable=True,
    )

    duration_minutes = Column(
        Integer,
        nullable=True,
    )

    fee = Column(
        Float,
        nullable=True,
    )

    status = Column(
        String,
        default="ACTIVE",
        nullable=False,
    )

    spot = relationship(
        "ParkingSpot",
        back_populates="sessions",
    )

    __table_args__ = (
        Index(
            "ix_active_spot",
            "spot_id",
            unique=True,
            sqlite_where=(status == "ACTIVE"),
        ),
        Index(
            "ix_active_vehicle",
            "vehicle_plate",
            unique=True,
            sqlite_where=(status == "ACTIVE"),
        ),
    )


class PricingConfig(Base):
    __tablename__ = "pricing_config"

    id = Column(Integer, primary_key=True)

    garage_id = Column(
        Integer,
        ForeignKey("garages.id"),
        unique=True,
        nullable=False,
    )

    first_hour_rate = Column(
        Float,
        default=50,
        nullable=False,
    )

    additional_hour_rate = Column(
        Float,
        default=30,
        nullable=False,
    )

    daily_cap = Column(
        Float,
        default=300,
        nullable=False,
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    garage = relationship(
        "Garage",
        back_populates="pricing",
    )


class RateCard(Base):
    __tablename__ = "rate_cards"

    id = Column(Integer, primary_key=True)

    garage_id = Column(
        Integer,
        ForeignKey("garages.id"),
        nullable=False,
    )

    spot_type = Column(
        String,
        nullable=False,
    )

    first_hour_rate = Column(
        Float,
        nullable=False,
    )

    additional_hour_rate = Column(
        Float,
        nullable=False,
    )

    daily_cap = Column(
        Float,
        nullable=False,
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    __table_args__ = (
        UniqueConstraint(
            "garage_id",
            "spot_type",
            name="uq_garage_spot_rate",
        ),
    )