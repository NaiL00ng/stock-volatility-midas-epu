"""Add an opt-in MSVC-compatible column shuffle to a LOCAL XGBoost 2.0.3 source.

Diagnostic compatibility build, not an upstream release or a recovered binary.
No download, compilation, dependency installation, or model training is performed.
The algorithm follows the ascending Fisher-Yates shuffle and rejection/modulo
mapping in Microsoft STL vs-2022-17.6 (algorithm, _Rng_from_urng and shuffle):
https://github.com/microsoft/STL/blob/vs-2022-17.6/stl/inc/algorithm
The mt19937 engine itself and every other XGBoost operation remain unchanged.
"""
from pathlib import Path
import argparse
import hashlib

EXPECTED_SHA256 = '0950f1ded9db8521cb96550251712b00f0b25a47135eb4453d39da32ddbbc276'
REPLACEMENT = r"""    // Diagnostic emulation of the MSVC 17.6 shuffle for a full-range mt19937.
    // Original algorithm remains selectable to separate compiler from sampler effects.
    if (std::getenv("FORENSIC_MSVC_SHUFFLE")) {
      auto &v = new_features.HostVector();
      for (size_t i = 1; i < v.size(); ++i) {
        uint64_t n = i + 1, u;
        constexpr uint64_t cap = 0xffffffffULL;
        do { u = rng_(); } while (u / n >= cap / n && cap % n != n - 1);
        std::swap(v[i], v[u % n]);
      }
    } else {
      std::shuffle(new_features.HostVector().begin(), new_features.HostVector().end(), rng_);
    }
"""


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, required=True)
    args = parser.parse_args()
    source = args.source_dir.resolve()
    target = (source / 'src/common/random.cc').resolve()
    if not target.is_relative_to(root / 'generated'):
        parser.error('Source must be inside this project\'s generated directory.')
    text = target.read_text()
    if 'FORENSIC_MSVC_SHUFFLE' in text:
        print('Diagnostic sampler is already present; no file changed.')
        return
    if hashlib.sha256(target.read_bytes()).hexdigest() != EXPECTED_SHA256:
        raise ValueError('Unexpected source content; only the verified XGBoost 2.0.3 file is supported.')
    old = '    std::shuffle(new_features.HostVector().begin(), new_features.HostVector().end(), rng_);\n'
    assert text.count(old) == 1
    text = text.replace(old, REPLACEMENT).replace('#include "random.h"', '#include "random.h"\n#include <cstdlib>')
    target.write_text(text)
    print('Patched local source. Set FORENSIC_MSVC_SHUFFLE=1 only for the diagnostic run.')


if __name__ == '__main__':
    main()
