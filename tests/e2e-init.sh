#!/usr/bin/env bash
# spec-vc · 最小端到端测试
#
# 验证骨架的核心承诺:
#   1. init 能正确铺开 doc/arch/ 结构
#   2. 无 [ADR-] 引用的 commit 被阻塞
#   3. [ADR-000] 引用存在时放行
#   4. [ADR-999] 引用不存在时被阻塞
#   5. [ADR-NNN] 引用 Superseded 状态的 ADR 被阻塞(Status 正则修复验证)
#
# 用法:  bash tests/e2e-init.sh
# 退出码: 0 = 全部通过, 非 0 = 有用例失败

set -uo pipefail

SKILL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

PASS=0
FAIL=0

pass() { echo "  ✓ $1"; PASS=$((PASS + 1)); }
fail() { echo "  ✗ $1" >&2; FAIL=$((FAIL + 1)); }

commit_msg_test() {
    local label="$1" msg="$2" expect="$3"  # expect: pass | block
    local tmp="$WORK/msg-$$"
    echo "$msg" > "$tmp"

    local rc=0
    ( cd "$WORK/proj" && bash "$WORK/proj/.git/hooks/commit-msg" "$tmp" 2>/dev/null ) || rc=$?

    case "$expect" in
        pass)  [[ "$rc" -eq 0 ]] && pass "$label (pass)" || fail "$label expected pass, rc=$rc" ;;
        block) [[ "$rc" -ne 0 ]] && pass "$label (block)" || fail "$label expected block, rc=$rc" ;;
    esac
}

echo "=== spec-vc e2e ==="
echo "SKILL_ROOT=$SKILL_ROOT"
echo "WORK=$WORK"
echo ""

# --- 准备目标项目 ---
echo "[setup] 初始化临时项目"
mkdir -p "$WORK/proj"
cd "$WORK/proj"
git init -q
git config user.email "test@example.com"
git config user.name "test"

# --- init(手工模拟 /spec-vc adr-init 的脚本部分) ---
echo "[setup] 模拟 /spec-vc adr-init"
mkdir -p doc/arch
cp "$SKILL_ROOT/templates/index.md" doc/arch/README.md
DATE=$(date +%Y-%m-%d)
AUTHOR=$(git config user.name)
sed -e "s|{{DATE}}|${DATE}|g" -e "s|{{AUTHOR}}|${AUTHOR}|g" \
    "$SKILL_ROOT/templates/seed-adr-000.md" > doc/arch/adr-000.md
cp "$SKILL_ROOT/hooks/prepare-commit-msg" .git/hooks/prepare-commit-msg
cp "$SKILL_ROOT/hooks/commit-msg"         .git/hooks/commit-msg
chmod +x .git/hooks/prepare-commit-msg .git/hooks/commit-msg

# --- 断言 1:骨架文件落位 ---
echo ""
echo "[test] 骨架落位"
[[ -f doc/arch/README.md ]] && pass "doc/arch/README.md 存在" || fail "doc/arch/README.md 缺失"
[[ -f doc/arch/adr-000.md ]] && pass "doc/arch/adr-000.md 存在" || fail "doc/arch/adr-000.md 缺失"
[[ -x .git/hooks/commit-msg ]] && pass ".git/hooks/commit-msg 可执行" || fail ".git/hooks/commit-msg 不可执行"

# --- 断言 2:种子 Status 是 Accepted ---
grep -q '^- \*\*Status\*\*: Accepted' doc/arch/adr-000.md \
    && pass "种子 ADR Status=Accepted" \
    || fail "种子 ADR Status 不正确"

# --- 断言 3:commit-msg hook 行为 ---
echo ""
echo "[test] commit-msg hook 严格校验"
commit_msg_test "缺少 ADR 引用的 commit"              "docs: fix typo"                 block
commit_msg_test "引用未填充槽位 [ADR-???]"            "docs: fix typo [ADR-???]"       block
commit_msg_test "引用存在的 ADR-000"                  "feat: init [ADR-000]"           pass
commit_msg_test "引用不存在的 ADR-999"                "feat: bogus [ADR-999]"          block
commit_msg_test "[ADR-none] 豁免(当前占位放行)"       "chore: bump [ADR-none]"         pass

# --- 断言 4:Status 正则修复(Superseded / Deprecated 应被阻塞) ---
echo ""
echo "[test] Status 正则修复(v0.1 的核心 bug 修复点)"

# 造一个 Superseded by ADR-099 的 ADR-001
cat > doc/arch/adr-001.md <<'EOF'
# ADR-001: 测试用废弃决策

- **Date**: 2026-04-20
- **Status**: Superseded by ADR-099
- **Deciders**: test
- **Tags**: test

## Context
test
EOF
commit_msg_test "引用 Superseded 状态的 ADR"          "feat: x [ADR-001]"              block

# 造一个 Deprecated 的 ADR-002
cat > doc/arch/adr-002.md <<'EOF'
# ADR-002: 测试用废弃决策 2

- **Date**: 2026-04-20
- **Status**: Deprecated
- **Deciders**: test
- **Tags**: test

## Context
test
EOF
commit_msg_test "引用 Deprecated 状态的 ADR"          "feat: y [ADR-002]"              block

# 再验证 Proposed 状态的 ADR 能通过
cat > doc/arch/adr-003.md <<'EOF'
# ADR-003: 提议中的决策

- **Date**: 2026-04-20
- **Status**: Proposed
- **Deciders**: test
- **Tags**: test

## Context
test
EOF
commit_msg_test "引用 Proposed 状态的 ADR"            "feat: z [ADR-003]"              pass

# --- 汇总 ---
echo ""
echo "=== 汇总 ==="
echo "  通过: $PASS"
echo "  失败: $FAIL"

if [[ "$FAIL" -gt 0 ]]; then
    exit 1
fi
exit 0
