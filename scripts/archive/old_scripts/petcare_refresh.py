#!/usr/bin/env python3
"""
Petcare refresh pipeline
- Fetch Petcare insights with angle parsing
- Generate Petcare dashboard (real data)
"""
from dotenv import load_dotenv

load_dotenv()

from fetch_petcare_with_angles import fetch_petcare_with_parsing
from create_petcare_dashboard import create_petcare_dashboard


def main():
    print("🐕 Petcare refresh: fetching + building dashboard")
    data = fetch_petcare_with_parsing()
    if not data:
        raise SystemExit("Petcare fetch failed or no data. Aborting dashboard build.")
    dashboard_file = create_petcare_dashboard()
    print(f"✅ Done. Dashboard: {dashboard_file}")


if __name__ == "__main__":
    main()

