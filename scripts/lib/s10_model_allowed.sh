#!/usr/bin/env bash
# Match the generated colon-separated S10 model allowlist or its raw array.
S10_MODEL_ALLOWED() {
    local candidate="${1:-}" model
    [[ "$candidate" =~ ^SM-G[0-9]{3}[A-Z]$ ]] || return 1
    local -a models=()
    if declare -p TARGET_ASSERT_MODEL 2>/dev/null | grep -Eq '^declare -a'; then
        models=("${TARGET_ASSERT_MODEL[@]}")
    else
        IFS=':' read -r -a models <<< "${TARGET_ASSERT_MODEL:-}"
    fi
    for model in "${models[@]}"; do
        [[ "$candidate" == "$model" ]] && return 0
    done
    return 1
}
