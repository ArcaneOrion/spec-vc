from __future__ import annotations

from dataclasses import dataclass, field


class SpecVCError(Exception):
    pass


class UsageError(SpecVCError):
    pass


class ValidationError(SpecVCError):
    pass


@dataclass(slots=True)
class BlockingError:
    """结构化阻塞输出（ADR-018）。

    所有 spec-vc 阻塞输出（hook 校验失败、CLI 命令拒绝）统一通过本结构构造，
    再 .format() 转 stderr 文本。AI 读取后可按 fix_commands 自我修复，避免循环 bypass。

    用法:
        err = BlockingError(
            reason="review.json 不存在",
            current_state="expected: .git/spec-vc-review.json\\nactual: 不存在",
            fix_commands=["spec-vc review --message '...'"],
            docs_ref=["SKILL.md#review", "ADR-018"],
        )
        raise ValidationError(err.format())
    """

    reason: str
    current_state: str
    fix_commands: list[str] = field(default_factory=list)
    docs_ref: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("BlockingError.reason 不能为空")
        if not self.current_state.strip():
            raise ValueError("BlockingError.current_state 不能为空")
        if not self.fix_commands:
            raise ValueError("BlockingError.fix_commands 至少需要一条命令")
        if not self.docs_ref:
            raise ValueError("BlockingError.docs_ref 至少需要一条引用")

    def format(self) -> str:
        lines = [f"[spec-vc] BLOCKED: {self.reason}", "", "Current state:"]
        state_lines = self.current_state.splitlines() or [self.current_state]
        for line in state_lines:
            lines.append(f"  {line}")
        lines.append("")
        lines.append("How to fix:")
        for cmd in self.fix_commands:
            lines.append(f"  $ {cmd}")
        lines.append("")
        lines.append("Docs:")
        for ref in self.docs_ref:
            lines.append(f"  - {ref}")
        return "\n".join(lines)
