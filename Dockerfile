# Container image that runs your code
FROM python:3-alpine

# Copies your code file from your action repository to the filesystem path `/` of the container
COPY entrypoint.py .
COPY requirements.txt .

RUN pip3 install --no-cache-dir -r requirements.txt
RUN apk add --no-cache git

# Code file to execute when the docker container starts up (`entrypoint.sh`)
ENTRYPOINT ["/entrypoint.py"]
