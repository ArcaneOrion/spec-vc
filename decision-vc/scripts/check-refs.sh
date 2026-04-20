#!/usr/bin/env bash
# decision-vc · check-refs.sh
#
# 扫描 ADR 与 git commit 的双向引用完整性,输出三类问题:
#   1. 孤儿 ADR       :ADR 文件存在,但没有任何 commit 引用它
#   2. 幽灵引用       :commit 引用了 [ADR-NNN],但该 ADR 文件不存在
#   3. 状态漂移       :ADR 状态为 Superseded by ADR-XXX,但 XXX 不存在
#
# 使用:
#   scripts/check-refs.sh                 # 全量扫描
#   scripts/check-refs.sh --since=<ref>   # 只扫描某个 git ref 之后的 commit

set -euo pipefail

ADR_DIR="${ADR_DIR:-doc/arch}"
SINCE="${1:-}"

if [[ ! -d "$ADR_DIR" ]]; then
    echo "[decision-vc] ADR 目录不存在:$ADR_DIR" >&2
    echo "            请先运行 /decision-vc init" >&2
    exit 2
fi

# ---- 收集所有 ADR 编号 ----
declare -A ADR_EXISTS
for adr_file in "$ADR_DIR"/adr-*.md; do
    [[ -f "$adr_file" ]] || continue
    id=$(basename "$adr_file" | sed -E 's/adr-([0-9]+)\.md/\1/')
    ADR_EXISTS[$id]=1
done

# ---- 收集所有 commit 中引用的 ADR 编号 ----
declare -A ADR_REFERENCED
GIT_LOG_ARGS=("log" "--format=%H %s")
if [[ -n "$SINCE" ]]; then
    GIT_LOG_ARGS+=("${SINCE}")
fi

while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    hash="${line%% *}"
    subject="${line#* }"
    # 提取 [ADR-NNN] (不含 none)
    for ref in $(echo "$subject" | grep -oE '\[ADR-[0-9]+\]' || true); do
        id=$(echo "$ref" | sed -E 's/\[ADR-([0-9]+)\]/\1/')
        ADR_REFERENCED[$id]="${ADR_REFERENCED[$id]:-}${hash} "
    done
done < <(git "${GIT_LOG_ARGS[@]}" 2>/dev/null || true)

# ---- 1. 检查幽灵引用 ----
GHOST_COUNT=0
echo "== 幽灵引用(commit 引用了不存在的 ADR) =="
for id in "${!ADR_REFERENCED[@]}"; do
    if [[ -z "${ADR_EXISTS[$id]:-}" ]]; then
        commits="${ADR_REFERENCED[$id]}"
        echo "  ADR-${id} 被以下 commit 引用,但文件不存在:"
        for h in $commits; do
            echo "    $(git log -1 --format='%h %s' "$h" 2>/dev/null || echo "$h (无法解析)")"
        done
        GHOST_COUNT=$((GHOST_COUNT + 1))
    fi
done
[[ "$GHOST_COUNT" -eq 0 ]] && echo "  (无)"

# ---- 2. 检查孤儿 ADR ----
ORPHAN_COUNT=0
echo ""
echo "== 孤儿 ADR(ADR 存在,但无 commit 引用) =="
for id in "${!ADR_EXISTS[@]}"; do
    if [[ -z "${ADR_REFERENCED[$id]:-}" ]]; then
        adr_file="${ADR_DIR}/adr-${id}.md"
        title=$(head -n1 "$adr_file" 2>/dev/null | sed -E 's/^#\s*ADR-[0-9]+:\s*//' || echo "(无标题)")
        echo "  ADR-${id}: ${title}"
        ORPHAN_COUNT=$((ORPHAN_COUNT + 1))
    fi
done
[[ "$ORPHAN_COUNT" -eq 0 ]] && echo "  (无)"

# ---- 3. 检查状态漂移 ----
DRIFT_COUNT=0
echo ""
echo "== 状态漂移(Superseded by 指向不存在的 ADR) =="
for adr_file in "$ADR_DIR"/adr-*.md; do
    [[ -f "$adr_file" ]] || continue
    id=$(basename "$adr_file" | sed -E 's/adr-([0-9]+)\.md/\1/')
    superseded_by=$(grep -oE 'Superseded by ADR-[0-9]+' "$adr_file" | grep -oE '[0-9]+' | head -n1 || true)
    if [[ -n "$superseded_by" ]] && [[ -z "${ADR_EXISTS[$superseded_by]:-}" ]]; then
        echo "  ADR-${id} 标记为 Superseded by ADR-${superseded_by},但后者不存在"
        DRIFT_COUNT=$((DRIFT_COUNT + 1))
    fi
done
[[ "$DRIFT_COUNT" -eq 0 ]] && echo "  (无)"

# ---- 汇总 ----
echo ""
echo "== 汇总 =="
echo "  幽灵引用: $GHOST_COUNT"
echo "  孤儿 ADR: $ORPHAN_COUNT"
echo "  状态漂移: $DRIFT_COUNT"

TOTAL=$((GHOST_COUNT + ORPHAN_COUNT + DRIFT_COUNT))
if [[ "$TOTAL" -gt 0 ]]; then
    exit 1
fi
exit 0
