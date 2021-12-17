
curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/install-poetry.py  | python 

poetry config virtualenvs.in-project true

poetry install 

source .venv/bin/activate

pre-commit install 

