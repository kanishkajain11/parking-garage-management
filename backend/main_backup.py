from fastapi import FastAPI

from database import Base, engine
import models

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Parking Garage Management API",
    description="REST API for managing parking garage operations.",
    version="1.0.0",
)


@app.get("/")
def root():
    return {
        "message": "Parking Garage Management API is running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }