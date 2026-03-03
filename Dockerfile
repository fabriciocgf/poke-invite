# Use an official lightweight Python image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

# Expose the port the app runs on
EXPOSE 5000

# Use Gunicorn to serve the Flask app in production
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:5000", "app:app"]