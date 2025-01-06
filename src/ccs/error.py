class CcsError(RuntimeError):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class MissingPropertyError(CcsError): ...


class EmptyPropertyError(CcsError): ...


class AmbiguousPropertyError(CcsError): ...
