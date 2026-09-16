# Single-container build for Hugging Face Spaces (free tier).
#
# Why Spaces and not Vercel/Render for the backend: the models need ~505 MB of
# RAM once loaded, and TensorFlow alone is 1.4 GB on disk. Vercel's Python limit
# is 250 MB and Render's free tier gives 512 MB — both fail. Spaces gives 16 GB
# and is built for exactly this.
#
# For local development use backend/Dockerfile and docker-compose.yml instead;
# this one exists because Spaces requires a Dockerfile at the repository root
# and an app listening on port 7860.

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    # Spaces runs as uid 1000 with a writable $HOME; anything that caches
    # elsewhere (matplotlib, keras, HF hub) fails on a read-only path.
    HOME=/home/user \
    MPLCONFIGDIR=/home/user/.cache/matplotlib \
    KERAS_HOME=/home/user/.keras

RUN useradd --create-home --uid 1000 user

# libgomp is what XGBoost and scikit-learn link against for OpenMP. Without it
# the failure is an ImportError at runtime rather than an error at build time.
# ca-certificates is not optional here: TiDB Cloud refuses a connection that is
# not TLS-verified, and verification needs a trust store. Without it the failure
# is an opaque SSL error that reads like a bad password.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Requirements first so the dependency layer survives code edits — reinstalling
# TensorFlow on every push would make the build unusable.
COPY --chown=user backend/requirements.txt ./backend/requirements.txt
RUN pip install --upgrade pip && pip install -r backend/requirements.txt

# The layout mirrors the repository, because inference_service resolves artifact
# paths relative to the project root (backend/services/../..). Keeping backend/
# one level down means "models/binary_rf_v1.pkl" means the same thing here as on
# a laptop, with no path rewriting.
COPY --chown=user backend/ ./backend/
COPY --chown=user ml/ ./ml/
COPY --chown=user models/ ./models/
COPY --chown=user data/ ./data/

USER user
WORKDIR /app/backend

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
  CMD curl -fsS http://localhost:7860/api/v1/health || exit 1

# One worker on purpose. Each worker loads its own copy of the models (~500 MB),
# and the live-monitor WebSocket fan-out is in-process — a second worker would
# hold connections the first one cannot broadcast to.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
