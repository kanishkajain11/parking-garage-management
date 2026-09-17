from database import (
    Base,
    engine,
    SessionLocal,
)

from models import (
    Garage,
    Floor,
    ParkingSpot,
    PricingConfig,
    RateCard,
)


Base.metadata.create_all(bind=engine)

db = SessionLocal()

try:
    garage = (
        db.query(Garage)
        .order_by(Garage.id)
        .first()
    )

    if not garage:
        garage = Garage(
            name="City Centre Parking Garage",
            address="City Centre",
        )

        db.add(garage)
        db.commit()
        db.refresh(garage)

    # Floors
    for floor_number in range(1, 4):

        floor = (
            db.query(Floor)
            .filter(
                Floor.garage_id == garage.id,
                Floor.floor_number
                == floor_number,
            )
            .first()
        )

        if not floor:
            floor = Floor(
                garage_id=garage.id,
                floor_number=floor_number,
            )

            db.add(floor)
            db.commit()
            db.refresh(floor)

        # Compact
        for number in range(1, 11):

            exists = (
                db.query(ParkingSpot)
                .filter(
                    ParkingSpot.floor_id
                    == floor.id,
                    ParkingSpot.spot_number
                    == f"C{number}",
                )
                .first()
            )

            if not exists:
                db.add(
                    ParkingSpot(
                        floor_id=floor.id,
                        spot_number=f"C{number}",
                        spot_type="COMPACT",
                        is_occupied=False,
                    )
                )

        # Standard
        for number in range(1, 11):

            exists = (
                db.query(ParkingSpot)
                .filter(
                    ParkingSpot.floor_id
                    == floor.id,
                    ParkingSpot.spot_number
                    == f"S{number}",
                )
                .first()
            )

            if not exists:
                db.add(
                    ParkingSpot(
                        floor_id=floor.id,
                        spot_number=f"S{number}",
                        spot_type="STANDARD",
                        is_occupied=False,
                    )
                )

        # EV
        for number in range(1, 6):

            exists = (
                db.query(ParkingSpot)
                .filter(
                    ParkingSpot.floor_id
                    == floor.id,
                    ParkingSpot.spot_number
                    == f"E{number}",
                )
                .first()
            )

            if not exists:
                db.add(
                    ParkingSpot(
                        floor_id=floor.id,
                        spot_number=f"E{number}",
                        spot_type="EV",
                        is_occupied=False,
                    )
                )

    # Legacy/global pricing config
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
            first_hour_rate=50,
            additional_hour_rate=30,
            daily_cap=300,
        )

        db.add(pricing)

    # Default rate cards.
    # These are fallback/demo values until
    # the actual messy rate card is imported.
    defaults = {
        "COMPACT": (50, 30, 300),
        "STANDARD": (50, 30, 300),
        "EV": (50, 30, 300),
    }

    for spot_type, values in defaults.items():

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
                first_hour_rate=values[0],
                additional_hour_rate=values[1],
                daily_cap=values[2],
            )

            db.add(rate)

    db.commit()

    total_spots = (
        db.query(ParkingSpot)
        .count()
    )

    print(
        f"Seed complete. Total spots: {total_spots}"
    )

finally:
    db.close()