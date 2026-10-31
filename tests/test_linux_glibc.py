"""Regression checks for the Linux package's declared glibc floor."""

import shutil
import subprocess
import sys

import pytest

from tools.audit_linux_bundle import audit, required_glibc


def test_reads_requirements_not_definitions():
    output = """Version definition section '.gnu.version_d' contains 1 entry:
  0x001c: Rev: 1  Flags: none  Index: 2  Cnt: 1  Name: GLIBC_9.99
Version needs section '.gnu.version_r' contains 2 entries:
  0x0010: Name: GLIBC_2.39  Flags: none  Version: 3
  0x0020: Name: GLIBCXX_3.4.30  Flags: none  Version: 4
  0x0030: Name: GLIBC_2.43  Flags: none  Version: 5
"""
    assert required_glibc(output) == [(2, 39), (2, 43)]


@pytest.mark.skipif(
    sys.platform != "linux" or not shutil.which("cc") or not shutil.which("readelf"),
    reason="Requires native Linux compiler and ELF tooling",
)
def test_real_elf_is_rejected_below_its_requirement(tmp_path):
    source = tmp_path / "probe.c"
    source.write_text('#include <stdio.h>\nvoid probe(void) { puts("probe"); }\n')
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    subprocess.run(
        ["cc", "-shared", "-fPIC", str(source), "-o", str(bundle / "probe.so")], check=True
    )
    with pytest.raises(ValueError, match="exceeds glibc"):
        audit(bundle, baseline=(0, 0))
    result = audit(bundle, baseline=(999, 0))
    assert result["elf_files"][0]["required_glibc"]
