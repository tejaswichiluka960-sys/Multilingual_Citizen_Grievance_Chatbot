"""Generate the multilingual complaint corpus used by the classifier task.

The generator is deterministic and works without an external API. It creates
synthetic training data for the prototype and keeps a separate handwritten
evaluation set so model quality is not measured only on generated text.
"""

import argparse
import csv
import random
import re
from dataclasses import asdict, dataclass
from pathlib import Path

LANGUAGES = ("en", "hi", "te", "hinglish", "tenglish")

DEPARTMENT_DATA = {
    "WATER": {
        "intent": "water_supply",
        "en": "water supply and sewage",
        "hi": "पानी और सीवर",
        "te": "నీటి సరఫరా మరియు డ్రైనేజీ",
        "hinglish": "pani aur sewer",
        "tenglish": "neellu mariyu drainage",
    },
    "POWER": {
        "intent": "electricity",
        "en": "electricity and power",
        "hi": "बिजली",
        "te": "విద్యుత్",
        "hinglish": "bijli",
        "tenglish": "current",
    },
    "ROADS": {
        "intent": "roads_infrastructure",
        "en": "road and pothole",
        "hi": "सड़क और गड्ढे",
        "te": "రోడ్డు మరియు గుంతలు",
        "hinglish": "sadak aur pothole",
        "tenglish": "road mariyu gunthalu",
    },
    "SANITATION": {
        "intent": "solid_waste",
        "en": "garbage collection and sanitation",
        "hi": "कचरा और सफाई",
        "te": "చెత్త సేకరణ మరియు పారిశుధ్యం",
        "hinglish": "kachra aur safai",
        "tenglish": "chetta mariyu sanitation",
    },
    "POLICE": {
        "intent": "public_safety",
        "en": "police and public safety",
        "hi": "पुलिस और सुरक्षा",
        "te": "పోలీసు మరియు ప్రజా భద్రత",
        "hinglish": "police aur safety",
        "tenglish": "police mariyu safety",
    },
    "HEALTH": {
        "intent": "health_service",
        "en": "public health service",
        "hi": "स्वास्थ्य सेवा",
        "te": "ప్రజా ఆరోగ్య సేవ",
        "hinglish": "health seva",
        "tenglish": "health seva",
    },
    "EDUCATION": {
        "intent": "education_service",
        "en": "school and education service",
        "hi": "स्कूल और शिक्षा",
        "te": "పాఠశాల మరియు విద్య",
        "hinglish": "school aur education",
        "tenglish": "school mariyu education",
    },
    "TRANSPORT": {
        "intent": "public_transport",
        "en": "bus and public transport",
        "hi": "बस और सार्वजनिक परिवहन",
        "te": "బస్సు మరియు ప్రజా రవాణా",
        "hinglish": "bus aur transport",
        "tenglish": "bus mariyu transport",
    },
    "REVENUE": {
        "intent": "land_certificates",
        "en": "land record and certificate",
        "hi": "भूमि रिकॉर्ड और प्रमाणपत्र",
        "te": "భూమి రికార్డు మరియు ధృవపత్రం",
        "hinglish": "land record aur certificate",
        "tenglish": "land record mariyu certificate",
    },
    "OTHER": {
        "intent": "human_review",
        "en": "civic service complaint",
        "hi": "नागरिक सेवा शिकायत",
        "te": "పౌర సేవ ఫిర్యాదు",
        "hinglish": "civic service complaint",
        "tenglish": "civic service complaint",
    },
}

LOCATIONS = {
    "en": ("near the market", "in Ward 12", "on Main Road", "near the school", "in our colony"),
    "hi": ("मेरे वार्ड में", "बाजार के पास", "मुख्य सड़क पर", "स्कूल के पास", "हमारी कॉलोनी में"),
    "te": ("మా వార్డులో", "మార్కెట్ దగ్గర", "ప్రధాన రోడ్డుపై", "పాఠశాల దగ్గర", "మా కాలనీలో"),
    "hinglish": ("mere ward mein", "market ke paas", "main road par", "school ke paas", "hamari colony mein"),
    "tenglish": ("maa ward lo", "market daggara", "main road pai", "school daggara", "maa colony lo"),
}

URGENCY = {
    "en": (
        "Please register this complaint.",
        "This is urgent and affecting residents.",
        "The issue has continued for several days.",
        "Please route it to the responsible department.",
    ),
    "hi": (
        "कृपया शिकायत दर्ज करें।",
        "यह जरूरी है और लोगों को प्रभावित कर रहा है।",
        "यह समस्या कई दिनों से जारी है।",
        "कृपया इसे संबंधित विभाग को भेजें।",
    ),
    "te": (
        "దయచేసి ఫిర్యాదు నమోదు చేయండి.",
        "ఇది అత్యవసరం మరియు ప్రజలను ఇబ్బంది పెడుతోంది.",
        "ఈ సమస్య చాలా రోజులుగా ఉంది.",
        "దయచేసి సంబంధిత శాఖకు పంపండి.",
    ),
    "hinglish": (
        "Please complaint register kijiye.",
        "Yeh urgent hai aur logon ko problem ho rahi hai.",
        "Yeh issue kai din se chal raha hai.",
        "Isko concerned department ko bhejiye.",
    ),
    "tenglish": (
        "Please complaint register cheyyandi.",
        "Idi urgent mariyu people ki problem undi.",
        "Ee issue chala rojula nundi undi.",
        "Related department ki pampandi.",
    ),
}

