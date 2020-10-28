FROM python:3.8-alpine

RUN pip install -U pip wheel setuptools typing-extensions

ARG install_arg="pymap[redis,admin,sieve,optional]"
ARG install_source=""
RUN apk --update add --virtual build-dependencies \
    build-base python3-dev libffi-dev \
  && pip install "${install_arg}${install_source}" \
  && apk del build-dependencies

ENTRYPOINT ["pymap"]
CMD ["--help"]
