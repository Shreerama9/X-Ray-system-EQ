import sys
import os
import time
import random

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sdk import xray_run, xray_step, client


def extract_product_attributes(product: dict):
    with xray_step("ExtractAttributes", "LLM") as step:
        time.sleep(0.3)
        step.log_stats(input_count=1)

        attributes = {
            "keywords": ["wireless", "charger", "phone", "fast", "charging"],
            "inferred_category_hints": ["Electronics", "Accessories", "Phone Accessories"],
            "material": "plastic",
            "power_output": "15W",
        }

        step.log_stats(output_count=1, keywords_extracted=len(attributes["keywords"]))
        return attributes


def match_category_candidates(attributes: dict, taxonomy: list):
    with xray_step("MatchCandidates", "API") as step:
        step.log_stats(input_count=1, taxonomy_size=len(taxonomy))
        time.sleep(0.2)

        # Simulate category matching
        candidates = []
        for i, category in enumerate(taxonomy):
            match_score = random.uniform(0.1, 0.95)
            if any(keyword in category["name"].lower() for keyword in attributes["keywords"]):
                match_score += 0.2  # Boost if keywords match

            candidates.append(
                {
                    "id": category["id"],
                    "name": category["name"],
                    "path": category["path"],
                    "match_score": min(match_score, 1.0),
                }
            )

        # Sort by match score
        candidates.sort(key=lambda x: x["match_score"], reverse=True)

        # Log top 10 candidates
        step.log_sampled_candidates(accepted=candidates[:10])
        step.log_stats(output_count=len(candidates))
        return candidates


def filter_by_confidence(candidates: list, threshold: float = 0.5):
    with xray_step("FilterByConfidence", "FILTER") as step:
        step.log_stats(input_count=len(candidates))

        kept = []
        dropped = []

        for cand in candidates:
            if cand["match_score"] >= threshold:
                kept.append(cand)
            else:
                dropped.append(cand)

        filter_rate = len(dropped) / len(candidates) if candidates else 0
        step.log_stats(
            output_count=len(kept),
            dropped_count=len(dropped),
            filter_rate=filter_rate,
            threshold=threshold,
        )

        # Sample candidates
        step.log_sampled_candidates(
            accepted=kept[:5], rejected=dropped[:5] if dropped else []
        )

        return kept


def score_with_business_rules(candidates: list, product: dict):
    with xray_step("ApplyBusinessRules", "RANKING") as step:
        step.log_stats(input_count=len(candidates))

        scored = []
        rejected = []

        for cand in candidates:
            # Simulate business rules
            # Rule 1: Prefer categories with "Phone" in the path
            if "Phone" in cand["path"]:
                cand["rule_boost"] = 0.15
            else:
                cand["rule_boost"] = 0.0

            # Rule 2: Penalize "Office" categories for phone accessories
            if "Office" in cand["path"] and "phone" in product["title"].lower():
                rejected.append(cand)
                continue

            cand["final_score"] = cand["match_score"] + cand["rule_boost"]
            scored.append(cand)

        scored.sort(key=lambda x: x["final_score"], reverse=True)

        step.log_stats(output_count=len(scored), rejected_count=len(rejected))
        step.log_sampled_candidates(accepted=scored[:5], rejected=rejected[:3] if rejected else [])

        return scored


def select_final_category(scored_candidates: list):
    with xray_step("SelectCategory", "LLM") as step:
        step.log_stats(input_count=len(scored_candidates))

        if not scored_candidates:
            step.log_stats(output_count=0)
            return None

        # Take top 3 and use LLM to make final decision
        top_3 = scored_candidates[:3]
        time.sleep(0.3)

        # Simulate LLM decision
        best = top_3[0]  # For simplicity, take the highest scored

        step.log_stats(
            output_count=1, final_score=best["final_score"], confidence=best["final_score"]
        )
        step.log_sampled_candidates(selected=[best])

        return best


def run_pipeline():
    product = {
        "id": "prod_CAT789",
        "title": "Wireless Fast Charger for iPhone and Samsung",
        "description": "15W fast wireless charging pad compatible with all Qi-enabled devices",
    }

    # Simulated taxonomy (in reality, this would be thousands of categories)
    taxonomy = [
        {"id": "cat_001", "name": "Electronics", "path": "Electronics"},
        {"id": "cat_002", "name": "Phone Accessories", "path": "Electronics > Phone Accessories"},
        {"id": "cat_003", "name": "Wireless Chargers", "path": "Electronics > Phone Accessories > Wireless Chargers"},
        {"id": "cat_004", "name": "Office Supplies", "path": "Office Supplies"},
        {"id": "cat_005", "name": "Desk Accessories", "path": "Office Supplies > Desk Accessories"},
        {"id": "cat_006", "name": "Car Accessories", "path": "Automotive > Car Accessories"},
        {"id": "cat_007", "name": "Home & Kitchen", "path": "Home & Kitchen"},
        {"id": "cat_008", "name": "Computers & Accessories", "path": "Computers & Accessories"},
    ]

    meta = {"product_id": product["id"], "taxonomy_version": "v2.5"}

    with xray_run("ProductCategorization", metadata=meta) as ctx:
        print(f"Started Run ID: {ctx.run_id}")

        attributes = extract_product_attributes(product)
        print(f"Extracted Attributes: {attributes['keywords']}")

        candidates = match_category_candidates(attributes, taxonomy)
        print(f"Matched {len(candidates)} category candidates")

        filtered = filter_by_confidence(candidates, threshold=0.5)
        print(f"Filtered to {len(filtered)} candidates (threshold 0.5)")

        scored = score_with_business_rules(filtered, product)
        print(f"Scored {len(scored)} candidates after business rules")

        final_category = select_final_category(scored)
        print(
            f"Final Category: {final_category['name']} ({final_category['path']}) - Score: {final_category['final_score']:.2f}"
        )


if __name__ == "__main__":
    print("Running Product Categorization Pipeline...")
    run_pipeline()
