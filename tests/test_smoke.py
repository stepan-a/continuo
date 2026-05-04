"""Smoke tests: package imports cleanly and exposes its version."""

import dynare_ct


def test_version_is_set():
    assert isinstance(dynare_ct.__version__, str)
    assert dynare_ct.__version__ == "0.0.1"


def test_subpackages_import():
    import dynare_ct.codegen  # noqa: F401
    import dynare_ct.io  # noqa: F401
    import dynare_ct.ir  # noqa: F401
    import dynare_ct.macro  # noqa: F401
    import dynare_ct.parser  # noqa: F401
    import dynare_ct.solve  # noqa: F401
    import dynare_ct.solve.disc  # noqa: F401
