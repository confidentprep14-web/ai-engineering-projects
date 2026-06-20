#!/bin/bash
# Local test using act (https://github.com/nektos/act)
# Install act: brew install act (Mac) or see https://github.com/nektos/act

set -e

echo "Running AI Review Action locally with act..."

# Export secrets from .env
export $(cat .env | grep -v '#' | xargs)

# Create a sample diff for testing
git diff HEAD~1 > /tmp/local_test.diff 2>/dev/null || cp tests/fixtures/sample.diff /tmp/local_test.diff

# Run with act (uses docker by default)
act pull_request \
    --secret ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
    --secret GITHUB_TOKEN="$GITHUB_TOKEN" \
    --env PR_NUMBER=1 \
    --env REPO_NAME="owner/test-repo" \
    --env BASE_REF=main \
    -j ai-review \
    --dry-run

echo "Local test complete."
