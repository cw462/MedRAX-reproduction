set -u
. /etc/network_turbo >/dev/null 2>&1
echo "=== HF dataset card: StanfordAIMI/chexbench ==="
for u in \
  "https://huggingface.co/api/datasets/StanfordAIMI/chexbench" \
  "https://huggingface.co/datasets/StanfordAIMI/chexbench/raw/main/README.md" ; do
  echo "--- $u"
  curl -sL --max-time 25 "$u" | head -c 1500
  echo
done

echo
echo "=== grep for human baseline language in the card ==="
curl -sL --max-time 25 "https://huggingface.co/datasets/StanfordAIMI/chexbench/raw/main/README.md" \
 | grep -iE "human|radiologist|expert|physician|ceiling" | head -20
