FROM python:3.10.0-slim-bullseye
 
# RUN apt clean && apt-get update && apt-get -y install curl
 
# ENV POETRY_VERSION 1.1.11
# RUN curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/install-poetry.py  | python 

RUN python3 -m pip install --user --upgrade pip

RUN pip3 install poetry 

# do not create venv since we are in the container already 
RUN poetry config virtualenvs.create false 

COPY poetry.lock pyproject.toml /blackops/
WORKDIR /blackops

RUN poetry install 

# copy venv 
COPY . /blackops/
WORKDIR /blackops

ENV FLASK_APP=blackops/api/app:app

CMD [ "python3", "-m" , "flask", "run", "--host=0.0.0.0"]