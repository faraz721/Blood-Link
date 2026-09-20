"""
BloodLink AI — language-aware answers, blood compatibility, steps, safety filter.
Works offline with rich local knowledge; optional LLM when AI_API_KEY is set.
Handles Roman Urdu, spelling mistakes, and mixed intent.
"""
import re
import requests
from typing import Tuple, Optional, List, Dict
from config.settings import Config
from services.rag_service import get_context_for_question

# ---------------------------------------------------------------------------
# Blood group compatibility (red cells)
# ---------------------------------------------------------------------------
DONATE_TO = {
    "O-": ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"],
    "O+": ["O+", "A+", "B+", "AB+"],
    "A-": ["A-", "A+", "AB-", "AB+"],
    "A+": ["A+", "AB+"],
    "B-": ["B-", "B+", "AB-", "AB+"],
    "B+": ["B+", "AB+"],
    "AB-": ["AB-", "AB+"],
    "AB+": ["AB+"],
}

RECEIVE_FROM = {
    "O-": ["O-"],
    "O+": ["O-", "O+"],
    "A-": ["O-", "A-"],
    "A+": ["O-", "O+", "A-", "A+"],
    "B-": ["O-", "B-"],
    "B+": ["O-", "O+", "B-", "B+"],
    "AB-": ["O-", "A-", "B-", "AB-"],
    "AB+": ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"],
}

SYSTEM_PROMPT = """You are BloodLink AI Help for Talagang and Chakwal districts, Pakistan.

RULES:
1. Answer ONLY from the knowledge-base context and platform facts. Do not invent medical facts.
2. Reply in the SAME language as the user (English / Urdu / Roman Urdu / Punjabi).
3. For how-to questions, give clear numbered steps.
4. For blood compatibility, be precise (yes/no + who can donate to whom).
5. End with: BloodLink AI provides information from its knowledge base and is not a substitute for professional medical advice.
6. Refuse illegal, harmful, abusive, or sexual requests politely.
7. Do not dump PDF page headers.

CONTEXT:
{context}
"""

# ---------------------------------------------------------------------------
# Spelling / informal variants → canonical tokens
# ---------------------------------------------------------------------------
SPELL_MAP = {
    # need / chahiye
    "chiaye": "chahiye", "chaiye": "chahiye", "chahye": "chahiye", "chahye": "chahiye", "chahie": "chahiye", "chahye": "chahiye",
    "chaye": "chahiye", "chahye": "chahiye", "chahia": "chahiye", "cahiye": "chahiye",
    "cahye": "chahiye", "chahye": "chahiye",
    # how / kaise
    "kaisy": "kaise", "kese": "kaise", "kesy": "kaise", "kaisay": "kaise", "kaisey": "kaise",
    "kaisy": "kaise", "kese": "kaise", "kis trah": "kaise", "kis tara": "kaise",
    # do / karna
    "kroon": "karun", "krun": "karun", "karoon": "karun", "karo": "karo", "kron": "karun",
    "krna": "karna", "karna": "karna", "karein": "karein", "kare": "kare",
    # me / mujhe
    "muje": "mujhe", "mujhe": "mujhe", "mjhe": "mujhe", "mujhay": "mujhe", "me": "main",
    "abhee": "abhi", "abhe": "abhi", "abhi": "abhi", "abhee": "abhi",
    # blood / donor
    "blod": "blood", "bloood": "blood", "khoon": "blood", "khun": "blood",
    "doner": "donor", "donar": "donor", "doner": "donor",
    # group
    "grup": "group", "grp": "group", "grop": "group",
    # find / search
    "dhoond": "dhoondo", "dhundo": "dhoondo", "dhoondo": "dhoondo", "dhoondho": "dhoondo",
    "milay": "mile", "mil jaye": "mile",
    # become / register
    "bane": "bane", "banu": "banun", "banun": "banun", "banna": "banna",
    # fill form
    "fill": "fill", "form": "form",
}


