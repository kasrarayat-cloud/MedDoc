#!/usr/bin/env bash
# QuillMD PRODUCTION host bootstrap: Ubuntu 24.04 LTS on EC2 (x86_64), run as root through AWS
# Systems Manager (Session Manager or Run Command). Never through SSH; this script disables sshd.
#
# DRY RUN BY DEFAULT. Without --execute it validates every input, verifies the release artifact and
# prints the plan; it changes nothing and needs no root. It was written and dry-run tested off-host;
# the --execute path has NOT been run anywhere yet (docs/rebuild/v1/cutover-plan.md, gate G2).
#
#   bootstrap-host.sh --release-sha <40 hex> --artifact <quillmd-<sha>.tar.gz> --artifact-sha256 <64 hex> \
#                     --aws-cli-artifact <awscli-exe-linux-x86_64-<version>.zip> --aws-cli-sha256 <64 hex> \
#                     --data-volume-id vol-<17 hex> [--existing-state-volume] \
#                     [--word-sdk-artifact <tar.gz> --word-sdk-sha256 <64 hex>] [--execute]
#
# Every host value (paths, service identity and its fixed number, ports, region, secret name, CA
# bundle path) comes from rebuild/ops/production_profile.json via `deployment_profile.py --shell`,
# read from the release that carries this script. The operator supplies only identities, each checked:
# the commit, the artifact and its sha256, the AWS CLI v2 bundle (a versioned file whose signature was
# verified per AWS's instructions and whose sha256 is recorded in the declaration; not the snap, whose
# confinement is not qualified inside the sandboxed environment unit), the encrypted data volume, and
# optionally the Word runtime.
#
# Steps, in order; each refuses rather than overwrites:
#   1 preconditions   root; Ubuntu 24.04; EC2 with IMDSv2 only; region = profile; no Docker; no
#                     /opt/meddoc-pro; install root absent; identity absent or exactly the profile's.
#   2 identity        non-login system user+group with the profile's FIXED number, created before
#                     any package so nothing else can take it; no supplementary groups.
#   3 packages        nginx, python3.12-venv, ffmpeg, postgresql-client-16, libseccomp2, openssl,
#                     unattended-upgrades (security only, no automatic reboot); AWS CLI v2 bundle. No Docker.
#   4 host hardening  swap off and removed; no core dumps; bounded persistent journal; sysctl; sshd off.
#   5 state volume    the EBS data volume must be encrypted with alias/quillmd-production-data and
#                     attached here; formatted only when blank (or adopted with --existing-state-volume
#                     when it carries the state marker); mounted nodev,nosuid at the state root by UUID;
#                     the empty mount point underneath is made immutable so nothing lands on the root disk.
#   6 release         artifact verified (sha256, pax commit id, single prefix, profile sha) and only
#                     rebuild/ installed root-owned, without group/other write; venv; collectstatic.
#   7 configuration   /etc/quillmd-production (operator/ and ingress/ root 0700), self-signed ALB target
#                     certificate, admin allowlist "deny all;", RDS CA bundle (sha printed for the
#                     activation commit, and compared when the profile already pins it).
#   8 units and proxy production units installed and verified, NOT enabled or started; nginx site
#                     installed and tested, nginx left stopped; CloudWatch agent config staged.
#   9 receipt         /var/lib/quillmd-bootstrap/receipt.json (root 0600) with every hash.
set -euo pipefail
umask 077

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
release_app=$(cd -- "$script_dir/../.." && pwd -P)
PYTHON=/usr/bin/python3
DATA_KEY_ALIAS=alias/quillmd-production-data
STATE_MARKER=.quillmd-production-state
PRIVATE_INSTALL=/opt/meddoc-pro
RDS_CA_URL=https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem

refuse() { echo "bootstrap: REFUSED: $*" >&2; exit 1; }
note() { echo "bootstrap: $*"; }

