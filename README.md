# Rentlora Booking Service

This service handles reservations and booking agreements for properties.

## Technology Stack
- FastAPI
- Motor (Async MongoDB)
- Uvicorn

## Environment Variables
- `MONGO_USER` (optional)
- `MONGO_PASSWORD` (optional)
- `MONGO_HOST` (default: `localhost`)
- `MONGO_PORT` (default: `27017`)
- `PORT` (default: `8003`)

## Running Locally

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the service:
   ```bash
   python -m src.main
   ```

## Running with Docker

1. Build the image:
   ```bash
   docker build -t rentlora-booking-service .
   ```

2. Run the container:
   ```bash
   docker run -p 8003:8003 -e MONGO_HOST="host.docker.internal" rentlora-booking-service
   ```