def normalize_text(text: str) -> str:
    t = (text or "").lower()
    t = re.sub(r"[^\w\s+\-]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    # apply spelling map word by word
    words = []
    for w in t.split():
        words.append(SPELL_MAP.get(w, w))
    t = " ".join(words)
    # drop fillers that break matching
    for w in ["a", "the", "please", "plz", "bhai", "yaar", "ji", "sir"]:
        t = re.sub(rf"\b{w}\b", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def normalize_group(token: str) -> Optional[str]:
    t = token.upper().replace(" ", "").replace("POSITIVE", "+").replace("NEGATIVE", "-")
    t = t.replace("POS", "+").replace("NEG", "-")
    m = re.match(r"^(A|B|AB|O)(\+|−|-)?$", t)
    if not m:
        return None
    abo, rh = m.group(1), m.group(2)
    if rh in (None, ""):
        return None
    if rh == "−":
        rh = "-"
    return f"{abo}{rh}"


def extract_groups(text: str) -> List[str]:
    found = []
    patterns = [
        r"\b(AB|A|B|O)\s*[\+\-−](?!\w)",
        r"\b(AB|A|B|O)\s*(positive|negative|pos|neg)\b",
    ]
    for pat in patterns:
        for m in re.finditer(pat, text, re.I):
            g = normalize_group(m.group(0))
            if g and g not in found:
                found.append(g)
    return found


def detect_lang(text: str) -> str:
    if any("\u0600" <= c <= "\u06FF" for c in text):
        return "urdu"
    t = text.lower()
    if any(x in t for x in ["english please", "in english", "answer in english", "reply in english"]):
        return "english"
    roman_cues = [
        "hai", "hain", "kya", "kaise", "kese", "kaisy", "kyun", "nahi", "mein", "hoon",
        "batao", "chahiye", "chiaye", "sakta", "sakti", "muje", "mujhe", "krna", "karna",
        "kroon", "karun", "khoon", "banu", "banun", "dhundo", "dhoond", "karein", "madad",
        "abhi", "abhee", "zaroori", "chahye",
    ]
    eng_cues = ["how to", "what is", "can a", "can i", "who can", "tell me", "please", "donate to", "receive"]
    rs = sum(1 for w in roman_cues if w in t)
    es = sum(1 for w in eng_cues if w in t)
    if rs >= 1 and rs >= es:
        return "roman"
    return "english"


def is_unsafe(text: str) -> bool:
    t = text.lower()
    bad = [
        "how to kill", "make bomb", "terror", "hack", "steal blood", "sell blood illegally",
        "poison", "suicide method", "child porn", "rape", "drug dealing",
    ]
    return any(b in t for b in bad)


def disclaimer(_lang: str = "english") -> str:
    return (
        "BloodLink AI provides information from its knowledge base and is not a "
        "substitute for professional medical advice."
    )


# ---------------------------------------------------------------------------
# Intent detection (priority order matters)
# ---------------------------------------------------------------------------
def detect_intent(question: str) -> Optional[str]:
    """
    Returns one of:
      need_blood | find_donor | become_donor | how_donate | compatibility |
      eligibility | about | report | after_donation | interval | safety |
      before_donation | hemoglobin | contact | login | districts | universal
    """
    q = normalize_text(question)
    groups = extract_groups(question)

    # --- NEED BLOOD / FIND DONOR (highest priority for "chahiye / need") ---
    need_cues = [
        "chahiye", "chiaye", "need blood", "need donor", "blood need", "donor need",
        "blood chahiye", "donor chahiye", "khoon chahiye", "urgent", "emergency",
        "zaroori", "abhi chahiye", "abhi blood", "blood mil", "donor mil",
        "find donor", "search donor", "dhoondo", "dhundo", "dhoond", "where donor",
        "donor kahan", "blood kahan", "get blood", "looking for donor", "looking for blood",
    ]
    if any(c in q for c in need_cues):
        return "need_blood"

    # also: "O+ blood group" + action words without "donate"
    if groups and any(w in q for w in ["group", "blood"]) and any(
        w in q for w in ["chahiye", "chiaye", "need", "mil", "dhoond", "find", "search", "urgent", "abhi"]
    ):
        return "need_blood"

    # --- COMPATIBILITY ---
    if len(groups) >= 1 and any(
        w in q
        for w in [
            "donate to", "donate blood to", "give to", "compatible", "compatibility",
            "de sakta", "de sakti", "dy sakta", "de skta", "receive", "le sakta",
            "kis ko", "kis kis", "who can", "can o", "can a", "can b", "can ab",
            "donate", "receive from",
        ]
    ):
        # if it's clearly "I need blood" already returned above
        return "compatibility"

    # --- BECOME DONOR / FORM ---
    become_cues = [
        "become donor", "become a donor", "register", "sign up", "donor form",
        "fill form", "form fill", "form kaise", "form kaisy", "create account",
        "account bana", "donor ban", "donor bane", "donor banu", "donor banun",
        "registration", "how to become", "kaise bane", "kaise banun",
    ]
    if any(c in q for c in become_cues):
        return "become_donor"

    # --- HOW TO DONATE (process at blood bank) ---
    donate_cues = [
        "how to donate", "donate blood", "blood donate", "donation process",
        "kaise donate", "donate karna", "donate krna", "blood dena", "khoon dena",
        "blood kaise de", "donation kaise", "kaise blood donate",
    ]
    # only if NOT need-blood style
    if any(c in q for c in donate_cues):
        return "how_donate"

    # --- ELIGIBILITY ---
    if any(
        c in q
        for c in [
            "eligible", "eligibility", "who can donate", "kaun de sakta", "kon donate",
            "requirements", "shart", "age", "weight", "kaun donate",
        ]
    ):
        return "eligibility"

    # --- ABOUT ---
    if any(
        c in q
        for c in [
            "about bloodlink", "what is bloodlink", "ye system", "this website",
            "this platform", "bloodlink kya", "kya hai bloodlink", "about",
        ]
    ):
        return "about"

    # --- REPORT ---
    if any(c in q for c in ["report", "complaint", "masla", "shikayat", "problem"]):
        return "report"

    # --- AFTER DONATION ---
    if any(
        c in q
        for c in [
            "after donation", "side effect", "side effects", "donation ke baad",
            "thakan", "dizzy", "chakkar", "reaction",
        ]
    ):
        return "after_donation"

    # --- INTERVAL ---
    if any(
        c in q
        for c in [
            "how often", "kitni baar", "kitne din", "interval", "gap", "phir kab",
            "dobara", "next donation", "frequency",
        ]
    ):
        return "interval"

    # --- SAFETY ---
    if any(c in q for c in ["safe", "safety", "khatra", "danger", "hiv", "hepatitis", "infection"]):
        return "safety"

    # --- BEFORE ---
    if any(
        c in q
        for c in [
            "before donation", "donation se pehle", "prepare", "tyari", "kya khana", "fasting",
        ]
    ):
        return "before_donation"

    # --- HEMOGLOBIN ---
    if any(c in q for c in ["hemoglobin", "hb", "anaemia", "anemia", "khoon ki kami"]):
        return "hemoglobin"

    # --- CONTACT ---
    if any(c in q for c in ["whatsapp", "call donor", "contact donor"]):
        return "contact"

    # --- LOGIN ---
    if any(c in q for c in ["password", "login", "forgot", "sign in"]):
        return "login"

    # --- DISTRICTS ---
    if any(c in q for c in ["talagang", "chakwal", "district"]):
        return "districts"

    # --- UNIVERSAL ---
    if any(c in q for c in ["universal donor", "universal recipient", "universal"]):
        return "universal"

    return None


# ---------------------------------------------------------------------------
# Answer builders
# ---------------------------------------------------------------------------
def answer_compatibility(question: str, lang: str) -> Optional[str]:
    q = question.lower()
    groups = extract_groups(question)

    compat_words = [
        "donate", "donat", "de sakta", "de sakti", "dy sakta", "de skta",
        "give to", "give blood", "compatible", "compatibility",
        "receive", "lg sakta", "lag sakta", "le sakta", "to ",
        "can o", "can a", "can b", "can ab", "kis ko", "kis kis", "who can",
    ]
    if len(groups) >= 2 and any(w in q for w in compat_words):
        donor, patient = groups[0], groups[1]
        if any(w in q for w in ["receive", "lg sakta", "lag sakta", "le sakta", "receive from", "kis se"]):
            patient, donor = groups[0], groups[1]
        ok = patient in DONATE_TO.get(donor, [])
        if lang == "english":
            if ok:
                body = (
                    f"Yes. A person with blood group {donor} can generally donate "
                    f"red blood cells to a patient with {patient}.\n\n"
                    "Note: Hospital laboratory cross-match is always required before any transfusion."
                )
            else:
                body = (
                    f"No. A person with blood group {donor} cannot generally donate "
                    f"red blood cells to a patient with {patient}.\n\n"
                    f"{donor} can generally donate to: {', '.join(DONATE_TO.get(donor, []))}."
                )
        else:
            if ok:
                body = (
                    f"Haan. {donor} wala donor generally {patient} patient ko "
                    "red cells de sakta hai.\n\nHospital cross-match zaroori hai."
                )
            else:
                body = (
                    f"Nahi. {donor} generally {patient} ko donate nahi kar sakta.\n\n"
                    f"{donor} generally in groups ko de sakta hai: "
                    f"{', '.join(DONATE_TO.get(donor, []))}."
                )
        return body + "\n\n" + disclaimer(lang)

    if len(groups) == 1 and any(
        w in q for w in ["who can", "kis kis", "kis ko", "donate to", "de sakta", "can donate", "kon kon"]
    ):
        g = groups[0]
        if any(w in q for w in ["receive", "lg sak", "receive from", "kis se", "le sakta"]):
            src = RECEIVE_FROM.get(g, [])
            if lang == "english":
                return (
                    f"A patient with blood group {g} can generally receive red blood cells from: "
                    f"{', '.join(src)}.\n\nHospital cross-match is always required.\n\n"
                    + disclaimer(lang)
                )
            return (
                f"{g} patient generally in donors se le sakta hai: {', '.join(src)}.\n\n"
                "Hospital cross-match zaroori hai.\n\n" + disclaimer(lang)
            )
        targets = DONATE_TO.get(g, [])
        if lang == "english":
            return (
                f"A donor with blood group {g} can generally donate red blood cells to: "
                f"{', '.join(targets)}.\n\n"
                "Hospital cross-match is always required before transfusion.\n\n"
                + disclaimer(lang)
            )
        return (
            f"{g} donor generally in groups ko donate kar sakta hai: {', '.join(targets)}.\n\n"
            "Hospital cross-match zaroori hai.\n\n" + disclaimer(lang)
        )
    return None


ANSWERS: Dict[str, Dict[str, str]] = {
    "need_blood": {
        "en": (
            "If you need blood right now:\n"
            "1. Open **Find Donor** on BloodLink.\n"
            "2. Select Blood Group **{group}** (required).\n"
            "3. Optional: choose District (Talagang / Chakwal) and Village.\n"
            "4. Click Search.\n"
            "5. Call or WhatsApp an available donor from the results.\n\n"
            "Also contact the nearest hospital blood bank for emergency support.\n"
            "BloodLink only helps you find donors — it does not store or deliver blood."
        ),
        "rom": (
            "Agar abhi blood chahiye:\n"
            "1. BloodLink pe **Find Donor** kholen.\n"
            "2. Blood Group **{group}** select karein (zaroori).\n"
            "3. Optional: District (Talagang / Chakwal) aur Village choose karein.\n"
            "4. Search dabayein.\n"
            "5. Result se available donor ko Call ya WhatsApp karein.\n\n"
            "Emergency ke liye nearest hospital blood bank se bhi contact karein.\n"
            "BloodLink sirf donors dhoondne mein madad karta hai — blood store/deliver nahi karta."
        ),
    },
    "find_donor": {
        "en": (
            "How to find a donor on BloodLink:\n"
            "1. Click **Find Donor** in the navbar.\n"
            "2. Select the required **Blood Group** (required).\n"
            "3. Optionally choose District (Talagang or Chakwal) and Village/Area.\n"
            "4. Click Search.\n"
            "5. Use **Call** or **WhatsApp** on a result card.\n"
            "Only available, non-suspended donors are shown."
        ),
        "rom": (
            "BloodLink par donor dhoondhne ke steps:\n"
            "1. Navbar se **Find Donor** pe click karein.\n"
            "2. **Blood Group** select karein (zaroori).\n"
            "3. Optional: District aur Village choose karein.\n"
            "4. Search dabayein.\n"
            "5. Result par **Call** ya **WhatsApp** use karein.\n"
            "Sirf available, non-suspended donors dikhte hain."
        ),
    },
    "become_donor": {
        "en": (
            "How to become a donor / fill the donor form on BloodLink:\n"
            "1. Click **Become a Donor** in the menu.\n"
            "2. If you already have an account: log in with phone + password.\n"
            "3. New account — fill the form:\n"
            "   • Full Name\n"
            "   • Phone (this is your login ID)\n"
            "   • Blood Group (A+, A-, B+, B-, AB+, AB-, O+, O-)\n"
            "   • District: only Talagang or Chakwal\n"
            "   • Village/Area from the list\n"
            "   • WhatsApp (optional)\n"
            "   • Password (minimum 8 characters)\n"
            "4. Submit / Register.\n"
            "5. Later, manage availability from **My Profile**."
        ),
        "rom": (
            "Donor banne / donor form fill karne ke steps:\n"
            "1. Menu se **Become a Donor** pe click karein.\n"
            "2. Pehle se account hai to phone + password se login.\n"
            "3. Naya account — form fill karein:\n"
            "   • Full Name\n"
            "   • Phone (yehi login ID hai)\n"
            "   • Blood Group (A+, A-, B+, B-, AB+, AB-, O+, O-)\n"
            "   • District: sirf Talagang ya Chakwal\n"
            "   • Village/Area list se choose karein\n"
            "   • WhatsApp (optional)\n"
            "   • Password (kam az kam 8 characters)\n"
            "4. Submit / Register karein.\n"
            "5. Baad mein **My Profile** se availability set karein."
        ),
    },
    "how_donate": {
        "en": (
            "How to donate blood (at a blood bank / camp):\n"
            "1. Check eligibility: usually age 18–60/65, weight ≥ 50 kg, good health, no active infection.\n"
            "2. Go to a licensed blood bank or donation camp (hospital / Red Crescent).\n"
            "3. Bring a valid ID. Staff will check medical history, hemoglobin and blood pressure.\n"
            "4. If cleared, whole blood donation takes about 8–15 minutes.\n"
            "5. Rest, drink fluids, avoid heavy exercise that day.\n"
            "6. You can usually donate whole blood again after about 3 months.\n\n"
            "On BloodLink: register via **Become a Donor** so people in Talagang/Chakwal can find you."
        ),
        "rom": (
            "Blood donate karne ke general steps (blood bank / camp):\n"
            "1. Eligibility: age aksar 18–60/65, weight kam az kam 50 kg, sehat theek, active infection na ho.\n"
            "2. Licensed blood bank ya donation camp jayein.\n"
            "3. ID le jayein. Staff history, hemoglobin, BP check karega.\n"
            "4. Clear hone pe whole blood ~8–15 minutes leti hai.\n"
            "5. Rest karein, fluids piyein, us din heavy exercise avoid karein.\n"
            "6. Whole blood aksar ~3 months baad dobara de sakte hain.\n\n"
            "BloodLink pe **Become a Donor** se register karein taake log aapko find kar saken."
        ),
    },
    "eligibility": {
        "en": (
            "General eligibility (final decision by the blood bank):\n"
            "1. Age usually 18–60 or 65 years\n"
            "2. Weight at least 50 kg\n"
            "3. Good health on the day; adequate hemoglobin\n"
            "4. No active infection, fever, or recent major illness\n"
            "5. Whole blood typically every ~3 months\n"
            "Some medicines, travel, tattoos, or pregnancy can cause temporary deferral."
        ),
        "rom": (
            "General eligibility (final decision blood bank ki):\n"
            "1. Age aksar 18–60/65\n"
            "2. Weight kam az kam 50 kg\n"
            "3. Donation din sehat theek, hemoglobin theek\n"
            "4. Active infection, bukhar, recent major illness na ho\n"
            "5. Whole blood aksar ~3 months baad\n"
            "Kuch medicines, travel, tattoo, pregnancy temporary deferral kar sakti hain."
        ),
    },
    "about": {
        "en": (
            "BloodLink is a free platform for **Talagang** and **Chakwal** districts only. "
            "It helps people find available blood donors and contact them by Call or WhatsApp. "
            "It does not collect or store blood. "
            "Features: Find Donor, Become Donor, AI Help, Report a Problem."
        ),
        "rom": (
            "BloodLink **Talagang** aur **Chakwal** ke liye free platform hai. "
            "Available donors dhoondhne aur Call/WhatsApp se contact karne mein madad karta hai. "
            "Blood collect/store nahi karta. "
            "Features: Find Donor, Become Donor, AI Help, Report a Problem."
        ),
    },
    "report": {
        "en": (
            "How to report a problem:\n"
            "1. Click the floating **Report a Problem** button (bottom-right).\n"
            "2. Enter Name, WhatsApp, Phone, District, Village/Area, and your message.\n"
            "3. Submit. Admins can review reports."
        ),
        "rom": (
            "Problem report karne ke steps:\n"
            "1. Neeche right **Report a Problem** button pe click karein.\n"
            "2. Name, WhatsApp, Phone, District, Village aur message bharein.\n"
            "3. Submit karein."
        ),
    },
    "after_donation": {
        "en": (
            "After donation (typical):\n"
            "• Mild tiredness or light-headedness — rest and drink fluids.\n"
            "• Keep the bandage on for a few hours; avoid heavy lifting with that arm the same day.\n"
            "• Serious reactions are uncommon. If unwell, tell staff or seek medical help.\n"
            "BloodLink does not perform donations — go to a licensed blood bank or camp."
        ),
        "rom": (
            "Donation ke baad (typical):\n"
            "• Thakan ya halka chakkar — rest karein, fluids piyein.\n"
            "• Bandage kuch hours rakhein; us din us arm se heavy lifting avoid karein.\n"
            "• Serious reaction uncommon. Tabiyat kharab ho to staff/doctor se rabta karein.\n"
            "BloodLink donation nahi karta — licensed blood bank/camp jayein."
        ),
    },
    "interval": {
        "en": (
            "Donation interval (typical):\n"
            "• Whole blood: about every 3 months (sometimes 8–12 weeks by local rules).\n"
            "• Platelets / plasma: shorter intervals may apply at some centres.\n"
            "Always follow the blood bank’s advice."
        ),
        "rom": (
            "Donation interval (typical):\n"
            "• Whole blood: aksar ~3 months (kabhi 8–12 weeks).\n"
            "• Platelets / plasma: kuch centres pe shorter gap.\n"
            "Blood bank ki guidance follow karein."
        ),
    },
    "safety": {
        "en": (
            "Licensed blood banks use sterile, single-use equipment. Donating at a proper centre is considered safe. "
            "Your blood is tested; the centre contacts you if needed as per their policy. "
            "BloodLink is only a donor-finder — actual donation is at blood banks/camps."
        ),
        "rom": (
            "Licensed blood banks sterile single-use equipment use karte hain. Proper centre pe donate karna safe maana jata hai. "
            "Blood test hota hai. BloodLink sirf donor-finder hai — donation blood bank/camp pe hoti hai."
        ),
    },
    "before_donation": {
        "en": (
            "Before donation (typical advice):\n"
            "• Eat a normal meal; avoid heavy fatty food just before.\n"
            "• Drink enough water.\n"
            "• Bring ID and list of medicines.\n"
            "• Sleep well the night before.\n"
            "Follow your blood bank’s instructions."
        ),
        "rom": (
            "Donation se pehle:\n"
            "• Normal meal lein; bilkul pehle heavy fatty food avoid karein.\n"
            "• Paani piyein.\n"
            "• ID aur medicines ki list le jayein.\n"
            "• Raat ko achhi neend lein.\n"
            "Blood bank ki instructions follow karein."
        ),
    },
    "hemoglobin": {
        "en": (
            "Hemoglobin is checked before donation. If it is below the centre’s minimum, "
            "you are deferred until it improves (diet, iron, medical advice). "
            "Do not self-medicate — ask a doctor or the blood bank."
        ),
        "rom": (
            "Donation se pehle hemoglobin check hota hai. Agar minimum se kam ho to defer ho sakta hai "
            "jab tak improve na ho. Khud dawai na lein — doctor ya blood bank se poochhein."
        ),
    },
    "contact": {
        "en": (
            "On Find Donor results use **Call** or **WhatsApp** on a donor card "
            "(if the donor shared a number). BloodLink does not store blood or arrange transport."
        ),
        "rom": (
            "Find Donor results pe donor card par **Call** ya **WhatsApp** use karein "
            "(agar number share ho). BloodLink blood store/transport nahi karta."
        ),
    },
    "login": {
        "en": (
            "Donors log in with **phone number + password**. "
            "If you forgot the password, use recovery on the login page if available, "
            "or contact support via Report a Problem."
        ),
        "rom": (
            "Donors **phone + password** se login karte hain. "
            "Password bhool gaye to login page recovery use karein, ya Report a Problem se contact karein."
        ),
    },
    "districts": {
        "en": (
            "BloodLink currently serves **Talagang** and **Chakwal** districts only. "
            "Donors and search are limited to these two districts and listed villages/areas."
        ),
        "rom": (
            "BloodLink abhi sirf **Talagang** aur **Chakwal** districts ke liye hai. "
            "Donors aur search inhi areas tak limited hain."
        ),
    },
    "universal": {
        "en": (
            "Blood group basics:\n"
            "• **O-** is the universal red-cell donor (can generally donate to all groups).\n"
            "• **AB+** is the universal red-cell recipient (can generally receive from all groups).\n"
            "• O+ can donate to all positive groups (O+, A+, B+, AB+).\n"
            "Hospital cross-match is always required before transfusion."
        ),
        "rom": (
            "Blood group basics:\n"
            "• **O-** universal red-cell donor hai (generally sab ko de sakta hai).\n"
            "• **AB+** universal red-cell recipient hai (generally sab se le sakta hai).\n"
            "• O+ positive groups ko de sakta hai (O+, A+, B+, AB+).\n"
            "Hospital cross-match hamesha zaroori hai."
        ),
    },
}


def answer_by_intent(intent: str, lang: str, question: str = "") -> Optional[str]:
    if intent == "compatibility":
        return answer_compatibility(question, lang)
    if intent == "need_blood":
        key = "need_blood"
    elif intent == "find_donor":
        key = "find_donor"
    else:
        key = intent
    block = ANSWERS.get(key)
    if not block:
        return None
    body = block["en"] if lang == "english" else block["rom"]
    groups = extract_groups(question)
    group = groups[0] if groups else "required group"
    # inject actual blood group into template
    if "{group}" in body:
        body = body.replace("{group}", group)
    if intent == "need_blood" and groups:
        if lang == "english":
            body = f"You need **{group}** — follow these steps:\n\n" + body
        else:
            body = f"Aapko **{group}** chahiye — ye steps follow karein:\n\n" + body
    return body + "\n\n" + disclaimer(lang)


def _local_answer(question: str, context: str) -> str:
    if is_unsafe(question):
        return (
            "I cannot help with that request. BloodLink AI only answers questions about blood donation "
            "and using the BloodLink platform.\n\n" + disclaimer("english")
        )

    lang = detect_lang(question)
    intent = detect_intent(question)

    if intent:
        ans = answer_by_intent(intent, lang, question)
        if ans:
            return ans

    # RAG fallback
    ctx = context or ""
    lines = []
    for line in ctx.splitlines():
        s = line.strip()
        if not s:
            continue
        if re.search(r"Page\s+\d+", s, re.I):
            continue
        if "BloodLink Knowledge Base" in s and len(s) < 80:
            continue
        if re.fullmatch(r"[-–—=\s]+", s):
            continue
        if "no relevant information" in s.lower():
            continue
        lines.append(s)
    cleaned = "\n".join(lines)[:900]
    if cleaned and len(cleaned) > 20:
        if lang == "english":
            return "From the BloodLink knowledge base:\n\n" + cleaned + "\n\n" + disclaimer(lang)
        return "Knowledge base se information:\n\n" + cleaned + "\n\n" + disclaimer(lang)

    if lang == "english":
        return (
            "I could not find a specific answer for that.\n\n"
            "Try asking about:\n"
            "• Need blood / find donor (e.g. O+ chahiye)\n"
            "• Blood group compatibility (can O+ donate to A+?)\n"
            "• How to donate / eligibility\n"
            "• Become a donor / fill form\n"
            "• Report a problem, Talagang/Chakwal\n\n"
            + disclaimer(lang)
        )
    return (
        "Is sawal ka specific jawab nahi mila.\n\n"
        "Aap poochh sakte hain:\n"
        "• Blood chahiye / donor dhoondo (jaise O+ chahiye)\n"
        "• Compatibility (can O+ donate to A+?)\n"
        "• Donate kaise karein / eligibility\n"
        "• Donor banne / form fill\n"
        "• Report problem, Talagang/Chakwal\n\n"
        + disclaimer(lang)
    )


def _call_gemini(api_key: str, model: str, system: str, user_content: str):
    model = (model or "gemini-1.5-flash").replace("models/", "").strip()
    if not model.startswith("gemini"):
        model = "gemini-1.5-flash"
    models = [model]
    for alt in ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-flash-latest", "gemini-pro"]:
        if alt not in models:
            models.append(alt)
    last = None
    for m in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user_content}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 900},
        }
        try:
            resp = requests.post(url, json=payload, timeout=45)
            if resp.status_code == 200:
                data = resp.json()
                cands = data.get("candidates") or []
                if cands:
                    parts = cands[0].get("content", {}).get("parts") or []
                    text = "".join(p.get("text", "") for p in parts).strip()
                    if text:
                        return text, None
            last = f"{m}:{resp.status_code}"
            if resp.status_code in (401, 403):
                return None, last
        except requests.Timeout:
            return None, "timeout"
        except Exception as e:
            last = str(e)
    return None, last


