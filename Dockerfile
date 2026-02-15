# Build stage
FROM python:3.12-slim as builder

WORKDIR /build

# Copy only what's needed for building the wheel
COPY setup.py pyproject.toml ./
COPY kioku/ ./kioku/

# Build the wheel inside the container
RUN pip wheel --no-deps -w /build/dist .

# Runtime stage
FROM python:3.12-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy the wheel from the build stage
COPY --from=builder /build/dist/*.whl /tmp/

# Install the wheel
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl

ENV HOST=0.0.0.0
ENV PORT=8000

EXPOSE 8000

CMD ["kioku"]
