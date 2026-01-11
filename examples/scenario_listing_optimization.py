import sys
import os
import time
import random

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sdk import xray_run, xray_step, client

def analyze_current_listing(product_data: dict):
    with xray_step("AnalyzeCurrentListing", "LLM") as step:
        time.sleep(0.4)
        step.log_stats(input_count=1)

        analysis = {
            "title_length": len(product_data["title"]),
            "keyword_density": random.uniform(0.3, 0.7),
            "readability_score": random.randint(50, 90),
            "bullet_points": len(product_data.get("bullets", [])),
        }

        step.log_stats(
            title_length=analysis["title_length"],
            keyword_density=analysis["keyword_density"],
            output_count=1,
        )
        return analysis


def extract_competitor_patterns(competitors: list):
    with xray_step("ExtractCompetitorPatterns", "API") as step:
        time.sleep(0.3)
        step.log_stats(input_count=len(competitors))

        patterns = []
        for comp in competitors:
            patterns.append(
                {
                    "id": comp["id"],
                    "avg_title_length": random.randint(100, 150),
                    "common_keywords": ["premium", "durable", "ergonomic"],
                    "bullet_count": random.randint(5, 7),
                }
            )

        step.log_sampled_candidates(accepted=patterns[:3])
        step.log_stats(output_count=len(patterns))
        return patterns


def generate_variations(current_analysis: dict, patterns: list):
    with xray_step("GenerateVariations", "LLM") as step:
        time.sleep(0.5)
        step.log_stats(input_count=1)

        variations = []
        for i in range(5):
            variation = {
                "id": f"var_{i+1}",
                "title": f"Premium Ergonomic Laptop Stand - Variation {i+1}",
                "bullets": [f"Benefit {j+1}" for j in range(random.randint(5, 7))],
                "description": f"Enhanced description variant {i+1}",
                "estimated_score": random.uniform(0.6, 0.95),
            }
            variations.append(variation)

        step.log_sampled_candidates(accepted=variations)
        step.log_stats(output_count=len(variations))
        return variations


def score_and_rank(variations: list, business_rules: dict):
    with xray_step("ScoreAndRank", "RANKING") as step:
        step.log_stats(input_count=len(variations))

        scored = []
        rejected = []

        for var in variations:
            score = var["estimated_score"]

            # Apply business rules
            if len(var["title"]) > 200:
                rejected.append(var)
                continue
            if len(var["bullets"]) < 5:
                rejected.append(var)
                continue

            var["final_score"] = score
            scored.append(var)

        # Sort by score
        scored.sort(key=lambda x: x["final_score"], reverse=True)

        step.log_stats(
            output_count=len(scored), rejected_count=len(rejected), avg_score=sum(s["final_score"] for s in scored) / len(scored) if scored else 0
        )
        step.log_sampled_candidates(accepted=scored, rejected=rejected)

        return scored


def select_best_variation(scored_variations: list):
    with xray_step("SelectBestVariation", "LLM") as step:
        step.log_stats(input_count=len(scored_variations))

        if not scored_variations:
            step.log_stats(output_count=0)
            return None

        best = scored_variations[0]
        step.log_stats(output_count=1, final_score=best["final_score"])
        step.log_sampled_candidates(selected=[best])
        return best


def run_pipeline():
    product = {
        "id": "prod_XYZ456",
        "title": "Aluminum Laptop Stand for Desk",
        "bullets": ["Adjustable", "Lightweight", "Durable"],
    }

    competitors = [
        {"id": f"comp_{i}", "title": f"Competitor Product {i}"} for i in range(10)
    ]

    business_rules = {"max_title_length": 200, "min_bullets": 5}

    meta = {"product_id": product["id"], "optimization_type": "listing_quality"}

    with xray_run("ListingOptimization", metadata=meta) as ctx:
        print(f"Started Run ID: {ctx.run_id}")

        analysis = analyze_current_listing(product)
        print(f"Current Listing Analysis: {analysis}")

        patterns = extract_competitor_patterns(competitors)
        print(f"Extracted {len(patterns)} competitor patterns")

        variations = generate_variations(analysis, patterns)
        print(f"Generated {len(variations)} variations")

        scored = score_and_rank(variations, business_rules)
        print(f"Scored {len(scored)} variations")

        best = select_best_variation(scored)
        print(f"Best Variation: {best['title'] if best else 'None'}")


if __name__ == "__main__":
    print("Running Listing Optimization Pipeline...")
    run_pipeline()
