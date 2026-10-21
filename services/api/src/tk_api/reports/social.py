"""Social media integration engine for civic report amplification (PRD §8, §14).

Generates optimized, authority-tagged social posts for X (Twitter) and Instagram
with 1-click Web Intents, Story graphic payloads, and intelligent municipal handle resolution.
"""

from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass
from typing import Any, Literal

ToneType = Literal["urgent", "nudge", "accountability"]
VerificationStatus = Literal["unverified", "verified_official"]

URL_REGEX = re.compile(r"https?://[^\s]+")


def calculate_x_char_weight(text: str) -> int:
    """Calculates Twitter/X weighted character count according to Twitter text spec.

    - URLs: standard 23 characters (t.co shortener) regardless of length.
    - Code points <= 0x10FF (Basic Multilingual Plane, Latin, Devanagari, digits): 1 character.
    - Code points > 0x10FF (emojis, supplementary symbols): 2 characters.
    """
    total = 0
    last_end = 0
    for match in URL_REGEX.finditer(text):
        non_url = text[last_end : match.start()]
        total += sum(2 if ord(c) > 0x10FF else 1 for c in non_url)
        total += 23  # standard t.co length
        last_end = match.end()
    remaining = text[last_end:]
    total += sum(2 if ord(c) > 0x10FF else 1 for c in remaining)
    return total


@dataclass(frozen=True)
class AuthorityInfo:
    name: str
    x_handle: str | None
    ig_handle: str | None
    jurisdiction: str
    is_primary: bool = True
    verification_status: VerificationStatus = "unverified"
    official_verification_source: str | None = None
    verified_by: str | None = None
    last_verified_at: str | None = None
    next_review_due: str | None = None


@dataclass(frozen=True)
class CityCivicDirectory:
    city_name: str
    aliases: tuple[str, ...]
    municipal_authority: AuthorityInfo
    traffic_authority: AuthorityInfo | None
    water_authority: AuthorityInfo | None
    power_authority: AuthorityInfo | None
    hashtags: tuple[str, ...]


