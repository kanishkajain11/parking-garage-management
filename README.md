cat > README.md <<'EOF'
# ParkEase 🚗

ParkEase is a full-stack parking garage management system built for a busy multi-level parking garage.

The idea is simple: parking attendants should be able to check vehicles in, assign the right parking spot, check them out, calculate the correct fee, and quickly find parking records when needed.

The system also handles EV parking, parking history, configurable rates, long-running sessions, messy rate-card imports, and valet vehicle hand-offs.

---

## Features

- User registration and login
- JWT-based authentication
- Multi-level parking garage management
- COMPACT, STANDARD and EV parking spots
- Automatic parking spot assignment
- EV vehicles can only use EV spots
- Live parking and EV availability
- Vehicle check-in and check-out
- Parking fee calculation
- First-hour rate, additional-hour rate and daily cap
- Partial hours rounded up
- Parking history
- Vehicle search by number plate
- Server-side pagination and sorting
- Configurable parking rates
- Messy rate-card import and cleaning
- Automatic billing for sessions parked over 24 hours
- Valet hand-off / vehicle plate transfer
- Persistent SQLite database
- REST APIs
- Swagger API documentation
- React-based dashboard

---

## Tech Stack

### Backend
- Python
- FastAPI
- SQLAlchemy
- SQLite
- Pydantic
- JWT Authentication
- Passlib

### Frontend
- React
- Vite
- JavaScript
- CSS

---

## Project Structure

```text
parking-garage-management/
│
├── backend/
│   ├── main.py
│   ├── models.py
│   ├── schemas.py
│   ├── database.py
│   ├── auth.py
│   └── seed.py
│
├── frontend/
│   ├── src/
│   │   └── App.jsx
│   ├── package.json
│   └── vite.config.js
│
├── README.md
├── REASONING.md
└── AI_LOGS.md