execute=0 existing_volume=0
release_sha='' artifact='' artifact_sha='' volume_id='' word_artifact='' word_sha='' cli_artifact='' cli_sha=''
while [ $# -gt 0 ]; do
  case "$1" in
    --execute) execute=1; shift ;;
    --existing-state-volume) existing_volume=1; shift ;;
    --release-sha|--artifact|--artifact-sha256|--data-volume-id|--word-sdk-artifact|--word-sdk-sha256|\
    --aws-cli-artifact|--aws-cli-sha256)
      [ $# -ge 2 ] || refuse "$1 needs a value"
      case "$1" in
        --release-sha) release_sha=$2 ;;
        --artifact) artifact=$2 ;;
        --artifact-sha256) artifact_sha=$2 ;;
        --data-volume-id) volume_id=$2 ;;
        --word-sdk-artifact) word_artifact=$2 ;;
        --word-sdk-sha256) word_sha=$2 ;;
        --aws-cli-artifact) cli_artifact=$2 ;;
        --aws-cli-sha256) cli_sha=$2 ;;
      esac
      shift 2 ;;
    *) refuse "unknown argument (see the header of this script)" ;;
  esac
done

[[ $release_sha =~ ^[0-9a-f]{40}$ ]] || refuse "--release-sha must be the full 40-character commit"
[[ $artifact_sha =~ ^[0-9a-f]{64}$ ]] || refuse "--artifact-sha256 must be 64 lowercase hex characters"
[[ $volume_id =~ ^vol-[0-9a-f]{17}$ ]] || refuse "--data-volume-id must look like vol-0123456789abcdef0"
[ -n "$artifact" ] && [ -f "$artifact" ] && [ ! -L "$artifact" ] || refuse "--artifact must be an existing regular file"
[ -n "$cli_artifact" ] && [ -f "$cli_artifact" ] && [ ! -L "$cli_artifact" ] || refuse "--aws-cli-artifact must be an existing regular file"
[[ $cli_sha =~ ^[0-9a-f]{64}$ ]] || refuse "--aws-cli-sha256 must be 64 lowercase hex characters"
if [ -n "$word_artifact$word_sha" ]; then
  [ -f "$word_artifact" ] && [ ! -L "$word_artifact" ] || refuse "--word-sdk-artifact must be an existing regular file"
  [[ $word_sha =~ ^[0-9a-f]{64}$ ]] || refuse "--word-sdk-sha256 must be 64 lowercase hex characters"
fi

# --- profile values: read, never evaluated ------------------------------------------------------
profile_text=$("$PYTHON" -B -E -s "$release_app/ops/deployment_profile.py" --shell) || refuse "the production profile is invalid"
declare -A P=()
while IFS='=' read -r key value; do
  case "$key" in
    PROFILE_SHA256|REGION|INSTALL_ROOT|APP_ROOT|STATE_ROOT|CONFIGURATION_ROOT|OPERATOR_DIRECTORY|ENVIRONMENT_FILE|\
ACCOUNT|ACCOUNT_ID_NUMBER|UNIT_PREFIX|DOCTOR_PORT|ADMIN_PORT|CA_BUNDLE|CA_BUNDLE_SHA256|DATABASE_HOST|SECRET_NAME|\
DOCTOR_HOST|ADMIN_HOST)
      P[$key]=$value ;;
    *) refuse "unexpected profile key" ;;
  esac
done <<< "$profile_text"
for key in PROFILE_SHA256 REGION INSTALL_ROOT APP_ROOT STATE_ROOT CONFIGURATION_ROOT OPERATOR_DIRECTORY ACCOUNT \
           ACCOUNT_ID_NUMBER UNIT_PREFIX DOCTOR_PORT ADMIN_PORT CA_BUNDLE SECRET_NAME; do
  [ -n "${P[$key]:-}" ] || refuse "profile value $key is missing"
done
INGRESS_DIRECTORY="${P[CONFIGURATION_ROOT]}/ingress"
UNITS=(environment doctor admin worker heartbeat)

# --- artifact: verified before anything else happens ---------------------------------------------
# The profile sha ties the artifact to this script's profile BYTES, not to this script's commit: an
# artifact of another commit with a byte-identical profile verifies. Run the script extracted from
# the same verified artifact (cutover-plan.md G3 step 2); --release-sha binds the commit.
verification=$("$PYTHON" -B -E -s "$release_app/ops/release_artifact.py" verify --artifact "$artifact" \
  --artifact-sha256 "$artifact_sha" --release-sha "$release_sha" --profile-sha256 "${P[PROFILE_SHA256]}") \
  || refuse "the release artifact failed verification"
