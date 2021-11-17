FROM python:3.8.12-slim-bullseye
 
RUN apt-get update && apt-get -y install curl
 
# ENV POETRY_VERSION 1.1.11
RUN curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/install-poetry.py  | python - 


# RUN export PATH="/root/.local/bin:"$PATH
# RUN python3 -m pip install --user --upgrade pip

# RUN pip3 install poetry 

# do not create venv since we are in the container already 
# RUN /root/.local/bin/poetry config virtualenvs.create false 

COPY poetry.lock pyproject.toml /blackops/
WORKDIR /blackops

RUN /root/.local/bin/poetry install 

RUN /root/.local/bin/poetry shell 

# copy venv 
COPY . /blackops/
WORKDIR /blackops

ENTRYPOINT [ "/blackops/docker-entrypoint.sh" ]
CMD ["uvicorn", "blackops.api.main:app", "--host", "0.0.0.0"]
