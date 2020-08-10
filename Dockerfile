# Container image that runs your code
FROM maven:3.6.3-jdk-8-slim

# Copies your code file from your action repository to the filesystem path `/` of the container
COPY entrypoint.py .
COPY requirements.txt .

RUN apk add --no-cache git python3 xmlstarlet
RUN pip3 install --no-cache-dir -r requirements.txt

# Code file to execute when the docker container starts up (`entrypoint.sh`)
ENTRYPOINT ["/entrypoint.py"]
