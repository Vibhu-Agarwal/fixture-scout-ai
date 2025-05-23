# Use an official Python slim image as a parent image
FROM python:3.12-slim

# Set environment variables for Python behavior
ENV PYTHONDONTWRITEBYTECODE 1  # Prevents python from writing .pyc files to disc
ENV PYTHONUNBUFFERED 1         # Prevents python from buffering stdout/stderr

# Set the working directory in the container
WORKDIR /app

# Install system dependencies if any are needed by your Python packages
# Example: RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

# Copy the requirements file first to leverage Docker's layer caching
COPY requirements.txt .

# Install Python dependencies
# Using --no-cache-dir reduces image size
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code into the container
# This assumes your application code (main.py, config.py, services/, etc.)
# is within an 'app' subdirectory relative to this Dockerfile.
COPY ./app ./app

# Cloud Run provides the PORT environment variable.
# The application inside the container should listen on this port.
# We don't need to EXPOSE here because Cloud Run handles port exposure based on the PORT env var.
# However, EXPOSE can be good for documentation or if used with other orchestrators.
# For Cloud Run, it's not strictly necessary if your CMD uses $PORT.
# EXPOSE 8080 # Or whatever $PORT typically is, for documentation.

# Define the command to run the application.
# Uvicorn will serve the FastAPI application located at app.main:app.
# It will listen on 0.0.0.0 to accept connections from any IP (necessary within container).
# The port is dynamically set by the PORT environment variable provided by Cloud Run (defaults to 8080).
# If PORT is not set (e.g. local docker run without -e PORT=xxxx), Uvicorn might default or error.
# We can provide a fallback port for Uvicorn if $PORT is not set, e.g. using shell parameter expansion.
# However, for Cloud Run, PORT will always be set.
# For local 'docker run', you'd use 'docker run -e PORT=8000 -p 8000:8000 ...'
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
