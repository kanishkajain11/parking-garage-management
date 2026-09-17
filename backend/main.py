from datetime import datetime, timedelta
from math import ceil
import re

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
)
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import (
    Base,
    engine,
    get_db,
)

from models import (
    User,
    Garage,
    Floor,
    ParkingSpot,
    ParkingSession,
    PricingConfig,
    RateCard,
)

from schemas import (
    RegisterRequest,
    LoginRequest,
    AuthResponse,
    CheckInRequest,
    PricingUpdateRequest,
    RateCardImportRequest,
    TransferRequest,
    ClockRequest,
)

from auth import (
    hash_password,
    verify_password,
    create_access_token,
)


Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="ParkEase Parking Garage API",
    description="Multi-level parking garage management system",
    version="1.0.0",
)


# =========================
# CORS
# =========================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================
# HELPERS
# =========================

def get_garage(db: Session):
    garage = (
        db.query(Garage)
        .order_by(Garage.id)
        .first()
    )

    if not garage:
        raise HTTPException(
            status_code=404,
            detail="Garage not found",
        )

    return garage


def parse_clock(value: str | None):
    if not value:
        return datetime.utcnow()

    value = value.replace("Z", "")

    try:
        parsed = datetime.fromisoformat(value)

        if parsed.tzinfo:
            parsed = parsed.replace(tzinfo=None)

        return parsed

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid datetime format",
        )


def get_rate(
    db: Session,
    garage_id: int,
    spot_type: str,
):
    rate = (
        db.query(RateCard)
        .filter(
            RateCard.garage_id == garage_id,
            RateCard.spot_type == spot_type,
        )
        .first()
    )

    if rate:
        return rate

    pricing = (
        db.query(PricingConfig)
        .filter(
            PricingConfig.garage_id == garage_id
        )
        .first()
    )

    if not pricing:
        raise HTTPException(
            status_code=500,
            detail="Pricing configuration not found",
        )

    return pricing


def calculate_fee(
    duration_minutes: int,
    rate,
):
    total_hours = ceil(
        max(duration_minutes, 0) / 60
    )

    if total_hours == 0:
        return 0

    full_days = total_hours // 24
    remaining_hours = total_hours % 24

    fee = full_days * rate.daily_cap

    if remaining_hours > 0:
        remaining_fee = (
            rate.first_hour_rate
            + max(
                0,
                remaining_hours - 1,
            )
            * rate.additional_hour_rate
        )

        fee += min(
            remaining_fee,
            rate.daily_cap,
        )

    return round(fee, 2)


def session_to_dict(session):
    return {
        "id": session.id,
        "vehicle_plate": session.vehicle_plate,
        "vehicle_type": session.vehicle_type,
        "spot_id": session.spot_id,
        "check_in_time": session.check_in_time,
        "check_out_time": session.check_out_time,
        "duration_minutes": session.duration_minutes,
        "fee": session.fee,
        "status": session.status,
    }


# =========================
# ROOT
# =========================

@app.get("/")
def root():
    return {
        "message": "ParkEase Parking Garage API",
        "docs": "/docs",
        "status": "running",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


# =========================
# AUTH
# =========================

@app.post(
    "/auth/register",
    response_model=AuthResponse,
)
def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
):
    existing = (
        db.query(User)
        .filter(User.email == request.email)
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Email already registered",
        )

    user = User(
        name=request.name,
        email=request.email,
        password_hash=hash_password(
            request.password
        ),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)

    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id,
        "name": user.name,
    }


@app.post(
    "/auth/login",
    response_model=AuthResponse,
)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
):
    user = (
        db.query(User)
        .filter(User.email == request.email)
        .first()
    )

    if not user or not verify_password(
        request.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

    token = create_access_token(user.id)

    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id,
        "name": user.name,
    }


# =========================
# GARAGE
# =========================

@app.get("/garage")
def garage_info(
    db: Session = Depends(get_db),
):
    garage = get_garage(db)

    return {
        "id": garage.id,
        "name": garage.name,
        "address": garage.address,
        "floors": len(garage.floors),
    }


