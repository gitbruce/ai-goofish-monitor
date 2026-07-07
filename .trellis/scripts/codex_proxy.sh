# trellis-headless-codex-pack
# Source this before invoking headless Codex through Trellis.

codex_proxy_enabled="$(python3 ./.trellis/scripts/headless_codex_pack.py proxy-enabled)" || {
  return 1 2>/dev/null || exit 1
}

case "$codex_proxy_enabled" in
  1)
    ;;
  *)
    unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
    echo "Codex proxy: disabled"
    return 0 2>/dev/null || exit 0
    ;;
esac

codex_proxy_url="$(python3 ./.trellis/scripts/headless_codex_pack.py proxy-url)" || {
  return 1 2>/dev/null || exit 1
}

if [ -z "$codex_proxy_url" ]; then
  echo "Codex proxy is enabled, but proxy-url is empty." >&2
  return 1 2>/dev/null || exit 1
fi

export http_proxy="$codex_proxy_url"
export https_proxy="$codex_proxy_url"
export HTTP_PROXY="$http_proxy"
export HTTPS_PROXY="$https_proxy"

echo "Codex proxy: $http_proxy"
