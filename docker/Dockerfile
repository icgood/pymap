FROM python:3.12-slim

WORKDIR /pymap
COPY . .

RUN pip install hatch
RUN hatch env create docker

EXPOSE 143 4190 50051
HEALTHCHECK CMD ./docker/check-stale-pid.sh $KEY_FILE

ENTRYPOINT ["hatch", "-e", "docker", "run", "pymap"]
CMD ["--help"]
