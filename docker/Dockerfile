FROM python:3.8-alpine

RUN pip install -U pip wheel setuptools typing-extensions

ARG install_arg="pymap[redis,admin,sieve,optional]"
ARG install_source=""
RUN apk --update add --virtual build-dependencies python3-dev build-base \
  && pip install "${install_arg}${install_source}" \
  && apk del build-dependencies

ENTRYPOINT ["pymap"]
