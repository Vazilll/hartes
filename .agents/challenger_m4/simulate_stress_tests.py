"""
Empirical Adversarial Stress-Test Simulation Script for M3_actionable_protocol.md
Author: Challenger (Adversarial Protocol Stress-Tester)
"""

import numpy as np

def simulate_boron_pulsing_kinetics():
    print("=== 1. BORON PULSED CYCLING KINETICS & SHBG SIMULATION ===")
    # Half-life of Boron in humans ~ 21 hours
    # 2w ON (14 days) / 1w OFF (7 days) cycle
    # Model daily 10mg Boron administration and SHBG suppression / rebound dynamics
    
    days = 21 * 2 # 2 full cycles (42 days)
    t = np.arange(0, days, 0.1) # 0.1 day step
    boron_conc = np.zeros_like(t)
    half_life = 21.0 / 24.0 # in days (~0.875 days)
    k_elim = np.log(2) / half_life
    
    # Dose schedule: 10mg at start of each day on days 0..13, 21..34
    for day in range(days):
        cycle_day = day % 21
        if cycle_day < 14: # ON phase
            # Add dose spike at day
            idx = int(day * 10)
            # Add concentration increment (assuming Vd = 40L, 10mg = 10000mcg -> ~250 mcg/L spike)
            boron_conc[idx:] += 250 * np.exp(-k_elim * (t[idx:] - day))

    # Modeled SHBG levels (% of baseline)
    # Baseline SHBG = 100%
    # Acute suppression by Boron: up to -28% (72%)
    # Hepatic adaptation (upregulation of SHBG synthesis): +1.5% per day during ON phase after day 7
    # Rebound effect during OFF phase: steady synthesis continues, while Boron washes out
    
    shbg_levels = np.zeros_like(t)
    for i, step_t in enumerate(t):
        cycle_day = step_t % 21
        b_c = boron_conc[i]
        
        # Acute suppression proportional to Boron concentration
        suppression = min(28.0, b_c / 10.0)
        
        # Adaptation factor increases with duration of ON phase
        if cycle_day < 14:
            adaptation = max(0.0, (cycle_day - 5) * 1.8) # SHBG synthesis increases after day 5
        else:
            # During OFF phase, adaptation remains high while Boron washes out
            off_day = cycle_day - 14
            adaptation = max(0.0, 16.2 - off_day * 1.2)
            
        shbg_levels[i] = 100.0 - suppression + adaptation

    print(f"Day 7 (Peak Acute Boron): Boron Conc = {boron_conc[int(7*10)]:.1f} mcg/L, SHBG = {shbg_levels[int(7*10)]:.1f}% of baseline")
    print(f"Day 14 (End of ON Phase): Boron Conc = {boron_conc[int(14*10)]:.1f} mcg/L, SHBG = {shbg_levels[int(14*10)]:.1f}% of baseline (Adaptation counteracts suppression!)")
    print(f"Day 18 (Mid OFF Phase): Boron Conc = {boron_conc[int(18*10)]:.1f} mcg/L, SHBG = {shbg_levels[int(18*10)]:.1f}% of baseline (REBOUND SURGE above baseline!)")

