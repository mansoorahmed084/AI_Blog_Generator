#!/bin/bash
set -e

TARGET="/var/app/current/cookies.txt"

if [ -n "$YTDLP_COOKIES_S3_BUCKET" ] && [ -n "$YTDLP_COOKIES_S3_KEY" ]; then
  echo "[ytdlp] Downloading cookies from s3://$YTDLP_COOKIES_S3_BUCKET/$YTDLP_COOKIES_S3_KEY"
  /usr/bin/aws s3 cp "s3://$YTDLP_COOKIES_S3_BUCKET/$YTDLP_COOKIES_S3_KEY" "$TARGET"
elif [ -n "$YTDLP_COOKIES_B64" ]; then
  echo "[ytdlp] Writing cookies from YTDLP_COOKIES_B64"
  echo "$YTDLP_COOKIES_B64" | base64 -d > "$TARGET"
else
  echo "[ytdlp] No cookies provided (YTDLP_COOKIES_S3_* or YTDLP_COOKIES_B64)"
fi

if [ -f "$TARGET" ]; then
  chown webapp:webapp "$TARGET" || true
  chmod 600 "$TARGET" || true
  echo "[ytdlp] Cookies saved to $TARGET"
fi
