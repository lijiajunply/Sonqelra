"""Compile and export a Muse source file: python -m muse_lang file.muse."""
import argparse
from pathlib import Path
import sys
from . import MuseError, compile_source, execute_exports

def main():
    parser = argparse.ArgumentParser(description='Compile and export Muse scores')
    parser.add_argument('source', type=Path)
    args = parser.parse_args()
    try:
        result = compile_source(args.source.read_text(encoding='utf-8'), filename=str(args.source))
        execute_exports(result, base_dir=args.source.resolve().parent)
    except (MuseError, OSError, UnicodeError) as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
