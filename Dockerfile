FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt setup.py README.md ./
COPY src ./src

RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir .

ENTRYPOINT ["rig"]
CMD ["--help"]
