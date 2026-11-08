import argparse
def main():
    parser = argparse.ArgumentParser(description="Generate SmartFleet synthetic data (implemented in Phase 2).")
    parser.add_argument("--mode", choices=["starter", "full"], default="starter")
    parser.add_argument("--seed", type=int, default=20261022)
    args = parser.parse_args()
    raise SystemExit(
        f"Data generator is scheduled for Phase 2. Requested mode={args.mode}, seed={args.seed}."
    )
if __name__ == "__main__":
    main()