def _call_openai(api_key, base_url, model, system, user_content):
    try:
        resp = requests.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_content},
                ],
                "temperature": 0.2,
                "max_tokens": 900,
            },
            timeout=45,
        )
        if resp.status_code != 200:
            return None, f"API {resp.status_code}"
        return resp.json()["choices"][0]["message"]["content"].strip(), None
    except requests.Timeout:
        return None, "timeout"
    except Exception as e:
        return None, str(e)


def ask_bloodlink_ai(question: str) -> Tuple[str, Optional[str]]:
    question = (question or "").strip()
    if not question:
        return "", "Please enter a question."
    if len(question) > 1000:
        return "", "Question is too long. Please keep it under 1000 characters."

    if is_unsafe(question):
        return _local_answer(question, ""), None

    context = get_context_for_question(question)
    lang = detect_lang(question)
    lang_hint = {
        "english": "Reply in clear English with numbered steps when explaining how-to.",
        "urdu": "Reply in Urdu (Arabic script).",
        "roman": "Reply in Roman Urdu.",
    }[lang]

    system = SYSTEM_PROMPT.format(context=context)
    user_content = f"{lang_hint}\n\nUser question:\n{question}"

    api_key = (Config.AI_API_KEY or "").strip()
    base_url = (Config.AI_BASE_URL or "").strip()
    model = (Config.AI_MODEL or "").strip()

    # Strong local path first
    intent = detect_intent(question)
    local = None
    if intent:
        local = answer_by_intent(intent, lang, question)

    if not api_key or api_key.startswith("your-"):
        return local or _local_answer(question, context), None

    is_gemini = (
        api_key.startswith("AQ.")
        or "generativelanguage.googleapis.com" in base_url.lower()
        or "gemini" in base_url.lower()
        or model.lower().startswith("gemini")
    )

    if is_gemini:
        answer, err = _call_gemini(api_key, model or "gemini-1.5-flash", system, user_content)
    else:
        answer, err = _call_openai(
            api_key, base_url or "https://api.openai.com/v1", model or "gpt-4o-mini", system, user_content
        )

    if answer:
        return answer, None

    print(f"[BloodLink AI] API failed: {err}")
    return local or _local_answer(question, context), None