"""Per-industry, per-disruption-type response playbooks.

Returned alongside HIGH/MEDIUM alerts so procurement teams know what to do
immediately — not just that there's a risk, but the concrete next steps.
"""
from __future__ import annotations

# Structure:
#   playbooks[industry][risk_type] = list of action strings (ordered by priority)
PLAYBOOKS: dict[str, dict[str, list[str]]] = {

    "electronics": {
        "geopolitical": [
            "Contact TaiwanSemi / Korean fab immediately to confirm safety stock status and lead time impact",
            "Check air freight capacity on TW→US, KR→US, JP→US lanes — book capacity now if available",
            "Qualify secondary fab in KR or JP for critical chip families within 30 days",
            "Audit on-hand wafer inventory — target 90 days buffer for high-runner SKUs",
            "Brief C-suite on dual sourcing timeline and cost delta vs single-source risk",
            "Review export control compliance for any US-origin technology at risk",
        ],
        "logistics": [
            "Pull Maersk/MSC/COSCO vessel ETAs for Singapore and Kaohsiung routes",
            "Authorize premium air freight for critical components if sea delay > 2 weeks",
            "Check bonded warehouse inventory at US West Coast DCs",
            "Escalate to freight forwarder for expedited customs clearance",
            "Identify alternative port pairs (LA/Long Beach → Seattle or East Coast)",
        ],
        "weather": [
            "Assess fab locations in affected region — contact facility managers for operational status",
            "Activate weather emergency protocol with key suppliers",
            "Pre-position inventory at non-affected locations",
            "Monitor power grid stability reports for affected manufacturing zones",
            "Check insurance coverage for weather-related production halts",
        ],
        "cyber": [
            "Verify that affected suppliers have isolated OT networks from disruption",
            "Request written confirmation that ERP/MES systems are operational from top 5 suppliers",
            "Review data-sharing agreements — check if supplier systems touch your IP",
            "Engage cybersecurity team for threat intelligence briefing",
            "Activate backup communication channels with affected suppliers",
        ],
    },

    "automotive": {
        "labor": [
            "Assess which OEM plants and Tier-1 suppliers are affected by strike action",
            "Check current JIT inventory buffer — typical automotive window is 3–5 days",
            "Contact fleet customers to communicate potential delay schedule",
            "Review force majeure clauses in key supply contracts",
            "Engage temporary staffing agencies for rapid supplemental labor if dispute resolves",
            "Model cash impact of assembly line shutdown at $1M/hour standard rate",
        ],
        "logistics": [
            "Audit inbound parts inventory at assembly plants",
            "Reroute ocean shipments through alternate ports (e.g., East Coast vs Gulf if LA congested)",
            "Authorize air freight for critical modules (e.g., seats, instrument panels) up to budget threshold",
            "Brief production schedulers on parts at risk of line-stop",
            "Engage 3PL for emergency cross-border trucking on key lanes",
        ],
        "geopolitical": [
            "Review tariff classification of affected parts — identify most cost-exposed line items",
            "Assess Mexico content under USMCA rules of origin for tariff mitigation",
            "Contact government affairs team to engage USTR/Commerce on tariff exemptions",
            "Evaluate nearshoring options in Mexico, Eastern Europe for top 10 exposed parts",
            "Model landed cost delta under new tariff scenario",
        ],
        "weather": [
            "Check status of stamping/casting plants in affected region",
            "Activate emergency supply from alternate approved suppliers",
            "Contact logistics partners for road condition updates in affected corridor",
            "Prepare dealer communications if vehicle delivery timelines are impacted",
        ],
    },

    "pharmaceutical": {
        "logistics": [
            "Check cold chain integrity for any in-transit biologic or vaccine shipments",
            "Contact freight forwarders for alternate routing — avoid affected ports",
            "Verify bonded warehouse inventory at US/EU distribution centers",
            "Assess regulatory timeline if alternate supplier must be qualified (typically 6–18 months)",
            "Review FDA/EMA import entry queue for API shipments at risk of delay",
        ],
        "geopolitical": [
            "Map API dependency on affected country — identify substitute manufacturers in DMF/ASMF database",
            "Contact FDA/EMA for guidance on emergency use of alternate supplier if critical shortage looms",
            "Estimate 12-month API demand and check global spot market availability",
            "Engage trade associations (PhrMA, EFPIA) for collective supply visibility",
            "Prepare briefing for CMO/CSO on shortage risk by product family",
        ],
        "weather": [
            "Contact manufacturing sites in affected region for production status",
            "Check temperature excursion reports for in-transit shipments near affected area",
            "Assess impact on packaging materials if paper/film mills are in affected zone",
            "Review business continuity plans for affected manufacturing sites",
        ],
        "cyber": [
            "Assess if affected party is a 21 CFR Part 11-regulated system supplier",
            "Check connectivity to ERP/SAP systems used for batch release and QC records",
            "Verify that electronic batch records and LIMS systems are isolated",
            "Engage CISA and HHS ASPR if critical drug supply systems are at risk",
        ],
    },

    "textile": {
        "labor": [
            "Contact Bangladesh Garment Manufacturers and Exporters Association (BGMEA) for factory status",
            "Assess in-transit shipments and inbound container ETAs from affected region",
            "Review compliance audit status — labor actions may indicate broader non-compliance issues",
            "Contact brand's corporate social responsibility (CSR) team for response protocol",
            "Identify backup factories in Vietnam, Cambodia, or India with quick-turnaround capacity",
        ],
        "weather": [
            "Request factory damage assessment from key suppliers in Chittagong / Dhaka Industrial Zones",
            "Check port of Chittagong operational status and vessel rerouting options",
            "Assess inventory of seasonal styles already in production — identify at-risk deliveries",
            "Authorize air freight for critical holiday-season styles if sea freight will miss window",
            "Engage freight forwarder for Colombo (Sri Lanka) or Bangkok as alternative trans-shipment hub",
        ],
        "geopolitical": [
            "Review country of origin requirements under buyer's trade compliance policy",
            "Assess tariff impact on cotton, yarn, and finished goods under active FTAs",
            "Contact OTEXA (Office of Textiles and Apparel) for trade data and quota status",
            "Evaluate Vietnam or India as tariff-preferred sourcing alternatives",
        ],
        "logistics": [
            "Confirm vessel bookings from Chittagong, Colombo, Ho Chi Minh on current schedules",
            "Check US West Coast / European port congestion for Asia-origin containers",
            "Authorize rerouting via East Coast if LA/Long Beach congested beyond 7 days",
            "Brief merchants on delivery window shifts — identify retailer penalty exposure",
        ],
    },

    "food_agriculture": {
        "weather": [
            "Assess crop production estimates for affected growing regions via USDA WASDE report",
            "Contact grain elevators and commodity traders for spot market availability and pricing",
            "Review forward contracts — assess if physical delivery is at risk",
            "Engage Chicago Mercantile Exchange (CME) for hedging options on exposed commodities",
            "Prepare communication for downstream food manufacturers on ingredient price outlook",
        ],
        "geopolitical": [
            "Monitor official export ban announcements from affected producing nations",
            "Contact USDA FAS and EU DG AGRI for diplomatic situation assessment",
            "Diversify sourcing away from single-country dependencies within 90 days",
            "Review grain storage capacity for emergency buffer build",
            "Engage commodity brokers for alternate origin certificates (non-sanctioned)",
        ],
        "logistics": [
            "Check reefer container availability on affected trade lanes",
            "Assess cold chain temperature logs for in-transit perishable shipments",
            "Contact Black Sea grain terminal operators for loading schedule status",
            "Authorize airfreight for high-value perishables (berries, seafood) if sea ETA at risk",
            "Review port storage capacity and dwell time at destination",
        ],
    },

    "oil_energy": {
        "geopolitical": [
            "Assess Strait of Hormuz / Red Sea transit risk — contact tanker operators immediately",
            "Review crude oil purchase contracts for force majeure / war risk clauses",
            "Contact US EIA, IEA, OPEC desk for official disruption assessment",
            "Check US Strategic Petroleum Reserve (SPR) release eligibility",
            "Engage insurance broker on war-risk premium uplift for affected tanker routes",
            "Model refinery crude slate alternatives if primary origin is blocked",
        ],
        "weather": [
            "Assess offshore platform and terminal status in Gulf of Mexico / North Sea",
            "Contact pipeline operators for shut-in status and restart timeline",
            "Review crude inventory at refinery tank farms — calculate days of cover",
            "Engage spot market for alternative crude feedstocks if pipeline cut",
            "Check LNG terminal gas nominations if pipeline supplies are reduced",
        ],
        "logistics": [
            "Monitor tanker AIS positions near affected chokepoints",
            "Authorize premium War Risk Insurance for vessels transiting affected zones",
            "Evaluate alternate trade routes (Cape of Good Hope, Suez Canal workarounds)",
            "Contact VLCC and Aframax owners for spot charter availability and rates",
        ],
    },

    "aerospace": {
        "geopolitical": [
            "Assess ITAR/EAR export control exposure — identify components subject to re-export restrictions",
            "Contact DoD DCSA or equivalent for classified supply chain guidance if applicable",
            "Review titanium and specialty alloy inventory (Russia/Ukraine sourcing exposure)",
            "Engage alternate titanium suppliers: Allegheny Technologies (US), VSMPO substitute sources",
            "Brief legal and compliance team on sanctions screening for affected entities",
        ],
        "logistics": [
            "Assess aircraft-on-ground (AOG) risk for customers if parts are delayed",
            "Authorize charter air freight for critical engine / avionics components",
            "Check bonded warehouse inventory at major MRO hubs (Dallas, Amsterdam, Singapore)",
            "Contact freight forwarders for ITAR-compliant routing alternatives",
        ],
        "cyber": [
            "Notify CISA and relevant ISACs (Aviation ISAC, DIB ISAC) of cyber disruption",
            "Isolate affected supplier systems from design data and technical data packages",
            "Review supply chain cyber risk register — assess if affected party has system access",
            "Engage incident response team for forensic assessment if breach is suspected",
        ],
        "weather": [
            "Check status of composites and precision machining facilities in affected region",
            "Assess titanium and aluminum forging shops — single-source risk in affected zone",
            "Contact facility managers for power-on status of CNC and heat treatment equipment",
        ],
    },
}

_DEFAULT_PLAYBOOK: list[str] = [
    "Assess immediate operational impact on your suppliers in the affected region",
    "Contact your top 5 suppliers by revenue to determine their status and safety stock",
    "Review open purchase orders and expedite or reroute where possible",
    "Brief your supply chain leadership team on risk exposure and timeline",
    "Activate your business continuity plan if disruption exceeds 72 hours",
]


def get_playbook(industry: str, risk_type: str) -> list[str]:
    """Return ordered action checklist for a given industry + risk type combination."""
    industry_book = PLAYBOOKS.get(industry, {})
    return industry_book.get(risk_type, _DEFAULT_PLAYBOOK)


def get_playbook_text(industry: str, risk_type: str) -> str:
    steps = get_playbook(industry, risk_type)
    return "\n".join(f"{i + 1}. {step}" for i, step in enumerate(steps))
