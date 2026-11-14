"""First half of Bayaman's tasks: python -m scripts.seed [--check]."""

import argparse
import json

from sqlalchemy.exc import IntegrityError

from app.modules.farms.demo import load_seed
from app.modules.farms.seed import seed_farms


def main() -> None:
    parser = argparse.ArgumentParser(description="Load the offline Asan demo and crop catalog")
    parser.add_argument(
        "--check", action="store_true", help="Validate seed without accessing the DB"
    )
    args = parser.parse_args()
    bundle = load_seed()
    summary = {
        "seed_version": bundle.version,
        "season": bundle.season,
        "farm_id": str(bundle.farm.id),
        "area_ha": bundle.farm.area_ha,
        "fields": len(bundle.farm.fields),
        "cows": sum(h.head_count for h in bundle.farm.herds),
        "crop_ids": {crop.code: str(crop.id) for crop in bundle.crops},
        "presets": [scenario.preset_code for scenario in bundle.scenarios],
    }
    if not args.check:
        from app.db.session import SessionLocal

        try:
            with SessionLocal.begin() as session:
                summary["inserted"] = seed_farms(session, bundle)
        except IntegrityError as exc:
            raise SystemExit(
                "Seed cancelled: a code or relation conflicts with existing data. "
                "No seed rows committed; existing records were not overwritten."
            ) from exc
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
