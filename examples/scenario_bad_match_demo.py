"""
Bad Match Debugging Demo

This example demonstrates the debugging scenario from ARCHITECTURE.md:
A "laptop stand" product is incorrectly matched with a "phone case" as its competitor.

This happens because:
1. LLM generates "phone case" as a keyword (hallucination)
2. Filters are too lenient (category filter missing)
3. Ranking LLM selects based on surface-level similarity

Run this, then query the X-Ray API to debug why the bad match happened.
"""

import sys
import os
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sdk import xray_run, xray_step, client


def generate_keywords(product_title: str):
    """LLM step that occasionally hallucinates irrelevant keywords."""
    with xray_step("GenerateKeywords", "LLM") as step:
        time.sleep(0.3)
        step.log_stats(input_count=1, model="gpt-4")

        # Intentionally generate a bad keyword to simulate LLM hallucination
        keywords = ["laptop stand", "desk organizer", "monitor riser", "phone case"]

        step.log_stats(output_count=len(keywords))
        return keywords


def search_competitors(keywords: list):
    """API call to search for products."""
    with xray_step("SearchCompetitors", "API") as step:
        time.sleep(0.2)
        step.log_stats(input_count=len(keywords))

        # Simulate search results including the problematic phone case
        candidates = [
            {
                "id": "prod_LS001",
                "title": "Aluminum Laptop Stand - Ergonomic",
                "price": 45,
                "rating": 4.7,
                "category": "Office Products > Laptop Accessories",
            },
            {
                "id": "prod_LS002",
                "title": "Wooden Desk Organizer with Laptop Stand",
                "price": 35,
                "rating": 4.5,
                "category": "Office Products > Desk Accessories",
            },
            {
                "id": "prod_XYZ789",  # The problematic match
                "title": "Premium Leather Phone Case",
                "price": 25,
                "rating": 4.8,
                "category": "Electronics > Phone Accessories",
            },
            {
                "id": "prod_MR001",
                "title": "Monitor Riser Stand",
                "price": 55,
                "rating": 4.6,
                "category": "Office Products > Monitor Accessories",
            },
        ]

        step.log_sampled_candidates(accepted=candidates)
        step.log_stats(output_count=len(candidates))
        return candidates


def filter_competitors(candidates: list):
    """Filter step with lenient rules that lets the phone case through."""
    with xray_step("FilterCompetitors", "FILTER") as step:
        step.log_stats(input_count=len(candidates))

        kept = []
        dropped_with_reasons = []

        for c in candidates:
            # Only filter by price and rating - missing category filter!
            if c["price"] > 100:
                dropped_with_reasons.append(
                    (c, f"Price ${c['price']} exceeds threshold $100")
                )
            elif c["rating"] < 4.0:
                dropped_with_reasons.append(
                    (c, f"Rating {c['rating']} below minimum 4.0")
                )
            else:
                # Phone case passes because price ($25) and rating (4.8) are good
                kept.append(c)

        filter_rate = len(dropped_with_reasons) / len(candidates) if candidates else 0
        step.log_stats(
            output_count=len(kept),
            dropped_count=len(dropped_with_reasons),
            filter_rate=filter_rate,
        )

        step.log_sampled_candidates(accepted=kept, rejected=dropped_with_reasons)
        return kept


def rank_and_select(candidates: list, product_title: str):
    """LLM ranking that selects based on surface-level similarity."""
    with xray_step("RankAndSelect", "LLM") as step:
        step.log_stats(input_count=len(candidates), model="gpt-4")
        time.sleep(0.3)

        if not candidates:
            step.log_stats(output_count=0)
            return None

        # Score each candidate
        scored = []
        for c in candidates:
            # Simple scoring logic (in reality, this would be an LLM call)
            score = 0.6  # Base score

            # Phone case gets decent score because it's a "desk accessory"
            if "Phone Case" in c["title"]:
                score = 0.75
                reasoning = "High rating and affordable price make it attractive"
            elif "Laptop" in c["title"]:
                score = 0.85
                reasoning = "Strong category match with product"
            elif "Desk" in c["title"]:
                score = 0.80
                reasoning = "Related desk accessory"
            elif "Monitor" in c["title"]:
                score = 0.70
                reasoning = "Related office accessory"

            c["score"] = score
            c["reasoning"] = reasoning
            scored.append(c)

        # Sort by score - phone case might win!
        scored.sort(key=lambda x: x["score"], reverse=True)
        winner = scored[0]

        step.log_stats(output_count=1, winner_score=winner["score"])

        # Log all scored candidates with their scores and reasoning
        step.log_sampled_candidates(
            selected=[
                (
                    winner,
                    {"relevance": winner["score"]},
                    winner.get("reasoning", "Selected as best match"),
                )
            ],
            rejected=[
                (c, {"relevance": c["score"]}, c.get("reasoning", ""))
                for c in scored[1:]
            ],
        )

        return winner


def run_bad_match_pipeline():
    """Run the pipeline that produces a bad match."""
    product = {
        "id": "prod_ABC123",
        "title": "Aluminum Foldable Laptop Stand",
        "category": "Office Products",
    }

    metadata = {
        "product_id": product["id"],
        "scenario": "bad_match_demo",
    }

    with xray_run("CompetitorDiscovery", metadata=metadata) as ctx:
        print(f"\n{'='*60}")
        print(f"🔍 X-Ray Run ID: {ctx.run_id}")
        print(f"{'='*60}\n")

        # Step 1: Generate Keywords
        print("Step 1: Generating keywords...")
        keywords = generate_keywords(product["title"])
        print(f"  ✓ Generated keywords: {keywords}")
        print(f"  ⚠️  Notice 'phone case' was generated (LLM hallucination)\n")

        # Step 2: Search for Competitors
        print("Step 2: Searching for competitors...")
        candidates = search_competitors(keywords)
        print(f"  ✓ Found {len(candidates)} candidates")
        print(f"  ⚠️  Includes phone case due to hallucinated keyword\n")

        # Step 3: Filter Competitors
        print("Step 3: Filtering competitors...")
        filtered = filter_competitors(candidates)
        print(f"  ✓ Filtered to {len(filtered)} candidates")
        print(
            f"  ⚠️  Phone case passed filters (good price & rating, no category check)\n"
        )

        # Step 4: Rank and Select
        print("Step 4: Ranking and selecting best competitor...")
        winner = rank_and_select(filtered, product["title"])
        print(f"  ✓ Selected: {winner['title']} (Score: {winner['score']:.2f})")

        if "Phone Case" in winner["title"]:
            print(f"\n{'='*60}")
            print(f"❌ BAD MATCH DETECTED!")
            print(f"{'='*60}")
            print(
                f"A phone case was matched with a laptop stand - clearly wrong!\n"
            )
            print(f"🔍 Debugging with X-Ray:")
            print(f"   1. Query run by product_id: {product['id']}")
            print(f"   2. Inspect GenerateKeywords step → see 'phone case' keyword")
            print(f"   3. Inspect FilterCompetitors step → see lenient filters")
            print(f"   4. Inspect RankAndSelect step → see why phone case scored high")
            print(f"\n   Run this to debug:")
            print(
                f"   curl 'http://localhost:8000/v1/runs?metadata.product_id=prod_ABC123' | python3 -m json.tool"
            )
        else:
            print(f"\n✅ Good match: {winner['title']}")

        print(f"\n{'='*60}\n")
        return winner


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("BAD MATCH DEBUGGING DEMO")
    print("Demonstrates the scenario from ARCHITECTURE.md")
    print("=" * 60)
    run_bad_match_pipeline()
