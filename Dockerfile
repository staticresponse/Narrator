# Use the official Python 3.9 image as a base
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Copy only requirements.txt first (to leverage Docker caching)
COPY requirements.txt /app/

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies from requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . /app

# Create necessary directories for uploads and processed files
RUN mkdir -p /app/uploads /app/clean_text

# Expose the port on which the app runs
EXPOSE 5000

# Define the entrypoint to run the application
CMD ["python", "app.py"]
