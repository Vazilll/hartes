import math

def test_cost_math():
    print("=== FINANCIAL COST MATH VERIFICATION ===")
    
    # Standalone Retail Items listed in M3_actionable_protocol.md line 257-264
    retail_items = {
        "D3+K2": 12.00,
        "Zinc": 10.00,
        "Copper": 8.00,
        "Magnesium": 22.00,
        "B-Complex": 18.00,
        "Creatine": 15.00,
        "Selenium": 8.00,
        "Boron": 9.00
    }
    
    retail_sum = sum(retail_items.values())
    retail_claimed = 95.00
    print(f"Retail Itemized Sum: ${retail_sum:.2f}")
    print(f"Retail Claimed Total: ${retail_claimed:.2f}")
    print(f"Retail Math Discrepancy: ${retail_sum - retail_claimed:.2f}")
    
    # Bundled Matrix Items listed in line 269-273
    bundled_items = {
        "Item A (D3+K2)": 6.50,
        "Item B (Zn+Cu+B+Se Matrix)": 10.50,
        "Item C (Bulk Mg Powder)": 9.00,
        "Item D (Bulk Creatine Powder)": 7.00,
        "Item E (Active B-Complex)": 6.00
    }
    
    bundled_sum = sum(bundled_items.values())
    bundled_claimed = 39.00
    print(f"\nBundled Itemized Sum: ${bundled_sum:.2f}")
    print(f"Bundled Claimed Total: ${bundled_claimed:.2f}")
    print(f"Bundled Math Discrepancy: ${bundled_sum - bundled_claimed:.2f}")
    
    # Net Savings Math
    claimed_savings = 56.00
    actual_savings_vs_claimed_retail = retail_claimed - bundled_sum
    actual_savings_vs_actual_retail = retail_sum - bundled_sum
    
    claimed_pct = (56.00 / 95.00) * 100
    actual_pct_vs_actual_retail = (actual_savings_vs_actual_retail / retail_sum) * 100
    
    print(f"\nClaimed Net Savings: ${claimed_savings:.2f} ({claimed_pct:.2f}%)")
    print(f"Actual Savings vs Actual Retail ($102): ${actual_savings_vs_actual_retail:.2f} ({actual_pct_vs_actual_retail:.2f}%)")
    
    # Omitted items analysis: Omega-3 rTG
    # Protocol Section 1.1/1.2 recommends 2,000-3,000 mg rTG Omega-3 oil (1,200-1,800 mg EPA+DHA)
    # Market cost of high-grade rTG Omega-3 (e.g. Nordic Naturals, Sports Research, Viva Labs): $25.00 - $35.00/month
    omega3_cost_low = 25.00
    omega3_cost_high = 35.00
    
    print("\n--- Omitted Omega-3 Analysis ---")
    print(f"Adding Omega-3 (${omega3_cost_low:.2f} - ${omega3_cost_high:.2f}/mo) to Bundled Total:")
    print(f"True Bundled Monthly Total: ${bundled_sum + omega3_cost_low:.2f} - ${bundled_sum + omega3_cost_high:.2f}")
    
    # Lab Work Amortization Analysis
    # Baseline + 12-week panel (2 panels per year)
    # Required markers: Total T, Free T (Equilibrium Dialysis), SHBG, Sensitive E2 (LC-MS/MS), 25(OH)D3, RBC Mg, Serum Se, ApoB, hs-CRP, HbA1c, CMP
    lab_cost_per_panel = 350.00 # conservative out-of-pocket self-pay cost
    annual_lab_cost = lab_cost_per_panel * 2
    monthly_lab_amortized = annual_lab_cost / 12.0
    
    print("\n--- Amortized Clinical Lab Panel Analysis ---")
    print(f"Estimated Out-of-Pocket Cost per Panel: ${lab_cost_per_panel:.2f}")
    print(f"Annual Lab Cost (2 panels): ${annual_lab_cost:.2f}")
    print(f"Amortized Monthly Lab Overhead: ${monthly_lab_amortized:.2f}/mo")
    print(f"Total Protocol True Cost (Bundled + Omega-3 + Labs): ${bundled_sum + omega3_cost_low + monthly_lab_amortized:.2f} - ${bundled_sum + omega3_cost_high + monthly_lab_amortized:.2f}/mo")

def test_toxicity_bounds():
    print("\n=== TOXICITY & SAFETY BOUNDS VERIFICATION ===")
    
    # 1. Selenium Toxicity Risk
    # UL for Selenium = 400 mcg/day
    supplement_se = 100.0 # mcg (upper end of protocol 50-100 mcg)
    brazil_nut_se = 68.0 # mcg per single nut average
    nuts_per_day = 4
    dietary_se = nuts_per_day * brazil_nut_se + 40.0 # food base
    total_se = supplement_se + dietary_se
    print(f"Selenium Protocol Dose: {supplement_se} mcg")
    print(f"Total Daily Se with 4 Brazil Nuts + Diet: {total_se} mcg (UL = 400 mcg) -> Exceeds UL by {total_se - 400} mcg!")
    
    # 2. Zinc:Copper Ratio & Metal Absorption Thresholds
    zn_dose = 30.0 # mg elemental
    cu_dose = 2.0 # mg elemental
    ratio = zn_dose / cu_dose
    print(f"\nZinc:Copper Ratio: {zn_dose}:{cu_dose} = {ratio:.1f}:1 (Target: 10:1 to 15:1) -> Pass ratio, but inspect total Zn load if dietary Zn = 15-20mg.")
    
    # 3. Magnesium Single Dose Upper Limit for Osmotic Diarrhea
    # Dietary Supplement UL for Magnesium (set by NIH / FNB) = 350 mg elemental Mg from supplements per day!
    # Protocol recommends 400-600 mg elemental Mg in a SINGLE evening dose!
    mg_dose = 600.0 # mg elemental
    fnb_ul = 350.0 # mg
    print(f"\nMagnesium Single Dose: {mg_dose} mg elemental")
    print(f"FNB Dietary Supplement Upper Limit (UL) for Mg: {fnb_ul} mg/day")
    print(f"Exceeds Supplement UL by: {mg_dose - fnb_ul} mg (High risk of GI hyper-motility / osmotic diarrhea)")

if __name__ == "__main__":
    test_cost_math()
    test_toxicity_bounds()
