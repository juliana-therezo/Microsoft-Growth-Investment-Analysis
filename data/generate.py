#!/usr/bin/env python3
"""
generate.py - synthetic data generator for
"Where to Invest: Microsoft Growth Investment Analysis"

=====================================================================
ALL DATA PRODUCED BY THIS SCRIPT IS SYNTHETIC, CALIBRATED TO
MICROSOFT'S PUBLISHED RESULTS.
Customers, people, transactions, prices, cost centres, projects and FX
rates are invented. Totals are calibrated so that revenue by segment and
fiscal quarter, operating margins, operating-expense ratios, capital
expenditures (including finance leases) and headcount are close to what
Microsoft published for FY24 Q3 - FY27 Q1 (see the "Calibration" block).
Product-line splits, regional figures, FY26 Q3-Q4 and FY27 Q1 capex and
the FY27 Q1 split into the old three segments are estimates. Individual
records are not Microsoft data.
=====================================================================

What it writes (./raw, 8 CSVs, Jan 2024 - Sep 2026):
    product_hierarchy.csv    ERP material master (SKU -> product line -> segment)
    regions.csv              ERP organisation master (country -> area -> region)
    treasury_fx_rates.csv    treasury rates (SAP TCURR style)
    erp_billing_lines.csv    ERP billing items (SAP style; ';' separated, decimal comma)
    gl_cost_postings.csv     general-ledger line items (SAP FAGLL03 style)
    datacenter_regions.csv   datacenter operations and capex by cloud region x month
    crm_opportunities.csv    CRM opportunity export (Dynamics 365 Sales style)
    fpa_budget.csv           planning-tool export (wide, months as columns)
The fiscal calendar (July-June) is built in SQL; it is not exported.

Run:   python generate.py          (needs Python 3.10+, numpy, pandas)
The random seed is fixed, so every run produces identical files.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
SEED = 42
FIRST_MONTH, LAST_MONTH = "2024-01", "2026-09"
N_ACCOUNTS = 19_700                     # CRM accounts before duplicates
OUT_DIR = Path(__file__).resolve().parent / "raw"

rng = np.random.default_rng(SEED)
MONTHS = pd.period_range(FIRST_MONTH, LAST_MONTH, freq="M")
T = len(MONTHS)                                            # 33 months
CAL_YEAR = np.array([p.year for p in MONTHS])
CAL_MONTH = np.array([p.month for p in MONTHS])
FISCAL_YEAR = CAL_YEAR + (CAL_MONTH >= 7)                  # FY ends 30 June
FISCAL_PERIOD = (CAL_MONTH - 7) % 12 + 1                   # P01 = July
MONTH_START = [p.start_time for p in MONTHS]
MONTH_END = [p.end_time.normalize() for p in MONTHS]
DAYS_IN_MONTH = np.array([p.days_in_month for p in MONTHS])

PBP = "Productivity and Business Processes"
IC = "Intelligent Cloud"
MPC = "More Personal Computing"
SEGMENT_MOVE_MONTH = 18          # index of Jul 2025: Windows Commercial moves MPC -> PBP

# Seasonality multipliers by calendar month (Jan..Dec) - synthetic
SEASON = {
    "flat": np.ones(12),
    "consumer": np.array([0.85, 0.80, 0.85, 0.85, 0.90, 0.95, 0.95, 1.00, 1.00, 1.05, 1.30, 1.50]),
    "ads": np.array([0.95, 0.92, 0.98, 0.98, 1.00, 0.97, 0.92, 0.93, 1.00, 1.05, 1.12, 1.18]),
}

# ---------------------------------------------------------------------------
# Product lines - every parameter below is invented for the simulation
#   growth: underlying annual growth used by the generator
#   cogs/rd/sm/ga: cost as a share of revenue (Azure COGS excludes depreciation)
# ---------------------------------------------------------------------------
PRODUCT_LINES = [
    # code, name, segment, revenue type, growth, billing, season, cogs, rd, sm, ga, existing-share
    ("M365C", "Microsoft 365 Commercial", PBP, "Subscription", 0.15, "monthly", "flat", .16, .10, .09, .025),
    ("M365X", "Microsoft 365 Consumer", PBP, "Subscription", 0.15, "monthly", "consumer", .14, .10, .10, .025),
    ("LNKD", "LinkedIn", PBP, "Subscription", 0.09, "monthly", "flat", .26, .19, .16, .025),
    ("D365", "Dynamics 365", PBP, "Subscription", 0.15, "monthly", "flat", .22, .15, .13, .025),
    ("AZR", "Azure", IC, "Consumption", 0.38, "monthly", "flat", .205, .105, .065, .025),
    ("SRV", "Server Products", IC, "License", -0.02, "monthly", "flat", .06, .09, .08, .025),
    ("EPS", "Enterprise and Partner Services", IC, "Services", 0.02, "monthly", "flat", .60, .04, .09, .025),
    ("WINC", "Windows Commercial", MPC, "Subscription", 0.05, "monthly", "flat", .07, .08, .06, .025),
    ("WOEM", "Windows OEM", MPC, "License", 0.01, "monthly", "consumer", .10, .12, .08, .025),
    ("DEV", "Devices", MPC, "Hardware", -0.10, "monthly", "consumer", .85, .14, .12, .025),
    ("GAME", "Gaming", MPC, "Content and Hardware", -0.04, "monthly", "consumer", .58, .20, .12, .025),
    ("ADS", "Search and News Advertising", MPC, "Advertising", 0.10, "monthly", "ads", .48, .10, .09, .025),
]
PL = pd.DataFrame(PRODUCT_LINES, columns=["code", "name", "segment", "rev_type", "growth", "billing",
                                          "season", "cogs", "rd", "sm", "ga"])
PL_IDX = {c: i for i, c in enumerate(PL.code)}

# SKUs: (product line, description, unit, synthetic list price in USD per unit per month)
SKUS = [
    ("M365C", "Microsoft 365 E3", "SEA", 34), ("M365C", "Microsoft 365 E5", "SEA", 52),
    ("M365C", "Office 365 E1", "SEA", 9), ("M365C", "Microsoft 365 Business Basic", "SEA", 5),
    ("M365C", "Microsoft 365 Business Premium", "SEA", 19), ("M365C", "Microsoft 365 Copilot", "SEA", 27),
    ("M365X", "Microsoft 365 Personal", "SEA", 7), ("M365X", "Microsoft 365 Family", "SEA", 9),
    ("LNKD", "LinkedIn Talent Solutions", "SEA", 640), ("LNKD", "LinkedIn Marketing Solutions", "CU", 1),
    ("LNKD", "LinkedIn Premium Subscriptions", "SEA", 32), ("LNKD", "LinkedIn Sales Navigator", "SEA", 78),
    ("D365", "Dynamics 365 Sales", "SEA", 81), ("D365", "Dynamics 365 Customer Service", "SEA", 86),
    ("D365", "Dynamics 365 Finance", "SEA", 160), ("D365", "Dynamics 365 Business Central", "SEA", 61),
    ("AZR", "Azure Compute", "CU", 1), ("AZR", "Azure Storage", "CU", 1), ("AZR", "Azure SQL Database", "CU", 1),
    ("AZR", "Azure OpenAI Service", "CU", 1), ("AZR", "Azure Networking", "CU", 1),
    ("AZR", "Azure Data and Analytics", "CU", 1),
    ("SRV", "SQL Server Enterprise", "EA", 1150), ("SRV", "Windows Server Datacenter", "EA", 540),
    ("SRV", "System Center", "EA", 280),
    ("EPS", "Unified Support", "CU", 1), ("EPS", "Consulting Services", "HR", 195), ("EPS", "Partner Training", "SEA", 420),
    ("WINC", "Windows Enterprise E3", "SEA", 6), ("WINC", "Windows 365 Cloud PC", "SEA", 27),
    ("WOEM", "Windows 11 Home OEM", "EA", 52), ("WOEM", "Windows 11 Pro OEM", "EA", 88),
    ("DEV", "Surface Laptop", "EA", 990), ("DEV", "Surface Pro", "EA", 940), ("DEV", "Surface Accessories", "EA", 79),
    ("GAME", "Xbox Game Pass", "SEA", 14), ("GAME", "Xbox Content", "EA", 42), ("GAME", "Xbox Hardware", "EA", 390),
    ("ADS", "Bing Search Ads", "CU", 1), ("ADS", "Microsoft Start Ads", "CU", 1),
]
SKU = pd.DataFrame(SKUS, columns=["pl", "desc", "unit", "price"])
SKU["material"] = [str(400100 + 10 * i) for i in range(len(SKU))]
SKU["pl_idx"] = SKU.pl.map(PL_IDX)

# ---------------------------------------------------------------------------
# Calibration to Microsoft's published results
#   Segment revenue per fiscal quarter in USD billions, on the recast basis
#   (Windows Commercial in Productivity and Business Processes for all periods).
#   Sources: Microsoft quarterly earnings releases FY24 Q3 - FY27 Q1. FY26 Q3 is
#   derived (FY26 total minus the other quarters); FY27 Q1 is estimated on the
#   old three-segment basis from the product-line growth Microsoft reported,
#   because Microsoft moved to two new segments in FY27.
#   The generator scales its simulated revenue so every segment-quarter matches
#   these totals; the split between product lines follows the shares below.
# ---------------------------------------------------------------------------
QUARTERS = ["FY24 Q3", "FY24 Q4", "FY25 Q1", "FY25 Q2", "FY25 Q3", "FY25 Q4",
            "FY26 Q1", "FY26 Q2", "FY26 Q3", "FY26 Q4", "FY27 Q1"]
SEGMENT_REVENUE_BN = {
    PBP: [27.2, 28.5, 28.3, 29.4, 29.9, 33.1, 33.0, 34.1, 35.1, 37.8, 38.3],
    IC:  [22.1, 23.7, 24.1, 25.5, 26.8, 29.9, 30.9, 32.9, 34.7, 39.3, 40.9],
    MPC: [12.6, 12.4, 13.2, 14.7, 13.4, 13.5, 13.8, 14.3, 13.1, 12.9, 13.1],
}
# product-line share of its (recast) segment at four anchor points; linear in between
#   anchor quarter index: 0.5 = FY24 H2, 3.5 = FY25, 7.5 = FY26, 10 = FY27 Q1
SHARE_ANCHORS = [0.5, 3.5, 7.5, 10.0]
LINE_SHARE = {
    "M365C": [.680, .686, .693, .700], "WINC": [.055, .051, .047, .045], "M365X": [.057, .059, .061, .062],
    "LNKD":  [.148, .143, .137, .132], "D365": [.060, .061, .062, .061],
    "AZR":   [.640, .700, .769, .810], "SRV":  [.275, .229, .174, .140], "EPS": [.085, .071, .057, .050],
    "GAME":  [.420, .430, .400, .410], "ADS":  [.245, .248, .286, .310], "WOEM": [.220, .218, .222, .210],
    "DEV":   [.115, .104, .092, .070],
}
RESTATED_SEGMENT = {"M365C": PBP, "WINC": PBP, "M365X": PBP, "LNKD": PBP, "D365": PBP,
                    "AZR": IC, "SRV": IC, "EPS": IC, "GAME": MPC, "ADS": MPC, "WOEM": MPC, "DEV": MPC}
# operating-expense ratios fall over time (operating leverage in the published results):
# R&D + S&M + G&A were about 25% of revenue in FY24, 23% in FY25, 21% in FY26, 18% in FY27 Q1
OPEX_TREND_ANCHORS = ([3, 12, 24, 31], [1.20, 1.00, 0.93, 0.83])
# capital expenditures including finance leases, USD billions per quarter (FY26 Q3-Q4 and
# FY27 Q1 are estimates: Microsoft reported cash additions to property and equipment of
# $115.9B for FY26 and $39.4B for FY27 Q1, before finance leases)
CAPEX_BN = [14.0, 19.0, 20.0, 22.6, 21.4, 24.2, 34.9, 37.5, 37.5, 46.0, 45.2]
FINANCE_LEASE_SHARE = 0.35       # share of datacenter capex financed through leases (synthetic)
TARGET_HEADCOUNT = 228_000       # Microsoft reported about 228,000 employees at June 2024 and June 2025


def quarter_index():
    """Index 0-10 of the fiscal quarter of each month (Jan 2024 = FY24 Q3)."""
    return np.arange(T) // 3


def revenue_targets():
    """Target monthly-quarter revenue per product line: array (product lines x quarters), USD."""
    q = np.arange(len(QUARTERS))
    out = np.zeros((len(PL), len(QUARTERS)))
    for code, seg in RESTATED_SEGMENT.items():
        out[PL_IDX[code]] = np.interp(q, SHARE_ANCHORS, LINE_SHARE[code])
    for seg in (PBP, IC, MPC):
        rows = [PL_IDX[c] for c, s in RESTATED_SEGMENT.items() if s == seg]
        out[rows] = out[rows] / out[rows].sum(0) * np.array(SEGMENT_REVENUE_BN[seg]) * 1e9
    return out


def revenue_scale(econ_pl):
    """Factor per product line and month that brings simulated revenue to the targets."""
    qi = quarter_index()
    sim_q = np.zeros((len(PL), len(QUARTERS)))
    for k in range(len(QUARTERS)):
        sim_q[:, k] = econ_pl[:, qi == k].sum(1)
    factor_q = revenue_targets() / np.maximum(sim_q, 1.0)
    return factor_q[:, qi]


# ---------------------------------------------------------------------------
# Geography - countries and public cloud-region names (weights are synthetic)
# ---------------------------------------------------------------------------
COUNTRIES = [
    # code, name, area, region, currency, account weight, cloud regions serving it
    ("US", "United States", "North America", "Americas", "USD", 30, ["US East", "US East 2", "US Central", "US South Central", "US West", "US West 2", "US West 3", "US North Central"]),
    ("CA", "Canada", "North America", "Americas", "CAD", 4, ["Canada Central", "Canada East"]),
    ("MX", "Mexico", "Latin America", "Americas", "USD", 2, ["Mexico Central", "US South Central"]),
    ("CL", "Chile", "Latin America", "Americas", "USD", 1, ["US East 2"]),
    ("CO", "Colombia", "Latin America", "Americas", "USD", 1, ["US East 2"]),
    ("AR", "Argentina", "Latin America", "Americas", "USD", 1, ["US East 2"]),
    ("GB", "United Kingdom", "Western Europe", "EMEA", "GBP", 7, ["UK South", "UK West"]),
    ("IE", "Ireland", "Western Europe", "EMEA", "EUR", 1, ["North Europe"]),
    ("NL", "Netherlands", "Western Europe", "EMEA", "EUR", 2, ["West Europe"]),
    ("BE", "Belgium", "Western Europe", "EMEA", "EUR", 1, ["West Europe"]),
    ("DE", "Germany", "Western Europe", "EMEA", "EUR", 6, ["Germany West Central", "West Europe"]),
    ("FR", "France", "Western Europe", "EMEA", "EUR", 5, ["France Central"]),
    ("ES", "Spain", "Western Europe", "EMEA", "EUR", 3, ["Spain Central"]),
    ("PT", "Portugal", "Western Europe", "EMEA", "EUR", 1, ["Spain Central", "West Europe"]),
    ("IT", "Italy", "Western Europe", "EMEA", "EUR", 3, ["Italy North"]),
    ("AT", "Austria", "Western Europe", "EMEA", "EUR", 1, ["Germany West Central"]),
    ("CH", "Switzerland", "Western Europe", "EMEA", "CHF", 2, ["Switzerland North"]),
    ("SE", "Sweden", "Northern Europe", "EMEA", "EUR", 1.5, ["Sweden Central"]),
    ("NO", "Norway", "Northern Europe", "EMEA", "EUR", 1, ["Norway East"]),
    ("DK", "Denmark", "Northern Europe", "EMEA", "EUR", 1, ["North Europe"]),
    ("FI", "Finland", "Northern Europe", "EMEA", "EUR", 1, ["Sweden Central"]),
    ("PL", "Poland", "Central and Eastern Europe", "EMEA", "EUR", 1.5, ["Poland Central"]),
    ("CZ", "Czechia", "Central and Eastern Europe", "EMEA", "EUR", 1, ["Germany West Central"]),
    ("AE", "United Arab Emirates", "Middle East and Africa", "EMEA", "USD", 1, ["UAE North"]),
    ("SA", "Saudi Arabia", "Middle East and Africa", "EMEA", "USD", 1, ["UAE North"]),
    ("IL", "Israel", "Middle East and Africa", "EMEA", "USD", 1, ["West Europe"]),
    ("ZA", "South Africa", "Middle East and Africa", "EMEA", "USD", 1, ["South Africa North"]),
    ("JP", "Japan", "Japan", "APAC", "JPY", 5, ["Japan East", "Japan West"]),
    ("AU", "Australia", "ANZ", "APAC", "AUD", 3, ["Australia East", "Australia Southeast"]),
    ("NZ", "New Zealand", "ANZ", "APAC", "AUD", 1, ["Australia East"]),
    ("IN", "India", "India", "APAC", "INR", 4, ["Central India", "South India"]),
    ("SG", "Singapore", "Greater Asia", "APAC", "USD", 1.5, ["Southeast Asia"]),
    ("HK", "Hong Kong SAR", "Greater Asia", "APAC", "USD", 1, ["East Asia"]),
    ("KR", "Korea", "Greater Asia", "APAC", "USD", 2, ["Korea Central"]),
    ("TW", "Taiwan", "Greater Asia", "APAC", "USD", 1, ["East Asia"]),
    ("MY", "Malaysia", "Greater Asia", "APAC", "USD", 1, ["Southeast Asia"]),
    ("ID", "Indonesia", "Greater Asia", "APAC", "USD", 1, ["Southeast Asia"]),
    ("TH", "Thailand", "Greater Asia", "APAC", "USD", 1, ["Southeast Asia"]),
    ("PH", "Philippines", "Greater Asia", "APAC", "USD", 1, ["Southeast Asia"]),
]
CTRY = pd.DataFrame(COUNTRIES, columns=["code", "name", "area", "region", "currency", "weight", "clouds"])
CTRY_IDX = {c: i for i, c in enumerate(CTRY.code)}

CLOUD_REGIONS = {  # public region name -> (code, hosting country)
    "US East": ("EUS", "US"), "US East 2": ("EUS2", "US"), "US Central": ("CUS", "US"),
    "US South Central": ("SCUS", "US"), "US West": ("WUS", "US"), "US West 2": ("WUS2", "US"),
    "US West 3": ("WUS3", "US"), "US North Central": ("NCUS", "US"), "Canada Central": ("CNC", "CA"),
    "Canada East": ("CNE", "CA"), "Mexico Central": ("MXC", "MX"), "UK South": ("UKS", "GB"),
    "UK West": ("UKW", "GB"), "North Europe": ("NEU", "IE"), "West Europe": ("WEU", "NL"),
    "France Central": ("FRC", "FR"), "Germany West Central": ("GWC", "DE"), "Switzerland North": ("SZN", "CH"),
    "Sweden Central": ("SEC", "SE"), "Norway East": ("NOE", "NO"), "Poland Central": ("PLC", "PL"),
    "Italy North": ("ITN", "IT"), "Spain Central": ("SPC", "ES"), "UAE North": ("UAN", "AE"),
    "South Africa North": ("SAN", "ZA"), "Japan East": ("JPE", "JP"), "Japan West": ("JPW", "JP"),
    "Australia East": ("AUE", "AU"), "Australia Southeast": ("AUSE", "AU"), "Central India": ("CIN", "IN"),
    "South India": ("SIN", "IN"), "Southeast Asia": ("SEA", "SG"), "East Asia": ("EAS", "HK"),
    "Korea Central": ("KRC", "KR"),
}
CLOUD_NAMES = list(CLOUD_REGIONS)
CLOUD_IDX = {n: i for i, n in enumerate(CLOUD_NAMES)}
CURRENCIES = ["EUR", "GBP", "JPY", "CAD", "AUD", "INR", "CHF"]   # plus USD = 8

LEGAL_SUFFIX = {"US": ["Inc.", "LLC", "Corp."], "CA": ["Inc.", "Ltd."], "GB": ["Ltd", "PLC"], "IE": ["Ltd", "DAC"],
                "DE": ["GmbH", "AG"], "AT": ["GmbH"], "CH": ["AG", "SA"], "FR": ["SA", "SAS"], "BE": ["NV", "SA"],
                "NL": ["B.V.", "N.V."], "ES": ["S.L.", "S.A."], "PT": ["Lda", "S.A."], "IT": ["S.p.A.", "S.r.l."],
                "SE": ["AB"], "NO": ["AS"], "DK": ["A/S"], "FI": ["Oy"], "PL": ["Sp. z o.o."], "CZ": ["s.r.o."],
                "JP": ["K.K.", "Co., Ltd."], "AU": ["Pty Ltd"], "NZ": ["Ltd"], "IN": ["Pvt Ltd", "Ltd"],
                "MX": ["S.A. de C.V."], "CL": ["SpA"], "CO": ["S.A.S."], "AR": ["S.A."], "ZA": ["(Pty) Ltd"]}
NAME_A = ["North", "Blue", "Silver", "Summit", "Harbor", "Pioneer", "Atlas", "Vertex", "Crescent", "Evergreen",
          "Granite", "Lumen", "Nova", "Orion", "Pine", "Quantum", "River", "Sterling", "Titan", "Union", "Bright",
          "Cedar", "Delta", "Falcon", "Golden", "Horizon", "Iron", "Juniper", "Keystone", "Liberty", "Maple",
          "Meridian", "Oak", "Pacific", "Red", "Sky", "Stone", "Sun", "Trinity", "West", "Alpine", "Coastal",
          "Metro", "Prime", "Royal", "Swift", "Vector", "Zenith", "Aurora", "Beacon", "Cobalt", "Echo", "Frontier",
          "Halo", "Indigo", "Jade", "Kestrel", "Lighthouse", "Magnolia", "Nimbus"]
NAME_B = ["Ridge", "Bay", "Point", "Peak", "Field", "Gate", "Bridge", "Lake", "Wood", "Hill", "Valley", "Crest",
          "Line", "Path", "Port", "Shore", "Spring", "Stream", "Way", "Works", "Light", "Wave", "Rock", "Haven",
          "Mark", "Star", "Arc", "Grove", "Mill", "Tower"]
NAME_C = ["Analytics", "Bank", "Health", "Logistics", "Foods", "Energy", "Retail", "Systems", "Insurance",
          "Motors", "Pharma", "Media", "Telecom", "Capital", "Industries", "Labs", "Solutions", "Partners",
          "Manufacturing", "Hotels", "Airlines", "Construction", "Software", "Holdings", "Group", "Networks",
          "Biotech", "Utilities", "Apparel", "Consulting"]
FIRST_NAMES = ["Ana", "Ben", "Carla", "David", "Elena", "Farid", "Grace", "Hugo", "Ines", "James", "Kenji", "Laura",
               "Marco", "Nadia", "Oliver", "Priya", "Quentin", "Rosa", "Samuel", "Tara", "Uma", "Victor", "Wen",
               "Ximena", "Yusuf", "Zoe", "Lucas", "Sofia", "Mateo", "Hannah"]
LAST_NAMES = ["Silva", "Novak", "Okafor", "Schmidt", "Tanaka", "Moreau", "Rossi", "Kowalski", "Haddad", "Larsen",
              "Patel", "Kim", "Nguyen", "Garcia", "Brown", "Murphy", "Fischer", "Costa", "Ivanova", "Walker",
              "Sato", "Dubois", "Jansen", "Lindqvist", "Mendes", "Chen", "Singh", "Reyes", "Evans", "Adeyemi"]

# ---------------------------------------------------------------------------
# Formatting helpers - each "system" exports numbers and dates differently
# ---------------------------------------------------------------------------
def us_number(x, decimals=2):                      # 1,234,567.89
    return [f"{v:,.{decimals}f}" for v in x]


def sap_trailing_minus(x):                         # 1,234.56-   (SAP list output)
    return [f"{abs(v):,.2f}" + ("-" if v < 0 else "") for v in x]


def decimal_comma(x):                              # 1.234,56    (German locale ERP export)
    return [f"{v:,.2f}".replace(",", "#").replace(".", ",").replace("#", ".") for v in x]


def d_us(dates):   return pd.DatetimeIndex(dates).strftime("%m/%d/%Y")    # CRM
def d_erp(dates):  return pd.DatetimeIndex(dates).strftime("%d.%m.%Y")    # ERP / GL
def d_iso(dates):  return pd.DatetimeIndex(dates).strftime("%Y-%m-%d")    # HR, calendar


def fy_label(y):
    return f"FY{str(int(y))[-2:]}"


def save(df: pd.DataFrame, name: str, sep=",", header_lines: list[str] | None = None):
    path = OUT_DIR / name
    with open(path, "w", encoding="utf-8", newline="") as f:
        for line in header_lines or []:
            f.write(line + "\n")
        df.to_csv(f, index=False, sep=sep, lineterminator="\n")
    print(f"  {name:<26} {len(df):>9,} rows  {path.stat().st_size / 1e6:6.1f} MB")
    return len(df)


# ---------------------------------------------------------------------------
# 1. Fiscal calendar
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 2. Product hierarchy (with the July 2025 segment move as two validity rows)
# ---------------------------------------------------------------------------
def build_product_hierarchy():
    rows = []
    for s in SKU.itertuples():
        p = PL.iloc[s.pl_idx]
        if s.pl == "WINC":
            rows.append((s.material, s.desc, p["name"], "PC-" + p.code, MPC, p.rev_type, s.unit, "20000101", "20250630"))
            rows.append((s.material, s.desc, p["name"], "PC-" + p.code, PBP, p.rev_type, s.unit, "20250701", "99991231"))
        else:
            rows.append((s.material, s.desc, p["name"], "PC-" + p.code, p.segment, p.rev_type, s.unit, "20000101",
                         "99991231"))
    return pd.DataFrame(rows, columns=["Material", "Material Description", "Product Line", "Profit Center", "Segment",
                                       "Revenue Type", "Base Unit", "Valid From", "Valid To"])


# ---------------------------------------------------------------------------
# 3. Regions
# ---------------------------------------------------------------------------
def build_regions():
    return pd.DataFrame({
        "Country Key": CTRY.code, "Country Name": CTRY.name, "Sales Area": CTRY.area, "Sales Region": CTRY.region,
        "Billing Currency": CTRY.currency, "Company Code": CTRY.code + "10",
        "Primary Cloud Region": [c[0] for c in CTRY.clouds],
    })


# ---------------------------------------------------------------------------
# 4. FX - synthetic random walks (foreign currency per 1 USD)
# ---------------------------------------------------------------------------
FX_START = {"EUR": 0.92, "GBP": 0.79, "JPY": 146.0, "CAD": 1.35, "AUD": 1.51, "INR": 83.0, "CHF": 0.87}


def build_fx():
    avg = {"USD": np.ones(T)}
    eom = {"USD": np.ones(T)}
    for cur in CURRENCIES:
        steps = rng.normal(0.0005, 0.016, T)
        avg[cur] = FX_START[cur] * np.exp(np.cumsum(steps))
        eom[cur] = avg[cur] * rng.normal(1, 0.006, T)
    rows = []
    for cur in CURRENCIES:
        for t in range(T):
            vf = MONTH_START[t].strftime("%Y%m%d")
            rows.append(("M", "USD", cur, vf, round(avg[cur][t], 5)))
            rows.append(("EOM", "USD", cur, MONTH_END[t].strftime("%Y%m%d"), round(eom[cur][t], 5)))
    df = pd.DataFrame(rows, columns=["Exchange Rate Type", "From Currency", "To Currency", "Valid From",
                                     "Exchange Rate"])
    return df, avg


# ---------------------------------------------------------------------------
# 5. CRM accounts
# ---------------------------------------------------------------------------
ACCOUNT_TYPES = {  # type: (share, wallet median USD/month, sigma, prospect share, monthly churn hazard)
    "Enterprise": (0.12, 55_000, 1.0, 0.35, 0.004),
    "SMB": (0.52, 1_400, 0.9, 0.72, 0.018),
    "Public Sector": (0.09, 30_000, 1.0, 0.35, 0.003),
    "Advertiser": (0.24, 12_000, 1.2, 0.72, 0.025),
    "OEM Partner": (0.008, 160_000, 0.7, 0.0, 0.002),
    "Retail and Distribution": (0.022, 70_000, 0.8, 0.0, 0.006),
}
INDUSTRIES = ["Financial Services", "Healthcare", "Manufacturing", "Retail", "Education", "Media and Communications",
              "Energy and Utilities", "Professional Services", "Technology", "Transportation and Logistics",
              "Hospitality", "Government"]


def company_names(n, countries):
    idx = rng.choice(len(NAME_A) * len(NAME_B) * len(NAME_C), size=n, replace=False)
    a, rest = np.divmod(idx, len(NAME_B) * len(NAME_C))
    b, c = np.divmod(rest, len(NAME_C))
    names = []
    for ai, bi, ci, cc in zip(a, b, c, countries):
        suffix = rng.choice(LEGAL_SUFFIX.get(cc, ["Ltd"]))
        names.append(f"{NAME_A[ai]}{NAME_B[bi].lower()} {NAME_C[ci]} {suffix}")
    return names


def build_accounts():
    types = list(ACCOUNT_TYPES)
    shares = np.array([ACCOUNT_TYPES[t][0] for t in types])
    acc_type = rng.choice(types, size=N_ACCOUNTS, p=shares / shares.sum())
    w = CTRY.weight.values / CTRY.weight.sum()
    country = rng.choice(CTRY.code.values, size=N_ACCOUNTS, p=w)
    names = company_names(N_ACCOUNTS, country)
    prospect = np.array([rng.random() < ACCOUNT_TYPES[t][3] for t in acc_type])
    wallet = np.array([rng.lognormal(np.log(ACCOUNT_TYPES[t][1]), ACCOUNT_TYPES[t][2]) for t in acc_type])
    emp_scale = {"Enterprise": 6000, "SMB": 60, "Public Sector": 3000, "Advertiser": 150, "OEM Partner": 20000,
                 "Retail and Distribution": 4000}
    employees = np.array([max(3, int(rng.lognormal(np.log(emp_scale[t]), 0.8))) for t in acc_type])
    industry = []
    for t in acc_type:
        if t == "Public Sector":
            industry.append(rng.choice(["Government", "Education", "Healthcare"]))
        elif t in ("OEM Partner",):
            industry.append("Technology")
        elif t == "Retail and Distribution":
            industry.append("Retail")
        else:
            industry.append(rng.choice(INDUSTRIES[:-1]))
    acc = pd.DataFrame({"acc_id": np.arange(N_ACCOUNTS), "type": acc_type, "country": country, "name": names,
                        "prospect": prospect, "wallet": wallet, "employees": employees, "industry": industry})
    # one direct online store account per country (consumer channel)
    stores = pd.DataFrame({
        "acc_id": np.arange(N_ACCOUNTS, N_ACCOUNTS + len(CTRY)), "type": "Direct Consumer Online",
        "country": CTRY.code.values, "name": [f"Online Store - {n}" for n in CTRY.name], "prospect": False,
        "wallet": 1_400_000 * CTRY.weight.values / CTRY.weight.max() * rng.lognormal(0, 0.2, len(CTRY)),
        "employees": 0, "industry": "Retail"})
    acc = pd.concat([acc, stores], ignore_index=True)
    acc["crm_number"] = [f"ACC-{1_000_000 + i * 7:07d}" for i in acc.acc_id]
    acc["erp_id"] = [f"00{20_000_000 + i * 13:08d}" for i in acc.acc_id]
    created_offset = rng.integers(30, 3650, len(acc))
    acc["created"] = pd.Timestamp("2024-01-01") - pd.to_timedelta(created_offset, unit="D")
    reps = [f"{f} {l}" for f in FIRST_NAMES for l in LAST_NAMES]
    rep_pool = {c: rng.choice(reps, size=8 if c == "US" else 3, replace=False) for c in CTRY.code}
    acc["owner"] = [rng.choice(rep_pool[c]) for c in acc.country]
    return acc


# ---------------------------------------------------------------------------
# 6. Contracts -> monthly revenue (the "truth" that every other table follows)
# ---------------------------------------------------------------------------
PL_CHOICE = {  # type: {product line: probability the account buys it}
    "Enterprise": {"M365C": .9, "AZR": .75, "D365": .35, "LNKD": .3, "SRV": .45, "EPS": .4, "WINC": .5},
    "SMB": {"M365C": .8, "AZR": .2, "D365": .1, "LNKD": .05, "WINC": .1},
    "Public Sector": {"M365C": .9, "AZR": .6, "D365": .2, "SRV": .5, "EPS": .35, "WINC": .4},
    "Advertiser": {"ADS": 1.0, "LNKD": .2},
    "OEM Partner": {"WOEM": 1.0},
    "Retail and Distribution": {"DEV": .8, "GAME": .7, "M365X": .5},
    "Direct Consumer Online": {"M365X": 1.0, "GAME": 1.0, "DEV": 1.0},
}
PL_WEIGHT = {"M365C": 1.0, "AZR": 1.3, "D365": .5, "LNKD": .7, "SRV": .5, "EPS": .4, "WINC": .25, "ADS": 1.0,
             "WOEM": 1.0, "DEV": 1.0, "GAME": 1.0, "M365X": .8}


def build_contracts(acc):
    rows = []  # acc_id, sku_idx, start, end, base, gc, cloud
    for a in acc.itertuples():
        if a.prospect:
            continue
        probs = PL_CHOICE[a.type]
        chosen = [p for p, pr in probs.items() if rng.random() < pr] or [max(probs, key=probs.get)]
        wsum = sum(PL_WEIGHT[p] for p in chosen)
        hazard = ACCOUNT_TYPES.get(a.type, (0, 0, 0, 0, 0.0))[4]
        clouds = CTRY.clouds.iloc[CTRY_IDX[a.country]]
        for p in chosen:
            g = PL.growth.iloc[PL_IDX[p]]
            skus = SKU.index[SKU.pl == p].values
            budget = a.wallet * PL_WEIGHT[p] / wsum
            if a.type == "Direct Consumer Online":
                pick = skus                                     # stores sell every consumer SKU
            elif p == "AZR":
                pick = rng.choice(skus, size=1 if a.type == "SMB" else rng.integers(1, 3), replace=False)
            else:
                pick = [rng.choice(skus)]
            for s in pick:
                desc = SKU.desc.iloc[s]
                p_exist = float(np.clip(0.88 - 1.2 * g, 0.40, 0.95))
                if a.type == "Direct Consumer Online" or a.type == "OEM Partner":
                    p_exist = 1.0
                if desc == "Microsoft 365 Copilot" or desc == "Azure OpenAI Service":
                    p_exist = 0.1
                start = -1 if rng.random() < p_exist else int(rng.integers(0, T))
                if desc in ("Microsoft 365 Copilot", "Azure OpenAI Service") and start >= 0:
                    start = int(rng.integers(min(start, T - 1), T))     # AI products skew late
                h = hazard * (1 + max(0.0, -g) * 8)
                life = rng.geometric(h) if h > 0 else 10_000
                end = max(start, 0) + life
                gc = g * 0.6 + rng.normal(0, 0.08)
                if desc in ("Azure OpenAI Service", "Microsoft 365 Copilot"):
                    gc += 0.45
                base = budget / len(pick) * rng.lognormal(0, 0.3)
                cloud = CLOUD_IDX[rng.choice(clouds)] if p == "AZR" else -1
                rows.append((a.acc_id, s, start, end, base, gc, cloud))
    return pd.DataFrame(rows, columns=["acc_id", "sku", "start", "end", "base", "gc", "cloud"])


QUARTERLY_TYPES = {"Enterprise", "Public Sector"}
QUARTERLY_PLS = {"M365C", "WINC", "D365", "EPS", "LNKD"}


def contract_revenue(con, scale=None):
    """Return monthly economic revenue per contract and the billing events.
    scale: optional (product lines x months) factor from revenue_scale()."""
    bill = []                                   # (contract row, month, usd)
    econ_pl = np.zeros((len(PL), T))
    econ_cloud = np.zeros((len(CLOUD_NAMES), T))
    econ_pl_ctry = np.zeros((len(PL), len(CTRY), T))
    acc_ctry = None
    for i, c in enumerate(con.itertuples()):
        pl_i = SKU.pl_idx.iloc[c.sku]
        p = PL.iloc[pl_i]
        m0 = max(c.start, 0)
        m1 = min(c.end, T - 1)
        if m1 < m0:
            continue
        m = np.arange(m0, m1 + 1)
        age = (m - m0) / 12
        noise_sd = {"Consumption": .07, "Advertising": .12, "Hardware": .12, "Content and Hardware": .10}.get(p.rev_type, .03)
        amt = c.base * np.exp(c.gc * age) * SEASON[p.season][CAL_MONTH[m] - 1] * rng.lognormal(0, noise_sd, len(m))
        if c.start >= 0:                         # ramp-up in the first months of a new contract
            amt *= np.minimum(1, 0.35 + 0.22 * (m - m0))
        if scale is not None:                    # calibrate to Microsoft's published revenue
            amt = amt * scale[pl_i, m]
        econ_pl[pl_i, m] += amt
        econ_pl_ctry[pl_i, c.ctry_i, m] += amt
        if c.cloud >= 0:
            econ_cloud[c.cloud, m] += amt
        if p.billing == "annual":                # invoiced once a year (EA anniversary or June)
            anchor = c.start if c.start >= 0 else 5
            mask = ((m - anchor) % 12 == 0)
            for mm in m[mask]:
                bill.append((i, mm, float(amt[m == mm][0]) * 12))
        elif c.acc_type in QUARTERLY_TYPES and p.code in QUARTERLY_PLS:
            # enterprise agreements: billed in arrears at calendar quarter end (or when the contract ends)
            bill_months = m[(CAL_MONTH[m] % 3 == 0) | (m == m1)]
            prev = m0 - 1
            for mm in bill_months:
                sel = (m > prev) & (m <= mm)
                bill.append((i, int(mm), float(amt[sel].sum())))
                prev = mm
        else:
            bill.extend(zip([i] * len(m), m.tolist(), amt.tolist()))
    b = pd.DataFrame(bill, columns=["con", "month", "usd"])
    return b, econ_pl, econ_cloud, econ_pl_ctry


# ---------------------------------------------------------------------------
# 7. ERP billing lines
# ---------------------------------------------------------------------------
def erp_name(name):
    r = rng.random()
    if r < 0.35:
        return name.upper().replace(",", "").replace(".", "")
    if r < 0.55:
        return (name.replace(" Ltd", " Limited").replace(" Inc.", " Incorporated").replace(" Corp.", " Corporation")
                .upper())
    if r < 0.70:
        return name + "  "
    return name


def build_billing(acc, con, b, fx_avg):
    b = b.merge(con[["acc_id", "sku", "cloud"]], left_on="con", right_index=True)
    b = b.merge(acc[["acc_id", "erp_id", "country", "name"]], on="acc_id")
    b["currency"] = b.country.map(dict(zip(CTRY.code, CTRY.currency)))
    rate = np.array([fx_avg[c][m] for c, m in zip(b.currency, b.month)])
    b["local"] = b.usd * rate
    # credit memos: ~0.8% of lines are partly credited 1-3 months later
    cm = b.sample(frac=0.008, random_state=SEED).copy()
    cm["orig_month"] = cm.month
    cm["month"] = np.minimum(cm.month + rng.integers(1, 4, len(cm)), T - 1)
    cm["local"] = -cm.local * rng.uniform(0.1, 1.0, len(cm))
    cm["usd"] = -cm.usd
    cm["type"] = "G2"
    b["type"] = "F2"
    b = pd.concat([b, cm]).sort_values(["month", "erp_id", "type"]).reset_index(drop=True)
    # one billing document per sold-to x month x type
    doc_key = b.month.astype(str) + "|" + b.erp_id + "|" + b.type
    doc_codes, _ = pd.factorize(doc_key)
    b["doc"] = [f"{90_000_000 + d}" for d in doc_codes]
    b["item"] = (b.groupby("doc").cumcount() + 1) * 10
    inv = b[b.type == "F2"].drop_duplicates(["erp_id", "sku", "month"])
    orig_doc = dict(zip(zip(inv.erp_id, inv.sku, inv.month), inv.doc))
    is_cm = (b.type == "G2").values
    b["ref"] = ""
    b.loc[is_cm, "ref"] = [orig_doc.get((e, s, int(m)), "") for e, s, m in
                           zip(b.erp_id[is_cm], b.sku[is_cm], b.orig_month[is_cm])]
    # ERP names differ from CRM names (one fixed variant per customer)
    variants = {e: erp_name(n) for e, n in zip(acc.erp_id, acc.name)}
    price = SKU.price.values[b.sku]
    qty = np.maximum(1, np.round(np.abs(b.usd.values) / price)).astype(int)
    billing_day = [MONTH_END[m] if t == "F2" else MONTH_START[m] + pd.Timedelta(days=int(d))
                   for m, t, d in zip(b.month, b.type, rng.integers(3, 25, len(b)))]
    out = pd.DataFrame({
        "Billing Type": b.type.values,
        "Billing Document": b.doc.values,
        "Item": [f"{i:06d}" for i in b["item"]],
        "Billing Date": d_erp(billing_day),
        "Sold-To Party": b.erp_id.values,
        "Sold-To Name": [variants[e] for e in b.erp_id],
        "Country": b.country.values,
        "Material": SKU.material.values[b.sku],
        "Plant": [CLOUD_REGIONS[CLOUD_NAMES[c]][0] if c >= 0 else "" for c in b.cloud],
        "Billed Quantity": qty,
        "Sales Unit": SKU.unit.values[b.sku],
        "Net Value": decimal_comma(b.local.values),
        "Document Currency": b.currency.values,
        "Reference Document": b.ref.values,
    })
    return out, b


# ---------------------------------------------------------------------------
# 8. CRM opportunities
# ---------------------------------------------------------------------------
WIN_RATE = {"Enterprise": .38, "SMB": .27, "Public Sector": .32, "Advertiser": .45}
REGION_WIN = {"Americas": 1.0, "EMEA": .95, "APAC": .82}
PL_WIN = {"AZR": 1.1, "D365": .85, "LNKD": .9}
TOPIC = {"M365C": ["Modern Workplace rollout", "Copilot pilot", "E5 security upgrade", "Office 365 renewal"],
         "AZR": ["Cloud migration", "AI platform build", "Data platform modernisation", "Datacenter exit"],
         "D365": ["CRM replacement", "ERP modernisation", "Customer service transformation"],
         "LNKD": ["Talent hiring programme", "B2B marketing campaign", "Sales Navigator rollout"],
         "SRV": ["Server licence true-up", "SQL Server consolidation"], "EPS": ["Unified Support renewal", "Consulting engagement"],
         "WINC": ["Windows 11 deployment", "Cloud PC pilot"], "ADS": ["Search advertising campaign", "Display campaign"]}
STAGES = [("1-Qualify", 10), ("2-Develop", 30), ("3-Propose", 60), ("4-Close", 80)]
LOSS_REASONS = ["Lost to competitor", "No budget", "Cancelled by customer", "No decision", "Price"]


PL_SCALE = {}                    # filled in main(): average revenue calibration factor per product line


def build_opportunities(acc, con, fx_avg):
    a = acc.set_index("acc_id")
    region = dict(zip(CTRY.code, CTRY.region))
    cur = dict(zip(CTRY.code, CTRY.currency))
    rows = []

    def add(acc_id, pl, status, created, close_est, close_act, value, stage, prob, reason, otype="New Business"):
        c = a.loc[acc_id]
        value = value * PL_SCALE.get(pl, 1.0)    # same calibration factor as the line's revenue
        m = int(np.clip((close_est.year - 2024) * 12 + close_est.month - 1, 0, T - 1))
        local = value * fx_avg[cur[c.country]][m]
        rows.append((acc_id, c["name"], c.crm_number, pl, status, created, close_est, close_act, local,
                     cur[c.country], stage, prob, reason, c.owner, otype))

    new = con[(con.start >= 0)].merge(a[["type"]], left_on="acc_id", right_index=True)
    new = new[new.type.isin(WIN_RATE)]
    won_counts = {}
    for c in new.itertuples():
        pl = SKU.pl.iloc[c.sku]
        start = MONTH_START[c.start]
        close = start - pd.Timedelta(days=int(rng.integers(0, 45)))
        created = close - pd.Timedelta(days=int(rng.integers(20, 200)))
        acv = c.base * 12 * rng.lognormal(0, 0.15)
        add(c.acc_id, pl, "Won", created, close + pd.Timedelta(days=int(rng.integers(-20, 20))), close, acv,
            "4-Close", 100, "")
        key = (c.type, region[a.loc[c.acc_id].country], pl)
        won_counts[key] = won_counts.get(key, 0) + 1
    # lost deals, in proportion to the win rate of each type x region x product line
    pool = {k: g.acc_id.values for k, g in acc[acc.type.isin(WIN_RATE)].assign(
        reg=lambda d: d.country.map(region)).groupby(["type", "reg"])}
    med = new.base.median()
    for (typ, reg, pl), n_won in won_counts.items():
        w = min(0.9, WIN_RATE[typ] * REGION_WIN[reg] * PL_WIN.get(pl, 1.0) * rng.normal(1, 0.05))
        n_lost = rng.poisson(n_won * (1 - w) / w)
        accs = rng.choice(pool[(typ, reg)], size=n_lost)
        for acc_id in accs:
            close = pd.Timestamp("2024-01-01") + pd.Timedelta(days=int(rng.integers(0, 1004)))
            created = close - pd.Timedelta(days=int(rng.integers(20, 240)))
            acv = a.loc[acc_id].wallet * 12 * rng.uniform(0.05, 0.4) * 1.2
            stage, _ = STAGES[rng.integers(0, 4)]
            add(acc_id, pl, "Lost", created, close, close, acv, stage, 0, rng.choice(LOSS_REASONS))
    # renewals of existing agreements (Enterprise / Public Sector): won each June, lost when the customer churns
    base = con[(con.start < 0)].merge(a[["type"]], left_on="acc_id", right_index=True)
    base = base[base.type.isin(["Enterprise", "Public Sector"])]
    for c in base.itertuples():
        pl = SKU.pl.iloc[c.sku]
        for m in (5, 17, 29):                                      # June 2024 / 2025 / 2026
            if c.end <= m:
                close = MONTH_START[min(c.end, T - 1)]
                add(c.acc_id, pl, "Lost", close - pd.Timedelta(days=90), close, close, c.base * 12, "3-Propose", 0,
                    "Customer churned", "Renewal")
                break
            close = MONTH_END[m] - pd.Timedelta(days=int(rng.integers(0, 20)))
            add(c.acc_id, pl, "Won", close - pd.Timedelta(days=int(rng.integers(60, 150))), close, close,
                c.base * 12 * np.exp(c.gc * (m + 1) / 12), "4-Close", 100, "", "Renewal")
    # open pipeline (closing Oct 2026 - Mar 2027)
    recent = new[new.start >= T - 6]
    n_open = int(len(recent) * 1.08 / 0.32)
    sample = recent.sample(n=n_open, replace=True, random_state=SEED)
    for c in sample.itertuples():
        pl = SKU.pl.iloc[c.sku]
        acc_id = rng.choice(pool[(c.type, region[a.loc[c.acc_id].country])])
        close = pd.Timestamp("2026-10-01") + pd.Timedelta(days=int(rng.integers(0, 182)))
        created = pd.Timestamp("2026-03-01") + pd.Timedelta(days=int(rng.integers(0, 213)))
        stage, prob = STAGES[rng.choice(4, p=[.35, .3, .2, .15])]
        add(acc_id, pl, "Open", created, close, pd.NaT, c.base * 12 * rng.lognormal(0.05, 0.3), stage, prob, "")
    o = pd.DataFrame(rows, columns=["acc_id", "name", "crm", "pl", "status", "created", "est_close", "act_close",
                                    "value", "cur", "stage", "prob", "reason", "owner", "otype"])
    o["erp_id"] = o.acc_id.map(a["erp_id"])
    o["ctype"] = o.acc_id.map(a["type"])
    o["country_name"] = o.acc_id.map(a["country"]).map(dict(zip(CTRY.code, CTRY.name)))
    o = o.sort_values("created").reset_index(drop=True)
    plname = dict(zip(PL.code, PL.name))
    topic = [f"{a.loc[i]['name'].split(' ')[0]} - {rng.choice(TOPIC.get(p, ['Licensing expansion']))}"
             for i, p in zip(o.acc_id, o.pl)]
    out = pd.DataFrame({
        "Opportunity ID": [f"OPP-{3_000_000 + i}" for i in range(len(o))],
        "Topic": topic,
        "Potential Customer": o.name.values,
        "Customer ID": o.erp_id.values,                 # = Sold-To Party in ERP billing
        "Customer Type": o.ctype.values,
        "Country/Region": o.country_name.values,        # full country name, as CRM stores it
        "Product Line": o.pl.map(plname).values,
        "Opportunity Type": o.otype.values,
        "Status": o.status.values,
        "Status Reason": np.where(o.status == "Won", "Won", np.where(o.status == "Open", "In Progress", o.reason)),
        "Sales Stage": o.stage.values,
        "Probability (%)": o.prob.values,
        "Est. Revenue": us_number(o.value.values),
        "Currency": o.cur.values,
        "Created On": d_us(o.created),
        "Est. Close Date": d_us(o.est_close),
        "Actual Close Date": [d.strftime("%m/%d/%Y") if pd.notna(d) else "" for d in o.act_close],
        "Owner": o.owner.values,
    })
    return out



# ---------------------------------------------------------------------------
# 9. Capex projects and data-centre capacity
# ---------------------------------------------------------------------------
REV_PER_MW_MONTH = 1_150_000     # synthetic: Azure revenue one MW of capacity supports per month
COST_PER_MW = 40_000_000         # synthetic: build + server/GPU fleet cost per MW (AI-era datacenters)


def scurve(n):
    x = np.linspace(0, 1, n + 2)[1:-1]
    w = np.sin(np.pi * x) + 0.15
    return w / w.sum()


def build_capex(econ_cloud):
    demand = econ_cloud / REV_PER_MW_MONTH                         # MW needed
    growth = (demand[:, -6:].sum(1) + 1e-9) / (demand[:, -18:-12].sum(1) + 1e-9)
    future = np.hstack([demand, demand[:, -1:] * growth[:, None] ** (np.arange(1, 25) / 12)])
    build_factor = rng.uniform(0.85, 1.20, len(CLOUD_NAMES))      # some regions over-built, some tight
    target_util = 0.90                                            # capacity-constrained, as Microsoft reported
    installed = np.zeros_like(demand)
    projects = []
    pid = 0
    for r, name in enumerate(CLOUD_NAMES):
        code, host = CLOUD_REGIONS[name]
        cap = future[r, 0] * build_factor[r] / target_util
        pipeline = []                                              # (complete month, MW)
        # in-flight projects started before the window
        for k in range(rng.integers(1, 4)):
            mw = max(2.0, cap * rng.uniform(0.05, 0.15))
            dur = int(rng.integers(10, 16))
            start = -int(rng.integers(2, dur - 1))
            pipeline.append((start + dur, mw))
            projects.append((pid, r, "Datacenter Build", start, dur, mw)); pid += 1
            projects.append((pid, r, "Server and GPU Fleet", start + dur - 4, 6, mw)); pid += 1
        for t in range(T):
            cap_t = cap + sum(mw for cm, mw in pipeline if cm <= t)
            installed[r, t] = cap_t
            planned = cap + sum(mw for cm, mw in pipeline)
            need = future[r, min(t + 14, future.shape[1] - 1)] * build_factor[r] / target_util
            if planned < need and t < T - 2:
                gap = need - planned
                while gap > 0.5:
                    mw = min(gap, max(3.0, rng.uniform(4, 18)))
                    dur = int(rng.integers(9, 16))
                    pipeline.append((t + dur, mw))
                    projects.append((pid, r, "Datacenter Build", t, dur, mw)); pid += 1
                    projects.append((pid, r, "Server and GPU Fleet", t + dur - 4, 6, mw)); pid += 1
                    gap -= mw
            if rng.random() < 0.12:
                projects.append((pid, r, "Network Backbone", t, int(rng.integers(3, 8)), 0.0)); pid += 1
    # (campus, office and devices capex is left out: it is a small share of Microsoft's capex,
    #  so all capex in this dataset is datacenter capex)
    used = np.minimum(demand, installed * 0.97)
    return projects, installed, used, demand


def capex_tables(projects, installed, used):
    rows = []
    complete_capex = np.zeros((len(CLOUD_NAMES), T))     # capex placed in service per month (for depreciation)
    office_country = ["US", "IE", "IN", "GB", "DE", "JP", "IL", "CA"]
    for pid, r, ptype, start, dur, mw in projects:
        if r >= 0:
            name = CLOUD_NAMES[r]
            code, host = CLOUD_REGIONS[name]
        else:
            name, code = "", ""
            host = office_country[pid % len(office_country)] if r == -1 else ["US", "IE", "JP"][pid % 3]
        share = {"Datacenter Build": 0.4, "Server and GPU Fleet": 0.6}.get(ptype)
        budget = mw * COST_PER_MW * share * rng.uniform(0.85, 1.2) if share else {
            "Network Backbone": rng.uniform(100e6, 600e6), "Campus and Offices": rng.uniform(150e6, 900e6),
            "Devices Tooling": rng.uniform(20e6, 80e6)}[ptype]
        delay = int(rng.choice([0, 0, 0, 1, 2, 3])) if ptype == "Datacenter Build" else 0
        overrun = rng.normal(1.06, 0.08)
        plan_w = scurve(dur)
        act_w = scurve(dur + delay)
        finish = start + dur + delay
        seg = "Intelligent Cloud" if r >= 0 else ("More Personal Computing" if r == -2 else "Corporate")
        wbs_prefix = {"Datacenter Build": "DC", "Server and GPU Fleet": "FL", "Network Backbone": "NW",
                      "Campus and Offices": "CO", "Devices Tooling": "DT"}[ptype]
        wbs = f"I-{wbs_prefix}-{code or host}-{pid:04d}"
        desc = {"Datacenter Build": f"{name} datacenter build phase {pid % 7 + 1}",
                "Server and GPU Fleet": f"{name} server and GPU fleet deployment",
                "Network Backbone": f"{name} network backbone upgrade",
                "Campus and Offices": f"{host} campus and office fit-out",
                "Devices Tooling": f"{host} devices manufacturing tooling"}[ptype]
        if r >= 0 and finish - 1 < T and ptype != "Network Backbone":
            complete_capex[r, max(finish - 1, 0)] += budget * overrun
        elif r >= 0 and ptype == "Network Backbone" and finish - 1 < T:
            complete_capex[r, max(finish - 1, 0)] += budget * overrun
        cum = 0.0
        for k in range(dur + delay):
            t = start + k
            plan = budget * plan_w[k] if k < dur else 0.0
            act = budget * overrun * act_w[k] * rng.lognormal(0, 0.05)
            cum += act
            if t < 0 or t >= T:
                continue
            status = "TECO" if t == finish - 1 else "REL"
            rows.append((wbs, desc, ptype, seg, name, code, host, fy_label(FISCAL_YEAR[t]), FISCAL_PERIOD[t],
                         str(MONTHS[t]), round(plan, 2), round(act, 2), round(cum, 2), round(mw, 1),
                         (MONTHS[0] + start).start_time.strftime("%Y-%m-%d"),
                         MONTH_END[min(start + dur - 1, T - 1)].strftime("%Y-%m-%d") if start + dur - 1 < T else "",
                         status))
    cap = pd.DataFrame(rows, columns=["WBS Element", "Description", "Project Type", "Segment", "Cloud Region",
                                      "Region Code", "Country", "Fiscal Year", "Period", "Posting Month",
                                      "Plan Cost (USD)", "Actual Cost (USD)", "Cumulative Actual (USD)",
                                      "Planned Capacity (MW)", "Start Date", "Planned Finish", "System Status"])
    # calibrate quarterly spend to Microsoft's published capex (including finance leases)
    qi = quarter_index()
    month_q = {str(MONTHS[t]): qi[t] for t in range(T)}
    q_of_row = cap["Posting Month"].map(month_q).values
    sim = np.bincount(q_of_row, weights=cap["Actual Cost (USD)"].values, minlength=len(QUARTERS))
    f_q = np.array(CAPEX_BN) * 1e9 / np.maximum(sim, 1.0)
    k_all = np.array(CAPEX_BN).sum() * 1e9 / sim.sum()
    pre = (cap.groupby("WBS Element")["Cumulative Actual (USD)"].transform("first")
           - cap.groupby("WBS Element")["Actual Cost (USD)"].transform("first")) * k_all
    cap["Actual Cost (USD)"] = (cap["Actual Cost (USD)"] * f_q[q_of_row]).round(2)
    cap["Plan Cost (USD)"] = (cap["Plan Cost (USD)"] * f_q[q_of_row]).round(2)
    cap["Cumulative Actual (USD)"] = (pre + cap.groupby("WBS Element")["Actual Cost (USD)"].cumsum()).round(2)
    complete_capex = complete_capex * f_q[qi][None, :]
    # financing and useful life (datacenter buildings are mostly leased; fleet is owned)
    wbs = cap["WBS Element"].drop_duplicates()
    leased = {w: (t == "Datacenter Build" and rng.random() < FINANCE_LEASE_SHARE / 0.4)
              for w, t in zip(wbs, cap.drop_duplicates("WBS Element")["Project Type"])}
    cap["Financing Type"] = np.where(cap["WBS Element"].map(leased), "Finance Lease", "Owned")
    # data-centre capacity report
    drows = []
    for r, name in enumerate(CLOUD_NAMES):
        code, host = CLOUD_REGIONS[name]
        for t in range(T):
            new = installed[r, t] - (installed[r, t - 1] if t else installed[r, t])
            drows.append((name, code, host, str(MONTHS[t]), round(installed[r, t], 1), round(used[r, t], 1),
                          round(100 * used[r, t] / installed[r, t], 1), round(new, 1),
                          round(min(99.999, rng.normal(99.97, 0.02)), 3)))
    dc = pd.DataFrame(drows, columns=["Datacenter Region", "Region Code", "Country", "Month",
                                      "Installed Capacity (MW)", "Used Capacity (MW)", "Utilization %",
                                      "New Capacity Online (MW)", "Availability %"])
    # one row per region x month: capex by asset class (and the leased part) next to capacity
    spend = cap.assign(lease=np.where(cap["Financing Type"] == "Finance Lease", cap["Actual Cost (USD)"], 0.0))
    spend = spend.pivot_table(index=["Region Code", "Posting Month"], columns="Project Type",
                              values="Actual Cost (USD)", aggfunc="sum", fill_value=0.0).join(
        spend.groupby(["Region Code", "Posting Month"])["lease"].sum())
    spend = spend.rename(columns={"Datacenter Build": "Capex Datacenter Build (USD)",
                                  "Server and GPU Fleet": "Capex Server and GPU Fleet (USD)",
                                  "Network Backbone": "Capex Network (USD)",
                                  "lease": "of which Finance Leases (USD)"}).reset_index()
    dcr = dc.merge(spend, left_on=["Region Code", "Month"], right_on=["Region Code", "Posting Month"],
                   how="left").drop(columns="Posting Month")
    capex_cols = ["Capex Datacenter Build (USD)", "Capex Server and GPU Fleet (USD)", "Capex Network (USD)",
                  "of which Finance Leases (USD)"]
    dcr[capex_cols] = dcr[capex_cols].fillna(0.0).round(2)
    dcr = dcr[["Datacenter Region", "Region Code", "Country", "Month"] + capex_cols +
              ["Installed Capacity (MW)", "Used Capacity (MW)", "Utilization %", "New Capacity Online (MW)",
               "Availability %"]]
    return cap, dcr, complete_capex


# ---------------------------------------------------------------------------
# 10. Cost centres, headcount and general-ledger postings
# ---------------------------------------------------------------------------
COST_PER_HEAD = {"US": 205_000, "IE": 118_000, "GB": 132_000, "DE": 138_000, "IN": 46_000, "JP": 122_000,
                 "AU": 128_000, "CA": 136_000, "FR": 124_000, "NL": 128_000, "SG": 118_000, "IL": 148_000}
HEADCOUNT_COST_SCALE = 1.0        # set in main() so total headcount is close to TARGET_HEADCOUNT
SALARY_SHARE = {"Cost of Revenue": .35, "Research and Development": .70, "Sales and Marketing": .50,
                "General and Administrative": .55, "Datacenter Operations": .15}
GL_ACCOUNTS = {
    "500100": "Cost of Revenue - Product", "500150": "Datacenter Power and Operations",
    "500200": "Cost of Revenue - Services", "500300": "Depreciation - Datacenter Assets",
    "600100": "Salaries and Wages", "600200": "Stock-Based Compensation", "600300": "Contractors",
    "610100": "Advertising and Marketing", "610200": "Partner Incentives", "620100": "Travel and Entertainment",
    "630100": "Facilities and Rent", "640100": "Software and Cloud Services", "650100": "Professional Fees",
}
FUNC_ACCOUNTS = {
    "Cost of Revenue": ["500100", "500200", "600300"],
    "Datacenter Operations": ["500150", "600300"],
    "Research and Development": ["600300", "640100", "620100"],
    "Sales and Marketing": ["610100", "610200", "620100", "600300"],
    "General and Administrative": ["630100", "650100", "640100"],
}
FUNC_AREA = {"Cost of Revenue": "COGS", "Datacenter Operations": "COGS", "Research and Development": "R&D",
             "Sales and Marketing": "S&M", "General and Administrative": "G&A"}


def build_cost_centres():
    ccs = []
    sales_ctry = ["US", "GB", "DE", "FR", "JP", "AU", "CA", "IN", "NL", "SG"]
    for p in PL.itertuples():
        if p.code != "AZR":
            for c in rng.choice(["US", "IE", "IN", "GB", "DE", "JP"], size=2, replace=False):
                ccs.append((p.code, "Cost of Revenue", c, None))
        for c in rng.choice(["US", "IN", "IE", "GB", "DE", "IL"], size=2, replace=False):
            ccs.append((p.code, "Research and Development", c, None))
        if "US" not in [x[2] for x in ccs if x[0] == p.code and x[1] == "Research and Development"]:
            ccs.append((p.code, "Research and Development", "US", None))
        for c in rng.choice(sales_ctry, size=5, replace=False):
            ccs.append((p.code, "Sales and Marketing", c, None))
    for name in CLOUD_NAMES:
        ccs.append(("AZR", "Datacenter Operations", CLOUD_REGIONS[name][1], name))
    for fn, c in [("Finance", "US"), ("Legal", "US"), ("Human Resources", "US"), ("Corporate IT", "US"),
                  ("Facilities", "US"), ("Finance", "IE"), ("Corporate IT", "IE"), ("Finance", "IN"),
                  ("Corporate IT", "IN"), ("Legal", "GB"), ("Human Resources", "GB"), ("Finance", "SG")]:
        ccs.append(("CORP", "General and Administrative", c, fn))
    cc = pd.DataFrame(ccs, columns=["pl", "function", "country", "detail"])
    cc["cc_id"] = [f"{100_000 + 37 * i}" for i in range(len(cc))]
    plname = dict(zip(PL.code, PL.name)) | {"CORP": "Corporate"}
    short = {"Cost of Revenue": "COR", "Research and Development": "RND", "Sales and Marketing": "SAM",
             "General and Administrative": "GNA", "Datacenter Operations": "DCO"}
    cc["cc_name"] = [f"{p}-{short[f]}-{c}" + (f"-{CLOUD_REGIONS[d][0]}" if f == "Datacenter Operations" else
                                              (f"-{d.replace(' ', '')[:8]}" if isinstance(d, str) else ""))
                     for p, f, c, d in zip(cc.pl, cc.function, cc.country, cc.detail)]
    cc["org"] = [f"{plname[p]} - {f}" if p != "CORP" else f"Corporate - {d}" for p, f, d in
                 zip(cc.pl, cc.function, cc.detail)]
    cc["profit_center"] = ["PC-" + p for p in cc.pl]
    cc["weight"] = rng.dirichlet(np.ones(len(cc)) * 2) * len(cc)
    return cc


def build_costs(cc, econ_pl, econ_cloud, complete_capex, fx_avg, installed):
    """Monthly cost per cost centre (USD) -> headcount table + GL line items."""
    T_ = T
    opex_trend = np.interp(np.arange(T), *OPEX_TREND_ANCHORS)       # operating leverage over time
    cost = np.zeros((len(cc), T_))
    for p in PL.itertuples():
        rev = econ_pl[PL_IDX[p.code]]
        for fn, pct in [("Cost of Revenue", p.cogs), ("Research and Development", p.rd), ("Sales and Marketing", p.sm)]:
            if p.code == "AZR" and fn == "Cost of Revenue":
                rows = cc.index[(cc.pl == "AZR") & (cc.function == "Datacenter Operations")]
                share = econ_cloud / np.maximum(econ_cloud.sum(0), 1)          # by region revenue share
                region_of = [CLOUD_IDX[d] for d in cc.detail[rows]]
                cost[rows] = rev * pct * share[region_of] * rng.lognormal(0, 0.04, (len(rows), T_))
                continue
            rows = cc.index[(cc.pl == p.code) & (cc.function == fn)]
            w = cc.weight[rows].values / cc.weight[rows].sum()
            trend = opex_trend if fn != "Cost of Revenue" else 1.0
            cost[rows] = np.outer(w, rev * pct * trend) * rng.lognormal(0, 0.04, (len(rows), T_))
    ga_total = sum(econ_pl[PL_IDX[p.code]] * p.ga for p in PL.itertuples()) * opex_trend
    rows = cc.index[cc.pl == "CORP"]
    w = cc.weight[rows].values / cc.weight[rows].sum()
    cost[rows] = np.outer(w, ga_total) * rng.lognormal(0, 0.04, (len(rows), T_))

    # depreciation of datacenter assets per region (pre-2024 base + assets placed in service)
    base_dep = installed[:, 0] * COST_PER_MW * (0.6 / 72 + 0.4 / 180) * 0.50
    in_service = np.cumsum(complete_capex, axis=1)
    # 15% of capitalised cost is land and construction in progress, which is not depreciated
    dep = base_dep[:, None] + np.hstack([np.zeros((len(CLOUD_NAMES), 1)), in_service[:, :-1]]) * (0.6 / 72 + 0.4 / 180) * 0.85

    ctry_cur = dict(zip(CTRY.code, CTRY.currency))
    gl = []
    hc_rows = []
    doc_no = 1_000_000_000

    def post(t, cci, acct, usd, day, dtype, text, period_t=None, rev_with=""):
        nonlocal doc_no
        doc_no += 1
        c = cc.iloc[cci]
        pt = t if period_t is None else period_t
        cur = ctry_cur[c.country]
        gl.append((c.country + "10", int(FISCAL_YEAR[pt]), int(FISCAL_PERIOD[pt]), str(doc_no), dtype,
                   day, acct, c.cc_id, c.cc_name, c.profit_center, FUNC_AREA[c.function], usd * fx_avg[cur][pt], cur, text,
                   rev_with))
        return str(doc_no)

    prev_hc = None
    for i, c in enumerate(cc.itertuples()):
        cph = COST_PER_HEAD.get(c.country, 120_000) * HEADCOUNT_COST_SCALE
        accts = FUNC_ACCOUNTS[c.function]
        acct_w = rng.dirichlet(np.ones(len(accts)) * 3)
        contractors_share = rng.uniform(0.05, 0.2)
        hc_prev = None
        for t in range(T):
            total = cost[i, t]
            sal_budget = total * SALARY_SHARE[c.function]
            hc = max(1, int(round(sal_budget / (cph / 12))))
            salary = hc * cph / 12 * rng.normal(1, 0.01)
            sbc = salary * (0.12 if c.function == "Research and Development" else 0.06)
            other = max(0.0, total - salary - sbc)
            me = MONTH_END[t]
            mid = MONTH_START[t] + pd.Timedelta(days=14)
            post(t, i, "600100", salary / 2, mid, "PR", "Payroll run 1")
            post(t, i, "600100", salary / 2, me, "PR", "Payroll run 2")
            post(t, i, "600200", sbc, me, "SA", "Stock award expense")
            for acct, w in zip(accts, acct_w):
                amt = other * w
                n_inv = int(rng.integers(1, 9))
                split = rng.dirichlet(np.ones(n_inv) * 2) * amt
                accr = 0.0
                if rng.random() < 0.5 and t < T - 1:
                    accr = amt * 0.1
                    split = split * 0.9
                for s in split:
                    day = MONTH_START[t] + pd.Timedelta(days=int(rng.integers(0, DAYS_IN_MONTH[t])))
                    r = rng.random()
                    if r < 0.015 and t < T - 1:              # late posting into a closed period
                        late = MONTH_START[t + 1] + pd.Timedelta(days=int(rng.integers(1, 10)))
                        post(t + 1, i, acct, s, late, "KR", "Vendor invoice (late)", period_t=t)
                    elif r < 0.025:                           # wrong amount, reversed and re-posted
                        wrong = post(t, i, acct, s * rng.uniform(1.5, 10), day, "KR", "Vendor invoice")
                        fix_day = min(day + pd.Timedelta(days=2), me)
                        rv = post(t, i, acct, -gl[-1][11] / fx_avg[ctry_cur[c.country]][t], fix_day,
                                  "KR", "Reversal of " + wrong, rev_with=wrong)
                        gl[-2] = gl[-2][:-1] + (rv,)
                        post(t, i, acct, s, fix_day, "KR", "Vendor invoice (corrected)")
                    else:
                        post(t, i, acct, s, day, "KR", "Vendor invoice")
                if accr:
                    a_doc = post(t, i, acct, accr, me, "SA", "Month-end accrual")
                    r_doc = post(t + 1, i, acct, -accr, MONTH_START[t + 1], "SA", "Accrual reversal", rev_with=a_doc)
                    gl[-2] = gl[-2][:-1] + (r_doc,)
                    post(t + 1, i, acct, accr, MONTH_START[t + 1] + pd.Timedelta(days=int(rng.integers(3, 20))),
                         "KR", "Vendor invoice (prior-month accrual)")
            if c.function == "Datacenter Operations":
                r_i = CLOUD_IDX[c.detail]
                post(t, i, "500300", dep[r_i, t], me, "AA", "Depreciation run")
            # headcount
            attr = rng.binomial(hc_prev, 0.012) if hc_prev else 0
            hires = max(0, hc - (hc_prev or hc) + attr)
            terms = max(0, (hc_prev or hc) + hires - hc)
            hc_rows.append((c.cc_id, c.cc_name, c.org, c.function, c.country, c.profit_center, MONTH_END[t],
                            hc, round(hc * rng.uniform(0.95, 1.0), 1), hires, terms,
                            int(hc * contractors_share)))
            hc_prev = hc
    g = pd.DataFrame(gl, columns=["Company Code", "Fiscal Year", "Posting Period", "Document Number",
                                  "Document Type", "Posting Date", "G/L Account", "Cost Center",
                                  "Cost Center Name", "Profit Center",
                                  "Functional Area", "Amount in LC", "Local Currency", "Text", "Reversed With"])
    g = g.sort_values(["Posting Date", "Document Number"]).reset_index(drop=True)
    g.insert(7, "G/L Account Text", g["G/L Account"].map(GL_ACCOUNTS))
    g["Posting Date"] = d_erp(g["Posting Date"])
    g["Amount in LC"] = sap_trailing_minus(g["Amount in LC"].values)
    missing_cc = rng.random(len(g)) < 0.005                    # missing cost centre (id and name)
    g.loc[missing_cc, ["Cost Center", "Cost Center Name"]] = ""
    hc = pd.DataFrame(hc_rows, columns=["Cost Center ID", "Cost Center", "Supervisory Organization", "Function",
                                        "Location Country", "Profit Center", "Period End Date", "Headcount", "FTE",
                                        "Hires", "Terminations", "Contingent Workers"])
    hc["Period End Date"] = d_iso(hc["Period End Date"])
    hc["FTE"] = hc["FTE"].astype(object)
    hc.loc[rng.random(len(hc)) < 0.01, "FTE"] = ""               # missing FTE
    cost_usd = cost.copy()
    cost_usd[cc.function.values == "Datacenter Operations"] += dep[[CLOUD_IDX[d] for d in
                                                                    cc.detail[cc.function == "Datacenter Operations"]]]
    return g, hc, cost_usd


# ---------------------------------------------------------------------------
# 11. FP&A budget (wide, with segment subtotals and two metadata lines)
# ---------------------------------------------------------------------------
def build_budget(econ_pl, cc, cost_usd):
    lines = ["Revenue", "Cost of Revenue", "Research and Development", "Sales and Marketing",
             "General and Administrative"]
    func_map = {"Cost of Revenue": ["Cost of Revenue", "Datacenter Operations"],
                "Research and Development": ["Research and Development"], "Sales and Marketing": ["Sales and Marketing"]}
    # actual (synthetic) monthly values per product line and line item, extended 9 months for FY27
    act = {}
    for p in PL.itertuples():
        i = PL_IDX[p.code]
        act[(p.code, "Revenue")] = econ_pl[i]
        for li, fns in func_map.items():
            act[(p.code, li)] = cost_usd[(cc.pl.values == p.code) & cc.function.isin(fns).values].sum(0)
        act[(p.code, "General and Administrative")] = econ_pl[i] * p.ga
    ext = {}
    for k, v in act.items():
        yoy = (v[-12:].sum() + 1) / (v[-24:-12].sum() + 1)
        ext[k] = np.concatenate([v, v[-12:-3] * yoy])              # Oct 2026 - Jun 2027 projection
    versions = [("Budget", 2025, 1.0), ("Budget", 2026, 1.0), ("Budget", 2027, 1.0), ("Forecast 6+6", 2026, 0.5)]
    rows = []
    for ver, fy, realism in versions:
        start = (fy - 1 - 2024) * 12 + 6                           # index of July of fiscal year start
        for p in PL.itertuples():
            seg = p.segment if not (p.code == "WINC" and fy >= 2026) else PBP
            # Microsoft has mostly beaten its own guidance: plan revenue slightly below actuals,
            # plan costs below actuals (AI infrastructure costs ran ahead of plan)
            bias_rev = rng.normal(0.985, 0.03) if ver == "Budget" else rng.normal(0.995, 0.015)
            for li in lines:
                bias = bias_rev if li == "Revenue" else rng.normal(0.975, 0.03)
                vals = ext[(p.code, li)][start:start + 12] * (1 + (bias - 1) * realism)
                vals = vals * rng.normal(1, 0.02, 12) / 1000
                rows.append([ver, fy_label(fy), seg, p.name, li] + list(np.round(vals, 1)))
    cols = ["Version", "Fiscal Year", "Segment", "Product Line", "Line Item"] + \
           ["Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun"]
    b = pd.DataFrame(rows, columns=cols)
    month_cols = cols[5:]
    # segment subtotal rows (a trap: summing everything double counts)
    sub = b.groupby(["Version", "Fiscal Year", "Segment", "Line Item"], as_index=False)[month_cols].sum()
    sub["Product Line"] = "Total " + sub.Segment
    b = pd.concat([b, sub[cols]]).sort_values(["Version", "Fiscal Year", "Segment", "Product Line"]).reset_index(drop=True)
    b["FY Total"] = b[month_cols].sum(axis=1)
    for c in month_cols + ["FY Total"]:
        b[c] = us_number(b[c].values, 1)
    return b


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Generating SYNTHETIC data (seed", SEED, ") ...")
    total = 0
    total += save(build_product_hierarchy(), "product_hierarchy.csv")
    total += save(build_regions(), "regions.csv")
    fx, fx_avg = build_fx()
    total += save(fx, "treasury_fx_rates.csv")

    acc = build_accounts()
    con = build_contracts(acc)
    con["ctry_i"] = con.acc_id.map(dict(zip(acc.acc_id, acc.country))).map(CTRY_IDX)
    con["acc_type"] = con.acc_id.map(dict(zip(acc.acc_id, acc.type)))
    state = rng.bit_generator.state                      # same random draws in both passes
    _, econ_raw, _, _ = contract_revenue(con)
    scale = revenue_scale(econ_raw)
    rng.bit_generator.state = state
    b, econ_pl, econ_cloud, _ = contract_revenue(con, scale)
    fy26 = (FISCAL_YEAR == 2026)
    PL_SCALE.update({c: float(scale[PL_IDX[c], fy26].mean()) for c in PL.code})

    total += save(build_opportunities(acc, con, fx_avg), "crm_opportunities.csv")
    billing, _ = build_billing(acc, con, b, fx_avg)
    total += save(billing, "erp_billing_lines.csv", sep=";")

    projects, installed, used, demand = build_capex(econ_cloud)
    capex, dc, complete_capex = capex_tables(projects, installed, used)
    total += save(dc, "datacenter_regions.csv")

    cc = build_cost_centres()
    global HEADCOUNT_COST_SCALE
    state = rng.bit_generator.state                      # pass 1 measures headcount, pass 2 calibrates it
    _, hc_try, _ = build_costs(cc, econ_pl, econ_cloud, complete_capex, fx_avg, installed)
    june25 = hc_try["Period End Date"] == "2025-06-30"
    HEADCOUNT_COST_SCALE = hc_try.loc[june25, "Headcount"].sum() / TARGET_HEADCOUNT
    rng.bit_generator.state = state
    gl, hc, cost_usd = build_costs(cc, econ_pl, econ_cloud, complete_capex, fx_avg, installed)
    total += save(gl, "gl_cost_postings.csv")
    total += save(build_budget(econ_pl, cc, cost_usd), "fpa_budget.csv",
                  header_lines=["FP&A Planning Export - Version comparison by product line",
                                "Units: USD thousands (synthetic data)"])
    print(f"Done: {total:,} rows in 8 files -> {OUT_DIR}")


if __name__ == "__main__":
    main()
