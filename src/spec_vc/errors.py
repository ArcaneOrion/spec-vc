class SpecVCError(Exception):
    pass


class UsageError(SpecVCError):
    pass


class ValidationError(SpecVCError):
    pass