# =========================
# SPOTS
# =========================

@app.get("/parking/spots")
def parking_spots(
    spot_type: str | None = None,
    floor: int | None = None,
    db: Session = Depends(get_db),
):
    query = (
        db.query(ParkingSpot)
        .join(Floor)
    )

    if spot_type:
        query = query.filter(
            ParkingSpot.spot_type
            == spot_type.upper()
        )

    if floor:
        query = query.filter(
            Floor.floor_number == floor
        )

    spots = query.order_by(
        Floor.floor_number,
        ParkingSpot.id,
    ).all()

    return {
        "total": len(spots),
        "results": [
            {
                "id": spot.id,
                "floor": spot.floor.floor_number,
                "spot_number": spot.spot_number,
                "spot_type": spot.spot_type,
                "is_occupied": spot.is_occupied,
            }
            for spot in spots
        ],
    }


# =========================
# AVAILABILITY
# =========================

@app.get("/parking/availability")
def parking_availability(
    db: Session = Depends(get_db),
):
    spots = db.query(ParkingSpot).all()

    total = len(spots)
    occupied = sum(
        1 for spot in spots
        if spot.is_occupied
    )

    available = total - occupied

    by_type = {}

    for spot_type in [
        "COMPACT",
        "STANDARD",
        "EV",
    ]:
        type_spots = [
            spot
            for spot in spots
            if spot.spot_type == spot_type
        ]

        type_occupied = sum(
            1
            for spot in type_spots
            if spot.is_occupied
        )

        by_type[spot_type] = {
            "total": len(type_spots),
            "occupied": type_occupied,
            "available": (
                len(type_spots)
                - type_occupied
            ),
        }

    return {
        "total_spots": total,
        "occupied_spots": occupied,
        "available_spots": available,
        "ev_available": by_type["EV"][
            "available"
        ],
        "by_type": by_type,
    }


# =========================
# CHECK-IN
# =========================

@app.post("/parking/check-in")
def check_in(
    request: CheckInRequest,
    db: Session = Depends(get_db),
):
    garage = get_garage(db)

    plate = request.vehicle_plate.strip().upper()

    vehicle_type = request.vehicle_type.upper()

    if vehicle_type not in [
        "STANDARD",
        "EV",
    ]:
        raise HTTPException(
            status_code=400,
            detail="Vehicle type must be STANDARD or EV",
        )

    existing_vehicle = (
        db.query(ParkingSession)
        .filter(
            ParkingSession.vehicle_plate == plate,
            ParkingSession.status == "ACTIVE",
        )
        .first()
    )

    if existing_vehicle:
        raise HTTPException(
            status_code=400,
            detail="Vehicle is already parked",
        )

    # Specific spot
    if request.spot_id is not None:

        spot = (
            db.query(ParkingSpot)
            .filter(
                ParkingSpot.id
                == request.spot_id
            )
            .first()
        )

        if not spot:
            raise HTTPException(
                status_code=404,
                detail="Parking spot not found",
            )

        if spot.is_occupied:
            raise HTTPException(
                status_code=400,
                detail="Parking spot is already occupied",
            )

        if (
            vehicle_type == "EV"
            and spot.spot_type != "EV"
        ):
            raise HTTPException(
                status_code=400,
                detail="EV vehicle can only be parked in an EV spot",
            )

    # Automatic spot assignment
    else:

        query = (
            db.query(ParkingSpot)
            .join(Floor)
            .filter(
                ParkingSpot.is_occupied == False
            )
        )

        if vehicle_type == "EV":
            query = query.filter(
                ParkingSpot.spot_type == "EV"
            )
        else:
            query = query.filter(
                ParkingSpot.spot_type.in_(
                    ["STANDARD", "COMPACT"]
                )
            )

        spot = query.order_by(
            Floor.floor_number,
            ParkingSpot.id,
        ).first()

        if not spot:
            raise HTTPException(
                status_code=400,
                detail="No suitable parking spot available",
            )

    now = datetime.utcnow()

    session = ParkingSession(
        garage_id=garage.id,
        vehicle_plate=plate,
        vehicle_type=vehicle_type,
        spot_id=spot.id,
        check_in_time=now,
        status="ACTIVE",
    )

    spot.is_occupied = True

    db.add(session)
    db.commit()
    db.refresh(session)

    return {
        "message": "Vehicle checked in successfully",
        "session_id": session.id,
        "vehicle_plate": plate,
        "spot_id": spot.id,
        "spot_type": spot.spot_type,
        "check_in_time": now,
    }


