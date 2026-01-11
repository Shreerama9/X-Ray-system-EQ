import sys
import os
import time
import random

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sdk import xray_run, xray_step, client

def generate_keywords(product_title: str):
    with xray_step("GenerateKeywords", "LLM") as step:
        time.sleep(0.5)
        # Explicit Stats
        step.log_stats(input_count=1)
        
        base = ["laptop stand", "desk organizer", "monitor riser"]
        if random.random() < 0.2:
            base.append("phone case")
        
        step.log_stats(output_count=len(base))
        return base

def search_competitors(keywords: list):
    with xray_step("SearchCompetitors", "API") as step:
        time.sleep(0.3)
        step.log_stats(input_count=len(keywords))
        
        candidates = []
        for k in keywords:
            for i in range(3):
                candidates.append({
                    "id": f"prod_{random.randint(1000,9999)}",
                    "title": f"Premium {k} {i+1}",
                    "price": random.randint(20, 150),
                    "rating": round(random.uniform(3.0, 5.0), 1),
                    "category": "Office" if "phone" not in k else "Accessories"
                })
        
        # Log sampled candidates (accepted here means 'found')
        step.log_sampled_candidates(accepted=candidates)
        step.log_stats(output_count=len(candidates))
        return candidates

def filter_competitors(candidates: list):
    with xray_step("FilterCompetitors", "FILTER") as step:
        step.log_stats(input_count=len(candidates))

        kept = []
        dropped_with_reasons = []

        for c in candidates:
            if c["price"] > 100:
                dropped_with_reasons.append((c, f"Price ${c['price']} exceeds threshold $100"))
            elif c["rating"] < 4.0:
                dropped_with_reasons.append((c, f"Rating {c['rating']} below minimum 4.0"))
            else:
                kept.append(c)

        step.log_stats(output_count=len(kept), dropped_count=len(dropped_with_reasons))

        # Log with reasoning - demonstrates the tuple format (candidate, reasoning)
        step.log_sampled_candidates(accepted=kept, rejected=dropped_with_reasons)
        return kept

def rank_and_select(candidates: list):
    with xray_step("RankAndSelect", "LLM") as step:
        step.log_stats(input_count=len(candidates))
        time.sleep(0.2)
        
        if not candidates:
            step.log_stats(output_count=0)
            return None
            
        best = random.choice(candidates)
        step.log_stats(output_count=1)
        
        # Log the winner
        step.log_sampled_candidates(selected=[best])
        return best

def run_pipeline(product_input):
    meta = {"product_id": "prod_123", "user_id": "user_456"}
    
    with xray_run("CompetitorDiscovery", metadata=meta) as ctx:
        print(f"Started Run ID: {ctx.run_id}")
        
        keywords = generate_keywords(product_input)
        print(f"Keywords: {keywords}")
        
        candidates = search_competitors(keywords)
        print(f"Found {len(candidates)} candidates")
        
        filtered = filter_competitors(candidates)
        print(f"Filtered down to {len(filtered)} candidates")
        
        final_selection = rank_and_select(filtered)
        print(f"Final Selection: {final_selection}")

if __name__ == "__main__":
    product = "Aluminum Foldable Laptop Stand"
    print("Running Pipeline...")
    run_pipeline(product)
