import argparse

def get_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("filename", help="Filename to frobnicate")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--count", type=int, help="Number of times to frobnicate")
    return parser

def main():
    parser = get_parser()
    args = parser.parse_args()
    print(args)

if __name__ == "__main__":
    main()
