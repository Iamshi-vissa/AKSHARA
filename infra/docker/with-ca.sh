#!/bin/sh
# Run a command trusting an optional extra CA (BuildKit secret "extra_ca"), e.g. a corporate
# TLS-inspecting proxy. The certificate is only mounted for this step; it never enters a layer.
set -e
if [ -s /run/secrets/extra_ca ]; then
  bundle=/tmp/ca-bundle.pem
  for f in /etc/ssl/certs/ca-certificates.crt /etc/ssl/cert.pem; do [ -f "$f" ] && cat "$f" > "$bundle" && break; done
  cat /run/secrets/extra_ca >> "$bundle"
  export SSL_CERT_FILE="$bundle" PIP_CERT="$bundle" REQUESTS_CA_BUNDLE="$bundle" NODE_EXTRA_CA_CERTS="$bundle"
fi
"$@"
status=$?
rm -f /tmp/ca-bundle.pem
exit $status
