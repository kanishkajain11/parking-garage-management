...# Technical Reasoning

## 1. Problem Understanding

The goal was to build a parking garage management system for a busy multi-level garage.

The main workflow is:

Vehicle arrives → Find a valid spot → Check-in → Track parking session → Checkout → Calculate fee → Release spot → Keep history.

Along with the basic parking flow, the system also needs to handle EV parking, authentication, search, pagination, sorting and persistent database storage.

The additional requirements were handled as part of the same system:

- T4 - Messy rate card import
- T2 - Automatic billing for sessions parked over 24 hours
- T6 - Valet hand-off by transferring an active session to another plate

---

## 2. Architecture

I kept the application simple by separating the frontend and backend.

```text
React Frontend
      |
      | REST APIs
      ↓
FastAPI Backend
      |
      | SQLAlchemy
      ↓
SQLite Database 

Database Design

The main entities are:

User
Garage
Floor
ParkingSpot
ParkingSession
PricingConfig / RateCard

A garage contains multiple floors, and each floor contains multiple parking spots.

A parking session stores the vehicle, parking spot, check-in time, checkout time, duration and fee.

Completed sessions are not deleted when a vehicle checks out. The parking spot becomes available again, while the session remains in the database for history.
EV Parking

EV vehicles have a specific parking requirement.

EV vehicle → EV spot only

During check-in, the selected spot is validated.

If a regular spot is selected for an EV vehicle, the request is rejected.

When the system automatically assigns a spot, it also looks specifically for an available EV spot.

The availability API separately shows EV capacity. 

User Login
    ↓
View Garage Availability
    ↓
Vehicle Check-in
    ↓
Assign Valid Parking Spot
    ↓
Active Parking Session
    ↓
        ┌───────────────┐
        │               │
        ↓               ↓
   Normal Checkout   >24 Hour Clock Job
        │               │
        └───────┬───────┘
                ↓
          Calculate Fee
                ↓
          Close Session
                ↓
          Release Spot
                ↓
          Parking History