#!/bin/sh
set -eu

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
repo_root="$(CDPATH= cd -- "$script_dir/.." && pwd)"
compose_file="$repo_root/docker-compose.qa.yml"
project="ttclamavcontract$(date -u +%Y%m%d%H%M%S)$$"
image='clamav/clamav:1.4.5@sha256:48eaad9644475c2d466ce6d4ba2da892dbd4dcd47713201d31b665364655cc3c'

test -f "$compose_file"

cleanup() {
  docker compose -p "$project" -f "$compose_file" down \
    --volumes --remove-orphans --timeout 15 >/dev/null 2>&1 || true
}
trap cleanup EXIT HUP INT TERM

docker compose -p "$project" -f "$compose_file" up -d template-twin-clamav
container_id="$(docker compose -p "$project" -f "$compose_file" ps -q template-twin-clamav)"
test -n "$container_id"

attempt=0
while :; do
  health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container_id")"
  state="$(docker inspect --format '{{.State.Status}}' "$container_id")"
  if [ "$health" = "healthy" ]; then
    break
  fi
  if [ "$state" = "exited" ] || [ "$state" = "dead" ]; then
    docker logs "$container_id" >&2
    exit 1
  fi
  attempt="$((attempt + 1))"
  if [ "$attempt" -ge 120 ]; then
    docker logs "$container_id" >&2
    echo "ClamAV did not become healthy within 10 minutes" >&2
    exit 1
  fi
  sleep 5
done

# Image metadata advertises the conventional clamd port, but the service must
# bind no TCP socket and Compose must publish no host port.
test "$(docker inspect --format '{{json .HostConfig.PortBindings}}' "$container_id")" = "{}"
test "$(docker inspect --format '{{len .NetworkSettings.Networks}}' "$container_id")" = "1"
scanner_network="$(docker inspect --format '{{range $name, $_ := .NetworkSettings.Networks}}{{$name}}{{end}}' "$container_id")"
case "$scanner_network" in
  *template_twin_scanner) ;;
  *)
    echo "ClamAV joined an unexpected network" >&2
    exit 1
    ;;
esac
docker compose -p "$project" -f "$compose_file" exec -T template-twin-clamav \
  sh -ec '! grep -Eq "^[[:space:]]*(TCPAddr|TCPSocket)[[:space:]]" /etc/clamav/clamd.conf'

socket_volume="${project}_qa_clamav_socket"
docker run --rm --network none --user 1001:1001 --group-add 101 \
  --volume "$socket_volume:/scanner:ro" --entrypoint /bin/sh "$image" -ec '
    test -S /scanner/clamd.sock
    printf "%s\n" "LocalSocket /scanner/clamd.sock" > /tmp/clamd-client.conf
    clamdscan --config-file=/tmp/clamd-client.conf --ping=1 >/dev/null
  '

docker compose -p "$project" -f "$compose_file" exec -T template-twin-clamav \
  sh -ec '
    clean_file="$(mktemp)"
    eicar_file="$(mktemp)"
    trap "rm -f \"$clean_file\" \"$eicar_file\"" EXIT
    printf "%s\n" "synthetic clean Template Twin runtime contract" > "$clean_file"
    if ! clean_result="$(clamdscan --stream --config-file=/etc/clamav/clamd.conf "$clean_file" 2>&1)"; then
      printf "%s\n" "$clean_result" >&2
      exit 1
    fi
    printf "%s%s%s" \
      "X5O!P%@AP[4\\PZX54(P^)7CC)7}\$EICAR-" \
      "STANDARD-ANTIVIRUS-TEST-FILE!" \
      "\$H+H*" > "$eicar_file"
    set +e
    result="$(clamdscan --stream --config-file=/etc/clamav/clamd.conf "$eicar_file" 2>&1)"
    status=$?
    set -e
    if [ "$status" -ne 1 ]; then
      printf "%s\n" "$result" >&2
      exit 1
    fi
    printf "%s" "$result" | grep -Eiq "EICAR.* FOUND"
  '

version="$(docker compose -p "$project" -f "$compose_file" exec -T template-twin-clamav clamdscan --version)"
printf 'PASS template-twin-clamav-runtime-contract-v1 %s %s\n' \
  'sha256:48eaad9644475c2d466ce6d4ba2da892dbd4dcd47713201d31b665364655cc3c' \
  "$version"
