FROM python:3.11-alpine

WORKDIR /pymap
COPY . .

RUN pip install -U pip hatch typing-extensions

RUN apk --update add --virtual build-dependencies \
    build-base python3-dev libffi-dev \
  && hatch env create docker \
  && apk del build-dependencies

EXPOSE 143 4190 50051
HEALTHCHECK CMD ./docker/check-stale-pid.sh $KEY_FILE

ENTRYPOINT ["hatch", "-e", "docker", "run", "pymap"]
CMD ["--help"]
