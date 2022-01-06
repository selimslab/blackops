mypy src

# Remove unused imports
autoflake --in-place -r src/

# Auto fix flake8 warnings
autopep8 --in-place --a --a -r src/

isort src 

black src

# Run hooks on all files
# pre-commit run --all-files




