set -u
export GIT_SSH_COMMAND="ssh -i /root/.ssh/medrax_deploy_key -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=20"
chmod 600 /root/.ssh/medrax_deploy_key
. /etc/network_turbo >/dev/null 2>&1
cd /dev/shm/rrsi_push

echo "=== current tree entry for upstream ==="
git ls-tree HEAD artifacts/rrsi_20261119_20261121/test848_v5/ | head -5

echo
echo "=== nested .git dirs found ==="
find artifacts -name .git -maxdepth 6 -print 2>/dev/null

echo
echo "=== removing nested .git and re-adding ==="
find artifacts -name .git -maxdepth 6 -exec rm -rf {} + 2>/dev/null || true
git rm -r --cached -q artifacts 2>/dev/null || true
git add -A
git commit -q --amend -m "archive: RRSI 2026-11-19..21 code, configs and results

Runtime bulk (~45G: dev/, interim_validation/, validation100/, search/,
rootfs snapshots in evidence/ and process-checks/) is intentionally excluded.
See artifacts/rrsi_20261119_20261121/README.md."

echo "files in commit: $(git ls-tree -r --name-only HEAD | wc -l)"
echo "tree entries of type commit (should be 0): $(git ls-tree -r HEAD | grep -c '^160000')"
echo "upstream files now: $(git ls-tree -r --name-only HEAD | grep -c 'test848_v5/upstream')"

echo
echo "=== force push (new commit) ==="
timeout 600 git push -f origin "HEAD:refs/heads/archive/rrsi-20261119-21" 2>&1 | tail -4

echo
echo "=== verify ==="
LOCAL_SHA=$(git rev-parse HEAD)
REMOTE_SHA=$(timeout 60 git ls-remote origin refs/heads/archive/rrsi-20261119-21 | awk '{print $1}')
echo "local  $LOCAL_SHA"
echo "remote $REMOTE_SHA"
if [ "$LOCAL_SHA" = "$REMOTE_SHA" ]; then echo "VERIFIED remote sha matches"; fi

echo
echo "=== independent check: clone the branch back and count files ==="
rm -rf /dev/shm/verify_clone
timeout 300 git clone -q --depth 1 --single-branch --branch archive/rrsi-20261119-21 \
  git@github.com:cw462/MedRAX-reproduction.git /dev/shm/verify_clone 2>&1 | tail -3
echo "files in fresh clone: $(find /dev/shm/verify_clone -type f -not -path '*/.git/*' | wc -l)"
echo "upstream files in clone: $(find /dev/shm/verify_clone -path '*test848_v5/upstream*' -type f | wc -l)"
echo "size: $(du -sh /dev/shm/verify_clone | cut -f1)"
