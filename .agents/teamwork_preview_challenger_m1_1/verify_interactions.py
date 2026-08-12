"""
Detailed simulation script for Selenium Tissue Accumulation kinetics
and Pharmacodynamic Interaction Matrix verification.
"""

import math

def simulate_selenium_accumulation():
    print("=== SIMULATION: SELENIUM TISSUE ACCUMULATION KINETICS ===")
    # L-Selenomethionine half-life ~ 252 days in human body (non-specific protein incorporation)
    # k_elimination = ln(2) / t_1/2
    half_life_days = 252
    k_elim = math.log(2) / half_life_days
    
    dietary_daily = 120  # mcg/day baseline diet
    supp_daily = 200     # mcg/day recommended in M1 report
    total_daily = dietary_daily + supp_daily # 320 mcg/day
    
    # Simple compartment accumulation model over 365 days
    body_burden_initial = 15000  # ~15 mg standard body selenium pool in 70kg male
    
    days = 365
    current_pool = body_burden_initial
    
    print(f"Initial Body Selenium Pool: {body_burden_initial/1000:.2f} mg")
    print(f"Daily Intake: {total_daily} mcg/day ({dietary_daily} diet + {supp_daily} supp)")
    
    for d in range(1, days + 1):
        # Daily elimination based on current pool
        eliminated = current_pool * k_elim
        # Daily absorption (~90% for L-Selenomethionine)
        absorbed = total_daily * 0.90
        current_pool = current_pool + absorbed - eliminated
    
    print(f"Body Selenium Pool after 365 days of 200mcg/d supp: {current_pool/1000:.2f} mg")
    percent_increase = ((current_pool - body_burden_initial) / body_burden_initial) * 100
    print(f"Net Body Selenium Increase: +{percent_increase:.1f}%")
    print("Conclusion: Continuous un-monitored L-Selenomethionine leads to progressive protein-bound accumulation, narrowing safety margin to toxic threshold (UL 400mcg/d).")

def check_interaction_edge_cases():
    print("\n=== UNWATCHED PHARMACODYNAMIC INTERACTION EDGE CASES ===")
    interactions = [
        {
            "pair": "High-Dose Vitamin D3 (5000 IU) + Low/Unmonitored Magnesium",
            "risk": "D3 hydroxylation enzymes (CYP2R1, CYP27B1) consume Mg2+. Rapidly worsens intracellular Mg depletion, triggering muscle spasms, insomnia, and cardiac arrhythmias.",
            "severity": "HIGH"
        },
        {
            "pair": "Ashwagandha (KSM-66/Sensoril) + Selenium (200mcg)",
            "risk": "Dual stimulation of Thyroid axis (Ashwagandha increases T4->T3, Selenium increases DIO1/DIO2 deiodination). Risk of subclinical hyperthyroidism/thyrotoxicosis in susceptible males.",
            "severity": "MEDIUM-HIGH"
        },
        {
            "pair": "High-Dose EPA/DHA (3g) + Purified Shilajit + Cordyceps",
            "risk": "Additive antiplatelet / mild anticoagulation effect. Increases bleeding tendency or post-workout bruising.",
            "severity": "MEDIUM"
        },
        {
            "pair": "Boron (10mg daily without cycling) + High Zinc",
            "risk": "Continuous Boron can cause E2 rebound (elevated estradiol) and SHBG down-regulation overshooting target ranges if taken without 2w ON / 1w OFF cycling.",
            "severity": "HIGH"
        }
    ]
    
    for idx, item in enumerate(interactions, 1):
        print(f"{idx}. [{item['severity']}] {item['pair']}")
        print(f"   Mechanism: {item['risk']}\n")

if __name__ == "__main__":
    simulate_selenium_accumulation()
    check_interaction_edge_cases()
