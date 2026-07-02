# trellis-headless-codex-pack
# Source this before invoking headless Codex through Trellis.

host_ip="$(ip route show 2>/dev/null | awk 'tolower($0) ~ /^default/ { print $3; exit }')"

if [ -z "$host_ip" ]; then
  echo "Unable to detect default gateway for Codex proxy." >&2
  echo "Expected a local proxy reachable at http://<default-gateway>:7890." >&2
  return 1 2>/dev/null || exit 1
fi

export http_proxy="http://${host_ip}:7890"
export https_proxy="http://${host_ip}:7890"
export HTTP_PROXY="$http_proxy"
export HTTPS_PROXY="$https_proxy"

echo "Codex proxy: $http_proxy"
