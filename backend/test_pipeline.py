"""Run the full portfolio graph against holdings already added through the UI."""
import argparse
import json

from app.database import DatabaseManager
from app.portfolio_agents.graph import PortfolioAnalysisUnavailable, run_portfolio_pipeline


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", required=True)
    args = parser.parse_args()
    holdings = DatabaseManager.get_holdings(args.user_id)
    if not holdings:
        raise SystemExit("No holdings found for this user ID")
    try:
        result = run_portfolio_pipeline(holdings)
    except PortfolioAnalysisUnavailable as exc:
        raise SystemExit(f"Analysis unavailable: {exc}") from exc
    print(json.dumps(result.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
