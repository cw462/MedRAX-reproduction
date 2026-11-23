set -u
echo "=== processing_maira2.py: phrase grounding + helpers ==="
sed -n '470,580p' /dev/shm/maira2/processing_maira2.py
echo
echo "=== adjust_box_for_original_image_size ==="
grep -n "adjust_box_for_original_image_size" -A 25 /dev/shm/maira2/processing_maira2.py | head -40
echo
echo "=== convert_output_to_plaintext_or_grounded_sequence ==="
grep -n "def convert_output_to_plaintext_or_grounded_sequence" -A 20 /dev/shm/maira2/processing_maira2.py | head -30
