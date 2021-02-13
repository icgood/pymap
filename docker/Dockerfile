FROM python:3.9-alpine

RUN pip install -U pip wheel setuptools typing-extensions

ARG install_arg="pymap[redis,admin,macaroon,sieve,optional]"
ARG install_source=""
RUN apk --update add --virtual build-dependencies \
    build-base python3-dev libffi-dev \
  && pip install "${install_arg}${install_source}" \
  && apk del build-dependencies

EXPOSE 143 4190 50051

ENTRYPOINT ["pymap"]
CMD ["--help"]