# =========================
# ACTIVE SESSIONS
# =========================

@app.get("/parking/active")
def active_sessions(
    db: Session = Depends(get_db),
):
    sessions = (
        db.query(ParkingSession)
        .filter(
            ParkingSession.status
            == "ACTIVE"
        )
        .order_by(
            ParkingSession.check_in_time
        )
        .all()
    )

    return {
        "total": len(sessions),
        "results": [
            session_to_dict(session)
            for session in sessions
        ],
    }


# =========================
# CHECK-OUT
# =========================

@app.post(
    "/parking/check-out/{vehicle_plate}"
)
def check_out(
    vehicle_plate: str,
    db: Session = Depends(get_db),
):
    plate = vehicle_plate.strip().upper()

    session = (
        db.query(ParkingSession)
        .filter(
            ParkingSession.vehicle_plate == plate,
            ParkingSession.status == "ACTIVE",
        )
        .first()
    )

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Active parking session not found",
        )

    checkout_time = datetime.utcnow()

    duration = (
        checkout_time
        - session.check_in_time
    )

    duration_minutes = max(
        0,
        int(
            duration.total_seconds() / 60
        ),
    )

    spot = (
        db.query(ParkingSpot)
        .filter(
            ParkingSpot.id == session.spot_id
        )
        .first()
    )

    if not spot:
        raise HTTPException(
            status_code=500,
            detail="Parking spot not found",
        )

    rate = get_rate(
        db,
        session.garage_id,
        spot.spot_type,
    )

    fee = calculate_fee(
        duration_minutes,
        rate,
    )

    session.check_out_time = checkout_time
    session.duration_minutes = duration_minutes
    session.fee = fee
    session.status = "COMPLETED"

    spot.is_occupied = False

    db.commit()

    return {
        "message": "Vehicle checked out successfully",
        "session_id": session.id,
        "vehicle_plate": session.vehicle_plate,
        "spot_id": session.spot_id,
        "duration_minutes": duration_minutes,
        "fee": fee,
        "check_out_time": checkout_time,
    }


# =========================
# HISTORY
# =========================

@app.get("/parking/history")
def parking_history(
    page: int = 1,
    limit: int = 10,
    sort_by: str = "check_in_time",
    order: str = "desc",
    search: str | None = None,
    db: Session = Depends(get_db),
):
    allowed_sort_fields = {
        "check_in_time":
            ParkingSession.check_in_time,
        "check_out_time":
            ParkingSession.check_out_time,
        "vehicle_plate":
            ParkingSession.vehicle_plate,
        "fee":
            ParkingSession.fee,
    }

    if sort_by not in allowed_sort_fields:
        raise HTTPException(
            status_code=400,
            detail="Invalid sort field",
        )

    if order.lower() not in [
        "asc",
        "desc",
    ]:
        raise HTTPException(
            status_code=400,
            detail="Order must be asc or desc",
        )

    page = max(1, page)
    limit = min(
        max(1, limit),
        100,
    )

    query = db.query(ParkingSession)

    if search:
        query = query.filter(
            ParkingSession.vehicle_plate.ilike(
                f"%{search.strip().upper()}%"
            )
        )

    sort_column = allowed_sort_fields[
        sort_by
    ]

    if order.lower() == "desc":
        query = query.order_by(
            sort_column.desc()
        )
    else:
        query = query.order_by(
            sort_column.asc()
        )

    total = query.count()

    sessions = (
        query
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "page": page,
        "limit": limit,
        "total": total,
        "results": [
            session_to_dict(session)
            for session in sessions
        ],
    }


