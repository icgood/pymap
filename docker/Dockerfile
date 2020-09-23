FROM python:3.8-alpine

RUN pip install -U pip wheel setuptools typing-extensions

ARG install_arg="pymap"
ARG install_arg_opt="redis,admin,sieve,optional"
RUN apk --update add --virtual build-dependencies python3-dev build-base \
  && pip install "${install_arg}[${install_arg_opt}]" \
  && apk del build-dependencies

ENTRYPOINT ["pymap"]
