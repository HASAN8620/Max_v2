name: Groq Roman Urdu Translator

on:
  workflow_dispatch: {}
  # Optional: uncomment to also run automatically. Keep the interval generous -
  # Groq's free-tier rate limits mean back-to-back runs won't help much anyway.
  # If you also add `push:` as a trigger, add `paths-ignore` for the checkpoint
  # files below, otherwise every checkpoint commit will re-trigger the workflow.
  # schedule:
  #   - cron: '0 3 * * *'

# Prevents two runs of this workflow from ever executing at the same time.
# This is what actually stops the "! [rejected] main -> main (fetch first)"
# error at the source, instead of just retrying around it.
concurrency:
  group: groq-translation
  cancel-in-progress: false

permissions:
  contents: write

jobs:
  translate:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install Dependencies
        run: pip install requests

      - name: Run Translation Script
        env:
          GROQ_API_KEYS: ${{ secrets.GROQ_API_KEYS }}
        run: python translate.py
        # Even if translate.py somehow raises and exits non-zero, the job
        # keeps going so the commit step below still runs.
        continue-on-error: true

      - name: Commit and Push Checkpoint (Resume Data)
        if: always()
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

          # Add each file individually and ignore failures - if a file doesn't
          # exist yet (e.g. the very first batch failed before any checkpoint
          # was written), `git add` on a missing path must NOT kill the step.
          git add translation_checkpoint.json 2>/dev/null || true
          git add american_roman.oxt 2>/dev/null || true

          if git diff --cached --quiet; then
            echo "ℹ️ No new progress to commit this run."
          else
            git commit -m "chore: update translation checkpoint [skip ci]"

            pushed=false
            for i in 1 2 3 4 5; do
              git pull --rebase origin main
              if git push origin main; then
                pushed=true
                break
              fi
              echo "⚠️ Push rejected (likely a race with another run) - retrying ($i/5)..."
              sleep 5
            done

            if [ "$pushed" = false ]; then
              echo "❌ Could not push checkpoint after 5 attempts."
              exit 1
            fi
            echo "✅ Checkpoint pushed successfully."
          fi
