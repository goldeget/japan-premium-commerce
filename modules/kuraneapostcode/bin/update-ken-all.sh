#!/bin/sh
set -eu

official_url='https://www.post.japanpost.jp/service/search/zipcode/download/kogaki/zip/ken_all.zip'
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
importer="$script_dir/import-ken-all.php"

for tool in curl unzip php mktemp grep sed; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        printf 'Required command is missing: %s\n' "$tool" >&2
        exit 127
    fi
done

if [ ! -f "$importer" ]; then
    printf 'The Japan Post CSV importer is missing: %s\n' "$importer" >&2
    exit 2
fi

tmp_dir=$(mktemp -d "${TMPDIR:-/tmp}/kuranea-ken-all.XXXXXX")
cleanup() {
    rm -rf -- "$tmp_dir"
}
trap cleanup 0
trap 'exit 1' HUP INT TERM

archive="$tmp_dir/ken_all.zip"
csv="$tmp_dir/KEN_ALL.CSV"

printf '%s\n' 'Downloading the official Japan Post KEN_ALL archive.'
download_details=''
if download_details=$(curl \
    --fail \
    --silent \
    --show-error \
    --location \
    --retry 3 \
    --retry-delay 2 \
    --max-time 180 \
    --proto '=https' \
    --proto-redir '=https' \
    --output "$archive" \
    --write-out '%{http_code}\n%{url_effective}' \
    "$official_url"); then
    curl_status=0
else
    curl_status=$?
fi

http_status=$(printf '%s\n' "$download_details" | sed -n '1p')
effective_url=$(printf '%s\n' "$download_details" | sed -n '2p')
case "$http_status" in
    [0-9][0-9][0-9]) ;;
    *) http_status='unknown' ;;
esac

effective_host='unavailable'
case "$effective_url" in
    https://*) authority=${effective_url#https://} ;;
    http://*) authority=${effective_url#http://} ;;
    *) authority='' ;;
esac
authority=${authority%%/*}
authority=${authority%%\?*}
authority=${authority%%\#*}
authority=${authority##*@}
case "$authority" in
    ''|*[!A-Za-z0-9.-]*) ;;
    *) effective_host=$authority ;;
esac

if [ "$curl_status" -ne 0 ]; then
    printf 'Japan Post KEN_ALL download failed (curl exit: %s, HTTP status: %s, effective host: %s); active postcode data was not changed.\n' \
        "$curl_status" "$http_status" "$effective_host" >&2
    exit 1
fi

case "$effective_url" in
    https://www.post.japanpost.jp/*) ;;
    *)
        printf 'Refusing an unexpected Japan Post archive redirect (HTTP status: %s, effective host: %s).\n' \
            "$http_status" "$effective_host" >&2
        exit 1
        ;;
esac

if ! unzip -tq "$archive" >/dev/null; then
    printf '%s\n' 'The downloaded Japan Post archive failed its ZIP integrity check.' >&2
    exit 1
fi

if ! members=$(unzip -Z1 "$archive"); then
    printf '%s\n' 'Could not list the downloaded Japan Post archive.' >&2
    exit 1
fi
if ! printf '%s\n' "$members" | grep -Fxq 'KEN_ALL.CSV'; then
    printf '%s\n' 'The Japan Post archive does not contain the expected KEN_ALL.CSV file.' >&2
    exit 1
fi

if ! unzip -p "$archive" KEN_ALL.CSV > "$csv" || [ ! -s "$csv" ]; then
    printf '%s\n' 'The Japan Post KEN_ALL.CSV file could not be extracted or was empty.' >&2
    exit 1
fi

printf '%s\n' 'Importing the validated CSV into the KURANEA postcode index.'
php "$importer" --file="$csv"