CIVIC_DIRECTORIES: list[CityCivicDirectory] = [
    CityCivicDirectory(
        city_name="Bengaluru",
        aliases=(
            "bengaluru",
            "bangalore",
            "blr",
            "koramangala",
            "indiranagar",
            "whitefield",
            "jayanagar",
            "hsr",
            "electronic city",
            "bbmp",
        ),
        municipal_authority=AuthorityInfo(
            name="BBMP (Bruhat Bengaluru Mahanagara Palike)",
            x_handle="@BBMPCOMM",
            ig_handle="@bbmp.bangalore",
            jurisdiction="Municipal Corporation",
            is_primary=True,
        ),
        traffic_authority=AuthorityInfo(
            name="Bangalore Traffic Police",
            x_handle="@blrcitytraffic",
            ig_handle="@bangaloretrafficpolice",
            jurisdiction="Traffic & Safety",
            is_primary=False,
        ),
        water_authority=AuthorityInfo(
            name="BWSSB (Water Supply & Sewerage)",
            x_handle="@BWSSB_Chairman",
            ig_handle="@bwssb_bangalore",
            jurisdiction="Water & Sanitation",
            is_primary=False,
        ),
        power_authority=AuthorityInfo(
            name="BESCOM (Electricity Distribution)",
            x_handle="@NammaBESCOM",
            ig_handle="@bescom_official",
            jurisdiction="Power & Streetlights",
            is_primary=False,
        ),
        hashtags=("#BengaluruCivic", "#BBMP", "#NammaBengaluru", "#FixMyRoadBLR"),
    ),
    CityCivicDirectory(
        city_name="Mumbai",
        aliases=(
            "mumbai",
            "bombay",
            "andheri",
            "bandra",
            "dadar",
            "colaba",
            "borivali",
            "thane",
            "kurla",
            "bmc",
        ),
        municipal_authority=AuthorityInfo(
            name="BMC (Brihanmumbai Municipal Corporation)",
            x_handle="@mybmc",
            ig_handle="@my_bmc",
            jurisdiction="Municipal Corporation",
            is_primary=True,
        ),
        traffic_authority=AuthorityInfo(
            name="Mumbai Traffic Police",
            x_handle="@MTPHereToHelp",
            ig_handle="@mumbaipolice",
            jurisdiction="Traffic & Safety",
            is_primary=False,
        ),
        water_authority=AuthorityInfo(
            name="BMC Hydraulic Dept",
            x_handle="@mybmc",
            ig_handle="@my_bmc",
            jurisdiction="Water Supply",
            is_primary=False,
        ),
        power_authority=None,
        hashtags=("#MumbaiCivic", "#BMC", "#AamchiMumbai", "#FixMyMumbai"),
    ),
    CityCivicDirectory(
        city_name="Delhi",
        aliases=(
            "delhi",
            "new delhi",
            "noida",
            "gurugram",
            "gurgaon",
            "dwarka",
            "rohini",
            "saket",
            "mcd",
        ),
        municipal_authority=AuthorityInfo(
            name="MCD (Municipal Corporation of Delhi)",
            x_handle="@MCD_Delhi",
            ig_handle="@mcd_delhi",
            jurisdiction="Municipal Corporation",
            is_primary=True,
        ),
        traffic_authority=AuthorityInfo(
            name="Delhi Traffic Police",
            x_handle="@dtptraffic",
            ig_handle="@delhipolice",
            jurisdiction="Traffic & Safety",
            is_primary=False,
        ),
        water_authority=AuthorityInfo(
            name="Delhi Jal Board",
            x_handle="@DelhiJalBoard",
            ig_handle="@delhijalboard",
            jurisdiction="Water & Sanitation",
            is_primary=False,
        ),
        power_authority=None,
        hashtags=("#DelhiCivic", "#MCD", "#DelhiRoads", "#SwachhDelhi"),
    ),
    CityCivicDirectory(
        city_name="Hyderabad",
        aliases=(
            "hyderabad",
            "secunderabad",
            "cyberabad",
            "hitec city",
            "ghmc",
            "jubilee hills",
            "banjara hills",
            "gachibowli",
        ),
        municipal_authority=AuthorityInfo(
            name="GHMC (Greater Hyderabad Municipal Corp)",
            x_handle="@GHMCOnline",
            ig_handle="@ghmconline",
            jurisdiction="Municipal Corporation",
            is_primary=True,
        ),
        traffic_authority=AuthorityInfo(
            name="Hyderabad Traffic Police",
            x_handle="@HYDTP",
            ig_handle="@hyderabadcitypolice",
            jurisdiction="Traffic & Safety",
            is_primary=False,
        ),
        water_authority=AuthorityInfo(
            name="HMWSSB",
            x_handle="@HMWSSBONLINE",
            ig_handle="@hmwssbonline",
            jurisdiction="Water Supply",
            is_primary=False,
        ),
        power_authority=None,
        hashtags=("#HyderabadCivic", "#GHMC", "#ManaHyderabad"),
    ),
    CityCivicDirectory(
        city_name="Chennai",
        aliases=("chennai", "madras", "t nagar", "adyar", "velachery", "anna nagar", "gcc"),
        municipal_authority=AuthorityInfo(
            name="GCC (Greater Chennai Corporation)",
            x_handle="@chennaicorp",
            ig_handle="@chennaicorp",
            jurisdiction="Municipal Corporation",
            is_primary=True,
        ),
        traffic_authority=AuthorityInfo(
            name="Chennai Traffic Police",
            x_handle="@chennaipolice_",
            ig_handle="@chennaicitypolice",
            jurisdiction="Traffic & Safety",
            is_primary=False,
        ),
        water_authority=AuthorityInfo(
            name="Chennai Metro Water",
            x_handle="@CHN_Metro_Water",
            ig_handle="@chennaimetrowater",
            jurisdiction="Water Supply",
            is_primary=False,
        ),
        power_authority=None,
        hashtags=("#ChennaiCivic", "#GCC", "#SingaraChennai"),
    ),
    CityCivicDirectory(
        city_name="Pune",
        aliases=("pune", "poona", "kothrud", "vimannagar", "hinjewadi", "wakad", "baner", "pmc"),
        municipal_authority=AuthorityInfo(
            name="PMC (Pune Municipal Corporation)",
            x_handle="@PMCPune",
            ig_handle="@pmc_pune",
            jurisdiction="Municipal Corporation",
            is_primary=True,
        ),
        traffic_authority=AuthorityInfo(
            name="Pune Traffic Police",
            x_handle="@PuneCityTraffic",
            ig_handle="@punecitypolice",
            jurisdiction="Traffic & Safety",
            is_primary=False,
        ),
        water_authority=None,
        power_authority=None,
        hashtags=("#PuneCivic", "#PMC", "#PuneTraffic"),
    ),
    CityCivicDirectory(
        city_name="Kolkata",
        aliases=("kolkata", "calcutta", "salt lake", "new town", "howrah", "kmc"),
        municipal_authority=AuthorityInfo(
            name="KMC (Kolkata Municipal Corporation)",
            x_handle="@kmc_kolkata",
            ig_handle="@kmc_kolkata",
            jurisdiction="Municipal Corporation",
            is_primary=True,
        ),
        traffic_authority=AuthorityInfo(
            name="Kolkata Police",
            x_handle="@KolkataPolice",
            ig_handle="@kolkatapolice",
            jurisdiction="Traffic & Safety",
            is_primary=False,
        ),
        water_authority=None,
        power_authority=None,
        hashtags=("#KolkataCivic", "#KMC", "#AmarKolkata"),
    ),
    CityCivicDirectory(
        city_name="Ahmedabad",
        aliases=("ahmedabad", "amdavad", "navrangpura", "bodakdev", "satellite", "amc"),
        municipal_authority=AuthorityInfo(
            name="AMC (Ahmedabad Municipal Corporation)",
            x_handle="@AmdavadAMC",
            ig_handle="@amc_official",
            jurisdiction="Municipal Corporation",
            is_primary=True,
        ),
        traffic_authority=AuthorityInfo(
            name="Ahmedabad Police",
            x_handle="@AhmedabadPolice",
            ig_handle="@ahmedabadpolice",
            jurisdiction="Traffic & Safety",
            is_primary=False,
        ),
        water_authority=None,
        power_authority=None,
        hashtags=("#AmdavadCivic", "#AMC", "#SmartCityAhmedabad"),
    ),
]

