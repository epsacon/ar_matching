FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY ar_matching.py .

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Run the application
# Assuming your FastAPI app is defined as: app = FastAPI() in ar_matching.py
CMD ["uvicorn", "ar_matching:app", "--host", "0.0.0.0", "--port", "8000"]
```

### **2. Create .dockerignore**

Create `.dockerignore` file:
```
.idea/
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
venv/
.venv/
env/
*.env
.git/
.gitignore
.pytest_cache/
.mypy_cache/
*.log
.DS_Store
*.swp
Test_Cases/
test_matching_api.py
README.md
*.md
Dockerfile
docker-compose.yml