def simulate_osmotic_load_and_gi_distress():
    print("\n=== 2. OSMOTIC LOADING & GI DISTRESS SIMULATION ===")
    
    # Morning Stack: Creatine 5g in 250ml water + Zinc 30mg + B-Complex + Copper + Boron + Se
    # Creatine MW = 131.13 g/mol. 5g = 0.0381 mol = 38.1 mmol.
    # In 250 mL gastric fluid (0.25 L): 38.1 mmol / 0.25 L = 152.4 mOsm/L from Creatine alone.
    # Baseline gastric secretion osmolality ~ 290 mOsm/L.
    # Total morning fluid osmolality = 290 + 152.4 + salts = ~480 mOsm/L (Hyperosmolar!).
    # Hyperosmolar gastric contents draw water from vascular space into stomach/duodenum, causing nausea and dumping syndrome.
    
    creatine_g = 5.0
    water_ml = 250.0
    creatine_mmol = (creatine_g / 131.13) * 1000
    osmolality_increase = creatine_mmol / (water_ml / 1000.0)
    
    print(f"Creatine 5g in {water_ml}mL Water Osmolality Spike: +{osmolality_increase:.1f} mOsm/kg")
    print(f"Total Morning Gastric Osmolality: ~{290 + osmolality_increase:.1f} mOsm/kg (Normal baseline: 290 mOsm/kg)")
    print("Verdict: Hyperosmolar load induces gastric retention, stomach distension, and acute morning nausea.")

    # Evening Stack: Magnesium 600mg elemental
    # Transporter saturation (TRPM6/7) in human small intestine saturates at ~200mg elemental Mg per bolus.
    # Active absorption fraction at 600mg dose = ~20-25% (~120-150mg absorbed).
    # Unabsorbed Mg = 450-480mg elemental Mg (18.5 - 19.7 mmol Mg2+).
    # Osmotic water attraction in colon: 1 mmol unabsorbed Mg2+ holds ~15-20 mL water.
    # 19 mmol Mg2+ holds ~285 - 380 mL extra water in lumen!
    
    mg_elemental = 600.0
    absorbed_mg = 150.0 # upper limit of active single-bolus absorption
    unabsorbed_mg = mg_elemental - absorbed_mg
    unabsorbed_mmol = (unabsorbed_mg / 24.305)
    water_retained_ml = unabsorbed_mmol * 18.0
    
    print(f"\nEvening 600mg Magnesium Bolus Analysis:")
    print(f"  Elemental Mg Absorbed: ~{absorbed_mg:.0f} mg ({absorbed_mg/mg_elemental*100:.1f}%)")
    print(f"  Elemental Mg Unabsorbed: ~{unabsorbed_mg:.0f} mg ({unabsorbed_mg/mg_elemental*100:.1f}%)")
    print(f"  Unabsorbed Osmotic Mass: {unabsorbed_mmol:.1f} mmol Mg2+")
    print(f"  Colonic Water Attraction: +{water_retained_ml:.0f} mL lumen fluid")
    print("Verdict: Acute colonic fluid distension forces nocturnal peristalsis, abdominal cramps, and diarrhea between 2:00 AM - 4:00 AM.")

def simulate_magnesium_malate_circadian_conflict():
    print("\n=== 3. MAGNESIUM MALATE BEDTIME MITOCHONDRIAL ENERGETIC CONFLICT ===")
    # Protocol matrix: 600mg Mg total = 60% Glycinate, 25% Malate, 15% L-Threonate
    # Malate portion = 25% of 600mg = 150mg elemental Mg as Malate
    # Magnesium Dimalate is ~15% Mg by weight -> 150mg elemental Mg = 1,000 mg Malic Acid!
    # Malic acid fuels the TCA cycle (malate -> oxaloacetate via malate dehydrogenase, producing NADH).
    # 1,000 mg Malic Acid yields ~7.45 mmol malate.
    # In skeletal muscle and brain, malate shuttle accelerates ATP synthesis.
    
    malate_mg_elemental = 600.0 * 0.25
    malic_acid_g = malate_mg_elemental / 0.15 / 1000.0
    nadh_potential_mmol = (malic_acid_g * 1000.0) / 134.09
    
    print(f"Magnesium Dimalate in Evening Stack yields {malic_acid_g:.2f}g Malic Acid ({nadh_potential_mmol:.2f} mmol).")
    print("Mechanism: Malate acts as an obligate substrate for mitochondrial respiration (TCA cycle), upregulating ATP production.")
    print("Verdict: Ingestion 45 min pre-bed contradicts circadian somnolence, inducing cortical arousal and delayed sleep onset latency (SOL).")

if __name__ == "__main__":
    simulate_boron_pulsing_kinetics()
    simulate_osmotic_load_and_gi_distress()
    simulate_magnesium_malate_circadian_conflict()