# =========================
# SEARCH
# =========================

@app.get("/parking/search")
def search_vehicle(
    plate: str,
    db: Session = Depends(get_db),
):
    results = (
        db.query(ParkingSession)
        .filter(
            ParkingSession.vehicle_plate.ilike(
                f"%{plate.strip().upper()}%"
            )
        )
        .order_by(
            ParkingSession.check_in_time.desc()
        )
        .all()
    )

    return {
        "total": len(results),
        "results": [
            session_to_dict(session)
            for session in results
        ],
    }


# =========================
# PRICING
# =========================

@app.get("/pricing")
def get_pricing(
    db: Session = Depends(get_db),
):
    garage = get_garage(db)

    rates = (
        db.query(RateCard)
        .filter(
            RateCard.garage_id
            == garage.id
        )
        .order_by(
            RateCard.spot_type
        )
        .all()
    )

    return {
        "garage_id": garage.id,
        "rates": [
            {
                "spot_type": rate.spot_type,
                "first_hour_rate":
                    rate.first_hour_rate,
                "additional_hour_rate":
                    rate.additional_hour_rate,
                "daily_cap":
                    rate.daily_cap,
            }
            for rate in rates
        ],
    }


@app.put("/pricing")
def update_pricing(
    request: PricingUpdateRequest,
    db: Session = Depends(get_db),
):
    garage = get_garage(db)

    if request.spot_type:
        spot_type = request.spot_type.upper()

        if spot_type not in [
            "COMPACT",
            "STANDARD",
            "EV",
        ]:
            raise HTTPException(
                status_code=400,
                detail="Invalid spot type",
            )

        rate = (
            db.query(RateCard)
            .filter(
                RateCard.garage_id
                == garage.id,
                RateCard.spot_type
                == spot_type,
            )
            .first()
        )

        if not rate:
            rate = RateCard(
                garage_id=garage.id,
                spot_type=spot_type,
            )
            db.add(rate)

        rate.first_hour_rate = (
            request.first_hour_rate
        )
        rate.additional_hour_rate = (
            request.additional_hour_rate
        )
        rate.daily_cap = request.daily_cap

    else:
        rates = (
            db.query(RateCard)
            .filter(
                RateCard.garage_id
                == garage.id
            )
            .all()
        )

        for rate in rates:
            rate.first_hour_rate = (
                request.first_hour_rate
            )
            rate.additional_hour_rate = (
                request.additional_hour_rate
            )
            rate.daily_cap = request.daily_cap

    db.commit()

    return {
        "message": "Pricing updated successfully"
    }


# =========================
# T4 - MESSY RATE CARD
# =========================

def parse_rate_card(raw_text: str):

    cleaned = {}

    lines = raw_text.upper().splitlines()

    for line in lines:

        line = line.replace(
            ",",
            "",
        )

        numbers = re.findall(
            r"\d+(?:\.\d+)?",
            line,
        )

        if len(numbers) < 3:
            continue

        for spot_type in [
            "COMPACT",
            "STANDARD",
            "EV",
        ]:

            if spot_type in line:

                cleaned[spot_type] = {
                    "first_hour_rate":
                        float(numbers[0]),
                    "additional_hour_rate":
                        float(numbers[1]),
                    "daily_cap":
                        float(numbers[2]),
                }

    return cleaned


