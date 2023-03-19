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

And add the `$CERT_FILE` and `$KEY_FILE`  environment variables to the service,
e.g.:

```yaml
    environment:
      CERT_FILE: /etc/ssl/private/mail/fullchain.pem
      KEY_FILE: /etc/ssl/private/mail/privkey.pem
```

The Docker image includes a [healthcheck][6] that will mark the service as
`unhealthy` if `$KEY_FILE` has changed since the service started.

[1]: https://github.com/icgood/pymap
[2]: https://github.com/icgood/proxy-protocol/pkgs/container/proxy-protocol
[3]: https://docs.docker.com/compose/compose-file/#volumes
[4]: https://letsencrypt.org/
[5]: https://github.com/icgood/letsencrypt-service/pkgs/container/letsencrypt-service
[6]: https://docs.docker.com/compose/compose-file/compose-file-v3/#healthcheck
