import argparse

from .config import MODELS


def main() -> None:
    parser = argparse.ArgumentParser(prog="testoracle")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("tasks")
    sub.add_parser("mutants")
    gen = sub.add_parser("generate")
    gen.add_argument("models", nargs="+", choices=list(MODELS))
    sub.add_parser("score")
    sub.add_parser("report")
    args = parser.parse_args()
    if args.command == "tasks":
        from .tasks import write
        write()
    elif args.command == "mutants":
        from .mutation import write
        write()
    elif args.command == "generate":
        from .experiment import generate
        generate(args.models)
    elif args.command == "score":
        from .experiment import score
        score()
    else:
        from .report import report
        report()
