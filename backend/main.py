from datetime import datetime, timedelta, timezone
from math import ceil
import re

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from database import Base, engine, get_db

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


# =========================================================
# DATABASE
# =========================================================

Base.metadata.create_all(bind=engine)


# =========================================================
# FASTAPI APP
# =========================================================

app = FastAPI(
    title="ParkEase Parking Garage API",
    description="REST API for smart multi-level parking garage management.",
    version="1.0.0",
)


# =========================================================
# CORS
# IMPORTANT: app must exist BEFORE add_middleware
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# HELPERS
# =========================================================

def utc_now_naive():
    """
    SQLite stores our timestamps as naive UTC datetimes.
    Keeping one format avoids aware/naive subtraction errors.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_datetime(value):
    """
    Convert ISO timestamp into naive UTC datetime.
    """
    if not value:
        return utc_now_naive()

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))

        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(
                tzinfo=None
            )

        return parsed

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid datetime format. Use ISO 8601 format.",
        )


def calculate_fee(duration_minutes: int, rate):
    """
    Parking fee rules:
    - Part-hours round UP.
    - First hour uses first_hour_rate.
    - Additional hours use additional_hour_rate.
    - Each 24-hour block uses daily_cap.
    - Remaining partial day is also capped at daily_cap.
    """

    duration_minutes = max(0, int(duration_minutes))

    if duration_minutes == 0:
        return 0.0

    total_hours = ceil(duration_minutes / 60)

    full_days = total_hours // 24
    remaining_hours = total_hours % 24

    fee = full_days * float(rate.daily_cap)

    if remaining_hours > 0:
        remaining_fee = (
            float(rate.first_hour_rate)
            + max(0, remaining_hours - 1)
            * float(rate.additional_hour_rate)
        )

        fee += min(
            remaining_fee,
            float(rate.daily_cap),
        )

    return round(fee, 2)


def serialize_session(session):
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


def get_garage_or_404(db: Session):
    garage = db.query(Garage).first()

    if not garage:
        raise HTTPException(
            status_code=404,
            detail="Garage not found",
        )

    return garage


def get_rate_for_session(db: Session, session):
    """
    Prefer spot-type specific RateCard.
    Fall back to garage PricingConfig.
    """

    rate_card = (
        db.query(RateCard)
        .filter(
            RateCard.garage_id == session.garage_id,
            RateCard.spot_type == session.vehicle_type,
        )
        .first()
    )

    if rate_card:
        return rate_card

    pricing = (
        db.query(PricingConfig)
        .filter(
            PricingConfig.garage_id == session.garage_id
        )
        .first()
    )

    return pricing


# =========================================================
# ROOT / HEALTH
# =========================================================

@app.get("/")
def root():
    return {
        "message": "ParkEase Parking Garage API",
        "docs": "/docs",
        "status": "running",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
    }


# =========================================================
# AUTHENTICATION
# =========================================================

@app.post(
    "/auth/register",
    response_model=AuthResponse,
)
def register(
    data: RegisterRequest,
    db: Session = Depends(get_db),
):
    email = str(data.email).lower().strip()

    existing_user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered",
        )

    user = User(
        name=data.name.strip(),
        email=email,
        password_hash=hash_password(data.password),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)

    return AuthResponse(
        access_token=token,
        user_id=user.id,
        name=user.name,
    )


@app.post(
    "/auth/login",
    response_model=AuthResponse,
)
def login(
    data: LoginRequest,
    db: Session = Depends(get_db),
):
    email = str(data.email).lower().strip()

    user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if not user or not verify_password(
        data.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

    token = create_access_token(user.id)

    return AuthResponse(
        access_token=token,
        user_id=user.id,
        name=user.name,
    )


# =========================================================
# GARAGE
# =========================================================

@app.get("/garage")
def get_garage(
    db: Session = Depends(get_db),
):
    garage = get_garage_or_404(db)

    return {
        "id": garage.id,
        "name": garage.name,
        "address": garage.address,
    }


# =========================================================
# PARKING SPOTS
# =========================================================

@app.get("/parking/spots")
def get_parking_spots(
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
            == spot_type.strip().upper()
        )

    if floor:
        query = query.filter(
            Floor.floor_number == floor
        )

    spots = (
        query
        .order_by(
            Floor.floor_number,
            ParkingSpot.spot_number,
        )
        .all()
    )

    return [
        {
            "id": spot.id,
            "floor": spot.floor.floor_number,
            "spot_number": spot.spot_number,
            "spot_type": spot.spot_type,
            "is_occupied": spot.is_occupied,
            "status": (
                "OCCUPIED"
                if spot.is_occupied
                else "AVAILABLE"
            ),
        }
        for spot in spots
    ]


# =========================================================
# AVAILABILITY
# =========================================================

@app.get("/parking/availability")
def get_parking_availability(
    db: Session = Depends(get_db),
):
    spots = db.query(ParkingSpot).all()

    total = len(spots)

    occupied = sum(
        1
        for spot in spots
        if spot.is_occupied
    )

    result = {}

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

        result[spot_type] = {
            "total": len(type_spots),
            "occupied": sum(
                1
                for spot in type_spots
                if spot.is_occupied
            ),
            "available": sum(
                1
                for spot in type_spots
                if not spot.is_occupied
            ),
        }

    return {
        "total_spots": total,
        "occupied_spots": occupied,
        "available_spots": total - occupied,
        "ev_available": result["EV"]["available"],
        "by_type": result,
    }


# =========================================================
# CHECK-IN
# =========================================================

@app.post("/parking/check-in")
def check_in(
    request: CheckInRequest,
    db: Session = Depends(get_db),
):
    vehicle_plate = (
        request.vehicle_plate
        .strip()
        .upper()
    )

    vehicle_type = (
        request.vehicle_type
        .strip()
        .upper()
    )

    # -----------------------------------------------------
    # VALIDATION
    # -----------------------------------------------------

    if not vehicle_plate:
        raise HTTPException(
            status_code=400,
            detail="Vehicle plate cannot be empty",
        )

    if len(vehicle_plate) > 30:
        raise HTTPException(
            status_code=400,
            detail="Vehicle plate is too long",
        )

    if vehicle_type not in [
        "COMPACT",
        "STANDARD",
        "EV",
    ]:
        raise HTTPException(
            status_code=400,
            detail="Vehicle type must be COMPACT, STANDARD or EV",
        )

    # -----------------------------------------------------
    # DUPLICATE ACTIVE VEHICLE
    # -----------------------------------------------------

    existing_session = (
        db.query(ParkingSession)
        .filter(
            ParkingSession.vehicle_plate
            == vehicle_plate,
            ParkingSession.status == "ACTIVE",
        )
        .first()
    )

    if existing_session:
        raise HTTPException(
            status_code=400,
            detail="Vehicle is already parked",
        )

    # -----------------------------------------------------
    # FIND SPOT
    # -----------------------------------------------------

    spot = None

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

        # EV MUST use EV
        if (
            vehicle_type == "EV"
            and spot.spot_type != "EV"
        ):
            raise HTTPException(
                status_code=400,
                detail="EV vehicle can only be parked in an EV spot",
            )

        # Non-EV should not use EV spot
        if (
            vehicle_type != "EV"
            and spot.spot_type == "EV"
        ):
            raise HTTPException(
                status_code=400,
                detail="Only EV vehicles can use EV spots",
            )

    else:
        # Automatic assignment
        query = (
            db.query(ParkingSpot)
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
                ParkingSpot.spot_type
                == vehicle_type
            )

        spot = (
            query
            .join(Floor)
            .order_by(
                Floor.floor_number,
                ParkingSpot.spot_number,
            )
            .first()
        )

        if not spot:
            raise HTTPException(
                status_code=409,
                detail=f"No available {vehicle_type} parking spot",
            )

    # -----------------------------------------------------
    # GARAGE
    # -----------------------------------------------------

    garage_id = spot.floor.garage_id

    # -----------------------------------------------------
    # CREATE SESSION
    # -----------------------------------------------------

    parking_session = ParkingSession(
        garage_id=garage_id,
        vehicle_plate=vehicle_plate,
        vehicle_type=vehicle_type,
        spot_id=spot.id,
        check_in_time=utc_now_naive(),
        status="ACTIVE",
    )

    spot.is_occupied = True

    db.add(parking_session)

    try:
        db.commit()
        db.refresh(parking_session)

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail="Parking spot or vehicle is already in use",
        )

    return {
        "message": "Vehicle checked in successfully",
        "session_id": parking_session.id,
        "vehicle_plate": parking_session.vehicle_plate,
        "vehicle_type": parking_session.vehicle_type,
        "spot_id": parking_session.spot_id,
        "check_in_time": parking_session.check_in_time,
    }


# =========================================================
# ACTIVE SESSIONS
# =========================================================

@app.get("/parking/active")
def get_active_sessions(
    db: Session = Depends(get_db),
):
    sessions = (
        db.query(ParkingSession)
        .filter(
            ParkingSession.status == "ACTIVE"
        )
        .order_by(
            ParkingSession.check_in_time.desc()
        )
        .all()
    )

    return [
        serialize_session(session)
        for session in sessions
    ]


# =========================================================
# CHECK-OUT
# Supports BOTH:
# /parking/check-out/123
# /parking/check-out/RJ14AB1234
# =========================================================

@app.post("/parking/check-out/{identifier}")
def check_out(
    identifier: str,
    db: Session = Depends(get_db),
):
    parking_session = None

    # First try session ID
    if identifier.isdigit():
        parking_session = (
            db.query(ParkingSession)
            .filter(
                ParkingSession.id
                == int(identifier),
                ParkingSession.status
                == "ACTIVE",
            )
            .first()
        )

    # If not found, try plate
    if not parking_session:
        plate = identifier.strip().upper()

        parking_session = (
            db.query(ParkingSession)
            .filter(
                ParkingSession.vehicle_plate
                == plate,
                ParkingSession.status
                == "ACTIVE",
            )
            .first()
        )

    if not parking_session:
        raise HTTPException(
            status_code=404,
            detail="Active parking session not found",
        )

    # -----------------------------------------------------
    # CHECKOUT TIME
    # -----------------------------------------------------

    checkout_time = utc_now_naive()

    duration_seconds = (
        checkout_time
        - parking_session.check_in_time
    ).total_seconds()

    duration_minutes = max(
        0,
        ceil(duration_seconds / 60),
    )

    # -----------------------------------------------------
    # PRICING
    # -----------------------------------------------------

    rate = get_rate_for_session(
        db,
        parking_session,
    )

    if not rate:
        raise HTTPException(
            status_code=500,
            detail="Pricing configuration not found",
        )

    fee = calculate_fee(
        duration_minutes,
        rate,
    )

    # -----------------------------------------------------
    # UPDATE SESSION
    # -----------------------------------------------------

    parking_session.check_out_time = checkout_time
    parking_session.duration_minutes = duration_minutes
    parking_session.fee = fee
    parking_session.status = "COMPLETED"

    # -----------------------------------------------------
    # RELEASE SPOT
    # -----------------------------------------------------

    spot = (
        db.query(ParkingSpot)
        .filter(
            ParkingSpot.id
            == parking_session.spot_id
        )
        .first()
    )

    if spot:
        spot.is_occupied = False

    db.commit()
    db.refresh(parking_session)

    return {
        "message": "Vehicle checked out successfully",
        "session_id": parking_session.id,
        "vehicle_plate": parking_session.vehicle_plate,
        "spot_id": parking_session.spot_id,
        "duration_minutes": parking_session.duration_minutes,
        "fee": parking_session.fee,
        "check_out_time": parking_session.check_out_time,
    }


# =========================================================
# SEARCH BY PLATE
# =========================================================

@app.get("/parking/search/{vehicle_plate}")
def search_vehicle(
    vehicle_plate: str,
    db: Session = Depends(get_db),
):
    plate = vehicle_plate.strip().upper()

    sessions = (
        db.query(ParkingSession)
        .filter(
            ParkingSession.vehicle_plate
            .ilike(f"%{plate}%")
        )
        .order_by(
            ParkingSession.check_in_time.desc()
        )
        .all()
    )

    return [
        serialize_session(session)
        for session in sessions
    ]


# =========================================================
# HISTORY
# Pagination + Sorting + Search
# =========================================================

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

        "duration_minutes":
            ParkingSession.duration_minutes,

        "status":
            ParkingSession.status,
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

    total_pages = (
        ceil(total / limit)
        if total
        else 0
    )

    return {
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": total_pages,
        "results": [
            serialize_session(session)
            for session in sessions
        ],
        # Alias useful for frontend clients
        "items": [
            serialize_session(session)
            for session in sessions
        ],
    }


# =========================================================
# PRICING - GET
# =========================================================

@app.get("/pricing")
def get_pricing(
    db: Session = Depends(get_db),
):
    garage = get_garage_or_404(db)

    pricing = (
        db.query(PricingConfig)
        .filter(
            PricingConfig.garage_id
            == garage.id
        )
        .first()
    )

    rate_cards = (
        db.query(RateCard)
        .filter(
            RateCard.garage_id
            == garage.id
        )
        .all()
    )

    return {
        "garage_id": garage.id,
        "pricing": (
            {
                "first_hour_rate":
                    pricing.first_hour_rate,
                "additional_hour_rate":
                    pricing.additional_hour_rate,
                "daily_cap":
                    pricing.daily_cap,
            }
            if pricing
            else None
        ),
        "rate_cards": [
            {
                "spot_type": rate.spot_type,
                "first_hour_rate":
                    rate.first_hour_rate,
                "additional_hour_rate":
                    rate.additional_hour_rate,
                "daily_cap":
                    rate.daily_cap,
            }
            for rate in rate_cards
        ],
    }


# =========================================================
# PRICING - UPDATE
# =========================================================

@app.put("/pricing")
def update_pricing(
    data: PricingUpdateRequest,
    db: Session = Depends(get_db),
):
    garage = get_garage_or_404(db)

    if (
        data.first_hour_rate < 0
        or data.additional_hour_rate < 0
        or data.daily_cap < 0
    ):
        raise HTTPException(
            status_code=400,
            detail="Pricing values cannot be negative",
        )

    if data.daily_cap < data.first_hour_rate:
        raise HTTPException(
            status_code=400,
            detail="Daily cap must be at least the first-hour rate",
        )

    # Spot-specific pricing
    if data.spot_type:
        spot_type = data.spot_type.strip().upper()

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

        rate.first_hour_rate = data.first_hour_rate
        rate.additional_hour_rate = (
            data.additional_hour_rate
        )
        rate.daily_cap = data.daily_cap

        db.commit()
        db.refresh(rate)

        return {
            "message": "Spot-type pricing updated",
            "spot_type": rate.spot_type,
            "first_hour_rate":
                rate.first_hour_rate,
            "additional_hour_rate":
                rate.additional_hour_rate,
            "daily_cap":
                rate.daily_cap,
        }

    # General garage pricing
    pricing = (
        db.query(PricingConfig)
        .filter(
            PricingConfig.garage_id
            == garage.id
        )
        .first()
    )

    if not pricing:
        pricing = PricingConfig(
            garage_id=garage.id,
        )
        db.add(pricing)

    pricing.first_hour_rate = (
        data.first_hour_rate
    )

    pricing.additional_hour_rate = (
        data.additional_hour_rate
    )

    pricing.daily_cap = data.daily_cap

    db.commit()
    db.refresh(pricing)

    return {
        "message": "Pricing updated",
        "first_hour_rate":
            pricing.first_hour_rate,
        "additional_hour_rate":
            pricing.additional_hour_rate,
        "daily_cap":
            pricing.daily_cap,
    }


# =========================================================
# T4 - MESSY RATE CARD IMPORT
# =========================================================

def parse_rate_card(raw_text: str):
    """
    Extract valid pricing lines and ignore junk.

    Expected useful examples:

    COMPACT 50 30 300
    STANDARD: 60, 35, 350
    EV = 40 / 25 / 250

    The parser ignores unrelated junk.
    """

    cleaned = {}

    if not raw_text:
        return cleaned

    text = raw_text.upper()

    for line in text.splitlines():

        # Remove commas, currency symbols and separators
        normalized = (
            line
            .replace(",", " ")
            .replace("₹", " ")
            .replace("$", " ")
            .replace("=", " ")
            .replace(":", " ")
            .replace("/", " ")
            .replace("|", " ")
            .replace("-", " ")
        )

        numbers = re.findall(
            r"\d+(?:\.\d+)?",
            normalized,
        )

        if len(numbers) < 3:
            continue

        spot_type = None

        for candidate in [
            "COMPACT",
            "STANDARD",
            "EV",
        ]:
            if re.search(
                rf"\b{candidate}\b",
                normalized,
            ):
                spot_type = candidate
                break

        if not spot_type:
            continue

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
def import_rate_card(
    data: RateCardImportRequest,
    db: Session = Depends(get_db),
):
    garage = get_garage_or_404(db)

    cleaned_rates = parse_rate_card(
        data.raw_text
    )

    if not cleaned_rates:
        raise HTTPException(
            status_code=400,
            detail="No valid rate-card entries found",
        )

    imported = []

    for spot_type, values in cleaned_rates.items():

        if (
            values["first_hour_rate"] < 0
            or values["additional_hour_rate"] < 0
            or values["daily_cap"] < 0
        ):
            continue

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

        imported.append(
            {
                "spot_type": spot_type,
                **values,
            }
        )

    db.commit()

    return {
        "message": "Rate card imported successfully",
        "garage_id": garage.id,
        "imported": imported,
        "ignored_junk": True,
    }


# Alias for alternate evaluator naming
@app.post("/pricing/rate-card/import")
def import_rate_card_alias(
    data: RateCardImportRequest,
    db: Session = Depends(get_db),
):
    return import_rate_card(data, db)


# =========================================================
# T6 - VALET HAND-OFF / TRANSFER
# =========================================================

@app.post("/parking/transfer")
def transfer_session(
    data: TransferRequest,
    db: Session = Depends(get_db),
):
    old_plate = (
        data.old_plate
        .strip()
        .upper()
    )

    new_plate = (
        data.new_plate
        .strip()
        .upper()
    )

    if not old_plate or not new_plate:
        raise HTTPException(
            status_code=400,
            detail="Both old and new plates are required",
        )

    if old_plate == new_plate:
        raise HTTPException(
            status_code=400,
            detail="Old and new plates must be different",
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
            detail="Active session for old plate not found",
        )

    existing_new_plate = (
        db.query(ParkingSession)
        .filter(
            ParkingSession.vehicle_plate
            == new_plate,
            ParkingSession.status
            == "ACTIVE",
        )
        .first()
    )

    if existing_new_plate:
        raise HTTPException(
            status_code=400,
            detail="New plate already has an active parking session",
        )

    original_spot_id = session.spot_id
    original_check_in = session.check_in_time

    session.vehicle_plate = new_plate

    try:
        db.commit()
        db.refresh(session)

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail="Unable to transfer parking session",
        )

    return {
        "message": "Parking session transferred successfully",
        "session_id": session.id,
        "old_plate": old_plate,
        "new_plate": session.vehicle_plate,
        "spot_id": original_spot_id,
        "check_in_time": original_check_in,
        "status": session.status,
    }


# Path-based alias
@app.post("/parking/transfer/{vehicle_plate}")
def transfer_session_by_path(
    vehicle_plate: str,
    data: TransferRequest,
    db: Session = Depends(get_db),
):
    old_plate = (
        vehicle_plate
        .strip()
        .upper()
    )

    new_plate = (
        data.new_plate
        .strip()
        .upper()
    )

    transfer_data = TransferRequest(
        old_plate=old_plate,
        new_plate=new_plate,
    )

    return transfer_session(
        transfer_data,
        db,
    )


# =========================================================
# T2 - NIGHTLY CLOCK JOB
# =========================================================

@app.post("/clock")
def run_clock_job(
    data: ClockRequest,
    db: Session = Depends(get_db),
):
    clock_time = normalize_datetime(
        data.now
    )

    cutoff = (
        clock_time
        - timedelta(hours=24)
    )

    sessions = (
        db.query(ParkingSession)
        .filter(
            ParkingSession.status == "ACTIVE",
            ParkingSession.check_in_time
            <= cutoff,
        )
        .all()
    )

    closed_sessions = []

    for session in sessions:

        duration_seconds = (
            clock_time
            - session.check_in_time
        ).total_seconds()

        duration_minutes = max(
            0,
            ceil(duration_seconds / 60),
        )

        rate = get_rate_for_session(
            db,
            session,
        )

        if not rate:
            continue

        fee = calculate_fee(
            duration_minutes,
            rate,
        )

        session.check_out_time = clock_time
        session.duration_minutes = (
            duration_minutes
        )
        session.fee = fee
        session.status = "COMPLETED"

        spot = (
            db.query(ParkingSpot)
            .filter(
                ParkingSpot.id
                == session.spot_id
            )
            .first()
        )

        if spot:
            spot.is_occupied = False

        closed_sessions.append(
            {
                "session_id": session.id,
                "vehicle_plate":
                    session.vehicle_plate,
                "spot_id":
                    session.spot_id,
                "duration_minutes":
                    duration_minutes,
                "fee": fee,
                "check_out_time":
                    clock_time,
            }
        )

    db.commit()

    return {
        "message": "Clock job completed",
        "clock_time": clock_time,
        "closed_sessions":
            len(closed_sessions),
        "sessions":
            closed_sessions,
    }