FALLBACK_MUNICIPAL = AuthorityInfo(
    name="Ministry of Housing & Urban Affairs",
    x_handle="@MoHUA_India",
    ig_handle="@mohua_india",
    jurisdiction="National Urban Affairs",
    is_primary=True,
)

FALLBACK_PLATFORM = AuthorityInfo(
    name="Theek Karo Platform",
    x_handle="@TheekKaro",
    ig_handle="@theekkaro",
    jurisdiction="Civic Verification Ledger",
    is_primary=False,
    verification_status="verified_official",
    official_verification_source="https://theekkaro.in/about",
    verified_by="theekkaro-security",
    last_verified_at="2026-10-01T00:00:00Z",
    next_review_due="2027-10-01T00:00:00Z",
)

CATEGORY_HASHTAGS: dict[str, tuple[str, ...]] = {
    "roads": ("#FixMyRoad", "#PotholeHazard", "#RoadSafety"),
    "transport": ("#PublicTransport", "#RoadSafety", "#TrafficAlert"),
    "sanitation": ("#SwachhBharat", "#CleanStreets", "#GarbageFree"),
    "waste": ("#SwachhBharat", "#ZeroWaste", "#WasteManagement"),
    "water": ("#CleanWater", "#SaveWater", "#WaterCrisis"),
    "drainage": ("#WaterLogging", "#DrainageFix", "#FloodAlert"),
    "electricity": ("#StreetLightRepair", "#PowerOutage", "#CivicSafety"),
    "lighting": ("#DarkSpots", "#WomenSafety", "#StreetLights"),
    "law_enforcement": ("#CivicSafety", "#PublicOrder"),
    "healthcare": ("#PublicHealth", "#CivicCare"),
    "education": ("#SchoolSafety", "#RightToEducation"),
}


def resolve_city_directory(
    *,
    address_hint: str | None,
    location_coords: list[float] | None,
    institution_name: str | None = None,
) -> CityCivicDirectory | None:
    """Intelligently detects city from coordinates (primary ground truth) or text hints."""
    # 1. Coordinate-to-city resolution: approximate bounding boxes for major metropolitan areas
    if location_coords and len(location_coords) >= 2:
        lon, lat = location_coords[0], location_coords[1]
        # Bengaluru: lat 12.8-13.2, lon 77.4-77.8
        if 12.8 <= lat <= 13.2 and 77.4 <= lon <= 77.8:
            return next(c for c in CIVIC_DIRECTORIES if c.city_name == "Bengaluru")
        # Mumbai: lat 18.8-19.3, lon 72.7-73.1
        if 18.8 <= lat <= 19.3 and 72.7 <= lon <= 73.1:
            return next(c for c in CIVIC_DIRECTORIES if c.city_name == "Mumbai")
        # Delhi: lat 28.4-28.9, lon 76.8-77.4
        if 28.4 <= lat <= 28.9 and 76.8 <= lon <= 77.4:
            return next(c for c in CIVIC_DIRECTORIES if c.city_name == "Delhi")
        # Hyderabad: lat 17.2-17.6, lon 78.2-78.6
        if 17.2 <= lat <= 17.6 and 78.2 <= lon <= 78.6:
            return next(c for c in CIVIC_DIRECTORIES if c.city_name == "Hyderabad")
        # Chennai: lat 12.9-13.2, lon 80.1-80.4
        if 12.9 <= lat <= 13.2 and 80.1 <= lon <= 80.4:
            return next(c for c in CIVIC_DIRECTORIES if c.city_name == "Chennai")
        # Pune: lat 18.4-18.7, lon 73.7-74.0
        if 18.4 <= lat <= 18.7 and 73.7 <= lon <= 74.0:
            return next(c for c in CIVIC_DIRECTORIES if c.city_name == "Pune")
        # Kolkata: lat 22.4-22.7, lon 88.2-88.5
        if 22.4 <= lat <= 22.7 and 88.2 <= lon <= 88.5:
            return next(c for c in CIVIC_DIRECTORIES if c.city_name == "Kolkata")
        # Ahmedabad: lat 22.9-23.2, lon 72.4-72.7
        if 22.9 <= lat <= 23.2 and 72.4 <= lon <= 72.7:
            return next(c for c in CIVIC_DIRECTORIES if c.city_name == "Ahmedabad")

    # 2. Text alias matching on address_hint or institution_name (fallback when coords unavailable)
    combined_text = f"{address_hint or ''} {institution_name or ''}".lower()
    for city_dir in CIVIC_DIRECTORIES:
        for alias in city_dir.aliases:
            if re.search(r"\b" + re.escape(alias) + r"\b", combined_text):
                return city_dir

    return None


