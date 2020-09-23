icgood/pymap
============

Runs a [pymap][1] IMAP server in a Docker container.

## Usage

First, create a new service in your `docker-compose.yml`:

```yaml
  imap-server:
    image: icgood/pymap
```

Declare one or more host port bindings:

```yaml
    ports:
      - "143:143"
      - "4190:4190"
      - "9090:9090"
```

Alternatively, use a [proxy-protocol][2] service to expose your IMAP ports to
preserve connection metadata. You will need to add `--proxy-protocol detect` to
the _pymap_ arguments below for this configuration.

Finally, modify the service entrypoint to declare the desired arguments:

```yaml
    entrypoint: >-
      pymap --debug dict --demo-data
```

The above example creates a basic in-memory server with `demouser`/`demopass`
credentials. See the [pymap][1] documentation for more useful ideas.

### SSL Certificates

If you need to provide certificates for TLS, some additional configuration is
necessary. The below examples are using [Let's Encrypt][4] via the
[icgood/letsencrypt-service][5] image, but should be adapted for other
configurations.

First, expose your certificates directory as a volume, e.g.:

```yaml
    volumes:
      - /etc/ssl/private:/etc/ssl/private
```

And add the new arguments to the entrypoint, e.g.:

```yaml
    entrypoint: >-
      pymap --debug
        --cert /etc/ssl/private/mail/fullchain.pem
        --key /etc/ssl/private/mail/privkey.pem
        dict --demo-data
```

Finally, add a healthcheck so that [pymap][1] will restart whenever a new
certificate is generated.

```yaml
    healthcheck:
      interval: 10s
      retries: 1
      test: test /etc/ssl/private/mail/privkey.pem -ot /tmp/pymap.pid
```

[1]: https://github.com/icgood/pymap
[2]: https://hub.docker.com/repository/docker/icgood/proxy-protocol
[3]: https://docs.docker.com/compose/compose-file/#volumes
[4]: https://letsencrypt.org/
[5]: https://hub.docker.com/repository/docker/icgood/letsencrypt-service
