set -u
export GIT_SSH_COMMAND="ssh -i /root/.ssh/medrax_deploy_key -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=20"
. /etc/network_turbo >/dev/null 2>&1
cd /dev/shm/rrsi_push

LOCAL_SHA=$(git rev-parse HEAD)
REMOTE_SHA=$(timeout 60 git ls-remote origin refs/heads/archive/rrsi-20261119-21 | awk '{print $1}')
echo "local  $LOCAL_SHA"
echo "remote $REMOTE_SHA"

echo
echo "=== tree-only fetch (no blobs) ==="
rm -rf /dev/shm/verify2
timeout 180 git clone -q --depth 1 --filter=blob:none --no-checkout \
  --single-branch --branch archive/rrsi-20261119-21 \
  git@github.com:cw462/MedRAX-reproduction.git /dev/shm/verify2 2>&1 | tail -3
if [ -d /dev/shm/verify2/.git ]; then
  echo "remote tree files: $(git -C /dev/shm/verify2 ls-tree -r --name-only HEAD | wc -l)"
  echo "remote upstream files: $(git -C /dev/shm/verify2 ls-tree -r --name-only HEAD | grep -c 'test848_v5/upstream')"
  echo "local  tree files: $(git ls-tree -r --name-only HEAD | wc -l)"
  D=$(git -C /dev/shm/verify2 ls-tree -r --name-only HEAD | sort | md5sum | cut -d' ' -f1)
  L=$(git ls-tree -r --name-only HEAD | sort | md5sum | cut -d' ' -f1)
  echo "remote filelist md5 $D"
  echo "local  filelist md5 $L"
  [ "$D" = "$L" ] && echo "TREE MATCH: remote file list is identical" || echo "TREE DIFFERS"
else
  echo "tree-only clone failed (will rely on commit sha equality)"
fi

echo
echo "=== final verdict ==="
if [ "$LOCAL_SHA" = "$REMOTE_SHA" ]; then
  echo "OK: remote branch sha == local commit sha."
  echo "    a git commit sha covers the entire tree, so content is bit-identical."
else
  echo "NOT OK: sha mismatch, do NOT delete anything"
fi
