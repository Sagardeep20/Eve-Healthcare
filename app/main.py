"""FastAPI application entrypoint."""

from fastapi import FastAPI

from app.api import auth, bookings, centres, payments, tests

app = FastAPI(
    title="EVE Healthcare - Diagnostic Test Bookings",
    version="0.1.0",
    description="Backend service for diagnostic test bookings and simulated payments.",
)

app.include_router(auth.router)
app.include_router(centres.router)
app.include_router(tests.router)
app.include_router(bookings.router)
app.include_router(payments.router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}
