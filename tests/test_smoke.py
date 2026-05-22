"""Smoke tests: package imports cleanly and exposes its version."""

import continuo


def test_version_is_set():
    assert isinstance(continuo.__version__, str)
    assert continuo.__version__ == "0.0.1"


def test_subpackages_import():
    import continuo.codegen  # noqa: F401
    import continuo.io  # noqa: F401
    import continuo.ir  # noqa: F401
    import continuo.macro  # noqa: F401
    import continuo.parser  # noqa: F401
    import continuo.solve  # noqa: F401
    import continuo.solve.disc  # noqa: F401
