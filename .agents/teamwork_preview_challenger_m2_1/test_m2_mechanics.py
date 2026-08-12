"""
Empirical Verification & Stress-Testing Suite for M2 Deliverable
"""

import math
import numpy as np

def test_solar_zenith_and_airmass():
    print("=== TEST 1: Solar Zenith Angle & Air Mass Calculations ===")
    
    # 1. Kasten-Young Air Mass formula test
    def air_mass_ky(theta_deg):
        theta_rad = math.radians(theta_deg)
        cos_theta = math.cos(theta_rad)
        term2 = 0.50572 * ((96.07995 - theta_deg) ** (-1.6364))
        return 1.0 / (cos_theta + term2)
    
    def air_mass_sec(theta_deg):
        return 1.0 / math.cos(math.radians(theta_deg))

    angles = [0, 15, 30, 45, 60, 75, 80, 85]
    print("Theta (deg) | Kasten-Young AM | Secant AM | Abs Diff | % Diff")
    for a in angles:
        am_ky = air_mass_ky(a)
        am_sec = air_mass_sec(a)
        diff = abs(am_ky - am_sec)
        pdiff = (diff / am_ky) * 100
        print(f"{a:11d} | {am_ky:15.4f} | {am_sec:9.4f} | {diff:8.4f} | {pdiff:6.2f}%")
        
    # Check AM at theta = 75 deg
    am_75 = air_mass_ky(75)
    print(f"\nAM at 75 deg (Document claims ~3.86): Calculated = {am_75:.4f}")

    # 2. Solar declination & Zenith angle over the year
    # Declination formula: delta = 23.45 * sin(360/365 * (284 + d))
    # Compute exact solar noon zenith angle for various latitudes across 365 days
    latitudes = [0, 20, 32.5, 39.5, 52.5, 65]
    lat_names = ["0 (Equator)", "20 (Tropics)", "32.5 (30-35)", "39.5 (37-42)", "52.5 (50-55)", "65 (60+)"]
    
    print("\nCalculated Solar Noon Zenith Angle > 45 deg Duration (Months):")
    print("Lat (deg) | Region | Days Theta > 45 | Calculated Months | M2 Claimed Months")
    
    for lat, name in zip(latitudes, lat_names):
        days_above_45 = 0
        for d in range(1, 366):
            delta = 23.45 * math.sin(math.radians(360 / 365 * (284 + d)))
            theta_z = abs(lat - delta)
            if theta_z > 45.0:
                days_above_45 += 1
        months = (days_above_45 / 365.0) * 12.0
        print(f"{lat:9.1f} | {name:15s} | {days_above_45:15d} | {months:17.2f} | M2 Table")

def test_rayleigh_and_ozone():
    print("\n=== TEST 2: Rayleigh Scattering & Ozone Beer-Lambert Attenuation ===")
    
    # Rayleigh scattering ratio: tau_R(295) / tau_R(360) = (360/295)^4
    ratio = (360.0 / 295.0) ** 4
    print(f"Rayleigh ratio (360/295)^4: Claimed = 2.21, Calculated = {ratio:.4f}")
    
    # Photon energy at 315 nm
    h = 6.62607015e-34
    c = 2.99792458e8
    ev_conv = 1.602176634e-19
    
    e_315_j = (h * c) / (315e-9)
    e_315_ev = e_315_j / ev_conv
    print(f"Photon energy at 315 nm: Claimed = 3.94 eV, Calculated = {e_315_ev:.4f} eV")

    e_290_ev = (h * c / 290e-9) / ev_conv
    print(f"Photon energy at 290 nm: Calculated = {e_290_ev:.4f} eV")

    tau_O3_295 = -math.log(0.716) / 0.1
    print(f"Ozone optical depth at 295 nm required for 28.4% drop on 10% DU increase: tau = {tau_O3_295:.2f}")

def test_selenium_pharmacokinetics():
    print("\n=== TEST 3: Selenium Pharmacokinetics (2-Compartment Model) ===")
    
    k_struct = math.log(2) / 252.0
    print(f"Elimination rate constant k_struct for t_1/2=252 days: {k_struct:.6f} day^-1")
    
    f_1yr = math.exp(-k_struct * 365)
    print(f"Fraction of organic Se pool remaining after 1 year: {f_1yr:.4f} ({f_1yr*100:.1f}%)")

def test_boron_free_t_formula():
    print("\n=== TEST 4: Free Testosterone Formula & Boron Impact ===")
    
    def calc_free_t_vermeulen(t_total_nmol, shbg_nmol, alb_g_l=43.0):
        # Albumin concentration in nmol/L: alb_g_l / 66437 * 1e9
        N = 1.0 + 3.6e-5 * (alb_g_l / 66.437 * 1e6 / 1000.0)
        Kt = 1.0 # 1/(nmol/L)
        
        a = Kt * N
        b = Kt * shbg_nmol + N - Kt * t_total_nmol
        c = -t_total_nmol
        
        free_t = (-b + math.sqrt(b**2 - 4*a*c)) / (2*a)
        return free_t

    ft_base = calc_free_t_vermeulen(20.0, 40.0)
    print(f"Baseline: T_total = 20 nmol/L, SHBG = 40 nmol/L => Free T = {ft_base:.4f} nmol/L ({ft_base/20.0*100:.2f}%)")
    
    ft_boron_15 = calc_free_t_vermeulen(20.0, 40.0 * 0.85)
    ft_boron_20 = calc_free_t_vermeulen(20.0, 40.0 * 0.80)
    
    surge_15 = ((ft_boron_15 - ft_base) / ft_base) * 100
    surge_20 = ((ft_boron_20 - ft_base) / ft_base) * 100
    
    print(f"Boron 15% SHBG drop (34 nmol/L): Free T = {ft_boron_15:.4f} nmol/L => Surge = +{surge_15:.2f}%")
    print(f"Boron 20% SHBG drop (32 nmol/L): Free T = {ft_boron_20:.4f} nmol/L => Surge = +{surge_20:.2f}%")

if __name__ == "__main__":
    test_solar_zenith_and_airmass()
    test_rayleigh_and_ozone()
    test_selenium_pharmacokinetics()
    test_boron_free_t_formula()
