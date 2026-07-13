#!/bin/bash
set -eu

if [ "$#" -ne 5 ]; then
  exit 64
fi

input_dir="$1"
output_bundle="$2"
cidfile="$3"
run_label="$4"
image_ref="$5"

if [ "$(id -u)" -eq 0 ]; then
  exit 77
fi

case "$run_label" in
  *[!a-zA-Z0-9_.-]*|'') exit 64 ;;
esac
case "$image_ref" in
  -*|*[!a-zA-Z0-9._/@:+-]*|'') exit 64 ;;
esac
if [ "${#image_ref}" -gt 256 ]; then
  exit 64
fi

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
  --tmpfs /output:rw,noexec,nosuid,size=64m,mode=0700,uid="$(id -u)",gid="$(id -g)" \
  --user "$(id -u):$(id -g)" \
  --rm \
  --cidfile "$cidfile" \
  --label "eyeagent.attachment-parser.run=$run_label" \
  -v "$input_dir:/input:ro" \
  -v "$output_bundle:/output.bundle:rw" \
  "$image_ref"
