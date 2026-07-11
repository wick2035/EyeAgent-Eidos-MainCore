#!/bin/bash
set -eu

if [ "$#" -ne 4 ]; then
  exit 64
fi

input_dir="$1"
output_dir="$2"
cidfile="$3"
run_label="$4"

if [ "$(id -u)" -eq 0 ]; then
  exit 77
fi

case "$run_label" in
  *[!a-zA-Z0-9_.-]*|'') exit 64 ;;
esac

cleanup_container() {
  if [ -f "$cidfile" ]; then
    container_id="$(tr -d '\r\n' < "$cidfile" 2>/dev/null || true)"
    if [[ "$container_id" =~ ^[0-9a-f]{64}$ ]]; then
      docker kill "$container_id" >/dev/null 2>&1 || true
      docker rm -f "$container_id" >/dev/null 2>&1 || true
    fi
    rm -f "$cidfile"
  fi
}

trap cleanup_container EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

docker run -i \
  --network none \
  --read-only \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  --pids-limit 64 \
  --memory 768m \
  --cpus 1 \
  --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --user "$(id -u):$(id -g)" \
  --rm \
  --cidfile "$cidfile" \
  --label "eyeagent.attachment-parser.run=$run_label" \
  -v "$input_dir:/input:ro" \
  -v "$output_dir:/output:rw" \
  eyeagent/attachment-parser:1
