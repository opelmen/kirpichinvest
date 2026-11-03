#!/bin/bash
# Ставит nginx-сайт и сертификат Let's Encrypt для одного домена на VPS. Идемпотентно.
# usage: setup-site.sh <domain> <conf-file> <cert-domains comma-separated> <email>
set -euo pipefail
DOMAIN="$1"; CONF="$2"; CERTS="$3"; EMAIL="$4"
export DEBIAN_FRONTEND=noninteractive
command -v nginx >/dev/null || { apt-get update -qq; apt-get install -y -qq nginx; }
command -v certbot >/dev/null || { apt-get update -qq; apt-get install -y -qq certbot; }
mkdir -p /var/www/letsencrypt "/var/www/$DOMAIN"
LIVE="/etc/letsencrypt/live/$DOMAIN/fullchain.pem"
if [ ! -f "$LIVE" ]; then
  # временный http-блок только для выпуска сертификата
  cat > "/etc/nginx/sites-available/$DOMAIN" <<NG
server { listen 80; listen [::]:80; server_name ${CERTS//,/ };
  location ^~ /.well-known/acme-challenge/ { root /var/www/letsencrypt; }
  location / { root /var/www/$DOMAIN; try_files \$uri \$uri/ =404; } }
NG
  ln -sf "/etc/nginx/sites-available/$DOMAIN" "/etc/nginx/sites-enabled/$DOMAIN"
  nginx -t && systemctl reload nginx
  args=(); IFS=, read -ra ds <<<"$CERTS"; for d in "${ds[@]}"; do args+=(-d "$d"); done
  certbot certonly --webroot -w /var/www/letsencrypt --cert-name "$DOMAIN" "${args[@]}" \
    --non-interactive --agree-tos -m "$EMAIL" --keep-until-expiring
fi
cp "$CONF" "/etc/nginx/sites-available/$DOMAIN"
ln -sf "/etc/nginx/sites-available/$DOMAIN" "/etc/nginx/sites-enabled/$DOMAIN"
nginx -t && systemctl reload nginx
# продление: certbot ставит таймер; после продления перечитываем nginx
mkdir -p /etc/letsencrypt/renewal-hooks/deploy
printf '#!/bin/sh\nsystemctl reload nginx\n' > /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
echo "site $DOMAIN ready: root /var/www/$DOMAIN"
