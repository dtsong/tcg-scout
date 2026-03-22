# Releasing Scout

## Versioning

Semantic versioning: `MAJOR.MINOR.PATCH`

- **PATCH** (1.1.1): Bug fixes, data corrections, copy changes
- **MINOR** (1.2.0): New features, new pages, new analysis types
- **MAJOR** (2.0.0): Breaking changes, major redesigns, new data sources

## Pre-Release Checklist

```
python -m pytest tests/ -v
cd web && npm test && cd ..
python cli.py --format <active-format> export-web --strict
python cli.py --format <active-format> validate
cd web && npx next build && cd ..
```

Spot-check in browser:
- Dashboard loads with current data
- At least one archetype detail page renders
- Card analysis page shows results
- No console errors

## Tag and Push

```
git tag -a vX.Y.Z -m "Short description of release"
git push && git push --tags
```

Vercel auto-deploys from main.

## Post-Deploy Verification

```
Hard refresh scout.trainerlab.io
Active format shows current tournament count
Archetype detail page renders correctly
Card search returns results
Mobile: nav works, tables scroll horizontally
```

The smoke-test GitHub Action runs automatically when data changes are pushed to main. A separate freshness-check workflow runs every 12 hours to detect stale data.
