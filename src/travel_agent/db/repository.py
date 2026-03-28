from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from travel_agent.db.models import EscalationORM, PaymentRecordORM, TripORM, TripSegmentORM


class TripRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: dict) -> TripORM:
        trip = TripORM(**data)
        self.session.add(trip)
        await self.session.commit()
        await self.session.refresh(trip)
        return trip

    async def get(self, trip_id: str) -> TripORM | None:
        result = await self.session.execute(
            select(TripORM)
            .where(TripORM.id == trip_id)
            .options(
                selectinload(TripORM.segments),
                selectinload(TripORM.escalations),
                selectinload(TripORM.payment_records),
            )
        )
        return result.scalar_one_or_none()

    async def update_status(self, trip_id: str, status: str) -> None:
        await self.session.execute(
            update(TripORM)
            .where(TripORM.id == trip_id)
            .values(status=status, updated_at=datetime.now(timezone.utc))
        )
        await self.session.commit()

    async def update(self, trip_id: str, **kwargs) -> None:
        kwargs["updated_at"] = datetime.now(timezone.utc)
        await self.session.execute(
            update(TripORM).where(TripORM.id == trip_id).values(**kwargs)
        )
        await self.session.commit()

    async def list_by_email(self, email: str) -> list[TripORM]:
        result = await self.session.execute(
            select(TripORM)
            .where(TripORM.traveler_email == email)
            .order_by(TripORM.created_at.desc())
            .options(selectinload(TripORM.segments))
        )
        return list(result.scalars().all())


class SegmentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: dict) -> TripSegmentORM:
        segment = TripSegmentORM(**data)
        self.session.add(segment)
        await self.session.commit()
        await self.session.refresh(segment)
        return segment

    async def update(self, segment_id: str, **kwargs) -> None:
        kwargs["updated_at"] = datetime.now(timezone.utc)
        await self.session.execute(
            update(TripSegmentORM).where(TripSegmentORM.id == segment_id).values(**kwargs)
        )
        await self.session.commit()

    async def get_by_trip(self, trip_id: str) -> list[TripSegmentORM]:
        result = await self.session.execute(
            select(TripSegmentORM).where(TripSegmentORM.trip_id == trip_id)
        )
        return list(result.scalars().all())


class EscalationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: dict) -> EscalationORM:
        escalation = EscalationORM(**data)
        self.session.add(escalation)
        await self.session.commit()
        await self.session.refresh(escalation)
        return escalation

    async def get(self, escalation_id: str) -> EscalationORM | None:
        result = await self.session.execute(
            select(EscalationORM).where(EscalationORM.id == escalation_id)
        )
        return result.scalar_one_or_none()

    async def update(self, escalation_id: str, **kwargs) -> None:
        await self.session.execute(
            update(EscalationORM).where(EscalationORM.id == escalation_id).values(**kwargs)
        )
        await self.session.commit()

    async def get_pending_by_trip(self, trip_id: str) -> list[EscalationORM]:
        result = await self.session.execute(
            select(EscalationORM).where(
                EscalationORM.trip_id == trip_id, EscalationORM.status == "pending"
            )
        )
        return list(result.scalars().all())


class PaymentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: dict) -> PaymentRecordORM:
        record = PaymentRecordORM(**data)
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def update(self, payment_id: str, **kwargs) -> None:
        await self.session.execute(
            update(PaymentRecordORM).where(PaymentRecordORM.id == payment_id).values(**kwargs)
        )
        await self.session.commit()

    async def get_by_segment(self, segment_id: str) -> PaymentRecordORM | None:
        result = await self.session.execute(
            select(PaymentRecordORM).where(PaymentRecordORM.segment_id == segment_id)
        )
        return result.scalar_one_or_none()
