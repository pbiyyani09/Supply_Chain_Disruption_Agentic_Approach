"""Industry profiles — define per-industry monitoring keywords, risk factors, and key regions.

Each profile shapes three parts of the pipeline:
  1. Signal Monitor  — which keywords filter raw news into the DB
  2. Risk Scorer     — what context Gemini uses when scoring suppliers
  3. Dashboard       — labels, descriptions, and country highlights shown to the user
"""
from __future__ import annotations

INDUSTRY_PROFILES: dict[str, dict] = {
    "electronics": {
        "label": "Electronics & Semiconductors",
        "description": "Chips, PCBs, displays, consumer electronics",
        "keywords": {
            "semiconductor", "chip", "fab", "wafer", "TSMC", "foundry",
            "PCB", "electronics", "display", "lithography", "rare earth",
            "phosphorus", "neon", "palladium", "silicon", "DRAM", "NAND",
            "export control", "trade restriction", "Taiwan Strait",
            "South Korea", "shipping", "port", "logistics", "tariff",
            "factory", "supply chain", "shortage", "sanctions",
        },
        "key_countries": ["TW", "CN", "KR", "JP", "MY", "SG", "VN", "PH"],
        "disruption_priorities": ["geopolitical", "logistics", "cyber"],
        "risk_context": (
            "This supplier operates in the electronics/semiconductor industry. "
            "Critical risk factors: export control restrictions on chips or fab equipment, "
            "Taiwan Strait geopolitical tensions (critical for fabs), rare earth material shortages, "
            "port congestion in East Asia, and US/China trade restrictions. "
            "Tier 1 chip fabs face the highest exposure. Score 9-10 for direct geopolitical threats to TW/CN/KR."
        ),
    },

    "automotive": {
        "label": "Automotive & EV",
        "description": "Vehicles, auto parts, batteries, EV components",
        "keywords": {
            "automotive", "auto parts", "vehicle", "EV", "electric vehicle",
            "battery", "lithium", "cobalt", "steel", "aluminum", "rubber",
            "just-in-time", "OEM", "tier-1 supplier", "stamping", "casting",
            "semiconductor shortage", "microchip", "logistics", "port",
            "shipping", "tariff", "factory", "strike", "UAW", "plant shutdown",
            "supply chain", "OSHA", "recall",
        },
        "key_countries": ["DE", "JP", "KR", "MX", "CN", "US", "CZ", "HU", "SK"],
        "disruption_priorities": ["labor", "logistics", "geopolitical"],
        "risk_context": (
            "This supplier operates in the automotive/EV industry. "
            "Critical risk factors: just-in-time delivery failures, semiconductor shortages for ECUs, "
            "lithium/cobalt supply disruptions for batteries, labor strikes at OEM plants, "
            "and port congestion delaying parts from Mexico/Germany/Japan. "
            "Score 9-10 for plant shutdowns or parts shortages that halt assembly lines."
        ),
    },

    "pharmaceutical": {
        "label": "Pharmaceutical & Life Sciences",
        "description": "Active ingredients, generics, medical devices, vaccines",
        "keywords": {
            "pharmaceutical", "API", "active pharmaceutical ingredient", "generic",
            "drug", "medicine", "vaccine", "medical device", "FDA", "GMP",
            "clinical", "shortage", "recall", "contamination", "regulatory",
            "cold chain", "biologic", "biosimilar", "excipient",
            "chemical", "solvent", "raw material", "import", "export",
            "India", "China", "Ireland", "supply chain", "logistics",
        },
        "key_countries": ["IN", "CN", "IE", "SG", "US", "DE", "CH", "IL"],
        "disruption_priorities": ["logistics", "geopolitical", "weather"],
        "risk_context": (
            "This supplier operates in the pharmaceutical/life sciences industry. "
            "Critical risk factors: API shortages (80%+ of global APIs come from IN/CN), "
            "FDA import bans or warning letters, cold-chain logistics disruptions, "
            "raw material contamination events, and regulatory shutdowns of manufacturing sites. "
            "Score 9-10 for API supply cuts or regulatory actions that could cause drug shortages."
        ),
    },

    "textile": {
        "label": "Textile & Apparel",
        "description": "Garments, fabric, yarn, fast fashion, sportswear",
        "keywords": {
            "textile", "apparel", "garment", "fabric", "yarn", "cotton",
            "polyester", "denim", "fast fashion", "sourcing", "factory",
            "labor", "wages", "workers", "Bangladesh", "Vietnam", "Cambodia",
            "port", "shipping", "container", "freight", "tariff",
            "supply chain", "import", "export", "flood", "cyclone",
            "strike", "minimum wage", "compliance", "audit",
        },
        "key_countries": ["BD", "VN", "IN", "CN", "TR", "KH", "PK", "ID", "ET"],
        "disruption_priorities": ["labor", "weather", "logistics"],
        "risk_context": (
            "This supplier operates in the textile/apparel industry. "
            "Critical risk factors: labor unrest and wage disputes in garment hubs (BD, VN, KH), "
            "monsoon flooding disrupting Bangladesh and Vietnam factories, "
            "cotton price spikes, port congestion at Chittagong/Ho Chi Minh, "
            "and trade compliance or sourcing audit failures. "
            "Score 9-10 for flooding of major garment districts or widespread factory strikes."
        ),
    },

    "food_agriculture": {
        "label": "Food & Agriculture",
        "description": "Grains, produce, proteins, food processing, packaging",
        "keywords": {
            "food", "agriculture", "grain", "wheat", "corn", "rice", "soybean",
            "crop", "harvest", "drought", "flood", "frost", "fertilizer",
            "pesticide", "protein", "meat", "seafood", "dairy",
            "food safety", "contamination", "recall", "cold chain",
            "port", "shipping", "logistics", "export ban", "import restriction",
            "Ukraine", "Russia", "Brazil", "Argentina", "US",
        },
        "key_countries": ["UA", "RU", "BR", "AR", "US", "AU", "CN", "IN", "TH"],
        "disruption_priorities": ["weather", "geopolitical", "logistics"],
        "risk_context": (
            "This supplier operates in the food/agriculture industry. "
            "Critical risk factors: extreme weather destroying harvests (drought, flood, frost), "
            "Black Sea grain corridor disruptions (Ukraine/Russia conflict), "
            "export bans by major producing nations, fertilizer supply shocks, "
            "and cold chain failures during transport. "
            "Score 9-10 for harvest failures in a major producing region or country-level export bans."
        ),
    },

    "oil_energy": {
        "label": "Oil, Gas & Energy",
        "description": "Crude oil, LNG, refining, petrochemicals, renewables",
        "keywords": {
            "oil", "crude", "petroleum", "LNG", "natural gas", "refinery",
            "pipeline", "OPEC", "energy", "fuel", "gasoline", "diesel",
            "petrochemical", "offshore", "drilling", "tanker",
            "sanctions", "embargo", "geopolitical", "Middle East",
            "conflict", "hurricane", "storm", "port", "shipping",
            "renewable", "solar panel", "wind turbine", "battery storage",
        },
        "key_countries": ["SA", "AE", "RU", "IQ", "IR", "NO", "US", "NG", "CN"],
        "disruption_priorities": ["geopolitical", "weather", "logistics"],
        "risk_context": (
            "This supplier operates in the oil, gas & energy industry. "
            "Critical risk factors: Middle East geopolitical escalation affecting Strait of Hormuz, "
            "OPEC production cuts, pipeline sabotage or infrastructure attacks, "
            "hurricane disruptions to Gulf of Mexico platforms, "
            "and Western sanctions on Russian energy. "
            "Score 9-10 for Hormuz closure threats, major pipeline outages, or new energy sanctions."
        ),
    },

    "aerospace": {
        "label": "Aerospace & Defense",
        "description": "Aircraft parts, engines, avionics, defense systems",
        "keywords": {
            "aerospace", "aviation", "aircraft", "engine", "avionics",
            "defense", "military", "missile", "satellite", "titanium",
            "aluminum alloy", "composite", "carbon fiber", "Boeing", "Airbus",
            "export control", "ITAR", "EAR", "sanctions",
            "supply chain", "machining", "forging", "casting",
            "MRO", "maintenance", "repair", "overhaul",
        },
        "key_countries": ["US", "FR", "DE", "UK", "CA", "JP", "RU", "UA", "IL"],
        "disruption_priorities": ["geopolitical", "logistics", "cyber"],
        "risk_context": (
            "This supplier operates in the aerospace/defense industry. "
            "Critical risk factors: export control violations (ITAR/EAR), "
            "titanium supply disruptions from Russia/Ukraine, "
            "composite material shortages, defense budget changes, "
            "and cyber attacks on defense supply chains. "
            "Score 9-10 for ITAR violations, critical material embargoes, or cyber breaches of defense contractors."
        ),
    },
}

DEFAULT_INDUSTRY = "electronics"


def get_profile(industry_key: str) -> dict:
    return INDUSTRY_PROFILES.get(industry_key, INDUSTRY_PROFILES[DEFAULT_INDUSTRY])


def get_keywords(industry_key: str) -> set[str]:
    return get_profile(industry_key)["keywords"]


def get_risk_context(industry_key: str) -> str:
    return get_profile(industry_key)["risk_context"]


def all_labels() -> dict[str, str]:
    """Returns {key: label} for the dashboard selectbox."""
    return {k: v["label"] for k, v in INDUSTRY_PROFILES.items()}