@app.post("/pricing/import")
@app.post("/pricing/rate-card/import")
def import_rate_card(
    request: RateCardImportRequest,
    db: Session = Depends(get_db),
):
    garage = get_garage(db)

    parsed = parse_rate_card(
        request.raw_text
    )

    if not parsed:
        raise HTTPException(
            status_code=400,
            detail="No valid rate-card entries found",
        )

    imported = []

    for spot_type, values in parsed.items():

        rate = (
            db.query(RateCard)
            .filter(
                RateCard.garage_id
                == garage.id,
                RateCard.spot_type
                == spot_type,
            )
            .first()
        )

        if not rate:
            rate = RateCard(
                garage_id=garage.id,
                spot_type=spot_type,
            )
            db.add(rate)

        rate.first_hour_rate = (
            values["first_hour_rate"]
        )

        rate.additional_hour_rate = (
            values["additional_hour_rate"]
        )

        rate.daily_cap = (
            values["daily_cap"]
        )

        imported.append(spot_type)

    db.commit()

    return {
        "message": "Messy rate card cleaned and imported",
        "imported_spot_types": imported,
        "rates": parsed,
    }


# =========================
# T6 - VALET TRANSFER
# =========================

@app.post("/parking/transfer")
def transfer_session(
    request: TransferRequest,
    db: Session = Depends(get_db),
):
    old_plate = request.old_plate.strip().upper()
    new_plate = request.new_plate.strip().upper()

    if old_plate == new_plate:
        raise HTTPException(
            status_code=400,
            detail="New plate must be different",
        )

    session = (
        db.query(ParkingSession)
        .filter(
            ParkingSession.vehicle_plate
            == old_plate,
            ParkingSession.status
            == "ACTIVE",
        )
        .first()
    )

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Active session not found",
        )

    existing = (
        db.query(ParkingSession)
        .filter(
            ParkingSession.vehicle_plate
            == new_plate,
            ParkingSession.status
            == "ACTIVE",
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=400,
            detail="New plate already has an active session",
        )

    original_spot = session.spot_id
    original_check_in = session.check_in_time

    session.vehicle_plate = new_plate

    db.commit()

    return {
        "message": "Parking session transferred successfully",
        "old_plate": old_plate,
        "new_plate": new_plate,
        "spot_id": original_spot,
        "check_in_time": original_check_in,
    }


@app.post(
    "/parking/transfer/{vehicle_plate}"
)
def transfer_session_by_path(
    vehicle_plate: str,
    request: TransferRequest,
    db: Session = Depends(get_db),
):
    request.old_plate = vehicle_plate

    return transfer_session(
        request,
        db,
    )


# =========================
# T2 - NIGHTLY CLOCK JOB
# =========================

@app.post("/clock")
def run_clock(
    request: ClockRequest | None = None,
    db: Session = Depends(get_db),
):
    now = parse_clock(
        request.now
        if request
        else None
    )

    cutoff = now - timedelta(
        hours=24
    )

    sessions = (
        db.query(ParkingSession)
        .filter(
            ParkingSession.status
            == "ACTIVE",
            ParkingSession.check_in_time
            < cutoff,
        )
        .all()
    )

    closed = []

    for session in sessions:

        duration = (
            now
            - session.check_in_time
        )

        duration_minutes = max(
            0,
            int(
                duration.total_seconds()
                / 60
            ),
        )

        spot = (
            db.query(ParkingSpot)
            .filter(
                ParkingSpot.id
                == session.spot_id
            )
            .first()
        )

        if not spot:
            continue

        rate = get_rate(
            db,
            session.garage_id,
            spot.spot_type,
        )

        fee = calculate_fee(
            duration_minutes,
            rate,
        )

        session.check_out_time = now
        session.duration_minutes = (
            duration_minutes
        )
        session.fee = fee
        session.status = "COMPLETED"

        spot.is_occupied = False

        closed.append(
            {
                "session_id": session.id,
                "vehicle_plate":
                    session.vehicle_plate,
                "spot_id":
                    session.spot_id,
                "duration_minutes":
                    duration_minutes,
                "fee": fee,
            }
        )

    db.commit()

    return {
        "message": "Clock job completed",
        "clock_time": now,
        "closed_sessions": len(closed),
        "sessions": closed,
    }