import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("filename", help="Filename to frobnicate")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--count", type=int, help="Number of times to frobnicate")
    args = parser.parse_args()
    print(args)

if __name__ == "__main__":
    main()
