# Container image that runs your code
FROM openjdk:8

# Copies your code file from your action repository to the filesystem path `/` of the container
COPY entrypoint.py .
COPY requirements.txt .

RUN apk add --no-cache git python3 xmlstarlet maven
RUN pip3 install --no-cache-dir -r requirements.txt

# Code file to execute when the docker container starts up (`entrypoint.sh`)
ENTRYPOINT ["/entrypoint.py"]
