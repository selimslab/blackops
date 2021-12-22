# Remove unused imports
autoflake --in-place -r blackops/

# Auto fix flake8 warnings
autopep8 --in-place --a --a -r blackops/