TEMPLATES = {
    "en": (
        "There is a {issue} problem {location}. {urgency}",
        "The {issue} service is not working {location}. {urgency}",
        "Please help with the {issue} complaint {location}. {urgency}",
        "Residents are facing a {issue} issue {location}. {urgency}",
    ),
    "hi": (
        "{location} {issue} की समस्या है। {urgency}",
        "{location} {issue} की सेवा नहीं मिल रही है। {urgency}",
        "{location} {issue} की शिकायत है। {urgency}",
        "लोग {location} {issue} से परेशान हैं। {urgency}",
    ),
    "te": (
        "{location} {issue} సమస్య ఉంది. {urgency}",
        "{location} {issue} సేవ అందడం లేదు. {urgency}",
        "{location} {issue} గురించి ఫిర్యాదు ఉంది. {urgency}",
        "ప్రజలు {location} {issue} వల్ల ఇబ్బంది పడుతున్నారు. {urgency}",
    ),
    "hinglish": (
        "{location} {issue} ka problem hai. {urgency}",
        "{location} {issue} ki service nahi mil rahi hai. {urgency}",
        "{location} {issue} ka complaint hai. {urgency}",
        "Log {location} {issue} se pareshaan hain. {urgency}",
    ),
    "tenglish": (
        "{location} {issue} problem undi. {urgency}",
        "{location} {issue} service ravatledu. {urgency}",
        "{location} {issue} gurinchi complaint undi. {urgency}",
        "People {location} {issue} valla ibbandi padutunnaru. {urgency}",
    ),
}


@dataclass(frozen=True, slots=True)
class ComplaintRecord:
    """One labeled complaint row."""

    text: str
    lang: str
    department: str
    intent: str
    priority: str


HANDWRITTEN_CASES = (
    ComplaintRecord("Water is not coming to our street since yesterday", "en", "WATER", "water_supply", "high"),
    ComplaintRecord("Street light is sparking near the bus stop", "en", "POWER", "electricity", "high"),
    ComplaintRecord("Road has a deep pothole outside the clinic", "en", "ROADS", "roads_infrastructure", "high"),
    ComplaintRecord("Garbage is not collected in Ward 4", "en", "SANITATION", "solid_waste", "medium"),
    ComplaintRecord("Please help, a person is threatening residents", "en", "POLICE", "public_safety", "high"),
    ComplaintRecord("The government health centre has no doctor today", "en", "HEALTH", "health_service", "medium"),
    ComplaintRecord("School certificate application is pending", "en", "EDUCATION", "education_service", "low"),
    ComplaintRecord("Bus route 8 has not arrived for two hours", "en", "TRANSPORT", "public_transport", "medium"),
    ComplaintRecord("My land record correction is still pending", "en", "REVENUE", "land_certificates", "low"),
    ComplaintRecord("I need help with a civic service issue", "en", "OTHER", "human_review", "low"),
    ComplaintRecord("Mere area mein pani nahi aa raha, please help", "hinglish", "WATER", "water_supply", "high"),
    ComplaintRecord("Bijli ka wire toot gaya hai market ke paas", "hinglish", "POWER", "electricity", "high"),
    ComplaintRecord("Sadak par bahut bada pothole hai", "hinglish", "ROADS", "roads_infrastructure", "medium"),
    ComplaintRecord("Kachra teen din se collect nahi hua", "hinglish", "SANITATION", "solid_waste", "medium"),
    ComplaintRecord("Police ko complaint karni hai, safety problem hai", "hinglish", "POLICE", "public_safety", "high"),
    ComplaintRecord("Ma area lo neellu levu, complaint register cheyyandi", "tenglish", "WATER", "water_supply", "high"),
    ComplaintRecord("Current pole daggara sparks vastunnayi", "tenglish", "POWER", "electricity", "high"),
    ComplaintRecord("Main road pai gunthalu unnayi", "tenglish", "ROADS", "roads_infrastructure", "medium"),
    ComplaintRecord("Chetta collection maa colony lo ledu", "tenglish", "SANITATION", "solid_waste", "medium"),
    ComplaintRecord("Bus service rendu gantalu nundi ledu", "tenglish", "TRANSPORT", "public_transport", "medium"),
    ComplaintRecord("मेरे इलाके में पानी नहीं आ रहा है", "hi", "WATER", "water_supply", "high"),
    ComplaintRecord("बिजली का तार सड़क पर गिरा है", "hi", "POWER", "electricity", "high"),
    ComplaintRecord("मुख्य सड़क पर बड़ा गड्ढा है", "hi", "ROADS", "roads_infrastructure", "medium"),
    ComplaintRecord("कूड़ा कई दिनों से नहीं उठाया गया", "hi", "SANITATION", "solid_waste", "medium"),
    ComplaintRecord("मुझे पुलिस सहायता चाहिए", "hi", "POLICE", "public_safety", "high"),
    ComplaintRecord("మా వీధిలో నీళ్లు రావడం లేదు", "te", "WATER", "water_supply", "high"),
    ComplaintRecord("విద్యుత్ తీగ తెగి రోడ్డుపై పడింది", "te", "POWER", "electricity", "high"),
    ComplaintRecord("ప్రధాన రోడ్డుపై పెద్ద గుంత ఉంది", "te", "ROADS", "roads_infrastructure", "medium"),
    ComplaintRecord("చెత్తను మూడు రోజులుగా తీసుకెళ్లలేదు", "te", "SANITATION", "solid_waste", "medium"),
    ComplaintRecord("నాకు పోలీసు సహాయం కావాలి", "te", "POLICE", "public_safety", "high"),
)


