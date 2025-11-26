FROM python:3.12-slim

WORKDIR /github/workspace

COPY update_readme.py /action/update_readme.py

RUN pip install --no-cache-dir pyyaml

ENTRYPOINT ["python", "/action/update_readme.py"]
