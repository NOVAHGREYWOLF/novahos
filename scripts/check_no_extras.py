#!/usr/bin/env python
"""The kernel must be usable with NO extras installed — and say so when it is not.

WHY THIS IS A SEPARATE CHECK FROM THE SUITE, and the only one that could have caught the
defect it exists for. `novahos` declares ZERO core dependencies on purpose, so the stdlib
rails install with nothing behind them. The test suite cannot verify that property: it runs
under `[dev]`, which declares pyyaml, sqlalchemy and the rest, so every lazy import it
exercises is satisfied. A suite green therefore says nothing about a plain `novahos` install.

That is not hypothetical. On 2026-09-26 reach sat red for a day and scope silently reported
an EMPTY agent fleet to the hub registry, both because `AgentManifest.from_file` lazy-imports
PyYAML and plain `novahos` never installs it. It was diagnosed twice at the wrong layer. A
job like this one, run once at the kernel, would have caught it before either consumer.

Run it by hand the same way CI does:

    pip install .          # NO extras
    python scripts/check_no_extras.py

Exits non-zero on the first thing that breaks the promise.
"""
from __future__ import annotations

import pathlib
import sys
import tempfile
import traceback

#: Everything `import novahos` surfaces eagerly, plus the foundation modules documented as
#: stdlib-only. Listed explicitly rather than walked, so ADDING a module is a deliberate
#: decision to keep it dependency-free rather than something this check quietly absorbs.
STDLIB_MODULES = (
    "auth", "constitution", "consent", "context", "knowledge", "mcp", "privacy",
    "service_auth", "service_client", "validators", "warden", "gateway_url", "audit_trail",
    "warden_runtime.gate",
)

#: Paths documented as lazily importing a third-party package. Each must fail with its OWN
#: exception type naming the extra to install — never a bare ModuleNotFoundError, which names
#: a package the caller never asked for and does not say what to do about it.
#: (callable, expected exception, string the message must contain)
failures: list[str] = []


def fail(msg: str) -> None:
    failures.append(msg)
    print(f"  FAIL {msg}")


def check_zero_dependency_imports() -> None:
    try:
        import novahos
        print(f"  ok   import novahos {novahos.__version__} (commit {novahos.__commit__})")
    except ModuleNotFoundError:
        # Not a kernel failure — this check MUST run against an INSTALLED novahos, because the
        # whole defect class is about what `pip install` does and does not pull in. Testing the
        # source tree on sys.path would pass while the installed package was still broken. Say
        # which of the two situations this is, rather than reporting a failure that means
        # something else entirely.
        print("  SKIP novahos is not installed. This check tests an INSTALLED package,")
        print("       not the source tree: run `pip install .` (no extras) first.")
        print("       Refusing to report a verdict either way.")
        raise SystemExit(2)
    except Exception:
        fail("import novahos raised something other than ModuleNotFoundError")
        traceback.print_exc()
        return
    for mod in STDLIB_MODULES:
        try:
            __import__(f"novahos.{mod}")
            print(f"  ok   novahos.{mod}")
        except Exception as exc:
            fail(f"novahos.{mod} needs a third-party package: {type(exc).__name__}: {exc}")


def check_lazy_paths_name_their_extra() -> None:
    """A documented-lazy path must refuse in a way that tells you what to install.

    Refuses to run at all if PyYAML is importable. Without that guard this check is ambiguous
    in a way that misdirects: with PyYAML present, `from_file` parses the fixture and then
    fails VALIDATION, which is also a ManifestError — so the check reported "did not name the
    extra" and pointed at a kernel bug when the real fault was the job's own environment. A
    check that cannot establish its state must not report one, including about itself.
    """
    try:
        import yaml  # noqa: F401
    except ModuleNotFoundError:
        pass
    else:
        print("  SKIP PyYAML is importable, so this job was NOT run with `pip install .` and")
        print("       cannot test the no-extras promise. Refusing to report a verdict.")
        raise SystemExit(2)
    try:
        from novahos.agent.manifest import AgentManifest, ManifestError
    except Exception as exc:
        fail(f"novahos.agent.manifest is not importable without extras: {exc}")
        return
    p = pathlib.Path(tempfile.mkdtemp()) / "m.yaml"
    p.write_text("name: X\n", encoding="utf-8")
    try:
        AgentManifest.from_file(p)
    except ManifestError as exc:
        if "novahos[manifests]" in str(exc):
            print("  ok   AgentManifest.from_file names novahos[manifests]")
        else:
            fail(f"from_file raised ManifestError but did not name the extra: {exc}")
    except ModuleNotFoundError as exc:
        fail(f"from_file leaked ModuleNotFoundError instead of naming an extra: {exc}")
    except Exception as exc:
        fail(f"from_file raised {type(exc).__name__} rather than ManifestError: {exc}")
    else:
        fail("from_file SUCCEEDED despite PyYAML being absent — the lazy import is gone?")


def main() -> int:
    print(f"python {sys.version.split()[0]} — expecting NO extras installed")
    check_zero_dependency_imports()
    check_lazy_paths_name_their_extra()
    if failures:
        print(f"\n{len(failures)} failure(s). The kernel is not usable without extras.")
        return 1
    print("\nOK — the kernel imports and refuses diagnosably with no extras installed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
