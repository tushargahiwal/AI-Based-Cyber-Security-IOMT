# TensorFlow and XGBoost wheels are large; the slim image plus explicit build
# tooling is still smaller and patches faster than the full python image.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# The layout inside the image mirrors the repository, because inference_service
# resolves artifact paths relative to the project root (backend/services/../..).
# Keeping backend/ one level down means "models/binary_rf_v1.pkl" means the same
# thing in the container as it does on a laptop, with no path rewriting.
WORKDIR /app/backend

# libgomp is what XGBoost and scikit-learn link against for OpenMP; without it
# the failure is an ImportError at runtime rather than an error at build time,
# which is a miserable way to find out.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 curl \
 && rm -rf /var/lib/apt/lists/*

# Requirements first so the dependency layer is cached across code changes —
# reinstalling TensorFlow on every edit would make this unusable.
COPY backend/requirements.txt ./requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY backend/ ./
COPY ml/ /app/ml/

# models/ and data/ are mounted at run time rather than baked in: they hold the
# trained artifacts and the capture, so a retrain should not mean an image
# rebuild. The directories are created so a missing mount fails loudly on the
# first inference instead of at import.
RUN mkdir -p /app/models /app/data

RUN useradd --create-home --uid 1000 iomt && chown -R iomt:iomt /app
USER iomt

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD curl -fsS http://localhost:8000/api/v1/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
