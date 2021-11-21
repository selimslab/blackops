FROM python:3.8.12-slim-bullseye
 
RUN apt-get update && apt-get -y install curl
 
# ENV POETRY_VERSION 1.1.11
RUN curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/install-poetry.py  | python - 

COPY poetry.lock pyproject.toml /blackops/
WORKDIR /blackops

ENV PATH="/root/.local/bin/poetry:${PATH}"

# do not create venv since we are in the container already 
RUN /root/.local/bin/poetry config virtualenvs.create false 

RUN /root/.local/bin/poetry install --no-dev

# RUN source .venv/bin/activate

COPY . /blackops/
WORKDIR /blackops

EXPOSE 7846 8000

# ENTRYPOINT [ "bash","/blackops/docker-entrypoint.sh" ]
CMD ["python", "-m", "uvicorn", "blackops.api.main:app", "--host", "0.0.0.0", "--port", "7846", "--workers", "1"]
