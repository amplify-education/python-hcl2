#!/usr/bin/env bash

set -e # halt script on error
set -x # print debugging

TARGET_BRANCH=$1
IS_PULL_REQUEST=$2  # false if not a pull request,

# Makes sure travis does not check version if doing a pull request
if [ "$IS_PULL_REQUEST" != "false" ]; then
    if git diff --quiet "origin/${TARGET_BRANCH}...HEAD" 'python_hcl2' "test" setup.* ./*.pip; then
        echo "No changes found to main code or dependencies: no version change needed"
        exit 0
    fi

    CURRENT_VERSION=$(git show "origin/${TARGET_BRANCH}:hcl2/version.py" | sed -n 's/^__version__ = "\(.*\)"$/\1/p')
    NEW_VERSION=$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' hcl2/version.py)

    if [ "$CURRENT_VERSION" == "$NEW_VERSION" ]; then
        FAILURE_REASON="Failure reason: Version number should be bumped."
    fi

    HIGHEST_VERSION=$(echo -e "$CURRENT_VERSION\n$NEW_VERSION" | sort --version-sort | tail -n 1)

    if [ "$HIGHEST_VERSION" != "$NEW_VERSION" ]; then
        FAILURE_REASON="Failure Reason: New version ($NEW_VERSION) is less than current version ($HIGHEST_VERSION)"
    fi


    if [ -n "$FAILURE_REASON" ]; then
        set +x # is super annoying
        echo "============== PR Build Failed ==================="
        echo
        echo "$FAILURE_REASON"
        echo
        echo "=================================================="
        exit 1
    fi
fi
