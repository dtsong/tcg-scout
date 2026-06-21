#!/usr/bin/env bash
# Local scrape-to-deploy pipeline for Scout formats.
#
# Runs the full ingestion pipeline locally, uploads data to GCS,
# updates the manifest, and pushes to main to trigger Vercel deploy.
#
# Usage:
#   ./scripts/local-scrape-deploy.sh              # Full pipeline with decklists
#   ./scripts/local-scrape-deploy.sh --no-decklists  # Skip Playwright decklists (faster)
#   ./scripts/local-scrape-deploy.sh --skip-scrape   # Skip scrape, just re-export and deploy

set -euo pipefail

FORMATS=("ninja-spinner" "tpci-standard" "tpci-standard-2025" "tpci-standard-2024")
PROJECT="trainerlab-prod"
DATA_BUCKET="tcg-scout-data"

FETCH_DECKLISTS="--fetch-decklists"
SKIP_SCRAPE=false

for arg in "$@"; do
  case $arg in
    --no-decklists) FETCH_DECKLISTS="" ;;
    --skip-scrape)  SKIP_SCRAPE=true ;;
  esac
done

echo "=== Local Scrape & Deploy ==="

# Step 1: Scrape
if [ "$SKIP_SCRAPE" = false ]; then
  echo ""
  echo "--- Step 1: Scraping ---"
  uv run scout --format ninja-spinner scrape-jp $FETCH_DECKLISTS
  uv run scout --format ninja-spinner backfill-archetypes
  uv run scout --format ninja-spinner translate-cards
fi

# Step 2: Meta + Export + Validate
echo ""
echo "--- Step 2: Meta + Export ---"
uv run scout --format ninja-spinner meta
for FORMAT in "${FORMATS[@]}"; do
  uv run scout --format "$FORMAT" export-web --strict
  uv run scout --format "$FORMAT" validate
done

# Step 3: Create tarball (COPYFILE_DISABLE prevents macOS xattr pollution)
echo ""
echo "--- Step 3: Upload to GCS ---"
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
TAR_FILE="data-${TIMESTAMP}.tar.gz"
COPYFILE_DISABLE=1 tar -czf "/tmp/${TAR_FILE}" --exclude='._*' -C web/public/data .

# Step 4: Upload
gsutil cp "/tmp/${TAR_FILE}" "gs://${DATA_BUCKET}/${TAR_FILE}"
gsutil cp "gs://${DATA_BUCKET}/${TAR_FILE}" "gs://${DATA_BUCKET}/data-latest.tar.gz"

# Step 5: Write manifest with immutable public URL
echo ""
echo "--- Step 4: Update manifest ---"
SHA256=$(sha256sum "/tmp/${TAR_FILE}" | cut -d' ' -f1)
PUBLIC_URL="https://storage.googleapis.com/${DATA_BUCKET}/${TAR_FILE}"

cat > web/data-manifest.json <<EOF
{
  "version": 1,
  "archives": [
    {
      "url": "${PUBLIC_URL}",
      "sha256": "${SHA256}",
      "created_at": "${TIMESTAMP}"
    }
  ]
}
EOF

# Step 6: Commit and push (triggers Vercel deploy on existing 'web' project)
echo ""
echo "--- Step 5: Push to main ---"
git add web/data-manifest.json
if git diff --cached --quiet; then
  echo "No manifest changes, skipping push"
else
  git commit -m "data: scrape $(date -u +%Y-%m-%dT%H:%MZ)"
  git push origin main
  echo "Pushed! Vercel will auto-deploy."
fi

# Cleanup
rm -f "/tmp/${TAR_FILE}"
echo ""
echo "=== Done ==="
