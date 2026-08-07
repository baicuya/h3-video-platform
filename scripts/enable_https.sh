#!/usr/bin/env bash
set -euo pipefail

DOMAIN=${1:-}
EMAIL=${2:-}
if [[ ! "$DOMAIN" =~ ^[A-Za-z0-9.-]+$ ]]; then
  echo "usage: $0 <domain> [email]" >&2
  exit 2
fi

PUBLIC_IP=$(curl --fail --silent --show-error https://checkip.amazonaws.com | tr -d '[:space:]')
DNS_IPS=$(getent ahostsv4 "$DOMAIN" | awk '{print $1}' | sort -u)
if ! grep -Fxq "$PUBLIC_IP" <<<"$DNS_IPS"; then
  echo "DNS mismatch: $DOMAIN does not resolve to this server ($PUBLIC_IP)." >&2
  exit 3
fi

SITE=/etc/nginx/sites-available/h3-video-platform.conf
sudo cp "$SITE" "$SITE.before-https"
sudo sed -i "s/server_name _;/server_name $DOMAIN;/" "$SITE"
sudo nginx -t
sudo systemctl reload nginx

CERTBOT_ARGS=(--nginx --non-interactive --agree-tos --redirect -d "$DOMAIN")
if [[ -n "$EMAIL" ]]; then
  CERTBOT_ARGS+=(--email "$EMAIL")
else
  CERTBOT_ARGS+=(--register-unsafely-without-email)
fi
sudo certbot "${CERTBOT_ARGS[@]}"
echo "HTTPS enabled for https://$DOMAIN"

