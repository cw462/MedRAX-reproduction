set -u
KEY=/root/.ssh/medrax_deploy_key
if [ ! -f "$KEY" ]; then echo "KEY MISSING"; exit 1; fi
chmod 600 "$KEY"

echo "=== direct 22 (baseline) ==="
timeout 25 ssh -i "$KEY" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  -o ConnectTimeout=12 -T git@github.com 2>&1 | head -3
echo "rc=$?"

echo
echo "=== ssh.github.com:443 ==="
timeout 30 ssh -i "$KEY" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  -o ConnectTimeout=12 -p 443 -T git@ssh.github.com 2>&1 | head -3
echo "rc=$?"

echo
echo "=== raw tcp reachability ==="
timeout 8 bash -c 'cat < /dev/null > /dev/tcp/github.com/22' 2>&1 && echo "tcp22 open" || echo "tcp22 blocked"
timeout 8 bash -c 'cat < /dev/null > /dev/tcp/ssh.github.com/443' 2>&1 && echo "tcp443 open" || echo "tcp443 blocked"
