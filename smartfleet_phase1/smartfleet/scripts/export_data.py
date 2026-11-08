import argparse
def main():
    parser = argparse.ArgumentParser(description="Export SmartFleet data (implemented in a later phase).")
    parser.add_argument("--format", choices=["csv", "json", "sql"], default="csv")
    args = parser.parse_args()
    raise SystemExit(f"Exporter is scheduled for a later phase. Requested format={args.format}.")
if __name__ == "__main__":
    main()
