set -u
export GIT_SSH_COMMAND="ssh -i /root/.ssh/medrax_deploy_key -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
. /etc/network_turbo >/dev/null 2>&1
rm -rf /dev/shm/gh1b
echo "=== verbose clone ==="
git clone --depth 1 --single-branch \
  --branch reports/m5-rrsi-s10-val100-20261120 \
  git@github.com:cw462/MedRAX-reproduction.git /dev/shm/gh1b 2>&1 | tail -12
echo "--- exit: ${PIPESTATUS[0]:-?} ---"
echo
echo "=== result ==="
ls -la /dev/shm/gh1b 2>/dev/null | head
git -C /dev/shm/gh1b log --oneline -3 2>&1 | head -3
git -C /dev/shm/gh1b ls-tree -r --name-only HEAD 2>/dev/null | head -30
echo "files: $(git -C /dev/shm/gh1b ls-tree -r --name-only HEAD 2>/dev/null | wc -l)"