def generate_rows(rows_per_language: int = 8, seed: int = 42) -> list[ComplaintRecord]:
    """Generate deterministic synthetic examples for every department and language."""

    if rows_per_language < 4:
        raise ValueError("rows_per_language must be at least 4")

    rng = random.Random(seed)
    rows: list[ComplaintRecord] = []
    for department, data in DEPARTMENT_DATA.items():
        for language in LANGUAGES:
            templates = TEMPLATES[language]
            locations = LOCATIONS[language]
            urgency = URGENCY[language]
            for index in range(rows_per_language):
                template = templates[index % len(templates)]
                row_text = template.format(
                    issue=data[language],
                    location=locations[index % len(locations)],
                    urgency=urgency[index % len(urgency)],
                )
                priority = ("high", "medium", "low", "medium")[index % 4]
                rows.append(
                    ComplaintRecord(
                        text=row_text,
                        lang=language,
                        department=department,
                        intent=data["intent"],
                        priority=priority,
                    )
                )
    rng.shuffle(rows)
    return deduplicate(rows)


def deduplicate(rows: list[ComplaintRecord]) -> list[ComplaintRecord]:
    """Remove duplicate text rows while preserving their first labels."""

    seen: set[str] = set()
    unique: list[ComplaintRecord] = []
    for row in rows:
        key = re.sub(r"\s+", " ", row.text.strip().lower())
        if key not in seen:
            seen.add(key)
            unique.append(row)
    return unique


def split_rows(
    rows: list[ComplaintRecord],
    test_ratio: float = 0.2,
    seed: int = 42,
) -> tuple[list[ComplaintRecord], list[ComplaintRecord]]:
    """Create a reproducible stratified train/test split by language and department."""

    if not 0.0 < test_ratio < 1.0:
        raise ValueError("test_ratio must be between 0 and 1")
    rng = random.Random(seed)
    groups: dict[tuple[str, str], list[ComplaintRecord]] = {}
    for row in rows:
        groups.setdefault((row.lang, row.department), []).append(row)

    train: list[ComplaintRecord] = []
    test: list[ComplaintRecord] = []
    for group_rows in groups.values():
        rng.shuffle(group_rows)
        test_count = max(1, round(len(group_rows) * test_ratio))
        test.extend(group_rows[:test_count])
        train.extend(group_rows[test_count:])
    rng.shuffle(train)
    rng.shuffle(test)
    return train, test


def write_csv(path: Path, rows: list[ComplaintRecord]) -> None:
    """Write complaint records as UTF-8 CSV."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["text", "lang", "department", "intent", "priority"])
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)


def build_datasets(output_dir: Path, rows_per_language: int = 8, seed: int = 42) -> dict[str, int]:
    """Generate raw, train, test and handwritten datasets."""

    raw_rows = generate_rows(rows_per_language=rows_per_language, seed=seed)
    train_rows, test_rows = split_rows(raw_rows, seed=seed)
    write_csv(output_dir / "raw.csv", raw_rows)
    write_csv(output_dir / "train.csv", train_rows)
    write_csv(output_dir / "test.csv", test_rows)
    write_csv(output_dir / "handwritten_test.csv", list(HANDWRITTEN_CASES))
    return {"raw": len(raw_rows), "train": len(train_rows), "test": len(test_rows), "handwritten_test": len(HANDWRITTEN_CASES)}


def main() -> None:
    """Run dataset generation from the command line."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("ml/data"))
    parser.add_argument("--rows-per-language", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    counts = build_datasets(args.output_dir, args.rows_per_language, args.seed)
    print("Datasets generated: " + ", ".join(f"{name}={count}" for name, count in counts.items()))


if __name__ == "__main__":
    main()