def select_relevant_authorities(
    city_dir: CityCivicDirectory | None,
    category_slug: str | None,
) -> list[AuthorityInfo]:
    """Selects 1-3 authorities tailored to the problem category."""
    if city_dir is None:
        return [FALLBACK_MUNICIPAL, FALLBACK_PLATFORM]

    authorities: list[AuthorityInfo] = [city_dir.municipal_authority]
    cat = (category_slug or "").lower()

    if any(k in cat for k in ("road", "transport", "traffic")) and city_dir.traffic_authority:
        authorities.append(city_dir.traffic_authority)
    elif (
        any(k in cat for k in ("water", "drain", "sewer", "sanitation"))
        and city_dir.water_authority
    ):
        authorities.append(city_dir.water_authority)
    elif any(k in cat for k in ("electric", "light", "power")) and city_dir.power_authority:
        authorities.append(city_dir.power_authority)

    return authorities


def build_social_post_package(
    *,
    report_id: str,
    ticket_no: str,
    title: str,
    description: str,
    category_slug: str | None,
    severity: str | None,
    address_hint: str | None,
    location_coords: list[float] | None,
    institution_name: str | None = None,
    tone: ToneType = "urgent",
    evidence_urls: list[str] | None = None,
    base_web_url: str = "https://theekkaro.in",
) -> dict[str, Any]:
    """Generates the full social amplification payload for X and Instagram."""
    city_dir = resolve_city_directory(
        address_hint=address_hint,
        location_coords=location_coords,
        institution_name=institution_name,
    )
    city_name = city_dir.city_name if city_dir else "Local Area"
    authorities = select_relevant_authorities(city_dir, category_slug)

    # Authority handles
    x_handles = [a.x_handle for a in authorities if a.x_handle]
    ig_handles = [a.ig_handle for a in authorities if a.ig_handle]

    # Gather hashtags
    hashtags_set: list[str] = ["#TheekKaro", "#CivicAction"]
    if city_dir:
        hashtags_set.extend(city_dir.hashtags)
    cat_key = (category_slug or "").lower()
    for key, tags in CATEGORY_HASHTAGS.items():
        if key in cat_key:
            hashtags_set.extend(tags)
            break

    # Location snippet
    loc_clean = (address_hint or city_name).strip()
    if len(loc_clean) > 40:
        loc_clean = loc_clean[:37] + "..."

    report_url = f"{base_web_url.rstrip('/')}/reports/{report_id}"

    # -------------------------------------------------------------
    # 1. X (Twitter) Post Crafting (Strictly fits standard 280 weighted chars)
    # -------------------------------------------------------------
    tag_str = " ".join(x_handles[:2])
    top_hashtag = hashtags_set[1] if len(hashtags_set) > 1 else "#TheekKaro"
    second_hashtag = hashtags_set[0]

    if tone == "urgent":
        prefix = "🚨 URGENT CIVIC ALERT: "
        call_to_action = "Severe hazard to commuters! Pls intervene"
    elif tone == "accountability":
        prefix = "📋 CIVIC RECORD: "
        call_to_action = "Awaiting municipal SLA action"
    else:  # nudge
        prefix = "📍 CIVIC REPORT: "
        call_to_action = "Requesting prompt inspection by"

    # Assemble base tweet metadata
    base_suffix = (
        f" at {loc_clean}. {call_to_action} {tag_str} "
        f"#{ticket_no} {report_url} {second_hashtag} {top_hashtag}"
    )

    clean_title = title.strip()
    full_candidate = f"{prefix}{clean_title}{base_suffix}".strip()

    # If full candidate exceeds 280 weighted chars, trim title progressively
    if calculate_x_char_weight(full_candidate) > 280:
        while (
            len(clean_title) > 10
            and calculate_x_char_weight(f"{prefix}{clean_title}...{base_suffix}") > 280
        ):
            clean_title = clean_title[:-4].strip()
        if calculate_x_char_weight(f"{prefix}{clean_title}...{base_suffix}") <= 280:
            x_post_text = f"{prefix}{clean_title}...{base_suffix}"
        else:
            # Minimal compact fallback guaranteeing required tags and ticket
            minimal_fmt = (
                f"{prefix}#{ticket_no} {clean_title[:15]} at {loc_clean} "
                f"{tag_str} {report_url} {top_hashtag}"
            )
            while len(clean_title) > 5 and calculate_x_char_weight(minimal_fmt) > 280:
                clean_title = clean_title[:-2].strip()
                minimal_fmt = (
                    f"{prefix}#{ticket_no} {clean_title} at {loc_clean} "
                    f"{tag_str} {report_url} {top_hashtag}"
                )
            x_post_text = minimal_fmt
    else:
        x_post_text = full_candidate

    weighted_char_count = calculate_x_char_weight(x_post_text)

    # Full encoded 1-click web intent
    x_intent_url = f"https://x.com/intent/tweet?text={urllib.parse.quote(x_post_text)}"

    # -------------------------------------------------------------
    # 2. Instagram Caption & Story Card Data
    # -------------------------------------------------------------
    ig_tag_str = " ".join(ig_handles)
    cat_label = (category_slug or "Civic Observation").replace("_", " ").title()
    sev_label = (severity or "Medium").capitalize()

    hashtag_block = " ".join(dict.fromkeys(hashtags_set))

    instagram_caption = f"""⚠️ CIVIC OBSERVATION — ACTION REQUIRED ⚠️

📍 Location: {address_hint or city_name}
🎫 Ticket ID: #{ticket_no}
🏷️ Category: {cat_label} (Severity: {sev_label})
🏛️ Responsible Authorities: {", ".join(a.name for a in authorities)}
📢 Tagging: {ig_tag_str}

📋 Observation Details:
"{title}"
{description.strip()[:400] + ("..." if len(description) > 400 else "")}

✅ Registered on Theek Karo — India's verified civic intelligence ledger.
🔗 Verify, corroborate, or track resolution status:
{report_url}

{hashtag_block}
""".strip()

    primary_image = evidence_urls[0] if evidence_urls else None

    story_card_data = {
        "ticket_no": ticket_no,
        "title": title,
        "category": cat_label,
        "severity": sev_label,
        "address": address_hint or city_name,
        "city": city_name,
        "primary_authority_name": authorities[0].name,
        "primary_authority_handle": authorities[0].x_handle
        or authorities[0].ig_handle
        or "@TheekKaro",
        "report_url": report_url,
        "primary_image_url": primary_image,
        "trust_tier": "COMMUNITY_VERIFIED",
    }

    authority_tags_out = [
        {
            "name": a.name,
            "x_handle": a.x_handle,
            "instagram_handle": a.ig_handle,
            "jurisdiction": a.jurisdiction,
            "is_primary": a.is_primary,
            "verification_status": a.verification_status,
            "official_verification_source": a.official_verification_source,
            "verified_by": a.verified_by,
            "last_verified_at": a.last_verified_at,
            "next_review_due": a.next_review_due,
        }
        for a in authorities
    ]

    return {
        "report_id": report_id,
        "ticket_no": ticket_no,
        "tone": tone,
        "x_post": {
            "text": x_post_text,
            "intent_url": x_intent_url,
            "handles": x_handles,
            "char_count": weighted_char_count,
            "fits_single_tweet": weighted_char_count <= 280,
        },
        "instagram_post": {
            "caption": instagram_caption,
            "handles": ig_handles,
            "hashtags": list(dict.fromkeys(hashtags_set)),
        },
        "authorities": authority_tags_out,
        "hashtags": list(dict.fromkeys(hashtags_set)),
        "report_url": report_url,
        "story_card": story_card_data,
        "official_broadcast_eligible": severity in ("high", "critical"),
    }