note "artifact verified: $verification"
if [ -n "$word_artifact" ]; then
  [ "$(sha256sum -- "$word_artifact" | cut -d' ' -f1)" = "$word_sha" ] || refuse "the Word runtime artifact sha256 differs"
fi
[ "$(sha256sum -- "$cli_artifact" | cut -d' ' -f1)" = "$cli_sha" ] || refuse "the AWS CLI bundle sha256 differs"
AWS=/usr/local/bin/aws

plan() {
  cat <<PLAN
bootstrap plan (profile ${P[PROFILE_SHA256]}, release $release_sha):
  1 preconditions  root, Ubuntu 24.04, EC2 IMDSv2-only in ${P[REGION]}, no Docker, no $PRIVATE_INSTALL, ${P[INSTALL_ROOT]} absent
  2 identity       ${P[ACCOUNT]} uid=gid=${P[ACCOUNT_ID_NUMBER]}, /usr/sbin/nologin, no home, no supplementary groups
  3 packages       nginx python3.12-venv ffmpeg postgresql-client-16 libseccomp2 openssl unzip unattended-upgrades; AWS CLI v2 -> $AWS
  4 hardening      swap off, no core dumps, journal bounded, sysctl, sshd disabled
  5 state volume   $volume_id encrypted with $DATA_KEY_ALIAS -> ${P[STATE_ROOT]} (nodev,nosuid) $( [ $existing_volume = 1 ] && echo "ADOPT existing marker" || echo "FORMAT only if blank" )
  6 release        rebuild/ -> ${P[APP_ROOT]} (root-owned, no group/other write), venv, collectstatic$( [ -n "$word_artifact" ] && echo ", Word runtime" )
  7 configuration  ${P[CONFIGURATION_ROOT]} (operator/ and ingress/ 0700), target certificate, admin deny-all, RDS CA bundle
  8 units          ${UNITS[*]/#/${P[UNIT_PREFIX]}} installed + verified, NOT enabled/started; nginx site tested, nginx stopped
  9 receipt        /var/lib/quillmd-bootstrap/receipt.json
PLAN
}

if [ "$execute" != 1 ]; then
  plan
  note "dry run: nothing was changed. Re-run with --execute as root through SSM to apply."
  exit 0
fi

# ================================= EXECUTE ======================================================
[ "$(id -u)" = 0 ] || refuse "--execute must run as root (through SSM)"

# --- 1 preconditions ------------------------------------------------------------------------------
. /etc/os-release
[ "${ID:-}" = ubuntu ] && [ "${VERSION_ID:-}" = 24.04 ] || refuse "this is not Ubuntu 24.04"
[ "$(uname -m)" = x86_64 ] || refuse "the qualified Word runtime is x86_64; this host is $(uname -m)"
imds() { curl -fsS --max-time 5 -H "X-aws-ec2-metadata-token: $token" "http://169.254.169.254/latest/meta-data/$1"; }
token=$(curl -fsS --max-time 5 -X PUT -H 'X-aws-ec2-metadata-token-ttl-seconds: 120' \
  http://169.254.169.254/latest/api/token) || refuse "no IMDSv2 token: this is not an EC2 instance"
v1_status=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://169.254.169.254/latest/meta-data/ || true)
[ "$v1_status" = 401 ] || refuse "IMDSv1 answers ($v1_status); set the instance metadata option http-tokens=required"
region=$(imds placement/region)
instance_id=$(imds instance-id)
[ "$region" = "${P[REGION]}" ] || refuse "instance region $region differs from the profile region ${P[REGION]}"
if command -v docker >/dev/null 2>&1 || [ -e /run/docker.sock ] || [ -e /var/run/docker.sock ]; then
  refuse "Docker is present; the production profile requires a host without it"
fi
[ ! -e "$PRIVATE_INSTALL" ] || refuse "$PRIVATE_INSTALL exists: this is not a fresh production host"
[ ! -e "${P[INSTALL_ROOT]}" ] || refuse "${P[INSTALL_ROOT]} exists: a bootstrapped host is replaced, never re-bootstrapped"

# --- 2 identity -----------------------------------------------------------------------------------
account=${P[ACCOUNT]} number=${P[ACCOUNT_ID_NUMBER]}
if getent passwd "$account" >/dev/null || getent group "$account" >/dev/null; then
  refuse "$account already exists"
fi
if getent passwd "$number" >/dev/null || getent group "$number" >/dev/null; then
  refuse "uid/gid $number is already taken"
fi
groupadd --system --gid "$number" "$account"
useradd --system --uid "$number" --gid "$number" --no-create-home --home-dir /nonexistent \
  --shell /usr/sbin/nologin --comment "QuillMD production application" "$account"
[ "$(id -Gn "$account")" = "$account" ] || refuse "$account has supplementary groups"
note "identity $account uid=gid=$number"

# --- 3 packages -----------------------------------------------------------------------------------
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q --no-install-recommends nginx python3.12-venv ffmpeg postgresql-client-16 libseccomp2 \
  openssl ca-certificates curl unzip unattended-upgrades
systemctl disable --now nginx
[ ! -e /usr/local/aws-cli ] || refuse "/usr/local/aws-cli already exists"
cli_stage=$(mktemp -d)
unzip -q "$cli_artifact" -d "$cli_stage"
"$cli_stage/aws/install" --bin-dir /usr/local/bin --install-dir /usr/local/aws-cli
rm -rf -- "$cli_stage"
[ -x "$AWS" ] || refuse "the AWS CLI did not install at $AWS"
cat > /etc/apt/apt.conf.d/52quillmd-production <<'APT'
// Security updates only, unattended; reboots happen in a declared maintenance window, never automatically.
Unattended-Upgrade::Allowed-Origins { "${distro_id}:${distro_codename}-security"; "${distro_id}ESMApps:${distro_codename}-apps-security"; "${distro_id}ESM:${distro_codename}-infra-security"; };
Unattended-Upgrade::Automatic-Reboot "false";
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT
chmod 0644 /etc/apt/apt.conf.d/52quillmd-production

# --- 4 host hardening -----------------------------------------------------------------------------
swapoff -a
sed -i.quillmd-bootstrap -E 's@^([^#].*[[:space:]]swap[[:space:]].*)$@# disabled by quillmd bootstrap: \1@' /etc/fstab
[ -z "$(swapon --show --noheadings)" ] || refuse "swap is still active"
install -m 0644 -D "$script_dir/sysctl-quillmd-production.conf" /etc/sysctl.d/60-quillmd-production.conf
sysctl --system >/dev/null
install -m 0644 -D "$script_dir/journald-quillmd-production.conf" /etc/systemd/journald.conf.d/quillmd-production.conf
install -d -m 0755 /etc/systemd/coredump.conf.d
printf '[Coredump]\nStorage=none\nProcessSizeMax=0\n' > /etc/systemd/coredump.conf.d/quillmd-production.conf
chmod 0644 /etc/systemd/coredump.conf.d/quillmd-production.conf
systemctl restart systemd-journald
systemctl disable --now ssh.socket ssh.service 2>/dev/null || true

# --- 5 state volume -------------------------------------------------------------------------------
volume_facts=$("$AWS" ec2 describe-volumes --region "$region" --volume-ids "$volume_id" \
  --query 'Volumes[0].[Encrypted,KmsKeyId,Attachments[0].InstanceId,Attachments[0].State]' --output text) \
  || refuse "cannot describe $volume_id (the bootstrap role needs ec2:DescribeVolumes)"
read -r encrypted kms_key attached_to attach_state <<< "$volume_facts"
expected_key=$("$AWS" kms describe-key --region "$region" --key-id "$DATA_KEY_ALIAS" \
  --query KeyMetadata.Arn --output text) || refuse "cannot resolve $DATA_KEY_ALIAS"
[ "$encrypted" = True ] || refuse "$volume_id is not encrypted"
[ "$kms_key" = "$expected_key" ] || refuse "$volume_id is not encrypted with $DATA_KEY_ALIAS"
[ "$attached_to" = "$instance_id" ] && [ "$attach_state" = attached ] || refuse "$volume_id is not attached to this instance"
device="/dev/disk/by-id/nvme-Amazon_Elastic_Block_Store_${volume_id/-/}"
[ -b "$device" ] || refuse "no block device for $volume_id at $device"
state=${P[STATE_ROOT]}
filesystem=$(blkid -p -s TYPE -o value "$device" || true)
if [ "$existing_volume" = 1 ]; then
  [ "$filesystem" = ext4 ] || refuse "--existing-state-volume needs an ext4 state volume"
else
  [ -z "$filesystem" ] || refuse "$volume_id already has a filesystem; adopt it explicitly with --existing-state-volume"
  mkfs.ext4 -q -L qmd-prod-state "$device"
fi
uuid=$(blkid -p -s UUID -o value "$device")
[[ $uuid =~ ^[0-9a-f-]{36}$ ]] || refuse "could not read the state filesystem UUID"
install -d -m 0755 -o root -g root "$state"
[ -z "$(ls -A "$state")" ] || refuse "$state is not empty on the root disk"
chattr +i "$state"
if grep -q "[[:space:]]$state[[:space:]]" /etc/fstab; then refuse "$state already has an fstab entry"; fi
printf 'UUID=%s %s ext4 defaults,nodev,nosuid,nofail,x-systemd.device-timeout=90s 0 2\n' "$uuid" "$state" >> /etc/fstab
systemctl daemon-reload
mount "$state"
mountpoint -q "$state" || refuse "$state did not mount"
if [ "$existing_volume" = 1 ]; then
  [ -f "$state/$STATE_MARKER" ] || refuse "the adopted volume carries no $STATE_MARKER marker"
  for name in files mail proofs tmp; do
    [ "$(stat -c '%u:%g:%a' "$state/$name")" = "$number:$number:700" ] || refuse "$state/$name ownership differs on the adopted volume"
  done
else
  printf 'QuillMD production state volume\ncreated %s on %s from %s\n' "$(date -u +%FT%TZ)" "$instance_id" "$volume_id" > "$state/$STATE_MARKER"
  chmod 0600 "$state/$STATE_MARKER"
  rmdir "$state/lost+found" 2>/dev/null || true
  for name in files mail proofs tmp; do
    install -d -m 0700 -o "$account" -g "$account" "$state/$name"
  done
fi
chown root:"$account" "$state"
chmod 0710 "$state"

# --- 6 release ------------------------------------------------------------------------------------
"$PYTHON" -B -E -s "$release_app/ops/release_artifact.py" install --artifact "$artifact" \
  --artifact-sha256 "$artifact_sha" --release-sha "$release_sha" --profile-sha256 "${P[PROFILE_SHA256]}" \
  --destination "${P[INSTALL_ROOT]}" || refuse "the release did not install"
app=${P[APP_ROOT]}
(umask 022 && python3.12 -m venv "$app/.venv" && "$app/.venv/bin/pip" install -q --no-cache-dir -r "$app/requirements.txt")
(cd "$app" && umask 022 && env -i PATH=/usr/bin:/bin QUILLMD_SECRET_KEY=bootstrap-collectstatic-only \
  QUILLMD_DB_PASSWORD=unused QUILLMD_ENV_MANAGED=1 QUILLMD_STATE_DIR="$state" \
  "$app/.venv/bin/python" -B manage.py collectstatic --noinput -v 0)
if [ -n "$word_artifact" ]; then
  install -d -m 0755 "$app/.word-sdk"
  tar -xzf "$word_artifact" -C "$app/.word-sdk" --no-same-owner
fi
chown -R root:root "${P[INSTALL_ROOT]}"
chmod -R go-w "${P[INSTALL_ROOT]}"

# --- 7 configuration ------------------------------------------------------------------------------
config=${P[CONFIGURATION_ROOT]}
install -d -m 0755 -o root -g root "$config"
install -d -m 0700 -o root -g root "${P[OPERATOR_DIRECTORY]}" "$INGRESS_DIRECTORY"
openssl req -x509 -newkey rsa:3072 -nodes -days 825 -subj '/CN=quillmd-production-alb-target' \
  -keyout "$INGRESS_DIRECTORY/target.key" -out "$INGRESS_DIRECTORY/target.crt" 2>/dev/null
chmod 0600 "$INGRESS_DIRECTORY/target.key" "$INGRESS_DIRECTORY/target.crt"
printf '# Reviewed operator source addresses only, one "allow <address>;" per line, above this.\ndeny all;\n' \
  > "$INGRESS_DIRECTORY/admin-allow.conf"
chmod 0600 "$INGRESS_DIRECTORY/admin-allow.conf"
curl -fsS --max-time 30 -o "${P[CA_BUNDLE]}.partial" "$RDS_CA_URL" || refuse "could not fetch the RDS CA bundle"
ca_sha=$(sha256sum -- "${P[CA_BUNDLE]}.partial" | cut -d' ' -f1)
if [ -n "${P[CA_BUNDLE_SHA256]}" ] && [ "$ca_sha" != "${P[CA_BUNDLE_SHA256]}" ]; then
  rm -f -- "${P[CA_BUNDLE]}.partial"
  refuse "the fetched RDS CA bundle differs from the profile's pinned sha256"
fi
chmod 0644 "${P[CA_BUNDLE]}.partial"
mv -- "${P[CA_BUNDLE]}.partial" "${P[CA_BUNDLE]}"
install -m 0644 "$script_dir/cloudwatch-agent.json" "$config/cloudwatch-agent.json"

# --- 8 units and proxy ----------------------------------------------------------------------------
declare -A unit_hashes=()
for unit in "${P[UNIT_PREFIX]}"{environment,doctor,admin,worker,heartbeat}.service "${P[UNIT_PREFIX]}heartbeat.timer"; do
  source_unit="$app/deploy/production/$unit"
  [ -f "$source_unit" ] || refuse "the release lacks $unit"
  [ ! -e "/etc/systemd/system/$unit" ] || refuse "/etc/systemd/system/$unit already exists"
  install -m 0644 -o root -g root "$source_unit" "/etc/systemd/system/$unit"
  unit_hashes[$unit]=$(sha256sum -- "/etc/systemd/system/$unit" | cut -d' ' -f1)
done
systemctl daemon-reload
systemd-analyze verify /etc/systemd/system/"${P[UNIT_PREFIX]}"*.service /etc/systemd/system/"${P[UNIT_PREFIX]}"*.timer
install -m 0644 "$app/deploy/production/nginx-quillmd-production.conf" /etc/nginx/sites-available/quillmd-production.conf
rm -f /etc/nginx/sites-enabled/default
ln -s /etc/nginx/sites-available/quillmd-production.conf /etc/nginx/sites-enabled/quillmd-production.conf
nginx -t -q || refuse "nginx rejected the production site"

# --- 9 receipt ------------------------------------------------------------------------------------
install -d -m 0700 /var/lib/quillmd-bootstrap
{
  printf '{"format":1,"completed_at":"%s","instance_id":"%s","region":"%s",' "$(date -u +%FT%TZ)" "$instance_id" "$region"
  printf '"release_sha":"%s","artifact_sha256":"%s","profile_sha256":"%s",' "$release_sha" "$artifact_sha" "${P[PROFILE_SHA256]}"
  printf '"state_volume":"%s","state_uuid":"%s","adopted_existing_volume":%s,' "$volume_id" "$uuid" "$([ $existing_volume = 1 ] && echo true || echo false)"
  printf '"identity":{"account":"%s","uid":%s,"gid":%s},' "$account" "$number" "$number"
  printf '"rds_ca_bundle_sha256":"%s","word_runtime_sha256":"%s","aws_cli_sha256":"%s","units":{' "$ca_sha" "$word_sha" "$cli_sha"
  first=1
  for unit in "${!unit_hashes[@]}"; do
    [ $first = 1 ] || printf ','
    printf '"%s":"%s"' "$unit" "${unit_hashes[$unit]}"
    first=0
  done
  printf '},"services_enabled":false,"services_started":false,"nginx_started":false}\n'
} > /var/lib/quillmd-bootstrap/receipt.json
chmod 0600 /var/lib/quillmd-bootstrap/receipt.json
"$PYTHON" -c 'import json,sys; json.load(open(sys.argv[1]))' /var/lib/quillmd-bootstrap/receipt.json \
  || refuse "the receipt is not valid JSON"
note "complete. RDS CA bundle sha256 = $ca_sha (pin it in the activation commit if the profile does not yet)."
note "nothing is enabled or started; activation follows docs/rebuild/v1/cutover-plan.md."
