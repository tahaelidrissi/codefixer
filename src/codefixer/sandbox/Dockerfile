FROM python:3.12-slim

RUN pip install --no-cache-dir pytest

RUN useradd --create-home --uid 1000 sandbox
USER sandbox

WORKDIR /repo
