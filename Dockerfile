FROM python:3.8.12-slim-bullseye
 
RUN apt-get update && apt-get -y install curl
 
# ENV POETRY_VERSION 1.1.11
RUN curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/install-poetry.py  | python - 

COPY poetry.lock pyproject.toml /src/
WORKDIR /src

ENV PATH="/root/.local/bin/poetry:${PATH}"

# do not create venv since we are in the container already 
RUN /root/.local/bin/poetry config virtualenvs.create false 

RUN /root/.local/bin/poetry install --no-dev

# RUN source .venv/bin/activate

COPY . /src/
WORKDIR /src

EXPOSE 80

ENV REDIS_URL=redis://redis_server:6379

ENTRYPOINT [ "bash","/src/docker-entrypoint.sh" ]
CMD ["python", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "80", "--workers", "1"]
