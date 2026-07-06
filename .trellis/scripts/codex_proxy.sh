# trellis-headless-codex-pack
# Source this before invoking headless Codex through Trellis.

case "${CODEX_USE_PROXY:-1}" in
  0|false|False|FALSE|no|No|NO|off|Off|OFF)
    unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
    echo "Codex proxy: disabled"
    return 0 2>/dev/null || exit 0
    ;;
esac

host_ip="$(ip route show | grep -i default | awk '{print $3}')"

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
