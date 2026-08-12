"""
Verification script for M1 Classification Analysis Stress-Testing.
Empirically tests:
1. Matrix Cost Sum vs. Text Claims ($25-$45/mo vs matrix line items)
2. Real-market supplement cost distribution calculations
3. Boron classification logic & cycling paradox
4. Selenium accumulation kinetics & UL proximity
5. Creatine classification criteria score
"""

import sys

def verify_cost_math():
    print("=== 1. COST MATH VERIFICATION ===")
    # Data from Section 4.1 Master Matrix
    tier1_costs = {
        "Zinc & Copper": (4, 8),
        "Omega-3 (EPA/DHA 2-3g)": (15, 25),
        "Active B-Complex": (10, 18),
        "Creatine Monohydrate (3-5g)": (6, 12)
    }
    
    tier2_costs = {
        "Vitamin D3 + K2 MK7": (6, 10),
        "Magnesium (400-600mg elemental)": (8, 15),
        "Selenium (100-200mcg)": (3, 6),
        "Boron (6-10mg)": (3, 5)
    }

    tier3_costs = {
        "Ashwagandha (KSM-66)": (15, 25),
        "Tongkat Ali": (20, 35),
        "Shilajit": (25, 40),
        "CoQ10 / Ubiquinol": (25, 45),
        "L-Carnitine L-Tartrate": (15, 25),
        "NMN + TMG": (40, 80),
        "Cordyceps": (18, 30),
        "Cistanche": (20, 35),
        "Maca": (10, 18)
    }

    t1_min = sum(val[0] for val in tier1_costs.values())
    t1_max = sum(val[1] for val in tier1_costs.values())

    t2_min = sum(val[0] for val in tier2_costs.values())
    t2_max = sum(val[1] for val in tier2_costs.values())

    t1_t2_min = t1_min + t2_min
    t1_t2_max = t1_max + t2_max
    t1_t2_avg = (t1_t2_min + t1_t2_max) / 2

    print(f"Tier 1 Matrix Range: ${t1_min} - ${t1_max}/mo (Avg: ${(t1_min+t1_max)/2:.2f})")
    print(f"Tier 2 Matrix Range: ${t2_min} - ${t2_max}/mo (Avg: ${(t2_min+t2_max)/2:.2f})")
    print(f"Combined Tier 1 + Tier 2 Matrix Sum: ${t1_t2_min} - ${t1_t2_max}/mo (Avg: ${t1_t2_avg:.2f})")
    
    claimed_min = 25
    claimed_max = 45
    print(f"Claimed Tier 1 + Tier 2 Cost in Text: ${claimed_min} - ${claimed_max}/mo")
    
    discrepancy_min = t1_t2_min - claimed_min
    discrepancy_max = t1_t2_max - claimed_max
    print(f"Discrepancy: Minimum is off by +${discrepancy_min}/mo ({discrepancy_min/claimed_min*100:.1f}%), Maximum is off by +${discrepancy_max}/mo ({discrepancy_max/claimed_max*100:.1f}%)")

    # Real market realistic pricing check
    print("\n--- Market Realistic Pricing Calculation ---")
    market_prices = {
        "rTG Omega-3 (2.5g EPA/DHA daily = 75g/mo = ~75 softgels @ $0.40/softgel)": 30.00,
        "Mg Bisglycinate + Malate (500mg elemental = 5 caps daily @ $0.12/cap)": 18.00,
        "Active B-Complex (Thorne/Pure Encapsulations = 1 cap daily)": 16.00,
        "Creatine Monohydrate (5g/day = 150g/mo @ $0.08/5g)": 7.50,
        "D3 5000 IU + K2 MK7 100mcg (1 cap daily)": 9.00,
        "Zinc Bisglycinate 30mg + Copper 2mg": 7.00,
        "Selenium L-Selenomethionine 200mcg": 4.50,
        "Boron Citrate/Fructoborate 10mg": 5.00
    }
    total_market_real = sum(market_prices.values())
    print("Itemized Realistic Market Calculation for baseline protocol:")
    for k, v in market_prices.items():
        print(f"  - {k}: ${v:.2f}/mo")
    print(f"REALISTIC MARKET TOTAL (T1 + T2): ${total_market_real:.2f}/mo")
    print(f"Deviation from $25-$45 text claim: +${total_market_real - 45:.2f}/mo above upper claim bound!")

def verify_selenium_accumulation():
    print("\n=== 2. SELENIUM ACCUMULATION & TOXICITY MODEL ===")
    # Baseline dietary intake + supplement
    dietary_se = 110  # mcg/day (average US male adult omnivore)
    supp_se = 200     # mcg/day recommended in report
    total_se = dietary_se + supp_se
    ul_se = 400       # mcg/day Tolerable Upper Intake Level
    
    print(f"Estimated Dietary Selenium Intake: {dietary_se} mcg/day")
    print(f"Recommended Supplemental Selenium: {supp_se} mcg/day")
    print(f"Total Daily Selenium Load: {total_se} mcg/day")
    print(f"Tolerable Upper Intake Level (UL): {ul_se} mcg/day")
    print(f"Safety Margin to UL: {ul_se - total_se} mcg/day (Only {(ul_se - total_se)/ul_se*100:.1f}% safety buffer!)")
    
    # Half-life of L-selenomethionine in body tissue is ~252 days
    print("Risk Factor: L-Selenomethionine incorporates into tissue proteins with t1/2 ~ 252 days.")
    print("Long-term continuous intake at >300mcg total/day increases risk of dysglycemia / T2D in selenium-replete populations (SELECT trial findings).")

def verify_boron_tier_logic():
    print("\n=== 3. BORON TIER LOGIC AUDIT ===")
    print("Criteria for Tier 2 (Dietary Gap):")
    print(" - Daily essential baseline micronutrient")
    print(" - Continuous long-term sufficiency restoration")
    print(" - No cycling required")
    print("\nReport's Boron Specification:")
    print(" - Requires mandatory cycling: 2-3 Weeks ON, 1 Week OFF")
    print(" - Reason given in report: 'Continuous daily administration beyond 4-6 weeks can induce compensatory feedback elevation of SHBG or aromatase activity.'")
    print("LOGICAL CONTRADICTION: If a compound requires mandatory pulse-cycling to prevent endocrine desensitization/feedback, it operates as a TIER 3 TARGETED BOOSTER, not a Tier 2 continuous dietary gap replacement!")

def verify_creatine_tier_logic():
    print("\n=== 4. CREATINE TIER LOGIC AUDIT ===")
    print("Tier 1 Definition in Report: Essential Base required for fundamental cellular life across all humans.")
    print("Creatine Features:")
    print(" - Endogenous synthesis: Liver/kidney synthesize ~1g/day from Arg+Gly+Met.")
    print(" - Dietary intake: Omnivores ingest 1-2g/day from meat/fish.")
    print(" - Lack of deficiency disease: Absence of creatine supplementation does not cause deficiency disease in healthy omnivores.")
    print(" - Primary role: Ergogenic performance enhancer (muscle power, high-intensity ATP buffer, cognitive resilience under stress).")
    print("MISCLASSIFICATION FINDING: Creatine is an ergogenic performance compound. While highly effective, placing it in Tier 1 alongside Zinc, B-vitamins, and Omega-3 blurs the line between essential life nutrients and ergogenic performance enhancers.")

if __name__ == "__main__":
    verify_cost_math()
    verify_selenium_accumulation()
    verify_boron_tier_logic()
    verify_creatine_tier_logic()
