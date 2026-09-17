# ParkEase - Parking Garage Management System

ParkEase is a full-stack parking garage management system built for busy multi-level city-centre garages.

It helps attendants check vehicles in and out, assign suitable parking spots, calculate parking fees, track EV availability, search vehicle history, and prevent double parking.

## Features

- Multi-level parking garage
- Compact, Standard and EV spots
- EV vehicles restricted to EV spots
- Automatic suitable spot assignment
- Manual spot selection
- Check-in and check-out
- Tiered hourly pricing
- Part-hours rounded up
- Daily fee cap
- Persistent SQLite database
- Vehicle search by plate
- Parking history
- Pagination
- Server-side sorting
- User registration and login
- Messy rate-card import
- Automatic 24+ hour session closing through `/clock`
- Valet plate transfer
- Swagger API documentation
- React dashboard

## Tech Stack

### Backend
- Python
- FastAPI
- SQLAlchemy
- SQLite
- JWT
- Pydantic

### Frontend
- React
- Vite
- JavaScript
- CSS

## Setup

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python seed.py
uvicorn main:app --reload --host 0.0.0.0 --port 8000