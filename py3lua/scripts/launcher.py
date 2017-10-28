import os
import argparse
from .. import Translator


def parse_args():
    parser = argparse.ArgumentParser(
        description="Python to Lua source to source translator"
    )
    parser.add_argument(
        'src_file', type=str,
        help="Source Python file to translate"
    )
    parser.add_argument(
        "-o", "--output",
        action="store",
        type=str,
        help="Output file name"
    )
    return parser.parse_args()


def run():
    args = parse_args()
    out_file = args.output
    if not out_file:
        out_file = os.path.basename(args.src_file).split('.')[0] + '.lua'
    translator = Translator(out_file=out_file)
    translator.translate(open(args.src_file).read())


if __name__ == '__main__':
    run()
