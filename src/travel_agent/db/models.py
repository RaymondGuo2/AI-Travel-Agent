from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def new_uuid() -> str:
    return str(uuid.uuid4())


class TripORM(Base):
    __tablename__ = "trips"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    traveler_name: Mapped[str] = mapped_column(String, nullable=False)
    traveler_email: Mapped[str] = mapped_column(String, nullable=False)
    origin: Mapped[str] = mapped_column(String, nullable=False)
    destination: Mapped[str] = mapped_column(String, nullable=False)
    departure_date: Mapped[str] = mapped_column(String, nullable=False)  # ISO date string
    return_date: Mapped[str | None] = mapped_column(String, nullable=True)
    purpose: Mapped[str] = mapped_column(String, nullable=False)
    total_cost_cents: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String, default="USD")
    status: Mapped[str] = mapped_column(String, nullable=False, default="planning")
    intent_mandate_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    request_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    segments: Mapped[list[TripSegmentORM]] = relationship(
        "TripSegmentORM", back_populates="trip", cascade="all, delete-orphan"
    )
    escalations: Mapped[list[EscalationORM]] = relationship(
        "EscalationORM", back_populates="trip", cascade="all, delete-orphan"
    )
    payment_records: Mapped[list[PaymentRecordORM]] = relationship(
        "PaymentRecordORM", back_populates="trip", cascade="all, delete-orphan"
    )


class TripSegmentORM(Base):
    __tablename__ = "trip_segments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    trip_id: Mapped[str] = mapped_column(String, ForeignKey("trips.id"), nullable=False)
    segment_type: Mapped[str] = mapped_column(String, nullable=False)  # flight|hotel|ground_transport
    merchant_url: Mapped[str] = mapped_column(String, nullable=False)
    merchant_name: Mapped[str] = mapped_column(String, nullable=False)
    checkout_session_id: Mapped[str | None] = mapped_column(String, nullable=True)
    order_id: Mapped[str | None] = mapped_column(String, nullable=True)
    details_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    cost_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String, default="USD")
    status: Mapped[str] = mapped_column(String, nullable=False, default="searching")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    trip: Mapped[TripORM] = relationship("TripORM", back_populates="segments")
    payment_records: Mapped[list[PaymentRecordORM]] = relationship(
        "PaymentRecordORM", back_populates="segment"
    )


class EscalationORM(Base):
    __tablename__ = "escalations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    trip_id: Mapped[str] = mapped_column(String, ForeignKey("trips.id"), nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    details_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    cart_mandate_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    approver_email: Mapped[str | None] = mapped_column(String, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    trip: Mapped[TripORM] = relationship("TripORM", back_populates="escalations")


class PaymentRecordORM(Base):
    __tablename__ = "payment_records"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    trip_id: Mapped[str] = mapped_column(String, ForeignKey("trips.id"), nullable=False)
    segment_id: Mapped[str] = mapped_column(
        String, ForeignKey("trip_segments.id"), nullable=False
    )
    payment_mandate_id: Mapped[str] = mapped_column(String, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String, default="USD")
    receipt_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    trip: Mapped[TripORM] = relationship("TripORM", back_populates="payment_records")
    segment: Mapped[TripSegmentORM] = relationship(
        "TripSegmentORM", back_populates="payment_records"
    )
