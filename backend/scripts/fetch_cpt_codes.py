#!/usr/bin/env python3
"""Fetch and generate comprehensive CPT-4 codes database.

This script generates a comprehensive CPT code database including:
- E/M codes (99201-99499) with full descriptions
- Surgery codes (10000-69999)
- Radiology codes (70000-79999)
- Pathology/Lab codes (80000-89999)
- Medicine codes (90000-99199)
- Category II codes (performance measurement)
- Category III codes (emerging technology)
- Modifier codes
- RVU values where available

Usage:
    python scripts/fetch_cpt_codes.py

This will generate fixtures/cpt_codes_full.json with 8,000+ codes.
"""

import json
import sys
from pathlib import Path
from typing import Any

# Output paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
FIXTURES_DIR = PROJECT_ROOT / "fixtures"
OUTPUT_FILE = FIXTURES_DIR / "cpt_codes_full.json"
EXISTING_FILE = FIXTURES_DIR / "cpt_codes.json"

# =============================================================================
# CPT MODIFIERS
# =============================================================================
CPT_MODIFIERS = {
    "22": {"description": "Increased procedural services", "usage": "When work is substantially greater than typically required"},
    "23": {"description": "Unusual anesthesia", "usage": "When general anesthesia needed for procedure normally under local"},
    "24": {"description": "Unrelated E/M during postop period", "usage": "E/M service unrelated to original procedure"},
    "25": {"description": "Significant, separately identifiable E/M", "usage": "E/M same day as procedure by same physician"},
    "26": {"description": "Professional component", "usage": "Physician interpretation only, no technical component"},
    "32": {"description": "Mandated services", "usage": "Services required by mandate"},
    "33": {"description": "Preventive service", "usage": "Service is preventive per ACA"},
    "47": {"description": "Anesthesia by surgeon", "usage": "Regional or general anesthesia provided by surgeon"},
    "50": {"description": "Bilateral procedure", "usage": "Procedure performed on both sides"},
    "51": {"description": "Multiple procedures", "usage": "Multiple procedures same session"},
    "52": {"description": "Reduced services", "usage": "Service partially reduced or eliminated"},
    "53": {"description": "Discontinued procedure", "usage": "Procedure discontinued due to patient risk"},
    "54": {"description": "Surgical care only", "usage": "Surgeon provides only surgical care"},
    "55": {"description": "Postoperative management only", "usage": "Surgeon provides only postop care"},
    "56": {"description": "Preoperative management only", "usage": "Surgeon provides only preop care"},
    "57": {"description": "Decision for surgery", "usage": "E/M resulted in decision for surgery"},
    "58": {"description": "Staged procedure", "usage": "Planned procedure during postop period"},
    "59": {"description": "Distinct procedural service", "usage": "Procedure distinct from other services"},
    "62": {"description": "Two surgeons", "usage": "Two surgeons perform distinct parts"},
    "63": {"description": "Procedure on infant", "usage": "Procedure on infant less than 4kg"},
    "66": {"description": "Surgical team", "usage": "Highly complex procedure requiring team"},
    "73": {"description": "Discontinued outpatient procedure before anesthesia", "usage": "Procedure cancelled before anesthesia"},
    "74": {"description": "Discontinued outpatient procedure after anesthesia", "usage": "Procedure cancelled after anesthesia started"},
    "76": {"description": "Repeat procedure same physician", "usage": "Same procedure repeated same day"},
    "77": {"description": "Repeat procedure different physician", "usage": "Same procedure by different physician"},
    "78": {"description": "Unplanned return to OR", "usage": "Return for complication during postop period"},
    "79": {"description": "Unrelated procedure during postop period", "usage": "New procedure unrelated to original"},
    "80": {"description": "Assistant surgeon", "usage": "Surgical assistant services"},
    "81": {"description": "Minimum assistant surgeon", "usage": "Minimal surgical assistant services"},
    "82": {"description": "Assistant surgeon (no qualified resident)", "usage": "Assistant when no resident available"},
    "90": {"description": "Reference (outside) laboratory", "usage": "Lab test performed by outside lab"},
    "91": {"description": "Repeat clinical diagnostic lab test", "usage": "Same lab test repeated same day"},
    "92": {"description": "Alternative laboratory platform testing", "usage": "Test performed on alternative platform"},
    "95": {"description": "Synchronous telemedicine service", "usage": "Real-time audio/video telehealth"},
    "96": {"description": "Habilitative services", "usage": "Service is habilitative"},
    "97": {"description": "Rehabilitative services", "usage": "Service is rehabilitative"},
    "99": {"description": "Multiple modifiers", "usage": "More than one modifier needed"},
    "LT": {"description": "Left side", "usage": "Procedure on left side"},
    "RT": {"description": "Right side", "usage": "Procedure on right side"},
    "TC": {"description": "Technical component", "usage": "Technical component only"},
    "XE": {"description": "Separate encounter", "usage": "Service distinct due to separate encounter"},
    "XP": {"description": "Separate practitioner", "usage": "Service distinct due to different practitioner"},
    "XS": {"description": "Separate structure", "usage": "Service distinct due to separate organ/structure"},
    "XU": {"description": "Unusual non-overlapping service", "usage": "Service distinct and unusual"},
}

# =============================================================================
# CLINICAL SYNONYMS - Maps common terms to CPT codes
# =============================================================================
CLINICAL_SYNONYMS: dict[str, list[str]] = {
    # E/M Office Visits
    "office visit": ["99202", "99203", "99204", "99205", "99211", "99212", "99213", "99214", "99215"],
    "new patient visit": ["99202", "99203", "99204", "99205"],
    "established patient visit": ["99211", "99212", "99213", "99214", "99215"],
    "follow up": ["99211", "99212", "99213", "99214", "99215"],
    "routine visit": ["99213", "99214"],
    "level 3 visit": ["99203", "99213"],
    "level 4 visit": ["99204", "99214"],
    "level 5 visit": ["99205", "99215"],

    # Hospital
    "hospital admission": ["99221", "99222", "99223"],
    "inpatient admission": ["99221", "99222", "99223"],
    "hospital visit": ["99231", "99232", "99233"],
    "subsequent hospital": ["99231", "99232", "99233"],
    "discharge": ["99238", "99239"],
    "hospital discharge": ["99238", "99239"],

    # Emergency
    "er visit": ["99281", "99282", "99283", "99284", "99285"],
    "ed visit": ["99281", "99282", "99283", "99284", "99285"],
    "emergency visit": ["99281", "99282", "99283", "99284", "99285"],
    "emergency room": ["99281", "99282", "99283", "99284", "99285"],

    # Critical Care
    "critical care": ["99291", "99292"],
    "icu": ["99291", "99292"],

    # Consults
    "consultation": ["99242", "99243", "99244", "99245"],
    "consult": ["99242", "99243", "99244", "99245"],
    "inpatient consult": ["99252", "99253", "99254", "99255"],

    # Preventive
    "annual physical": ["99385", "99386", "99387", "99395", "99396", "99397"],
    "wellness visit": ["99381", "99382", "99383", "99384", "99385", "99386", "99387"],
    "physical exam": ["99385", "99386", "99387", "99395", "99396", "99397"],
    "annual wellness": ["G0438", "G0439"],

    # Telehealth
    "telehealth": ["99441", "99442", "99443"],
    "telemedicine": ["99441", "99442", "99443"],
    "phone visit": ["99441", "99442", "99443"],
    "video visit": ["99441", "99442", "99443"],

    # Procedures - GI
    "colonoscopy": ["45378", "45380", "45381", "45382", "45384", "45385", "45386", "45388"],
    "screening colonoscopy": ["45378"],
    "colonoscopy with biopsy": ["45380"],
    "colonoscopy with polypectomy": ["45384", "45385"],
    "egd": ["43235", "43239", "43249", "43251"],
    "upper endoscopy": ["43235", "43239", "43249"],
    "esophagogastroduodenoscopy": ["43235", "43239"],

    # Radiology
    "chest xray": ["71045", "71046", "71047", "71048"],
    "cxr": ["71045", "71046"],
    "chest x-ray": ["71045", "71046"],
    "ct head": ["70450", "70460", "70470"],
    "ct brain": ["70450", "70460", "70470"],
    "ct chest": ["71250", "71260", "71270"],
    "ct abdomen": ["74150", "74160", "74170", "74176", "74177", "74178"],
    "ct pelvis": ["72192", "72193", "72194"],
    "ct abdomen pelvis": ["74176", "74177", "74178"],
    "mri brain": ["70551", "70552", "70553"],
    "mri spine": ["72141", "72146", "72148", "72156", "72157", "72158"],
    "mri lumbar": ["72148", "72149", "72158"],
    "mri cervical": ["72141", "72142", "72156"],
    "mri knee": ["73721", "73722", "73723"],
    "mri shoulder": ["73221", "73222", "73223"],
    "ultrasound abdomen": ["76700", "76705"],
    "abdominal ultrasound": ["76700", "76705"],
    "echocardiogram": ["93306", "93307", "93308"],
    "echo": ["93306", "93307", "93308"],
    "tte": ["93306", "93307"],
    "stress test": ["93015", "93016", "93017", "93018"],
    "nuclear stress": ["78451", "78452"],
    "mammogram": ["77065", "77066", "77067"],
    "dexa": ["77080", "77081"],
    "bone density": ["77080", "77081"],

    # Cardiac
    "ecg": ["93000", "93005", "93010"],
    "ekg": ["93000", "93005", "93010"],
    "electrocardiogram": ["93000", "93005", "93010"],
    "holter": ["93224", "93225", "93226", "93227"],
    "holter monitor": ["93224", "93225", "93226", "93227"],
    "cardiac cath": ["93451", "93452", "93453", "93454", "93455", "93456", "93457", "93458", "93459", "93460", "93461"],
    "heart cath": ["93458", "93459", "93460"],
    "coronary angiography": ["93454", "93455", "93456", "93457", "93458", "93459"],
    "pci": ["92920", "92924", "92928", "92933", "92937", "92941", "92943"],
    "stent": ["92928", "92929", "92933", "92934", "92937", "92938"],
    "pacemaker": ["33206", "33207", "33208", "33210", "33211", "33212", "33213"],
    "defibrillator": ["33249", "33262", "33263", "33264"],
    "icd": ["33249", "33262", "33263", "33264"],

    # Labs
    "cbc": ["85025", "85027"],
    "complete blood count": ["85025", "85027"],
    "cmp": ["80053"],
    "comprehensive metabolic": ["80053"],
    "bmp": ["80048"],
    "basic metabolic": ["80048"],
    "lipid panel": ["80061"],
    "cholesterol": ["80061", "82465"],
    "hemoglobin a1c": ["83036"],
    "hba1c": ["83036"],
    "a1c": ["83036"],
    "tsh": ["84443"],
    "thyroid": ["84436", "84439", "84443"],
    "psa": ["84153", "84154"],
    "urinalysis": ["81001", "81002", "81003"],
    "ua": ["81001", "81002", "81003"],
    "urine culture": ["87086", "87088"],
    "blood culture": ["87040"],
    "strep test": ["87880"],
    "flu test": ["87804"],
    "covid test": ["87635", "87426"],
    "pt inr": ["85610", "85730"],
    "coagulation": ["85610", "85730"],
    "bun": ["84520"],
    "creatinine": ["82565"],
    "potassium": ["84132"],
    "sodium": ["84295"],
    "glucose": ["82947", "82950"],
    "liver function": ["80076"],
    "hepatic panel": ["80076"],
    "troponin": ["84484"],
    "bnp": ["83880"],

    # Injections
    "injection": ["96372", "96373", "96374", "96375"],
    "im injection": ["96372"],
    "iv injection": ["96374"],
    "joint injection": ["20600", "20605", "20610"],
    "knee injection": ["20610"],
    "shoulder injection": ["20610"],
    "steroid injection": ["20610", "62320", "62321", "62322", "62323"],
    "epidural": ["62320", "62321", "62322", "62323", "62324", "62325", "62326", "62327"],
    "trigger point": ["20552", "20553"],
    "botox": ["64612", "64615", "64616", "64617", "64642", "64643", "64644", "64645", "64646", "64647"],

    # Vaccines
    "flu shot": ["90658", "90686", "90688"],
    "flu vaccine": ["90658", "90686", "90688"],
    "influenza vaccine": ["90658", "90686", "90688"],
    "tdap": ["90715"],
    "tetanus": ["90714", "90715"],
    "pneumonia vaccine": ["90670", "90671", "90732"],
    "shingles vaccine": ["90750"],
    "covid vaccine": ["91300", "91301", "91302", "91303", "91304", "91305", "91306", "91307", "91308", "91309", "91310", "91311", "91312"],
    "hepatitis b vaccine": ["90740", "90743", "90744", "90746", "90747"],
    "mmr": ["90707"],

    # Surgery - Orthopedic
    "knee arthroscopy": ["29870", "29871", "29873", "29874", "29875", "29876", "29877", "29879", "29880", "29881", "29882", "29883", "29884", "29885", "29886", "29887", "29888"],
    "knee scope": ["29870", "29871", "29873", "29874", "29875", "29876", "29877", "29879", "29880", "29881"],
    "meniscectomy": ["29880", "29881"],
    "acl repair": ["29888"],
    "total knee replacement": ["27447"],
    "tkr": ["27447"],
    "total hip replacement": ["27130"],
    "thr": ["27130"],
    "hip replacement": ["27130"],
    "rotator cuff repair": ["23410", "23412", "23420", "29827"],
    "carpal tunnel": ["64721"],
    "carpal tunnel release": ["64721"],
    "fracture repair": ["27236", "27244", "27245", "27269"],

    # Surgery - General
    "appendectomy": ["44950", "44955", "44960", "44970"],
    "cholecystectomy": ["47562", "47563", "47564", "47600", "47605", "47610"],
    "lap chole": ["47562", "47563", "47564"],
    "gallbladder removal": ["47562", "47563", "47564"],
    "hernia repair": ["49491", "49492", "49495", "49496", "49500", "49501", "49505", "49507", "49520", "49521", "49525", "49550", "49553", "49555", "49557", "49560", "49561", "49565", "49566", "49568", "49570", "49572", "49580", "49582", "49585", "49587", "49590"],
    "inguinal hernia": ["49505", "49507", "49520", "49521", "49525", "49650"],
    "umbilical hernia": ["49580", "49582", "49585", "49587"],
    "hemorrhoidectomy": ["46250", "46255", "46257", "46258", "46260", "46261", "46262"],
    "biopsy": ["11102", "11104", "11106"],
    "skin biopsy": ["11102", "11104", "11106"],
    "excision": ["11400", "11401", "11402", "11403", "11404", "11406"],
    "lesion removal": ["11400", "11401", "11402", "11403", "11404", "11406"],
    "wound repair": ["12001", "12002", "12004", "12005", "12006", "12007", "12011", "12013", "12014", "12015", "12016", "12017", "12018", "12020", "12021", "12031", "12032", "12034", "12035", "12036", "12037", "12041", "12042", "12044", "12045", "12046", "12047", "12051", "12052", "12053", "12054", "12055", "12056", "12057"],
    "laceration repair": ["12001", "12002", "12004", "12005", "12006", "12007"],

    # Physical Therapy
    "physical therapy": ["97110", "97112", "97116", "97140", "97530", "97535", "97542", "97750", "97755"],
    "pt": ["97110", "97112", "97116", "97140"],
    "therapeutic exercise": ["97110"],
    "manual therapy": ["97140"],
    "gait training": ["97116"],
    "neuromuscular reeducation": ["97112"],

    # Mental Health
    "psychotherapy": ["90832", "90834", "90837", "90847"],
    "therapy session": ["90832", "90834", "90837"],
    "counseling": ["90832", "90834", "90837", "90847"],
    "psychiatric evaluation": ["90791", "90792"],
    "psych eval": ["90791", "90792"],

    # Sleep
    "sleep study": ["95810", "95811"],
    "polysomnography": ["95810", "95811"],
    "cpap titration": ["95811"],

    # Pulmonary
    "pulmonary function": ["94010", "94060", "94070", "94375", "94726", "94727", "94728", "94729"],
    "pft": ["94010", "94060", "94726", "94727", "94728", "94729"],
    "spirometry": ["94010", "94060"],
    "bronchoscopy": ["31622", "31623", "31624", "31625", "31628", "31629", "31632", "31633"],

    # Ophthalmology
    "cataract surgery": ["66982", "66984"],
    "cataract removal": ["66982", "66984"],
    "eye exam": ["92002", "92004", "92012", "92014"],
    "refraction": ["92015"],
    "visual field": ["92081", "92082", "92083"],

    # Dialysis
    "dialysis": ["90935", "90937", "90945", "90947", "90951", "90952", "90953", "90954", "90955", "90956", "90957", "90958", "90959", "90960", "90961", "90962", "90963", "90964", "90965", "90966", "90967", "90968", "90969", "90970"],
    "hemodialysis": ["90935", "90937"],

    # Chemotherapy
    "chemotherapy": ["96401", "96402", "96405", "96406", "96409", "96411", "96413", "96415", "96416", "96417", "96420", "96422", "96423", "96425", "96440", "96446", "96450"],
    "chemo": ["96401", "96402", "96409", "96411", "96413", "96415"],
    "infusion": ["96360", "96361", "96365", "96366", "96367", "96368", "96369", "96370", "96371", "96374", "96375", "96376", "96377"],

    # Wound Care
    "wound care": ["97597", "97598", "97602", "97605", "97606", "97607", "97608"],
    "debridement": ["11042", "11043", "11044", "11045", "11046", "11047", "97597", "97598"],
    "negative pressure wound": ["97605", "97606", "97607", "97608"],
}


# =============================================================================
# E/M CODES (99201-99499) - COMPREHENSIVE
# =============================================================================
def generate_em_codes() -> list[dict[str, Any]]:
    """Generate all E/M codes with detailed descriptions and RVUs."""
    codes = []

    # Office/Outpatient New Patient (99202-99205)
    office_new = [
        {"code": "99202", "desc": "Office/outpatient visit, new patient, straightforward MDM, 15-29 min", "rvu": 0.93, "time": 22},
        {"code": "99203", "desc": "Office/outpatient visit, new patient, low MDM, 30-44 min", "rvu": 1.60, "time": 37},
        {"code": "99204", "desc": "Office/outpatient visit, new patient, moderate MDM, 45-59 min", "rvu": 2.60, "time": 52},
        {"code": "99205", "desc": "Office/outpatient visit, new patient, high MDM, 60-74 min", "rvu": 3.50, "time": 67},
    ]

    # Office/Outpatient Established Patient (99211-99215)
    office_est = [
        {"code": "99211", "desc": "Office/outpatient visit, established patient, minimal problem, 5 min", "rvu": 0.18, "time": 5},
        {"code": "99212", "desc": "Office/outpatient visit, established patient, straightforward MDM, 10-19 min", "rvu": 0.70, "time": 15},
        {"code": "99213", "desc": "Office/outpatient visit, established patient, low MDM, 20-29 min", "rvu": 1.30, "time": 24},
        {"code": "99214", "desc": "Office/outpatient visit, established patient, moderate MDM, 30-39 min", "rvu": 1.92, "time": 34},
        {"code": "99215", "desc": "Office/outpatient visit, established patient, high MDM, 40-54 min", "rvu": 2.80, "time": 47},
    ]

    # Initial Hospital Care (99221-99223)
    hospital_init = [
        {"code": "99221", "desc": "Initial hospital care, low/moderate MDM, 40 min", "rvu": 2.00, "time": 40},
        {"code": "99222", "desc": "Initial hospital care, moderate MDM, 55 min", "rvu": 2.61, "time": 55},
        {"code": "99223", "desc": "Initial hospital care, high MDM, 75 min", "rvu": 3.86, "time": 75},
    ]

    # Subsequent Hospital Care (99231-99233)
    hospital_sub = [
        {"code": "99231", "desc": "Subsequent hospital care, straightforward/low MDM, 25 min", "rvu": 0.76, "time": 25},
        {"code": "99232", "desc": "Subsequent hospital care, moderate MDM, 35 min", "rvu": 1.39, "time": 35},
        {"code": "99233", "desc": "Subsequent hospital care, high MDM, 50 min", "rvu": 2.00, "time": 50},
    ]

    # Observation Care (99218-99220, 99224-99226)
    observation = [
        {"code": "99218", "desc": "Initial observation care, low/moderate MDM, 40 min", "rvu": 1.92, "time": 40},
        {"code": "99219", "desc": "Initial observation care, moderate MDM, 50 min", "rvu": 2.60, "time": 50},
        {"code": "99220", "desc": "Initial observation care, high MDM, 70 min", "rvu": 3.56, "time": 70},
        {"code": "99224", "desc": "Subsequent observation care, straightforward/low MDM, 15 min", "rvu": 0.76, "time": 15},
        {"code": "99225", "desc": "Subsequent observation care, moderate MDM, 25 min", "rvu": 1.30, "time": 25},
        {"code": "99226", "desc": "Subsequent observation care, high MDM, 40 min", "rvu": 1.92, "time": 40},
    ]

    # Hospital Discharge (99238-99239)
    discharge = [
        {"code": "99238", "desc": "Hospital discharge day management, 30 min or less", "rvu": 1.28, "time": 30},
        {"code": "99239", "desc": "Hospital discharge day management, more than 30 min", "rvu": 1.90, "time": 45},
    ]

    # Consultations - Office (99241-99245)
    consult_office = [
        {"code": "99242", "desc": "Office consultation, straightforward MDM, 20 min", "rvu": 0.65, "time": 20},
        {"code": "99243", "desc": "Office consultation, low MDM, 30 min", "rvu": 1.11, "time": 30},
        {"code": "99244", "desc": "Office consultation, moderate MDM, 40 min", "rvu": 1.67, "time": 40},
        {"code": "99245", "desc": "Office consultation, high MDM, 55 min", "rvu": 2.25, "time": 55},
    ]

    # Consultations - Inpatient (99251-99255)
    consult_inpt = [
        {"code": "99252", "desc": "Inpatient consultation, straightforward MDM, 35 min", "rvu": 0.80, "time": 35},
        {"code": "99253", "desc": "Inpatient consultation, low MDM, 45 min", "rvu": 1.17, "time": 45},
        {"code": "99254", "desc": "Inpatient consultation, moderate MDM, 60 min", "rvu": 1.74, "time": 60},
        {"code": "99255", "desc": "Inpatient consultation, high MDM, 80 min", "rvu": 2.29, "time": 80},
    ]

    # Emergency Department (99281-99285)
    emergency = [
        {"code": "99281", "desc": "Emergency department visit, self-limited/minor problem", "rvu": 0.45, "time": 10},
        {"code": "99282", "desc": "Emergency department visit, low severity problem", "rvu": 0.88, "time": 20},
        {"code": "99283", "desc": "Emergency department visit, moderate severity problem", "rvu": 1.42, "time": 30},
        {"code": "99284", "desc": "Emergency department visit, high severity problem, urgent evaluation", "rvu": 2.56, "time": 45},
        {"code": "99285", "desc": "Emergency department visit, high severity problem, immediate threat to life", "rvu": 3.80, "time": 60},
    ]

    # Critical Care (99291-99292)
    critical = [
        {"code": "99291", "desc": "Critical care, first 30-74 minutes", "rvu": 4.50, "time": 60},
        {"code": "99292", "desc": "Critical care, each additional 30 minutes", "rvu": 2.25, "time": 30},
    ]

    # Nursing Facility (99304-99318)
    nursing = [
        {"code": "99304", "desc": "Nursing facility initial care, low MDM", "rvu": 1.50, "time": 30},
        {"code": "99305", "desc": "Nursing facility initial care, moderate MDM", "rvu": 2.10, "time": 45},
        {"code": "99306", "desc": "Nursing facility initial care, high MDM", "rvu": 2.80, "time": 60},
        {"code": "99307", "desc": "Nursing facility subsequent care, straightforward MDM", "rvu": 0.65, "time": 10},
        {"code": "99308", "desc": "Nursing facility subsequent care, low MDM", "rvu": 0.95, "time": 15},
        {"code": "99309", "desc": "Nursing facility subsequent care, moderate MDM", "rvu": 1.30, "time": 25},
        {"code": "99310", "desc": "Nursing facility subsequent care, high MDM", "rvu": 1.92, "time": 35},
        {"code": "99315", "desc": "Nursing facility discharge day, 30 min or less", "rvu": 1.28, "time": 30},
        {"code": "99316", "desc": "Nursing facility discharge day, more than 30 min", "rvu": 1.90, "time": 45},
        {"code": "99318", "desc": "Nursing facility annual assessment", "rvu": 1.30, "time": 30},
    ]

    # Domiciliary/Rest Home (99324-99337)
    domiciliary = [
        {"code": "99324", "desc": "Domiciliary/rest home visit, new patient, straightforward MDM", "rvu": 0.70, "time": 15},
        {"code": "99325", "desc": "Domiciliary/rest home visit, new patient, low MDM", "rvu": 1.10, "time": 25},
        {"code": "99326", "desc": "Domiciliary/rest home visit, new patient, moderate MDM", "rvu": 1.65, "time": 35},
        {"code": "99327", "desc": "Domiciliary/rest home visit, new patient, moderate MDM, 60 min", "rvu": 2.15, "time": 60},
        {"code": "99328", "desc": "Domiciliary/rest home visit, new patient, high MDM", "rvu": 2.75, "time": 75},
        {"code": "99334", "desc": "Domiciliary/rest home visit, established patient, straightforward MDM", "rvu": 0.50, "time": 10},
        {"code": "99335", "desc": "Domiciliary/rest home visit, established patient, low MDM", "rvu": 0.75, "time": 15},
        {"code": "99336", "desc": "Domiciliary/rest home visit, established patient, moderate MDM", "rvu": 1.25, "time": 25},
        {"code": "99337", "desc": "Domiciliary/rest home visit, established patient, high MDM", "rvu": 1.80, "time": 40},
    ]

    # Home Services (99341-99350)
    home = [
        {"code": "99341", "desc": "Home visit, new patient, straightforward MDM", "rvu": 1.00, "time": 20},
        {"code": "99342", "desc": "Home visit, new patient, low MDM", "rvu": 1.45, "time": 30},
        {"code": "99343", "desc": "Home visit, new patient, moderate MDM", "rvu": 2.00, "time": 45},
        {"code": "99344", "desc": "Home visit, new patient, moderate MDM, 60 min", "rvu": 2.60, "time": 60},
        {"code": "99345", "desc": "Home visit, new patient, high MDM", "rvu": 3.25, "time": 75},
        {"code": "99347", "desc": "Home visit, established patient, straightforward MDM", "rvu": 0.75, "time": 15},
        {"code": "99348", "desc": "Home visit, established patient, low MDM", "rvu": 1.10, "time": 25},
        {"code": "99349", "desc": "Home visit, established patient, moderate MDM", "rvu": 1.60, "time": 40},
        {"code": "99350", "desc": "Home visit, established patient, high MDM", "rvu": 2.25, "time": 60},
    ]

    # Prolonged Services (99354-99360, 99415-99417)
    prolonged = [
        {"code": "99354", "desc": "Prolonged service, outpatient, first hour", "rvu": 1.77, "time": 60},
        {"code": "99355", "desc": "Prolonged service, outpatient, each additional 30 min", "rvu": 1.77, "time": 30},
        {"code": "99356", "desc": "Prolonged service, inpatient, first hour", "rvu": 1.71, "time": 60},
        {"code": "99357", "desc": "Prolonged service, inpatient, each additional 30 min", "rvu": 1.71, "time": 30},
        {"code": "99358", "desc": "Prolonged clinical staff services, first hour", "rvu": 1.77, "time": 60},
        {"code": "99359", "desc": "Prolonged clinical staff services, each additional 30 min", "rvu": 0.88, "time": 30},
        {"code": "99415", "desc": "Prolonged clinical staff service, first 15 min", "rvu": 0.61, "time": 15},
        {"code": "99416", "desc": "Prolonged clinical staff service, each additional 15 min", "rvu": 0.61, "time": 15},
        {"code": "99417", "desc": "Prolonged outpatient E/M, each 15 min beyond total time", "rvu": 0.61, "time": 15},
    ]

    # Care Management (99487-99491)
    care_mgmt = [
        {"code": "99487", "desc": "Complex chronic care management, 60+ min", "rvu": 1.89, "time": 60},
        {"code": "99489", "desc": "Complex chronic care management, each additional 30 min", "rvu": 0.94, "time": 30},
        {"code": "99490", "desc": "Chronic care management, 20+ min", "rvu": 0.61, "time": 20},
        {"code": "99491", "desc": "Chronic care management by physician, 30+ min", "rvu": 1.20, "time": 30},
    ]

    # Preventive Medicine New (99381-99387)
    prev_new = [
        {"code": "99381", "desc": "Preventive medicine, new patient, infant (under 1 year)", "rvu": 1.50, "time": 30},
        {"code": "99382", "desc": "Preventive medicine, new patient, early childhood (1-4 years)", "rvu": 1.55, "time": 30},
        {"code": "99383", "desc": "Preventive medicine, new patient, late childhood (5-11 years)", "rvu": 1.55, "time": 30},
        {"code": "99384", "desc": "Preventive medicine, new patient, adolescent (12-17 years)", "rvu": 1.68, "time": 35},
        {"code": "99385", "desc": "Preventive medicine, new patient, 18-39 years", "rvu": 1.68, "time": 35},
        {"code": "99386", "desc": "Preventive medicine, new patient, 40-64 years", "rvu": 2.00, "time": 40},
        {"code": "99387", "desc": "Preventive medicine, new patient, 65+ years", "rvu": 2.14, "time": 45},
    ]

    # Preventive Medicine Established (99391-99397)
    prev_est = [
        {"code": "99391", "desc": "Preventive medicine, established patient, infant (under 1 year)", "rvu": 1.37, "time": 25},
        {"code": "99392", "desc": "Preventive medicine, established patient, early childhood (1-4 years)", "rvu": 1.37, "time": 25},
        {"code": "99393", "desc": "Preventive medicine, established patient, late childhood (5-11 years)", "rvu": 1.37, "time": 25},
        {"code": "99394", "desc": "Preventive medicine, established patient, adolescent (12-17 years)", "rvu": 1.50, "time": 30},
        {"code": "99395", "desc": "Preventive medicine, established patient, 18-39 years", "rvu": 1.50, "time": 30},
        {"code": "99396", "desc": "Preventive medicine, established patient, 40-64 years", "rvu": 1.68, "time": 35},
        {"code": "99397", "desc": "Preventive medicine, established patient, 65+ years", "rvu": 1.82, "time": 40},
    ]

    # Counseling (99401-99412)
    counseling = [
        {"code": "99401", "desc": "Preventive counseling, individual, 15 min", "rvu": 0.48, "time": 15},
        {"code": "99402", "desc": "Preventive counseling, individual, 30 min", "rvu": 0.98, "time": 30},
        {"code": "99403", "desc": "Preventive counseling, individual, 45 min", "rvu": 1.43, "time": 45},
        {"code": "99404", "desc": "Preventive counseling, individual, 60 min", "rvu": 1.88, "time": 60},
        {"code": "99406", "desc": "Smoking cessation counseling, 3-10 min", "rvu": 0.24, "time": 7},
        {"code": "99407", "desc": "Smoking cessation counseling, greater than 10 min", "rvu": 0.50, "time": 15},
        {"code": "99408", "desc": "Alcohol/substance screening, 15-30 min", "rvu": 0.48, "time": 22},
        {"code": "99409", "desc": "Alcohol/substance screening, greater than 30 min", "rvu": 0.98, "time": 45},
        {"code": "99411", "desc": "Preventive counseling, group, 30 min", "rvu": 0.25, "time": 30},
        {"code": "99412", "desc": "Preventive counseling, group, 60 min", "rvu": 0.50, "time": 60},
    ]

    # Telephone Services (99441-99443)
    telephone = [
        {"code": "99441", "desc": "Telephone E/M service, 5-10 minutes", "rvu": 0.25, "time": 8},
        {"code": "99442", "desc": "Telephone E/M service, 11-20 minutes", "rvu": 0.50, "time": 15},
        {"code": "99443", "desc": "Telephone E/M service, 21-30 minutes", "rvu": 0.75, "time": 25},
    ]

    # Online Services (99421-99423, 99458)
    online = [
        {"code": "99421", "desc": "Online digital E/M service, 5-10 minutes", "rvu": 0.25, "time": 8},
        {"code": "99422", "desc": "Online digital E/M service, 11-20 minutes", "rvu": 0.50, "time": 15},
        {"code": "99423", "desc": "Online digital E/M service, 21+ minutes", "rvu": 0.75, "time": 25},
        {"code": "99458", "desc": "Remote physiologic monitoring treatment, each additional 20 min", "rvu": 0.61, "time": 20},
    ]

    # Interprofessional Consultation (99446-99449, 99451-99452)
    interpro = [
        {"code": "99446", "desc": "Interprofessional telephone/internet consultation, 5-10 min", "rvu": 0.35, "time": 8},
        {"code": "99447", "desc": "Interprofessional telephone/internet consultation, 11-20 min", "rvu": 0.70, "time": 15},
        {"code": "99448", "desc": "Interprofessional telephone/internet consultation, 21-30 min", "rvu": 1.05, "time": 25},
        {"code": "99449", "desc": "Interprofessional telephone/internet consultation, 31+ min", "rvu": 1.40, "time": 35},
        {"code": "99451", "desc": "Interprofessional telephone/internet assessment, 5+ min", "rvu": 0.35, "time": 5},
        {"code": "99452", "desc": "Interprofessional telephone/internet referral, 16-30 min", "rvu": 0.70, "time": 23},
    ]

    # Transitional Care (99495-99496)
    transitional = [
        {"code": "99495", "desc": "Transitional care management, moderate complexity, face-to-face within 14 days", "rvu": 2.36, "time": 45},
        {"code": "99496", "desc": "Transitional care management, high complexity, face-to-face within 7 days", "rvu": 3.10, "time": 60},
    ]

    # Advance Care Planning (99497-99498)
    acp = [
        {"code": "99497", "desc": "Advance care planning, first 30 minutes", "rvu": 1.50, "time": 30},
        {"code": "99498", "desc": "Advance care planning, each additional 30 minutes", "rvu": 1.40, "time": 30},
    ]

    # Combine all E/M codes
    all_em = (
        office_new + office_est + hospital_init + hospital_sub + observation +
        discharge + consult_office + consult_inpt + emergency + critical +
        nursing + domiciliary + home + prolonged + care_mgmt +
        prev_new + prev_est + counseling + telephone + online + interpro +
        transitional + acp
    )

    for em in all_em:
        codes.append({
            "concept_code": em["code"],
            "concept_name": em["desc"],
            "category": "Evaluation and Management",
            "work_rvu": em["rvu"],
            "typical_time_minutes": em["time"],
            "synonyms": [],
            "documentation_requirements": get_em_documentation(em["code"]),
        })

    return codes


def get_em_documentation(code: str) -> list[str]:
    """Get documentation requirements for E/M codes."""
    base_reqs = ["Chief complaint", "History of present illness"]

    if code.startswith("9921") or code.startswith("9920"):
        # Office visits
        return base_reqs + [
            "Review of systems (as appropriate)",
            "Past medical/family/social history (as appropriate)",
            "Medical decision making complexity OR total time",
            "Assessment and plan",
        ]
    elif code.startswith("9922"):
        # Hospital care
        return base_reqs + [
            "Comprehensive review of systems",
            "Complete past/family/social history",
            "Physical examination",
            "Medical decision making",
            "Admission orders/plan",
        ]
    elif code.startswith("9928"):
        # Emergency
        return base_reqs + [
            "Physical examination",
            "Medical decision making",
            "Emergency medical condition documentation",
        ]
    elif code.startswith("9929"):
        # Critical care
        return [
            "Critical illness/injury documentation",
            "Time spent in critical care activities",
            "Vital organ dysfunction",
            "Direct personal management",
        ]
    elif code.startswith("993"):
        # Preventive
        return [
            "Age-appropriate history",
            "Age-appropriate examination",
            "Counseling/anticipatory guidance",
            "Risk factor assessment",
        ]
    else:
        return base_reqs + ["Medical decision making", "Assessment and plan"]


# =============================================================================
# SURGERY CODES (10000-69999)
# =============================================================================
def generate_surgery_codes() -> list[dict[str, Any]]:
    """Generate common surgery codes with descriptions and RVUs."""
    codes = []

    surgery_codes = [
        # Integumentary (10000-19999)
        {"code": "10021", "desc": "Fine needle aspiration biopsy without imaging", "rvu": 1.10, "cat": "Integumentary"},
        {"code": "10060", "desc": "Incision and drainage of abscess, simple", "rvu": 1.22, "cat": "Integumentary"},
        {"code": "10061", "desc": "Incision and drainage of abscess, complicated", "rvu": 2.32, "cat": "Integumentary"},
        {"code": "10080", "desc": "Incision and drainage of pilonidal cyst, simple", "rvu": 1.67, "cat": "Integumentary"},
        {"code": "10120", "desc": "Incision and removal of foreign body, simple", "rvu": 1.40, "cat": "Integumentary"},
        {"code": "10121", "desc": "Incision and removal of foreign body, complicated", "rvu": 2.77, "cat": "Integumentary"},
        {"code": "10140", "desc": "Incision and drainage of hematoma, seroma, fluid collection", "rvu": 1.67, "cat": "Integumentary"},
        {"code": "10160", "desc": "Puncture aspiration of abscess, hematoma, cyst", "rvu": 0.80, "cat": "Integumentary"},
        {"code": "11000", "desc": "Debridement of extensive skin, up to 10% body surface", "rvu": 0.95, "cat": "Integumentary"},
        {"code": "11042", "desc": "Debridement, subcutaneous tissue, first 20 sq cm", "rvu": 1.01, "cat": "Integumentary"},
        {"code": "11043", "desc": "Debridement, muscle/fascia, first 20 sq cm", "rvu": 1.76, "cat": "Integumentary"},
        {"code": "11044", "desc": "Debridement, bone, first 20 sq cm", "rvu": 2.76, "cat": "Integumentary"},
        {"code": "11102", "desc": "Tangential biopsy of skin, single lesion", "rvu": 0.54, "cat": "Integumentary"},
        {"code": "11104", "desc": "Punch biopsy of skin, single lesion", "rvu": 0.61, "cat": "Integumentary"},
        {"code": "11106", "desc": "Incisional biopsy of skin, single lesion", "rvu": 1.05, "cat": "Integumentary"},
        {"code": "11200", "desc": "Removal of skin tags, up to 15 lesions", "rvu": 0.70, "cat": "Integumentary"},
        {"code": "11300", "desc": "Shaving of lesion, trunk/arms/legs, 0.5 cm or less", "rvu": 0.56, "cat": "Integumentary"},
        {"code": "11305", "desc": "Shaving of lesion, scalp/neck/hands/feet, 0.5 cm or less", "rvu": 0.54, "cat": "Integumentary"},
        {"code": "11310", "desc": "Shaving of lesion, face, 0.5 cm or less", "rvu": 0.61, "cat": "Integumentary"},
        {"code": "11400", "desc": "Excision benign lesion, trunk/arms/legs, 0.5 cm or less", "rvu": 0.90, "cat": "Integumentary"},
        {"code": "11401", "desc": "Excision benign lesion, trunk/arms/legs, 0.6-1.0 cm", "rvu": 1.10, "cat": "Integumentary"},
        {"code": "11402", "desc": "Excision benign lesion, trunk/arms/legs, 1.1-2.0 cm", "rvu": 1.35, "cat": "Integumentary"},
        {"code": "11403", "desc": "Excision benign lesion, trunk/arms/legs, 2.1-3.0 cm", "rvu": 1.60, "cat": "Integumentary"},
        {"code": "11404", "desc": "Excision benign lesion, trunk/arms/legs, 3.1-4.0 cm", "rvu": 2.05, "cat": "Integumentary"},
        {"code": "11406", "desc": "Excision benign lesion, trunk/arms/legs, over 4.0 cm", "rvu": 2.89, "cat": "Integumentary"},
        {"code": "11420", "desc": "Excision benign lesion, scalp/neck/hands/feet, 0.5 cm or less", "rvu": 1.04, "cat": "Integumentary"},
        {"code": "11440", "desc": "Excision benign lesion, face, 0.5 cm or less", "rvu": 1.20, "cat": "Integumentary"},
        {"code": "11600", "desc": "Excision malignant lesion, trunk/arms/legs, 0.5 cm or less", "rvu": 1.35, "cat": "Integumentary"},
        {"code": "11601", "desc": "Excision malignant lesion, trunk/arms/legs, 0.6-1.0 cm", "rvu": 1.73, "cat": "Integumentary"},
        {"code": "11602", "desc": "Excision malignant lesion, trunk/arms/legs, 1.1-2.0 cm", "rvu": 2.23, "cat": "Integumentary"},
        {"code": "11603", "desc": "Excision malignant lesion, trunk/arms/legs, 2.1-3.0 cm", "rvu": 2.64, "cat": "Integumentary"},
        {"code": "11604", "desc": "Excision malignant lesion, trunk/arms/legs, 3.1-4.0 cm", "rvu": 3.16, "cat": "Integumentary"},
        {"code": "11606", "desc": "Excision malignant lesion, trunk/arms/legs, over 4.0 cm", "rvu": 3.95, "cat": "Integumentary"},
        {"code": "11620", "desc": "Excision malignant lesion, scalp/neck/hands/feet, 0.5 cm or less", "rvu": 1.45, "cat": "Integumentary"},
        {"code": "11640", "desc": "Excision malignant lesion, face, 0.5 cm or less", "rvu": 1.72, "cat": "Integumentary"},
        {"code": "11719", "desc": "Trimming of nondystrophic nails, any number", "rvu": 0.17, "cat": "Integumentary"},
        {"code": "11720", "desc": "Debridement of nails, 1-5", "rvu": 0.26, "cat": "Integumentary"},
        {"code": "11721", "desc": "Debridement of nails, 6 or more", "rvu": 0.37, "cat": "Integumentary"},
        {"code": "11730", "desc": "Avulsion of nail plate, partial or complete, simple", "rvu": 0.66, "cat": "Integumentary"},
        {"code": "11750", "desc": "Excision of nail and nail matrix, permanent removal", "rvu": 1.30, "cat": "Integumentary"},
        {"code": "11765", "desc": "Wedge excision of skin of nail fold", "rvu": 0.89, "cat": "Integumentary"},
        {"code": "11770", "desc": "Excision of pilonidal cyst or sinus, simple", "rvu": 2.20, "cat": "Integumentary"},
        {"code": "11771", "desc": "Excision of pilonidal cyst or sinus, extensive", "rvu": 4.63, "cat": "Integumentary"},
        {"code": "11772", "desc": "Excision of pilonidal cyst or sinus, complicated", "rvu": 7.70, "cat": "Integumentary"},
        {"code": "11900", "desc": "Injection, intralesional, up to 7 lesions", "rvu": 0.56, "cat": "Integumentary"},
        {"code": "11901", "desc": "Injection, intralesional, more than 7 lesions", "rvu": 0.88, "cat": "Integumentary"},
        {"code": "11920", "desc": "Tattooing, intradermal, up to 6 sq cm", "rvu": 1.00, "cat": "Integumentary"},
        {"code": "11950", "desc": "Subcutaneous injection of filling material, 1 cc or less", "rvu": 0.62, "cat": "Integumentary"},
        {"code": "11960", "desc": "Insertion of tissue expander", "rvu": 4.69, "cat": "Integumentary"},
        {"code": "11970", "desc": "Replacement of tissue expander with permanent implant", "rvu": 6.50, "cat": "Integumentary"},

        # Wound Repair (12001-13160)
        {"code": "12001", "desc": "Simple repair superficial wounds, 2.5 cm or less", "rvu": 0.86, "cat": "Integumentary"},
        {"code": "12002", "desc": "Simple repair superficial wounds, 2.6-7.5 cm", "rvu": 1.14, "cat": "Integumentary"},
        {"code": "12004", "desc": "Simple repair superficial wounds, 7.6-12.5 cm", "rvu": 1.43, "cat": "Integumentary"},
        {"code": "12005", "desc": "Simple repair superficial wounds, 12.6-20.0 cm", "rvu": 1.79, "cat": "Integumentary"},
        {"code": "12006", "desc": "Simple repair superficial wounds, 20.1-30.0 cm", "rvu": 2.18, "cat": "Integumentary"},
        {"code": "12007", "desc": "Simple repair superficial wounds, over 30.0 cm", "rvu": 2.94, "cat": "Integumentary"},
        {"code": "12011", "desc": "Simple repair superficial wounds, face, 2.5 cm or less", "rvu": 1.01, "cat": "Integumentary"},
        {"code": "12013", "desc": "Simple repair superficial wounds, face, 2.6-5.0 cm", "rvu": 1.31, "cat": "Integumentary"},
        {"code": "12014", "desc": "Simple repair superficial wounds, face, 5.1-7.5 cm", "rvu": 1.63, "cat": "Integumentary"},
        {"code": "12015", "desc": "Simple repair superficial wounds, face, 7.6-12.5 cm", "rvu": 2.00, "cat": "Integumentary"},
        {"code": "12031", "desc": "Intermediate repair, scalp/trunk/extremities, 2.5 cm or less", "rvu": 1.56, "cat": "Integumentary"},
        {"code": "12032", "desc": "Intermediate repair, scalp/trunk/extremities, 2.6-7.5 cm", "rvu": 2.10, "cat": "Integumentary"},
        {"code": "12034", "desc": "Intermediate repair, scalp/trunk/extremities, 7.6-12.5 cm", "rvu": 2.53, "cat": "Integumentary"},
        {"code": "12035", "desc": "Intermediate repair, scalp/trunk/extremities, 12.6-20.0 cm", "rvu": 3.30, "cat": "Integumentary"},
        {"code": "12041", "desc": "Intermediate repair, neck/hands/feet, 2.5 cm or less", "rvu": 1.91, "cat": "Integumentary"},
        {"code": "12042", "desc": "Intermediate repair, neck/hands/feet, 2.6-7.5 cm", "rvu": 2.39, "cat": "Integumentary"},
        {"code": "12051", "desc": "Intermediate repair, face, 2.5 cm or less", "rvu": 2.13, "cat": "Integumentary"},
        {"code": "12052", "desc": "Intermediate repair, face, 2.6-5.0 cm", "rvu": 2.63, "cat": "Integumentary"},
        {"code": "12053", "desc": "Intermediate repair, face, 5.1-7.5 cm", "rvu": 3.13, "cat": "Integumentary"},
        {"code": "13100", "desc": "Repair complex, trunk, 1.1-2.5 cm", "rvu": 2.49, "cat": "Integumentary"},
        {"code": "13101", "desc": "Repair complex, trunk, 2.6-7.5 cm", "rvu": 3.38, "cat": "Integumentary"},
        {"code": "13120", "desc": "Repair complex, scalp/arms/legs, 1.1-2.5 cm", "rvu": 2.57, "cat": "Integumentary"},
        {"code": "13121", "desc": "Repair complex, scalp/arms/legs, 2.6-7.5 cm", "rvu": 3.64, "cat": "Integumentary"},
        {"code": "13131", "desc": "Repair complex, forehead/cheeks/chin, 1.1-2.5 cm", "rvu": 3.00, "cat": "Integumentary"},
        {"code": "13132", "desc": "Repair complex, forehead/cheeks/chin, 2.6-7.5 cm", "rvu": 4.15, "cat": "Integumentary"},
        {"code": "13151", "desc": "Repair complex, eyelids/nose/ears/lips, 1.1-2.5 cm", "rvu": 3.40, "cat": "Integumentary"},
        {"code": "13152", "desc": "Repair complex, eyelids/nose/ears/lips, 2.6-7.5 cm", "rvu": 4.70, "cat": "Integumentary"},

        # Musculoskeletal (20000-29999)
        {"code": "20200", "desc": "Biopsy, muscle, superficial", "rvu": 1.54, "cat": "Musculoskeletal"},
        {"code": "20205", "desc": "Biopsy, muscle, deep", "rvu": 2.78, "cat": "Musculoskeletal"},
        {"code": "20220", "desc": "Biopsy, bone, trocar or needle, superficial", "rvu": 1.67, "cat": "Musculoskeletal"},
        {"code": "20225", "desc": "Biopsy, bone, trocar or needle, deep", "rvu": 2.67, "cat": "Musculoskeletal"},
        {"code": "20240", "desc": "Biopsy, bone, open, superficial", "rvu": 3.62, "cat": "Musculoskeletal"},
        {"code": "20245", "desc": "Biopsy, bone, open, deep", "rvu": 6.21, "cat": "Musculoskeletal"},
        {"code": "20500", "desc": "Injection of sinus tract, diagnostic", "rvu": 0.75, "cat": "Musculoskeletal"},
        {"code": "20520", "desc": "Removal of foreign body, muscle or tendon sheath, simple", "rvu": 2.47, "cat": "Musculoskeletal"},
        {"code": "20525", "desc": "Removal of foreign body, muscle or tendon sheath, deep", "rvu": 4.98, "cat": "Musculoskeletal"},
        {"code": "20550", "desc": "Injection, tendon sheath, ligament, trigger point", "rvu": 0.75, "cat": "Musculoskeletal"},
        {"code": "20551", "desc": "Injection, tendon origin/insertion", "rvu": 0.75, "cat": "Musculoskeletal"},
        {"code": "20552", "desc": "Injection, trigger point, 1 or 2 muscles", "rvu": 0.66, "cat": "Musculoskeletal"},
        {"code": "20553", "desc": "Injection, trigger point, 3 or more muscles", "rvu": 0.78, "cat": "Musculoskeletal"},
        {"code": "20600", "desc": "Arthrocentesis, small joint or bursa", "rvu": 0.55, "cat": "Musculoskeletal"},
        {"code": "20605", "desc": "Arthrocentesis, intermediate joint or bursa", "rvu": 0.65, "cat": "Musculoskeletal"},
        {"code": "20610", "desc": "Arthrocentesis, major joint or bursa", "rvu": 0.79, "cat": "Musculoskeletal"},
        {"code": "20612", "desc": "Aspiration and/or injection of ganglion cyst", "rvu": 0.94, "cat": "Musculoskeletal"},
        {"code": "20670", "desc": "Removal of implant, superficial", "rvu": 2.18, "cat": "Musculoskeletal"},
        {"code": "20680", "desc": "Removal of implant, deep", "rvu": 5.06, "cat": "Musculoskeletal"},

        # Spine (22000-22899)
        {"code": "22100", "desc": "Partial excision of posterior vertebral component, cervical", "rvu": 11.09, "cat": "Spine"},
        {"code": "22102", "desc": "Partial excision of posterior vertebral component, thoracic", "rvu": 11.56, "cat": "Spine"},
        {"code": "22103", "desc": "Partial excision of posterior vertebral component, lumbar", "rvu": 11.76, "cat": "Spine"},
        {"code": "22210", "desc": "Osteotomy of spine, posterior/posterolateral, cervical", "rvu": 20.36, "cat": "Spine"},
        {"code": "22212", "desc": "Osteotomy of spine, posterior/posterolateral, thoracic", "rvu": 21.20, "cat": "Spine"},
        {"code": "22214", "desc": "Osteotomy of spine, posterior/posterolateral, lumbar", "rvu": 21.85, "cat": "Spine"},
        {"code": "22505", "desc": "Manipulation of spine under anesthesia", "rvu": 4.00, "cat": "Spine"},
        {"code": "22510", "desc": "Percutaneous vertebroplasty, 1 vertebral body, thoracic", "rvu": 7.14, "cat": "Spine"},
        {"code": "22511", "desc": "Percutaneous vertebroplasty, 1 vertebral body, lumbar", "rvu": 7.14, "cat": "Spine"},
        {"code": "22512", "desc": "Percutaneous vertebroplasty, each additional vertebral body", "rvu": 3.05, "cat": "Spine"},
        {"code": "22551", "desc": "Arthrodesis, anterior interbody, cervical below C2", "rvu": 20.25, "cat": "Spine"},
        {"code": "22552", "desc": "Arthrodesis, anterior interbody, cervical, each additional", "rvu": 4.28, "cat": "Spine"},
        {"code": "22554", "desc": "Arthrodesis, anterior interbody technique, cervical", "rvu": 17.35, "cat": "Spine"},
        {"code": "22556", "desc": "Arthrodesis, anterior interbody technique, thoracic", "rvu": 24.79, "cat": "Spine"},
        {"code": "22558", "desc": "Arthrodesis, anterior interbody technique, lumbar", "rvu": 21.33, "cat": "Spine"},
        {"code": "22612", "desc": "Arthrodesis, posterior or posterolateral, lumbar", "rvu": 20.21, "cat": "Spine"},
        {"code": "22630", "desc": "Arthrodesis, posterior interbody technique, lumbar", "rvu": 17.52, "cat": "Spine"},
        {"code": "22633", "desc": "Arthrodesis, combined posterior/posterolateral and interbody", "rvu": 24.58, "cat": "Spine"},
        {"code": "22800", "desc": "Arthrodesis, posterior, for spinal deformity, up to 6 segments", "rvu": 26.11, "cat": "Spine"},
        {"code": "22802", "desc": "Arthrodesis, posterior, for spinal deformity, 7-12 segments", "rvu": 30.89, "cat": "Spine"},
        {"code": "22804", "desc": "Arthrodesis, posterior, for spinal deformity, 13+ segments", "rvu": 35.66, "cat": "Spine"},

        # Fracture Care
        {"code": "23500", "desc": "Closed treatment of clavicular fracture without manipulation", "rvu": 2.01, "cat": "Musculoskeletal"},
        {"code": "23505", "desc": "Closed treatment of clavicular fracture with manipulation", "rvu": 3.80, "cat": "Musculoskeletal"},
        {"code": "23515", "desc": "Open treatment of clavicular fracture", "rvu": 8.71, "cat": "Musculoskeletal"},
        {"code": "24500", "desc": "Closed treatment of humeral shaft fracture without manipulation", "rvu": 3.09, "cat": "Musculoskeletal"},
        {"code": "24505", "desc": "Closed treatment of humeral shaft fracture with manipulation", "rvu": 5.77, "cat": "Musculoskeletal"},
        {"code": "24515", "desc": "Open treatment of humeral shaft fracture with plate/screws", "rvu": 13.42, "cat": "Musculoskeletal"},
        {"code": "25500", "desc": "Closed treatment of radial shaft fracture without manipulation", "rvu": 2.52, "cat": "Musculoskeletal"},
        {"code": "25505", "desc": "Closed treatment of radial shaft fracture with manipulation", "rvu": 4.90, "cat": "Musculoskeletal"},
        {"code": "25515", "desc": "Open treatment of radial shaft fracture, with internal fixation", "rvu": 11.31, "cat": "Musculoskeletal"},
        {"code": "25600", "desc": "Closed treatment of distal radial fracture without manipulation", "rvu": 2.17, "cat": "Musculoskeletal"},
        {"code": "25605", "desc": "Closed treatment of distal radial fracture with manipulation", "rvu": 4.34, "cat": "Musculoskeletal"},
        {"code": "25607", "desc": "Open treatment of distal radial extra-articular fracture", "rvu": 10.50, "cat": "Musculoskeletal"},
        {"code": "25608", "desc": "Open treatment of distal radial intra-articular fracture, 2 fragments", "rvu": 12.40, "cat": "Musculoskeletal"},
        {"code": "25609", "desc": "Open treatment of distal radial intra-articular fracture, 3+ fragments", "rvu": 14.50, "cat": "Musculoskeletal"},
        {"code": "27230", "desc": "Closed treatment of femoral fracture, proximal, without manipulation", "rvu": 2.22, "cat": "Musculoskeletal"},
        {"code": "27232", "desc": "Closed treatment of femoral fracture, proximal, with manipulation", "rvu": 5.15, "cat": "Musculoskeletal"},
        {"code": "27235", "desc": "Percutaneous skeletal fixation of femoral fracture, proximal", "rvu": 10.82, "cat": "Musculoskeletal"},
        {"code": "27236", "desc": "Open treatment of femoral fracture, proximal", "rvu": 15.87, "cat": "Musculoskeletal"},
        {"code": "27244", "desc": "Treatment of intertrochanteric femoral fracture with plate/screws", "rvu": 15.07, "cat": "Musculoskeletal"},
        {"code": "27245", "desc": "Treatment of intertrochanteric femoral fracture with intramedullary implant", "rvu": 14.67, "cat": "Musculoskeletal"},
        {"code": "27500", "desc": "Closed treatment of femoral shaft fracture without manipulation", "rvu": 3.21, "cat": "Musculoskeletal"},
        {"code": "27506", "desc": "Open treatment of femoral shaft fracture with plate/screws", "rvu": 15.54, "cat": "Musculoskeletal"},
        {"code": "27507", "desc": "Open treatment of femoral shaft fracture with intramedullary rod", "rvu": 15.29, "cat": "Musculoskeletal"},
        {"code": "27750", "desc": "Closed treatment of tibial shaft fracture without manipulation", "rvu": 2.68, "cat": "Musculoskeletal"},
        {"code": "27752", "desc": "Closed treatment of tibial shaft fracture with manipulation", "rvu": 5.53, "cat": "Musculoskeletal"},
        {"code": "27756", "desc": "Percutaneous skeletal fixation of tibial shaft fracture", "rvu": 10.67, "cat": "Musculoskeletal"},
        {"code": "27758", "desc": "Open treatment of tibial shaft fracture", "rvu": 14.72, "cat": "Musculoskeletal"},
        {"code": "27759", "desc": "Treatment of tibial shaft fracture with intramedullary rod", "rvu": 12.43, "cat": "Musculoskeletal"},
        {"code": "27780", "desc": "Closed treatment of proximal fibula or shaft fracture without manipulation", "rvu": 1.58, "cat": "Musculoskeletal"},
        {"code": "27784", "desc": "Open treatment of proximal fibula or shaft fracture", "rvu": 7.57, "cat": "Musculoskeletal"},

        # Joint Replacement
        {"code": "27125", "desc": "Hemiarthroplasty, hip, partial", "rvu": 13.86, "cat": "Musculoskeletal"},
        {"code": "27130", "desc": "Arthroplasty, acetabular and proximal femoral prosthetic (total hip)", "rvu": 20.05, "cat": "Musculoskeletal"},
        {"code": "27132", "desc": "Conversion of previous hip surgery to total hip arthroplasty", "rvu": 25.16, "cat": "Musculoskeletal"},
        {"code": "27134", "desc": "Revision of total hip arthroplasty, both components", "rvu": 27.46, "cat": "Musculoskeletal"},
        {"code": "27137", "desc": "Revision of total hip arthroplasty, acetabular component only", "rvu": 20.48, "cat": "Musculoskeletal"},
        {"code": "27138", "desc": "Revision of total hip arthroplasty, femoral component only", "rvu": 22.25, "cat": "Musculoskeletal"},
        {"code": "27438", "desc": "Arthroplasty, patella, with prosthesis", "rvu": 10.26, "cat": "Musculoskeletal"},
        {"code": "27440", "desc": "Arthroplasty, knee, tibial plateau", "rvu": 10.11, "cat": "Musculoskeletal"},
        {"code": "27441", "desc": "Arthroplasty, knee, tibial plateau, with debridement", "rvu": 11.25, "cat": "Musculoskeletal"},
        {"code": "27442", "desc": "Arthroplasty, femoral condyles or tibial plateau, single compartment", "rvu": 14.23, "cat": "Musculoskeletal"},
        {"code": "27443", "desc": "Arthroplasty, knee, constrained (hinge) prosthesis", "rvu": 21.79, "cat": "Musculoskeletal"},
        {"code": "27445", "desc": "Arthroplasty, knee, hinge prosthesis", "rvu": 21.79, "cat": "Musculoskeletal"},
        {"code": "27446", "desc": "Arthroplasty, knee, condyle and plateau, medial OR lateral compartment", "rvu": 14.65, "cat": "Musculoskeletal"},
        {"code": "27447", "desc": "Arthroplasty, knee, condyle and plateau, medial AND lateral (total knee)", "rvu": 20.69, "cat": "Musculoskeletal"},
        {"code": "27486", "desc": "Revision of total knee arthroplasty, with or without bone graft", "rvu": 26.04, "cat": "Musculoskeletal"},
        {"code": "27487", "desc": "Revision of total knee arthroplasty, femoral and tibial components", "rvu": 27.27, "cat": "Musculoskeletal"},
        {"code": "23470", "desc": "Arthroplasty, glenohumeral joint, hemiarthroplasty", "rvu": 16.26, "cat": "Musculoskeletal"},
        {"code": "23472", "desc": "Arthroplasty, glenohumeral joint, total shoulder", "rvu": 21.31, "cat": "Musculoskeletal"},
        {"code": "23473", "desc": "Revision of total shoulder arthroplasty, humeral or glenoid component", "rvu": 24.40, "cat": "Musculoskeletal"},
        {"code": "23474", "desc": "Revision of total shoulder arthroplasty, humeral and glenoid components", "rvu": 28.03, "cat": "Musculoskeletal"},

        # Arthroscopy
        {"code": "29805", "desc": "Arthroscopy, shoulder, diagnostic, with or without synovial biopsy", "rvu": 4.84, "cat": "Musculoskeletal"},
        {"code": "29806", "desc": "Arthroscopy, shoulder, surgical, capsulorrhaphy", "rvu": 11.75, "cat": "Musculoskeletal"},
        {"code": "29807", "desc": "Arthroscopy, shoulder, surgical, repair SLAP lesion", "rvu": 11.50, "cat": "Musculoskeletal"},
        {"code": "29819", "desc": "Arthroscopy, shoulder, surgical, with removal loose body or foreign body", "rvu": 6.64, "cat": "Musculoskeletal"},
        {"code": "29820", "desc": "Arthroscopy, shoulder, surgical, synovectomy, partial", "rvu": 6.95, "cat": "Musculoskeletal"},
        {"code": "29821", "desc": "Arthroscopy, shoulder, surgical, synovectomy, complete", "rvu": 8.55, "cat": "Musculoskeletal"},
        {"code": "29822", "desc": "Arthroscopy, shoulder, surgical, debridement, limited", "rvu": 5.82, "cat": "Musculoskeletal"},
        {"code": "29823", "desc": "Arthroscopy, shoulder, surgical, debridement, extensive", "rvu": 7.34, "cat": "Musculoskeletal"},
        {"code": "29824", "desc": "Arthroscopy, shoulder, surgical, distal claviculectomy", "rvu": 7.37, "cat": "Musculoskeletal"},
        {"code": "29825", "desc": "Arthroscopy, shoulder, surgical, with lysis of adhesions", "rvu": 6.23, "cat": "Musculoskeletal"},
        {"code": "29826", "desc": "Arthroscopy, shoulder, surgical, decompression of subacromial space", "rvu": 8.08, "cat": "Musculoskeletal"},
        {"code": "29827", "desc": "Arthroscopy, shoulder, surgical, with rotator cuff repair", "rvu": 14.48, "cat": "Musculoskeletal"},
        {"code": "29828", "desc": "Arthroscopy, shoulder, surgical, biceps tenodesis", "rvu": 7.46, "cat": "Musculoskeletal"},
        {"code": "29870", "desc": "Arthroscopy, knee, diagnostic, with or without synovial biopsy", "rvu": 3.72, "cat": "Musculoskeletal"},
        {"code": "29871", "desc": "Arthroscopy, knee, surgical, with infection lavage/drainage", "rvu": 5.87, "cat": "Musculoskeletal"},
        {"code": "29873", "desc": "Arthroscopy, knee, surgical, with lateral release", "rvu": 5.12, "cat": "Musculoskeletal"},
        {"code": "29874", "desc": "Arthroscopy, knee, surgical, for removal loose body or foreign body", "rvu": 5.67, "cat": "Musculoskeletal"},
        {"code": "29875", "desc": "Arthroscopy, knee, surgical, synovectomy, limited", "rvu": 5.48, "cat": "Musculoskeletal"},
        {"code": "29876", "desc": "Arthroscopy, knee, surgical, synovectomy, major, 2+ compartments", "rvu": 7.45, "cat": "Musculoskeletal"},
        {"code": "29877", "desc": "Arthroscopy, knee, surgical, debridement/shaving of articular cartilage", "rvu": 5.94, "cat": "Musculoskeletal"},
        {"code": "29879", "desc": "Arthroscopy, knee, surgical, abrasion arthroplasty", "rvu": 6.19, "cat": "Musculoskeletal"},
        {"code": "29880", "desc": "Arthroscopy, knee, surgical, with meniscectomy, medial AND lateral", "rvu": 8.13, "cat": "Musculoskeletal"},
        {"code": "29881", "desc": "Arthroscopy, knee, surgical, with meniscectomy, medial OR lateral", "rvu": 8.67, "cat": "Musculoskeletal"},
        {"code": "29882", "desc": "Arthroscopy, knee, surgical, with meniscus repair, medial OR lateral", "rvu": 9.19, "cat": "Musculoskeletal"},
        {"code": "29883", "desc": "Arthroscopy, knee, surgical, with meniscus repair, medial AND lateral", "rvu": 11.03, "cat": "Musculoskeletal"},
        {"code": "29884", "desc": "Arthroscopy, knee, surgical, with lysis of adhesions", "rvu": 6.46, "cat": "Musculoskeletal"},
        {"code": "29885", "desc": "Arthroscopy, knee, surgical, drilling for osteochondritis dissecans", "rvu": 6.96, "cat": "Musculoskeletal"},
        {"code": "29886", "desc": "Arthroscopy, knee, surgical, drilling for intact osteochondritis dissecans lesion", "rvu": 6.96, "cat": "Musculoskeletal"},
        {"code": "29887", "desc": "Arthroscopy, knee, surgical, drilling for intact osteochondritis dissecans lesion with internal fixation", "rvu": 8.58, "cat": "Musculoskeletal"},
        {"code": "29888", "desc": "Arthroscopically aided ACL repair/augmentation or reconstruction", "rvu": 13.09, "cat": "Musculoskeletal"},
        {"code": "29889", "desc": "Arthroscopically aided PCL repair/augmentation or reconstruction", "rvu": 14.94, "cat": "Musculoskeletal"},

        # General Surgery - Digestive (40000-49999)
        {"code": "43235", "desc": "Esophagogastroduodenoscopy, diagnostic", "rvu": 2.39, "cat": "Digestive"},
        {"code": "43236", "desc": "EGD with directed submucosal injection", "rvu": 2.76, "cat": "Digestive"},
        {"code": "43237", "desc": "EGD with endoscopic ultrasound examination", "rvu": 4.81, "cat": "Digestive"},
        {"code": "43238", "desc": "EGD with transendoscopic ultrasound-guided intramural/transmural fine needle aspiration/biopsy", "rvu": 5.93, "cat": "Digestive"},
        {"code": "43239", "desc": "EGD with biopsy, single or multiple", "rvu": 3.25, "cat": "Digestive"},
        {"code": "43240", "desc": "EGD with transmural drainage of pseudocyst", "rvu": 5.86, "cat": "Digestive"},
        {"code": "43241", "desc": "EGD with insertion of intraluminal tube or catheter", "rvu": 3.06, "cat": "Digestive"},
        {"code": "43242", "desc": "EGD with transendoscopic ultrasound-guided intramural/transmural fine needle aspiration/biopsy, esophagus", "rvu": 5.56, "cat": "Digestive"},
        {"code": "43243", "desc": "EGD with injection sclerosis of esophageal varices", "rvu": 4.30, "cat": "Digestive"},
        {"code": "43244", "desc": "EGD with band ligation of esophageal varices", "rvu": 4.35, "cat": "Digestive"},
        {"code": "43245", "desc": "EGD with dilation of gastric/duodenal stricture", "rvu": 3.13, "cat": "Digestive"},
        {"code": "43246", "desc": "EGD with directed placement of percutaneous gastrostomy tube", "rvu": 4.11, "cat": "Digestive"},
        {"code": "43247", "desc": "EGD with removal of foreign body", "rvu": 3.81, "cat": "Digestive"},
        {"code": "43248", "desc": "EGD with insertion of guide wire followed by dilation over guide wire", "rvu": 3.30, "cat": "Digestive"},
        {"code": "43249", "desc": "EGD with balloon dilation of esophagus", "rvu": 3.13, "cat": "Digestive"},
        {"code": "43250", "desc": "EGD with removal of tumor(s), polyp(s), or other lesion(s) by hot biopsy forceps", "rvu": 3.38, "cat": "Digestive"},
        {"code": "43251", "desc": "EGD with removal of tumor(s), polyp(s), or other lesion(s) by snare technique", "rvu": 4.01, "cat": "Digestive"},
        {"code": "43252", "desc": "EGD with optical endomicroscopy", "rvu": 3.50, "cat": "Digestive"},
        {"code": "43253", "desc": "EGD with transendoscopic stent placement", "rvu": 5.22, "cat": "Digestive"},
        {"code": "43254", "desc": "EGD with endoscopic mucosal resection", "rvu": 6.00, "cat": "Digestive"},
        {"code": "43255", "desc": "EGD with control of bleeding", "rvu": 4.58, "cat": "Digestive"},
        {"code": "43259", "desc": "EGD with endoscopic ultrasound examination", "rvu": 4.99, "cat": "Digestive"},

        # Colonoscopy
        {"code": "45378", "desc": "Colonoscopy, flexible, diagnostic", "rvu": 3.69, "cat": "Digestive"},
        {"code": "45379", "desc": "Colonoscopy with removal of foreign body(s)", "rvu": 4.58, "cat": "Digestive"},
        {"code": "45380", "desc": "Colonoscopy with biopsy, single or multiple", "rvu": 4.43, "cat": "Digestive"},
        {"code": "45381", "desc": "Colonoscopy with directed submucosal injection", "rvu": 4.41, "cat": "Digestive"},
        {"code": "45382", "desc": "Colonoscopy with control of bleeding", "rvu": 5.51, "cat": "Digestive"},
        {"code": "45384", "desc": "Colonoscopy with removal of tumor(s), polyp(s), or other lesion(s) by hot biopsy forceps", "rvu": 4.60, "cat": "Digestive"},
        {"code": "45385", "desc": "Colonoscopy with removal of tumor(s), polyp(s), or other lesion(s) by snare technique", "rvu": 5.18, "cat": "Digestive"},
        {"code": "45386", "desc": "Colonoscopy with transendoscopic balloon dilation", "rvu": 4.87, "cat": "Digestive"},
        {"code": "45388", "desc": "Colonoscopy with ablation of tumor(s), polyp(s), or other lesion(s)", "rvu": 5.20, "cat": "Digestive"},
        {"code": "45389", "desc": "Colonoscopy with endoscopic stent placement", "rvu": 5.98, "cat": "Digestive"},
        {"code": "45390", "desc": "Colonoscopy with endoscopic mucosal resection", "rvu": 7.45, "cat": "Digestive"},
        {"code": "45391", "desc": "Colonoscopy with endoscopic ultrasound examination", "rvu": 5.95, "cat": "Digestive"},
        {"code": "45392", "desc": "Colonoscopy with transendoscopic ultrasound guided intramural or transmural fine needle aspiration/biopsy", "rvu": 7.11, "cat": "Digestive"},
        {"code": "45393", "desc": "Colonoscopy with decompression", "rvu": 4.52, "cat": "Digestive"},
        {"code": "45398", "desc": "Colonoscopy with band ligation", "rvu": 5.50, "cat": "Digestive"},

        # Cholecystectomy
        {"code": "47562", "desc": "Laparoscopy, surgical; cholecystectomy", "rvu": 8.76, "cat": "Digestive"},
        {"code": "47563", "desc": "Laparoscopy, surgical; cholecystectomy with cholangiography", "rvu": 9.89, "cat": "Digestive"},
        {"code": "47564", "desc": "Laparoscopy, surgical; cholecystectomy with exploration of common duct", "rvu": 13.09, "cat": "Digestive"},
        {"code": "47600", "desc": "Cholecystectomy", "rvu": 12.26, "cat": "Digestive"},
        {"code": "47605", "desc": "Cholecystectomy with cholangiography", "rvu": 13.17, "cat": "Digestive"},
        {"code": "47610", "desc": "Cholecystectomy with exploration of common duct", "rvu": 17.47, "cat": "Digestive"},

        # Appendectomy
        {"code": "44950", "desc": "Appendectomy", "rvu": 8.89, "cat": "Digestive"},
        {"code": "44955", "desc": "Appendectomy; when done for indicated purpose at time of other major procedure", "rvu": 2.51, "cat": "Digestive"},
        {"code": "44960", "desc": "Appendectomy; for ruptured appendix with abscess or generalized peritonitis", "rvu": 14.22, "cat": "Digestive"},
        {"code": "44970", "desc": "Laparoscopy, surgical, appendectomy", "rvu": 7.63, "cat": "Digestive"},

        # Hernia Repair
        {"code": "49505", "desc": "Repair initial inguinal hernia, age 5 years or older; reducible", "rvu": 6.16, "cat": "Digestive"},
        {"code": "49507", "desc": "Repair initial inguinal hernia, age 5 years or older; incarcerated or strangulated", "rvu": 8.38, "cat": "Digestive"},
        {"code": "49520", "desc": "Repair recurrent inguinal hernia, any age; reducible", "rvu": 8.64, "cat": "Digestive"},
        {"code": "49521", "desc": "Repair recurrent inguinal hernia, any age; incarcerated or strangulated", "rvu": 10.61, "cat": "Digestive"},
        {"code": "49525", "desc": "Repair inguinal hernia, sliding, any age", "rvu": 7.67, "cat": "Digestive"},
        {"code": "49550", "desc": "Repair initial femoral hernia, any age; reducible", "rvu": 6.52, "cat": "Digestive"},
        {"code": "49553", "desc": "Repair initial femoral hernia, any age; incarcerated or strangulated", "rvu": 8.13, "cat": "Digestive"},
        {"code": "49555", "desc": "Repair recurrent femoral hernia; reducible", "rvu": 9.00, "cat": "Digestive"},
        {"code": "49557", "desc": "Repair recurrent femoral hernia; incarcerated or strangulated", "rvu": 10.96, "cat": "Digestive"},
        {"code": "49560", "desc": "Repair initial incisional or ventral hernia; reducible", "rvu": 9.35, "cat": "Digestive"},
        {"code": "49561", "desc": "Repair initial incisional or ventral hernia; incarcerated or strangulated", "rvu": 12.43, "cat": "Digestive"},
        {"code": "49565", "desc": "Repair recurrent incisional or ventral hernia; reducible", "rvu": 13.18, "cat": "Digestive"},
        {"code": "49566", "desc": "Repair recurrent incisional or ventral hernia; incarcerated or strangulated", "rvu": 16.03, "cat": "Digestive"},
        {"code": "49580", "desc": "Repair umbilical hernia, under age 5 years; reducible", "rvu": 4.00, "cat": "Digestive"},
        {"code": "49582", "desc": "Repair umbilical hernia, under age 5 years; incarcerated or strangulated", "rvu": 5.71, "cat": "Digestive"},
        {"code": "49585", "desc": "Repair umbilical hernia, age 5 years or older; reducible", "rvu": 5.16, "cat": "Digestive"},
        {"code": "49587", "desc": "Repair umbilical hernia, age 5 years or older; incarcerated or strangulated", "rvu": 7.30, "cat": "Digestive"},
        {"code": "49650", "desc": "Laparoscopy, surgical; repair initial inguinal hernia", "rvu": 7.60, "cat": "Digestive"},
        {"code": "49651", "desc": "Laparoscopy, surgical; repair recurrent inguinal hernia", "rvu": 9.30, "cat": "Digestive"},
        {"code": "49652", "desc": "Laparoscopy, surgical; repair ventral, umbilical, spigelian or epigastric hernia; reducible", "rvu": 9.95, "cat": "Digestive"},
        {"code": "49653", "desc": "Laparoscopy, surgical; repair ventral, umbilical, spigelian or epigastric hernia; incarcerated or strangulated", "rvu": 12.28, "cat": "Digestive"},

        # Cardiovascular (33000-37799)
        {"code": "33206", "desc": "Insertion of permanent pacemaker, atrial", "rvu": 7.14, "cat": "Cardiovascular"},
        {"code": "33207", "desc": "Insertion of permanent pacemaker, ventricular", "rvu": 7.14, "cat": "Cardiovascular"},
        {"code": "33208", "desc": "Insertion of permanent pacemaker, atrial and ventricular", "rvu": 8.01, "cat": "Cardiovascular"},
        {"code": "33210", "desc": "Insertion or replacement of temporary transvenous single chamber cardiac electrode", "rvu": 3.50, "cat": "Cardiovascular"},
        {"code": "33211", "desc": "Insertion or replacement of temporary transvenous dual chamber pacing electrodes", "rvu": 4.79, "cat": "Cardiovascular"},
        {"code": "33212", "desc": "Insertion of pacemaker pulse generator only; single chamber, atrial or ventricular", "rvu": 5.43, "cat": "Cardiovascular"},
        {"code": "33213", "desc": "Insertion of pacemaker pulse generator only; dual chamber", "rvu": 5.43, "cat": "Cardiovascular"},
        {"code": "33214", "desc": "Upgrade of implanted pacemaker system, conversion of single chamber to dual chamber", "rvu": 7.14, "cat": "Cardiovascular"},
        {"code": "33215", "desc": "Repositioning of previously implanted transvenous pacemaker or defibrillator electrode", "rvu": 5.00, "cat": "Cardiovascular"},
        {"code": "33216", "desc": "Insertion of single transvenous electrode, permanent pacemaker or ICD", "rvu": 5.38, "cat": "Cardiovascular"},
        {"code": "33217", "desc": "Insertion of 2 transvenous electrodes, permanent pacemaker or ICD", "rvu": 7.16, "cat": "Cardiovascular"},
        {"code": "33218", "desc": "Repair of single transvenous electrode, permanent pacemaker or ICD", "rvu": 5.74, "cat": "Cardiovascular"},
        {"code": "33220", "desc": "Repair of 2 transvenous electrodes, permanent pacemaker or ICD", "rvu": 8.15, "cat": "Cardiovascular"},
        {"code": "33221", "desc": "Insertion of pacemaker pulse generator, dual chamber, existing dual leads", "rvu": 5.43, "cat": "Cardiovascular"},
        {"code": "33222", "desc": "Relocation of skin pocket for pacemaker", "rvu": 4.00, "cat": "Cardiovascular"},
        {"code": "33223", "desc": "Relocation of skin pocket for implantable defibrillator", "rvu": 6.01, "cat": "Cardiovascular"},
        {"code": "33224", "desc": "Insertion of pacing electrode, left ventricular", "rvu": 8.00, "cat": "Cardiovascular"},
        {"code": "33225", "desc": "Insertion of pacing electrode, left ventricular; at time of insertion of ICD", "rvu": 4.52, "cat": "Cardiovascular"},
        {"code": "33226", "desc": "Repositioning of previously implanted left ventricular electrode", "rvu": 5.75, "cat": "Cardiovascular"},
        {"code": "33227", "desc": "Removal of permanent pacemaker pulse generator with replacement of pulse generator; single lead system", "rvu": 3.23, "cat": "Cardiovascular"},
        {"code": "33228", "desc": "Removal of permanent pacemaker pulse generator with replacement of pulse generator; dual lead system", "rvu": 3.23, "cat": "Cardiovascular"},
        {"code": "33229", "desc": "Removal of permanent pacemaker pulse generator with replacement of pulse generator; multiple lead system", "rvu": 3.23, "cat": "Cardiovascular"},
        {"code": "33230", "desc": "Insertion of pacing cardioverter-defibrillator pulse generator only; single lead system", "rvu": 6.54, "cat": "Cardiovascular"},
        {"code": "33231", "desc": "Insertion of pacing cardioverter-defibrillator pulse generator only; dual lead system", "rvu": 6.54, "cat": "Cardiovascular"},
        {"code": "33249", "desc": "Insertion or replacement of ICD system with single or dual chamber", "rvu": 10.62, "cat": "Cardiovascular"},
        {"code": "33262", "desc": "Removal of ICD pulse generator with replacement of pulse generator; single lead", "rvu": 4.62, "cat": "Cardiovascular"},
        {"code": "33263", "desc": "Removal of ICD pulse generator with replacement of pulse generator; dual lead", "rvu": 4.62, "cat": "Cardiovascular"},
        {"code": "33264", "desc": "Removal of ICD pulse generator with replacement of pulse generator; multiple lead", "rvu": 4.62, "cat": "Cardiovascular"},

        # CABG
        {"code": "33510", "desc": "Coronary artery bypass, vein only; single coronary venous graft", "rvu": 30.00, "cat": "Cardiovascular"},
        {"code": "33511", "desc": "Coronary artery bypass, vein only; 2 coronary venous grafts", "rvu": 33.00, "cat": "Cardiovascular"},
        {"code": "33512", "desc": "Coronary artery bypass, vein only; 3 coronary venous grafts", "rvu": 35.82, "cat": "Cardiovascular"},
        {"code": "33513", "desc": "Coronary artery bypass, vein only; 4 coronary venous grafts", "rvu": 38.00, "cat": "Cardiovascular"},
        {"code": "33514", "desc": "Coronary artery bypass, vein only; 5 coronary venous grafts", "rvu": 40.00, "cat": "Cardiovascular"},
        {"code": "33516", "desc": "Coronary artery bypass, vein only; 6 or more coronary venous grafts", "rvu": 42.00, "cat": "Cardiovascular"},
        {"code": "33533", "desc": "Coronary artery bypass, using arterial graft; single arterial graft", "rvu": 33.00, "cat": "Cardiovascular"},
        {"code": "33534", "desc": "Coronary artery bypass, using arterial graft; 2 coronary arterial grafts", "rvu": 36.00, "cat": "Cardiovascular"},
        {"code": "33535", "desc": "Coronary artery bypass, using arterial graft; 3 coronary arterial grafts", "rvu": 38.64, "cat": "Cardiovascular"},
        {"code": "33536", "desc": "Coronary artery bypass, using arterial graft; 4 or more coronary arterial grafts", "rvu": 41.00, "cat": "Cardiovascular"},

        # Carpal Tunnel
        {"code": "64721", "desc": "Neuroplasty and/or transposition; median nerve at carpal tunnel", "rvu": 5.52, "cat": "Nervous"},
        {"code": "29848", "desc": "Endoscopy, wrist, surgical; with release of transverse carpal ligament", "rvu": 5.77, "cat": "Nervous"},

        # Eye Surgery (65000-68899)
        {"code": "66982", "desc": "Extracapsular cataract removal with insertion of intraocular lens prosthesis, complex", "rvu": 11.30, "cat": "Eye"},
        {"code": "66984", "desc": "Extracapsular cataract removal with insertion of intraocular lens prosthesis, manual or mechanical technique", "rvu": 10.19, "cat": "Eye"},

        # Ear Surgery (69000-69979)
        {"code": "69210", "desc": "Removal impacted cerumen requiring instrumentation, unilateral", "rvu": 0.61, "cat": "Ear"},
        {"code": "69436", "desc": "Tympanostomy, myringotomy with insertion of ventilating tube", "rvu": 2.45, "cat": "Ear"},
    ]

    for surg in surgery_codes:
        codes.append({
            "concept_code": surg["code"],
            "concept_name": surg["desc"],
            "category": "Surgery",
            "subcategory": surg.get("cat", "Surgery"),
            "work_rvu": surg["rvu"],
            "synonyms": [],
        })

    return codes


# =============================================================================
# RADIOLOGY CODES (70000-79999)
# =============================================================================
def generate_radiology_codes() -> list[dict[str, Any]]:
    """Generate radiology codes with descriptions and RVUs."""
    codes = []

    radiology_codes = [
        # Head/Neck
        {"code": "70030", "desc": "Radiologic examination, eye, for detection of foreign body", "rvu": 0.17},
        {"code": "70100", "desc": "Radiologic examination, mandible, partial, less than 4 views", "rvu": 0.17},
        {"code": "70110", "desc": "Radiologic examination, mandible, complete, minimum of 4 views", "rvu": 0.22},
        {"code": "70120", "desc": "Radiologic examination, mastoids, less than 3 views per side", "rvu": 0.17},
        {"code": "70130", "desc": "Radiologic examination, mastoids, complete, minimum of 3 views per side", "rvu": 0.22},
        {"code": "70140", "desc": "Radiologic examination, facial bones, less than 3 views", "rvu": 0.17},
        {"code": "70150", "desc": "Radiologic examination, facial bones, complete, minimum of 3 views", "rvu": 0.22},
        {"code": "70160", "desc": "Radiologic examination, nasal bones, complete, minimum of 3 views", "rvu": 0.17},
        {"code": "70200", "desc": "Radiologic examination, orbits, complete, minimum of 4 views", "rvu": 0.22},
        {"code": "70210", "desc": "Radiologic examination, sinuses, paranasal, less than 3 views", "rvu": 0.17},
        {"code": "70220", "desc": "Radiologic examination, sinuses, paranasal, complete, minimum of 3 views", "rvu": 0.22},
        {"code": "70250", "desc": "Radiologic examination, skull, less than 4 views", "rvu": 0.17},
        {"code": "70260", "desc": "Radiologic examination, skull, complete, minimum of 4 views", "rvu": 0.22},
        {"code": "70328", "desc": "Radiologic examination, temporomandibular joint, open and closed mouth, unilateral", "rvu": 0.17},
        {"code": "70330", "desc": "Radiologic examination, temporomandibular joint, open and closed mouth, bilateral", "rvu": 0.22},
        {"code": "70336", "desc": "MRI, temporomandibular joint(s)", "rvu": 1.35},
        {"code": "70360", "desc": "Radiologic examination; neck, soft tissue", "rvu": 0.17},

        # CT Head/Neck
        {"code": "70450", "desc": "CT, head or brain; without contrast material", "rvu": 0.85},
        {"code": "70460", "desc": "CT, head or brain; with contrast material", "rvu": 1.13},
        {"code": "70470", "desc": "CT, head or brain; without contrast material, followed by contrast and further sections", "rvu": 1.27},
        {"code": "70480", "desc": "CT, orbit, sella, or posterior fossa; without contrast material", "rvu": 0.90},
        {"code": "70481", "desc": "CT, orbit, sella, or posterior fossa; with contrast material", "rvu": 1.07},
        {"code": "70482", "desc": "CT, orbit, sella, or posterior fossa; without contrast followed by contrast", "rvu": 1.40},
        {"code": "70486", "desc": "CT, maxillofacial area; without contrast material", "rvu": 0.85},
        {"code": "70487", "desc": "CT, maxillofacial area; with contrast material", "rvu": 1.00},
        {"code": "70488", "desc": "CT, maxillofacial area; without contrast followed by contrast", "rvu": 1.27},
        {"code": "70490", "desc": "CT, soft tissue neck; without contrast material", "rvu": 0.92},
        {"code": "70491", "desc": "CT, soft tissue neck; with contrast material", "rvu": 1.16},
        {"code": "70492", "desc": "CT, soft tissue neck; without contrast followed by contrast", "rvu": 1.40},
        {"code": "70496", "desc": "CT angiography, head, with contrast", "rvu": 1.75},
        {"code": "70498", "desc": "CT angiography, neck, with contrast", "rvu": 1.75},

        # MRI Head/Neck
        {"code": "70540", "desc": "MRI, orbit, face, and/or neck; without contrast material(s)", "rvu": 1.28},
        {"code": "70542", "desc": "MRI, orbit, face, and/or neck; with contrast material(s)", "rvu": 1.62},
        {"code": "70543", "desc": "MRI, orbit, face, and/or neck; without contrast material(s), followed by contrast material(s)", "rvu": 1.90},
        {"code": "70544", "desc": "MRA, head; without contrast material(s)", "rvu": 1.28},
        {"code": "70545", "desc": "MRA, head; with contrast material(s)", "rvu": 1.54},
        {"code": "70546", "desc": "MRA, head; without contrast material(s), followed by contrast material(s)", "rvu": 1.90},
        {"code": "70547", "desc": "MRA, neck; without contrast material(s)", "rvu": 1.28},
        {"code": "70548", "desc": "MRA, neck; with contrast material(s)", "rvu": 1.54},
        {"code": "70549", "desc": "MRA, neck; without contrast material(s), followed by contrast material(s)", "rvu": 1.90},
        {"code": "70551", "desc": "MRI, brain; without contrast material", "rvu": 1.48},
        {"code": "70552", "desc": "MRI, brain; with contrast material(s)", "rvu": 1.88},
        {"code": "70553", "desc": "MRI, brain; without contrast material, followed by contrast material(s)", "rvu": 2.10},
        {"code": "70554", "desc": "MRI, brain, functional MRI", "rvu": 2.84},
        {"code": "70555", "desc": "MRI, brain, functional MRI; requiring physician or psychologist administration", "rvu": 2.84},

        # Chest X-Ray
        {"code": "71045", "desc": "Radiologic examination, chest; single view", "rvu": 0.18},
        {"code": "71046", "desc": "Radiologic examination, chest; 2 views", "rvu": 0.22},
        {"code": "71047", "desc": "Radiologic examination, chest; 3 views", "rvu": 0.27},
        {"code": "71048", "desc": "Radiologic examination, chest; 4 or more views", "rvu": 0.30},

        # CT Chest
        {"code": "71250", "desc": "CT, thorax; without contrast material", "rvu": 1.16},
        {"code": "71260", "desc": "CT, thorax; with contrast material(s)", "rvu": 1.38},
        {"code": "71270", "desc": "CT, thorax; without contrast material, followed by contrast material(s)", "rvu": 1.74},
        {"code": "71271", "desc": "CT, thorax, low dose for lung cancer screening, without contrast material(s)", "rvu": 0.74},
        {"code": "71275", "desc": "CT angiography, chest (noncoronary), with contrast", "rvu": 2.00},

        # MRI Chest
        {"code": "71550", "desc": "MRI, chest; without contrast material(s)", "rvu": 1.48},
        {"code": "71551", "desc": "MRI, chest; with contrast material(s)", "rvu": 1.82},
        {"code": "71552", "desc": "MRI, chest; without contrast material(s), followed by contrast material(s)", "rvu": 2.17},
        {"code": "71555", "desc": "MRA, chest, with or without contrast material(s)", "rvu": 1.75},

        # Spine X-Ray
        {"code": "72020", "desc": "Radiologic examination, spine, single view, specify level", "rvu": 0.16},
        {"code": "72040", "desc": "Radiologic examination, spine, cervical; 2 or 3 views", "rvu": 0.21},
        {"code": "72050", "desc": "Radiologic examination, spine, cervical; 4 or 5 views", "rvu": 0.26},
        {"code": "72052", "desc": "Radiologic examination, spine, cervical; 6 or more views", "rvu": 0.33},
        {"code": "72070", "desc": "Radiologic examination, spine; thoracic, 2 views", "rvu": 0.21},
        {"code": "72072", "desc": "Radiologic examination, spine; thoracic, 3 views", "rvu": 0.26},
        {"code": "72074", "desc": "Radiologic examination, spine; thoracic, minimum of 4 views", "rvu": 0.29},
        {"code": "72080", "desc": "Radiologic examination, spine; thoracolumbar junction, minimum of 2 views", "rvu": 0.21},
        {"code": "72081", "desc": "Radiologic examination, spine, entire thoracic and lumbar, including skull, cervical and sacral spine if performed; one view", "rvu": 0.30},
        {"code": "72082", "desc": "Radiologic examination, spine, entire thoracic and lumbar; 2 or 3 views", "rvu": 0.36},
        {"code": "72083", "desc": "Radiologic examination, spine, entire thoracic and lumbar; 4 or 5 views", "rvu": 0.41},
        {"code": "72084", "desc": "Radiologic examination, spine, entire thoracic and lumbar; minimum of 6 views", "rvu": 0.46},
        {"code": "72100", "desc": "Radiologic examination, spine, lumbosacral; 2 or 3 views", "rvu": 0.21},
        {"code": "72110", "desc": "Radiologic examination, spine, lumbosacral; minimum of 4 views", "rvu": 0.28},
        {"code": "72114", "desc": "Radiologic examination, spine, lumbosacral; complete, including bending views, minimum of 6 views", "rvu": 0.38},
        {"code": "72120", "desc": "Radiologic examination, spine, lumbosacral; bending views only, 2 or 3 views", "rvu": 0.21},

        # CT Spine
        {"code": "72125", "desc": "CT, cervical spine; without contrast material", "rvu": 1.05},
        {"code": "72126", "desc": "CT, cervical spine; with contrast material", "rvu": 1.27},
        {"code": "72127", "desc": "CT, cervical spine; without contrast material, followed by contrast material(s)", "rvu": 1.52},
        {"code": "72128", "desc": "CT, thoracic spine; without contrast material", "rvu": 1.05},
        {"code": "72129", "desc": "CT, thoracic spine; with contrast material", "rvu": 1.27},
        {"code": "72130", "desc": "CT, thoracic spine; without contrast material, followed by contrast material(s)", "rvu": 1.52},
        {"code": "72131", "desc": "CT, lumbar spine; without contrast material", "rvu": 1.05},
        {"code": "72132", "desc": "CT, lumbar spine; with contrast material", "rvu": 1.27},
        {"code": "72133", "desc": "CT, lumbar spine; without contrast material, followed by contrast material(s)", "rvu": 1.52},

        # MRI Spine
        {"code": "72141", "desc": "MRI, spinal canal and contents, cervical; without contrast material", "rvu": 1.48},
        {"code": "72142", "desc": "MRI, spinal canal and contents, cervical; with contrast material(s)", "rvu": 1.87},
        {"code": "72146", "desc": "MRI, spinal canal and contents, thoracic; without contrast material", "rvu": 1.48},
        {"code": "72147", "desc": "MRI, spinal canal and contents, thoracic; with contrast material(s)", "rvu": 1.87},
        {"code": "72148", "desc": "MRI, spinal canal and contents, lumbar; without contrast material", "rvu": 1.48},
        {"code": "72149", "desc": "MRI, spinal canal and contents, lumbar; with contrast material(s)", "rvu": 1.87},
        {"code": "72156", "desc": "MRI, spinal canal and contents, without contrast material, followed by contrast material(s); cervical", "rvu": 2.30},
        {"code": "72157", "desc": "MRI, spinal canal and contents, without contrast material, followed by contrast material(s); thoracic", "rvu": 2.30},
        {"code": "72158", "desc": "MRI, spinal canal and contents, without contrast material, followed by contrast material(s); lumbar", "rvu": 2.30},

        # Pelvis
        {"code": "72170", "desc": "Radiologic examination, pelvis; 1 or 2 views", "rvu": 0.17},
        {"code": "72190", "desc": "Radiologic examination, pelvis; complete, minimum of 3 views", "rvu": 0.22},
        {"code": "72192", "desc": "CT, pelvis; without contrast material", "rvu": 1.09},
        {"code": "72193", "desc": "CT, pelvis; with contrast material(s)", "rvu": 1.27},
        {"code": "72194", "desc": "CT, pelvis; without contrast material, followed by contrast material(s)", "rvu": 1.56},
        {"code": "72195", "desc": "MRI, pelvis; without contrast material(s)", "rvu": 1.48},
        {"code": "72196", "desc": "MRI, pelvis; with contrast material(s)", "rvu": 1.87},
        {"code": "72197", "desc": "MRI, pelvis; without contrast material(s), followed by contrast material(s)", "rvu": 2.30},
        {"code": "72198", "desc": "MRA, pelvis, with or without contrast material(s)", "rvu": 1.75},

        # Upper Extremity
        {"code": "73000", "desc": "Radiologic examination; clavicle, complete", "rvu": 0.16},
        {"code": "73010", "desc": "Radiologic examination; scapula, complete", "rvu": 0.17},
        {"code": "73020", "desc": "Radiologic examination, shoulder; 1 view", "rvu": 0.15},
        {"code": "73030", "desc": "Radiologic examination, shoulder; complete, minimum of 2 views", "rvu": 0.18},
        {"code": "73050", "desc": "Radiologic examination; acromioclavicular joints, bilateral, with or without weighted distraction", "rvu": 0.18},
        {"code": "73060", "desc": "Radiologic examination; humerus, minimum of 2 views", "rvu": 0.17},
        {"code": "73070", "desc": "Radiologic examination; elbow, 2 views", "rvu": 0.16},
        {"code": "73080", "desc": "Radiologic examination, elbow; complete, minimum of 3 views", "rvu": 0.18},
        {"code": "73090", "desc": "Radiologic examination; forearm, 2 views", "rvu": 0.16},
        {"code": "73092", "desc": "Radiologic examination; upper extremity, infant, minimum of 2 views", "rvu": 0.17},
        {"code": "73100", "desc": "Radiologic examination, wrist; 2 views", "rvu": 0.16},
        {"code": "73110", "desc": "Radiologic examination, wrist; complete, minimum of 3 views", "rvu": 0.18},
        {"code": "73120", "desc": "Radiologic examination, hand; 2 views", "rvu": 0.15},
        {"code": "73130", "desc": "Radiologic examination, hand; minimum of 3 views", "rvu": 0.17},
        {"code": "73140", "desc": "Radiologic examination, finger(s), minimum of 2 views", "rvu": 0.14},

        # CT/MRI Upper Extremity
        {"code": "73200", "desc": "CT, upper extremity; without contrast material", "rvu": 0.82},
        {"code": "73201", "desc": "CT, upper extremity; with contrast material(s)", "rvu": 0.97},
        {"code": "73202", "desc": "CT, upper extremity; without contrast material, followed by contrast material(s)", "rvu": 1.22},
        {"code": "73206", "desc": "CT angiography, upper extremity, with contrast", "rvu": 1.40},
        {"code": "73218", "desc": "MRI, upper extremity, other than joint; without contrast material(s)", "rvu": 1.20},
        {"code": "73219", "desc": "MRI, upper extremity, other than joint; with contrast material(s)", "rvu": 1.48},
        {"code": "73220", "desc": "MRI, upper extremity, other than joint; without contrast material(s), followed by contrast material(s)", "rvu": 1.80},
        {"code": "73221", "desc": "MRI, any joint of upper extremity; without contrast material(s)", "rvu": 1.30},
        {"code": "73222", "desc": "MRI, any joint of upper extremity; with contrast material(s)", "rvu": 1.60},
        {"code": "73223", "desc": "MRI, any joint of upper extremity; without contrast material(s), followed by contrast material(s)", "rvu": 1.95},
        {"code": "73225", "desc": "MRA, upper extremity, with or without contrast material(s)", "rvu": 1.40},

        # Lower Extremity
        {"code": "73501", "desc": "Radiologic examination, hip, unilateral; 1 view", "rvu": 0.16},
        {"code": "73502", "desc": "Radiologic examination, hip, unilateral; 2-3 views", "rvu": 0.19},
        {"code": "73503", "desc": "Radiologic examination, hip, unilateral; minimum of 4 views", "rvu": 0.25},
        {"code": "73521", "desc": "Radiologic examination, hips, bilateral; 2 views", "rvu": 0.20},
        {"code": "73522", "desc": "Radiologic examination, hips, bilateral; 3-4 views", "rvu": 0.25},
        {"code": "73523", "desc": "Radiologic examination, hips, bilateral; minimum of 5 views", "rvu": 0.30},
        {"code": "73551", "desc": "Radiologic examination, femur; 1 view", "rvu": 0.14},
        {"code": "73552", "desc": "Radiologic examination, femur; minimum of 2 views", "rvu": 0.17},
        {"code": "73560", "desc": "Radiologic examination, knee; 1 or 2 views", "rvu": 0.16},
        {"code": "73562", "desc": "Radiologic examination, knee; 3 views", "rvu": 0.18},
        {"code": "73564", "desc": "Radiologic examination, knee; complete, 4 or more views", "rvu": 0.22},
        {"code": "73565", "desc": "Radiologic examination, both knees, standing, anteroposterior", "rvu": 0.18},
        {"code": "73590", "desc": "Radiologic examination; tibia and fibula, 2 views", "rvu": 0.17},
        {"code": "73592", "desc": "Radiologic examination; lower extremity, infant, minimum of 2 views", "rvu": 0.17},
        {"code": "73600", "desc": "Radiologic examination, ankle; 2 views", "rvu": 0.16},
        {"code": "73610", "desc": "Radiologic examination, ankle; complete, minimum of 3 views", "rvu": 0.18},
        {"code": "73620", "desc": "Radiologic examination, foot; 2 views", "rvu": 0.16},
        {"code": "73630", "desc": "Radiologic examination, foot; complete, minimum of 3 views", "rvu": 0.18},
        {"code": "73650", "desc": "Radiologic examination; calcaneus, minimum of 2 views", "rvu": 0.16},
        {"code": "73660", "desc": "Radiologic examination; toe(s), minimum of 2 views", "rvu": 0.14},

        # CT/MRI Lower Extremity
        {"code": "73700", "desc": "CT, lower extremity; without contrast material", "rvu": 0.82},
        {"code": "73701", "desc": "CT, lower extremity; with contrast material(s)", "rvu": 0.97},
        {"code": "73702", "desc": "CT, lower extremity; without contrast material, followed by contrast material(s)", "rvu": 1.22},
        {"code": "73706", "desc": "CT angiography, lower extremity, with contrast", "rvu": 1.50},
        {"code": "73718", "desc": "MRI, lower extremity other than joint; without contrast material(s)", "rvu": 1.20},
        {"code": "73719", "desc": "MRI, lower extremity other than joint; with contrast material(s)", "rvu": 1.48},
        {"code": "73720", "desc": "MRI, lower extremity other than joint; without contrast material(s), followed by contrast material(s)", "rvu": 1.80},
        {"code": "73721", "desc": "MRI, any joint of lower extremity; without contrast material", "rvu": 1.30},
        {"code": "73722", "desc": "MRI, any joint of lower extremity; with contrast material(s)", "rvu": 1.60},
        {"code": "73723", "desc": "MRI, any joint of lower extremity; without contrast material(s), followed by contrast material(s)", "rvu": 1.95},
        {"code": "73725", "desc": "MRA, lower extremity, with or without contrast material(s)", "rvu": 1.50},

        # Abdomen
        {"code": "74018", "desc": "Radiologic examination, abdomen; 1 view", "rvu": 0.17},
        {"code": "74019", "desc": "Radiologic examination, abdomen; 2 views", "rvu": 0.21},
        {"code": "74021", "desc": "Radiologic examination, abdomen; 3 or more views", "rvu": 0.26},
        {"code": "74022", "desc": "Radiologic examination, complete acute abdomen series", "rvu": 0.27},

        # CT Abdomen
        {"code": "74150", "desc": "CT, abdomen; without contrast material", "rvu": 1.19},
        {"code": "74160", "desc": "CT, abdomen; with contrast material(s)", "rvu": 1.40},
        {"code": "74170", "desc": "CT, abdomen; without contrast material, followed by contrast material(s)", "rvu": 1.82},
        {"code": "74174", "desc": "CT angiography, abdomen and pelvis, with contrast, including noncontrast images", "rvu": 2.70},
        {"code": "74175", "desc": "CT angiography, abdomen, with contrast", "rvu": 1.90},
        {"code": "74176", "desc": "CT, abdomen and pelvis; without contrast material", "rvu": 1.74},
        {"code": "74177", "desc": "CT, abdomen and pelvis; with contrast material(s)", "rvu": 2.01},
        {"code": "74178", "desc": "CT, abdomen and pelvis; without contrast material in one or both body regions, followed by contrast material(s)", "rvu": 2.46},

        # MRI Abdomen
        {"code": "74181", "desc": "MRI, abdomen; without contrast material(s)", "rvu": 1.52},
        {"code": "74182", "desc": "MRI, abdomen; with contrast material(s)", "rvu": 1.98},
        {"code": "74183", "desc": "MRI, abdomen; without contrast material(s), followed by with contrast material(s)", "rvu": 2.53},
        {"code": "74185", "desc": "MRA, abdomen, with or without contrast material(s)", "rvu": 1.75},

        # Ultrasound
        {"code": "76536", "desc": "Ultrasound, soft tissues of head and neck, real time with image documentation", "rvu": 0.50},
        {"code": "76604", "desc": "Ultrasound, chest, real time with image documentation", "rvu": 0.44},
        {"code": "76641", "desc": "Ultrasound, breast, unilateral, real time with image documentation, complete", "rvu": 0.64},
        {"code": "76642", "desc": "Ultrasound, breast, unilateral, real time with image documentation, limited", "rvu": 0.42},
        {"code": "76700", "desc": "Ultrasound, abdominal, real time with image documentation; complete", "rvu": 0.81},
        {"code": "76705", "desc": "Ultrasound, abdominal, real time with image documentation; limited", "rvu": 0.50},
        {"code": "76770", "desc": "Ultrasound, retroperitoneal, real time with image documentation; complete", "rvu": 0.74},
        {"code": "76775", "desc": "Ultrasound, retroperitoneal, real time with image documentation; limited", "rvu": 0.50},
        {"code": "76801", "desc": "Ultrasound, pregnant uterus, real time with image documentation, fetal and maternal evaluation, first trimester, single or first gestation", "rvu": 0.99},
        {"code": "76805", "desc": "Ultrasound, pregnant uterus, real time with image documentation, fetal and maternal evaluation, after first trimester", "rvu": 1.17},
        {"code": "76815", "desc": "Ultrasound, pregnant uterus, real time with image documentation, limited", "rvu": 0.65},
        {"code": "76817", "desc": "Ultrasound, pregnant uterus, real time with image documentation, transvaginal", "rvu": 0.65},
        {"code": "76830", "desc": "Ultrasound, transvaginal", "rvu": 0.65},
        {"code": "76856", "desc": "Ultrasound, pelvic (nonobstetric), real time with image documentation; complete", "rvu": 0.65},
        {"code": "76857", "desc": "Ultrasound, pelvic (nonobstetric), real time with image documentation; limited or follow-up", "rvu": 0.42},
        {"code": "76870", "desc": "Ultrasound, scrotum and contents", "rvu": 0.55},
        {"code": "76881", "desc": "Ultrasound, complete joint, real time with image documentation", "rvu": 0.65},
        {"code": "76882", "desc": "Ultrasound, limited, joint or other nonvascular extremity structure(s)", "rvu": 0.42},

        # Mammography
        {"code": "77065", "desc": "Diagnostic mammography, including computer-aided detection; unilateral", "rvu": 0.70},
        {"code": "77066", "desc": "Diagnostic mammography, including computer-aided detection; bilateral", "rvu": 0.87},
        {"code": "77067", "desc": "Screening mammography, bilateral, including computer-aided detection", "rvu": 0.70},

        # DEXA
        {"code": "77080", "desc": "Dual-energy X-ray absorptiometry (DXA), bone density study; axial skeleton", "rvu": 0.20},
        {"code": "77081", "desc": "Dual-energy X-ray absorptiometry (DXA), bone density study; appendicular skeleton", "rvu": 0.12},
        {"code": "77085", "desc": "Dual-energy X-ray absorptiometry (DXA), bone density study; axial skeleton including vertebral fracture assessment", "rvu": 0.30},

        # Fluoroscopy
        {"code": "77001", "desc": "Fluoroscopic guidance for central venous access device placement", "rvu": 0.40},
        {"code": "77002", "desc": "Fluoroscopic guidance for needle placement", "rvu": 0.33},
        {"code": "77003", "desc": "Fluoroscopic guidance and localization of needle or catheter tip for spine or paraspinous diagnostic or therapeutic injection procedures", "rvu": 0.51},

        # Nuclear Medicine
        {"code": "78014", "desc": "Thyroid imaging, with uptake; single determination", "rvu": 0.61},
        {"code": "78015", "desc": "Thyroid imaging, with uptake; multiple determinations", "rvu": 0.67},
        {"code": "78016", "desc": "Thyroid imaging, with uptake, with stimulation or suppression", "rvu": 0.67},
        {"code": "78070", "desc": "Parathyroid planar imaging", "rvu": 0.74},
        {"code": "78071", "desc": "Parathyroid planar imaging with tomographic SPECT", "rvu": 1.03},
        {"code": "78072", "desc": "Parathyroid planar imaging with tomographic SPECT and CT", "rvu": 1.40},
        {"code": "78226", "desc": "Hepatobiliary system imaging, including gallbladder", "rvu": 0.79},
        {"code": "78227", "desc": "Hepatobiliary system imaging, including gallbladder; with pharmacologic intervention", "rvu": 1.01},
        {"code": "78264", "desc": "Gastric emptying imaging study", "rvu": 0.80},
        {"code": "78300", "desc": "Bone and/or joint imaging; limited area", "rvu": 0.54},
        {"code": "78305", "desc": "Bone and/or joint imaging; multiple areas", "rvu": 0.66},
        {"code": "78306", "desc": "Bone and/or joint imaging; whole body", "rvu": 0.94},
        {"code": "78315", "desc": "Bone and/or joint imaging; 3 phase study", "rvu": 1.10},
        {"code": "78414", "desc": "Determination of central c-v hemodynamics, imaging, with imaging supervision", "rvu": 0.59},
        {"code": "78451", "desc": "Myocardial perfusion imaging, tomographic (SPECT), single study", "rvu": 1.34},
        {"code": "78452", "desc": "Myocardial perfusion imaging, tomographic (SPECT), multiple studies", "rvu": 1.62},
        {"code": "78453", "desc": "Myocardial perfusion imaging, planar; single study", "rvu": 0.74},
        {"code": "78454", "desc": "Myocardial perfusion imaging, planar; multiple studies", "rvu": 1.03},
        {"code": "78466", "desc": "Myocardial imaging, infarct avid, planar", "rvu": 0.58},
        {"code": "78472", "desc": "Cardiac blood pool imaging, gated equilibrium; planar, single study", "rvu": 0.74},
        {"code": "78579", "desc": "Pulmonary perfusion imaging", "rvu": 0.74},
        {"code": "78580", "desc": "Pulmonary perfusion imaging, particulate", "rvu": 0.74},
        {"code": "78582", "desc": "Pulmonary ventilation and perfusion imaging", "rvu": 1.10},
        {"code": "78597", "desc": "Quantitative differential pulmonary perfusion and ventilation", "rvu": 1.18},
        {"code": "78600", "desc": "Brain imaging, less than 4 static views", "rvu": 0.80},
        {"code": "78601", "desc": "Brain imaging, with vascular flow", "rvu": 1.04},
        {"code": "78607", "desc": "Brain imaging, tomographic (SPECT)", "rvu": 1.34},
        {"code": "78608", "desc": "Brain imaging, positron emission tomography (PET)", "rvu": 1.80},
        {"code": "78609", "desc": "Brain imaging, positron emission tomography (PET); with CT for attenuation correction", "rvu": 2.10},
        {"code": "78800", "desc": "Radiopharmaceutical localization of tumor; limited area", "rvu": 0.80},
        {"code": "78801", "desc": "Radiopharmaceutical localization of tumor; multiple areas", "rvu": 1.10},
        {"code": "78802", "desc": "Radiopharmaceutical localization of tumor; whole body, single day imaging", "rvu": 1.34},
        {"code": "78803", "desc": "Radiopharmaceutical localization of tumor; tomographic (SPECT)", "rvu": 1.50},
        {"code": "78811", "desc": "Positron emission tomography (PET) imaging; limited area", "rvu": 1.35},
        {"code": "78812", "desc": "Positron emission tomography (PET) imaging; skull base to mid-thigh", "rvu": 1.75},
        {"code": "78813", "desc": "Positron emission tomography (PET) imaging; whole body", "rvu": 1.98},
        {"code": "78814", "desc": "Positron emission tomography (PET) with concurrently acquired CT; limited area", "rvu": 1.75},
        {"code": "78815", "desc": "Positron emission tomography (PET) with concurrently acquired CT; skull base to mid-thigh", "rvu": 2.37},
        {"code": "78816", "desc": "Positron emission tomography (PET) with concurrently acquired CT; whole body", "rvu": 2.68},
    ]

    for rad in radiology_codes:
        codes.append({
            "concept_code": rad["code"],
            "concept_name": rad["desc"],
            "category": "Radiology",
            "work_rvu": rad["rvu"],
            "synonyms": [],
        })

    return codes


# =============================================================================
# PATHOLOGY/LAB CODES (80000-89999)
# =============================================================================
def generate_pathology_codes() -> list[dict[str, Any]]:
    """Generate pathology and laboratory codes."""
    codes = []

    pathology_codes = [
        # Organ/Disease Panels
        {"code": "80047", "desc": "Basic metabolic panel (Calcium, ionized)", "rvu": 0.0},
        {"code": "80048", "desc": "Basic metabolic panel (Calcium, total)", "rvu": 0.0},
        {"code": "80050", "desc": "General health panel", "rvu": 0.0},
        {"code": "80051", "desc": "Electrolyte panel", "rvu": 0.0},
        {"code": "80053", "desc": "Comprehensive metabolic panel", "rvu": 0.0},
        {"code": "80055", "desc": "Obstetric panel", "rvu": 0.0},
        {"code": "80061", "desc": "Lipid panel", "rvu": 0.0},
        {"code": "80069", "desc": "Renal function panel", "rvu": 0.0},
        {"code": "80074", "desc": "Acute hepatitis panel", "rvu": 0.0},
        {"code": "80076", "desc": "Hepatic function panel", "rvu": 0.0},

        # Drug Testing
        {"code": "80305", "desc": "Drug test(s), presumptive, any number of drug classes; any number of devices or procedures, read by direct optical observation", "rvu": 0.0},
        {"code": "80306", "desc": "Drug test(s), presumptive, any number of drug classes; any number of devices or procedures, read by instrument", "rvu": 0.0},
        {"code": "80307", "desc": "Drug test(s), presumptive, any number of drug classes; by instrument chemistry analyzers", "rvu": 0.0},

        # Therapeutic Drug Assays
        {"code": "80150", "desc": "Amikacin", "rvu": 0.0},
        {"code": "80155", "desc": "Caffeine", "rvu": 0.0},
        {"code": "80156", "desc": "Carbamazepine; total", "rvu": 0.0},
        {"code": "80157", "desc": "Carbamazepine; free", "rvu": 0.0},
        {"code": "80158", "desc": "Cyclosporine", "rvu": 0.0},
        {"code": "80162", "desc": "Digoxin; total", "rvu": 0.0},
        {"code": "80164", "desc": "Valproic acid (dipropylacetic acid); total", "rvu": 0.0},
        {"code": "80165", "desc": "Valproic acid (dipropylacetic acid); free", "rvu": 0.0},
        {"code": "80168", "desc": "Ethosuximide", "rvu": 0.0},
        {"code": "80170", "desc": "Gentamicin", "rvu": 0.0},
        {"code": "80171", "desc": "Gabapentin, whole blood, serum, or plasma", "rvu": 0.0},
        {"code": "80175", "desc": "Lamotrigine", "rvu": 0.0},
        {"code": "80177", "desc": "Levetiracetam", "rvu": 0.0},
        {"code": "80178", "desc": "Lithium", "rvu": 0.0},
        {"code": "80180", "desc": "Mycophenolate (mycophenolic acid)", "rvu": 0.0},
        {"code": "80183", "desc": "Oxcarbazepine", "rvu": 0.0},
        {"code": "80184", "desc": "Phenobarbital", "rvu": 0.0},
        {"code": "80185", "desc": "Phenytoin; total", "rvu": 0.0},
        {"code": "80186", "desc": "Phenytoin; free", "rvu": 0.0},
        {"code": "80188", "desc": "Primidone", "rvu": 0.0},
        {"code": "80190", "desc": "Procainamide", "rvu": 0.0},
        {"code": "80192", "desc": "Procainamide; with metabolites", "rvu": 0.0},
        {"code": "80194", "desc": "Quinidine", "rvu": 0.0},
        {"code": "80195", "desc": "Sirolimus", "rvu": 0.0},
        {"code": "80197", "desc": "Tacrolimus", "rvu": 0.0},
        {"code": "80198", "desc": "Theophylline", "rvu": 0.0},
        {"code": "80199", "desc": "Tiagabine", "rvu": 0.0},
        {"code": "80200", "desc": "Tobramycin", "rvu": 0.0},
        {"code": "80201", "desc": "Topiramate", "rvu": 0.0},
        {"code": "80202", "desc": "Vancomycin", "rvu": 0.0},
        {"code": "80203", "desc": "Zonisamide", "rvu": 0.0},

        # Chemistry
        {"code": "82040", "desc": "Albumin; serum, plasma or whole blood", "rvu": 0.0},
        {"code": "82042", "desc": "Albumin; urine or other source, quantitative", "rvu": 0.0},
        {"code": "82043", "desc": "Albumin; urine, microalbumin, quantitative", "rvu": 0.0},
        {"code": "82044", "desc": "Albumin; urine, microalbumin, semiquantitative", "rvu": 0.0},
        {"code": "82105", "desc": "Alpha-fetoprotein (AFP); serum", "rvu": 0.0},
        {"code": "82106", "desc": "Alpha-fetoprotein (AFP); amniotic fluid", "rvu": 0.0},
        {"code": "82108", "desc": "Aluminum", "rvu": 0.0},
        {"code": "82140", "desc": "Ammonia", "rvu": 0.0},
        {"code": "82150", "desc": "Amylase", "rvu": 0.0},
        {"code": "82164", "desc": "Angiotensin I - converting enzyme (ACE)", "rvu": 0.0},
        {"code": "82172", "desc": "Apolipoprotein, each", "rvu": 0.0},
        {"code": "82175", "desc": "Arsenic", "rvu": 0.0},
        {"code": "82180", "desc": "Ascorbic acid (Vitamin C), blood", "rvu": 0.0},
        {"code": "82232", "desc": "Beta-2 microglobulin", "rvu": 0.0},
        {"code": "82247", "desc": "Bilirubin; total", "rvu": 0.0},
        {"code": "82248", "desc": "Bilirubin; direct", "rvu": 0.0},
        {"code": "82270", "desc": "Blood, occult, by peroxidase activity, feces; qualitative", "rvu": 0.0},
        {"code": "82271", "desc": "Blood, occult, by peroxidase activity, other sources; qualitative", "rvu": 0.0},
        {"code": "82272", "desc": "Blood, occult, by peroxidase activity, feces; 1-3 simultaneous determinations", "rvu": 0.0},
        {"code": "82274", "desc": "Blood, occult, by fecal hemoglobin determination by immunoassay, qualitative", "rvu": 0.0},
        {"code": "82306", "desc": "Vitamin D; 25 hydroxy, includes fraction(s), if performed", "rvu": 0.0},
        {"code": "82310", "desc": "Calcium; total", "rvu": 0.0},
        {"code": "82330", "desc": "Calcium; ionized", "rvu": 0.0},
        {"code": "82340", "desc": "Calcium; urine quantitative, timed specimen", "rvu": 0.0},
        {"code": "82374", "desc": "Carbon dioxide (bicarbonate)", "rvu": 0.0},
        {"code": "82378", "desc": "Carcinoembryonic antigen (CEA)", "rvu": 0.0},
        {"code": "82379", "desc": "Carnitine (total and free), quantitative, each specimen", "rvu": 0.0},
        {"code": "82380", "desc": "Carotene", "rvu": 0.0},
        {"code": "82384", "desc": "Catecholamines; total urine", "rvu": 0.0},
        {"code": "82435", "desc": "Chloride; blood", "rvu": 0.0},
        {"code": "82436", "desc": "Chloride; urine", "rvu": 0.0},
        {"code": "82465", "desc": "Cholesterol, serum or whole blood, total", "rvu": 0.0},
        {"code": "82507", "desc": "Citrate", "rvu": 0.0},
        {"code": "82523", "desc": "Collagen cross links, any method", "rvu": 0.0},
        {"code": "82530", "desc": "Cortisol; free", "rvu": 0.0},
        {"code": "82533", "desc": "Cortisol; total", "rvu": 0.0},
        {"code": "82550", "desc": "Creatine kinase (CK), (CPK); total", "rvu": 0.0},
        {"code": "82552", "desc": "Creatine kinase (CK), (CPK); isoenzymes", "rvu": 0.0},
        {"code": "82553", "desc": "Creatine kinase (CK), (CPK); MB fraction only", "rvu": 0.0},
        {"code": "82565", "desc": "Creatinine; blood", "rvu": 0.0},
        {"code": "82570", "desc": "Creatinine; other source", "rvu": 0.0},
        {"code": "82575", "desc": "Creatinine; clearance", "rvu": 0.0},
        {"code": "82607", "desc": "Cyanocobalamin (Vitamin B-12)", "rvu": 0.0},
        {"code": "82627", "desc": "Dehydroepiandrosterone-sulfate (DHEA-S)", "rvu": 0.0},
        {"code": "82670", "desc": "Estradiol", "rvu": 0.0},
        {"code": "82677", "desc": "Estriol", "rvu": 0.0},
        {"code": "82728", "desc": "Ferritin", "rvu": 0.0},
        {"code": "82746", "desc": "Folic acid; serum", "rvu": 0.0},
        {"code": "82747", "desc": "Folic acid; RBC", "rvu": 0.0},
        {"code": "82784", "desc": "Gammaglobulin (immunoglobulin); IgA, IgD, IgG, IgM, each", "rvu": 0.0},
        {"code": "82785", "desc": "Gammaglobulin (immunoglobulin); IgE", "rvu": 0.0},
        {"code": "82803", "desc": "Gases, blood, any combination of pH, pCO2, pO2, CO2, HCO3", "rvu": 0.0},
        {"code": "82941", "desc": "Gastrin", "rvu": 0.0},
        {"code": "82943", "desc": "Glucagon", "rvu": 0.0},
        {"code": "82947", "desc": "Glucose; quantitative, blood (except reagent strip)", "rvu": 0.0},
        {"code": "82948", "desc": "Glucose; blood, reagent strip", "rvu": 0.0},
        {"code": "82950", "desc": "Glucose; post glucose dose (includes glucose)", "rvu": 0.0},
        {"code": "82951", "desc": "Glucose; tolerance test (GTT), 3 specimens", "rvu": 0.0},
        {"code": "82952", "desc": "Glucose; tolerance test, each additional beyond 3 specimens", "rvu": 0.0},
        {"code": "82962", "desc": "Glucose, blood by glucose monitoring device(s) cleared by FDA", "rvu": 0.0},
        {"code": "83001", "desc": "Gonadotropin; follicle stimulating hormone (FSH)", "rvu": 0.0},
        {"code": "83002", "desc": "Gonadotropin; luteinizing hormone (LH)", "rvu": 0.0},
        {"code": "83003", "desc": "Growth hormone, human (HGH) (somatotropin)", "rvu": 0.0},
        {"code": "83010", "desc": "Haptoglobin; quantitative", "rvu": 0.0},
        {"code": "83036", "desc": "Hemoglobin; glycosylated (A1C)", "rvu": 0.0},
        {"code": "83037", "desc": "Hemoglobin; glycosylated (A1C) by device cleared by FDA for home use", "rvu": 0.0},
        {"code": "83516", "desc": "Immunoassay for analyte other than infectious agent antibody or infectious agent antigen; qualitative or semiquantitative, multiple step method", "rvu": 0.0},
        {"code": "83518", "desc": "Immunoassay for analyte other than infectious agent antibody or infectious agent antigen; qualitative or semiquantitative, single step method", "rvu": 0.0},
        {"code": "83520", "desc": "Immunoassay for analyte other than infectious agent antibody or infectious agent antigen; quantitative, not otherwise specified", "rvu": 0.0},
        {"code": "83540", "desc": "Iron", "rvu": 0.0},
        {"code": "83550", "desc": "Iron binding capacity", "rvu": 0.0},
        {"code": "83615", "desc": "Lactate dehydrogenase (LDH)", "rvu": 0.0},
        {"code": "83625", "desc": "Lactate dehydrogenase (LDH); isoenzymes, separation and quantitation", "rvu": 0.0},
        {"code": "83690", "desc": "Lipase", "rvu": 0.0},
        {"code": "83695", "desc": "Lipoprotein (a)", "rvu": 0.0},
        {"code": "83718", "desc": "Lipoprotein, direct measurement; high density cholesterol (HDL cholesterol)", "rvu": 0.0},
        {"code": "83719", "desc": "Lipoprotein, direct measurement; VLDL cholesterol", "rvu": 0.0},
        {"code": "83721", "desc": "Lipoprotein, direct measurement; LDL cholesterol", "rvu": 0.0},
        {"code": "83735", "desc": "Magnesium", "rvu": 0.0},
        {"code": "83825", "desc": "Mercury, quantitative", "rvu": 0.0},
        {"code": "83835", "desc": "Metanephrines", "rvu": 0.0},
        {"code": "83880", "desc": "Natriuretic peptide (BNP)", "rvu": 0.0},
        {"code": "83970", "desc": "Parathormone (parathyroid hormone)", "rvu": 0.0},
        {"code": "84075", "desc": "Phosphatase, alkaline", "rvu": 0.0},
        {"code": "84080", "desc": "Phosphatase, alkaline; isoenzymes", "rvu": 0.0},
        {"code": "84100", "desc": "Phosphorus inorganic (phosphate)", "rvu": 0.0},
        {"code": "84132", "desc": "Potassium; serum, plasma or whole blood", "rvu": 0.0},
        {"code": "84133", "desc": "Potassium; urine", "rvu": 0.0},
        {"code": "84134", "desc": "Prealbumin", "rvu": 0.0},
        {"code": "84144", "desc": "Progesterone", "rvu": 0.0},
        {"code": "84146", "desc": "Prolactin", "rvu": 0.0},
        {"code": "84152", "desc": "Prostate specific antigen (PSA); complexed (direct measurement)", "rvu": 0.0},
        {"code": "84153", "desc": "Prostate specific antigen (PSA); total", "rvu": 0.0},
        {"code": "84154", "desc": "Prostate specific antigen (PSA); free", "rvu": 0.0},
        {"code": "84155", "desc": "Protein, total, except by refractometry; serum, plasma or whole blood", "rvu": 0.0},
        {"code": "84156", "desc": "Protein, total, except by refractometry; urine", "rvu": 0.0},
        {"code": "84165", "desc": "Protein; electrophoretic fractionation and quantitation, serum", "rvu": 0.0},
        {"code": "84166", "desc": "Protein; electrophoretic fractionation and quantitation, other fluids", "rvu": 0.0},
        {"code": "84295", "desc": "Sodium; serum, plasma or whole blood", "rvu": 0.0},
        {"code": "84300", "desc": "Sodium; urine", "rvu": 0.0},
        {"code": "84402", "desc": "Testosterone; free", "rvu": 0.0},
        {"code": "84403", "desc": "Testosterone; total", "rvu": 0.0},
        {"code": "84436", "desc": "Thyroxine; total", "rvu": 0.0},
        {"code": "84439", "desc": "Thyroxine; free", "rvu": 0.0},
        {"code": "84443", "desc": "Thyroid stimulating hormone (TSH)", "rvu": 0.0},
        {"code": "84450", "desc": "Transferase; aspartate amino (AST) (SGOT)", "rvu": 0.0},
        {"code": "84460", "desc": "Transferase; alanine amino (ALT) (SGPT)", "rvu": 0.0},
        {"code": "84478", "desc": "Triglycerides", "rvu": 0.0},
        {"code": "84479", "desc": "Thyroid hormone (T3 or T4) uptake or thyroid hormone binding ratio (THBR)", "rvu": 0.0},
        {"code": "84480", "desc": "Triiodothyronine T3; total (TT-3)", "rvu": 0.0},
        {"code": "84481", "desc": "Triiodothyronine T3; free", "rvu": 0.0},
        {"code": "84482", "desc": "Triiodothyronine T3; reverse", "rvu": 0.0},
        {"code": "84484", "desc": "Troponin, quantitative", "rvu": 0.0},
        {"code": "84520", "desc": "Urea nitrogen; quantitative", "rvu": 0.0},
        {"code": "84540", "desc": "Urea nitrogen, urine", "rvu": 0.0},
        {"code": "84550", "desc": "Uric acid; blood", "rvu": 0.0},
        {"code": "84560", "desc": "Uric acid; other source", "rvu": 0.0},
        {"code": "84702", "desc": "Gonadotropin, chorionic (hCG); quantitative", "rvu": 0.0},
        {"code": "84703", "desc": "Gonadotropin, chorionic (hCG); qualitative", "rvu": 0.0},

        # Hematology
        {"code": "85004", "desc": "Blood count; automated differential WBC count", "rvu": 0.0},
        {"code": "85007", "desc": "Blood count; blood smear, microscopic examination with manual differential WBC count", "rvu": 0.0},
        {"code": "85008", "desc": "Blood count; blood smear, microscopic examination without manual differential WBC count", "rvu": 0.0},
        {"code": "85014", "desc": "Blood count; hematocrit (Hct)", "rvu": 0.0},
        {"code": "85018", "desc": "Blood count; hemoglobin (Hgb)", "rvu": 0.0},
        {"code": "85025", "desc": "Blood count; complete (CBC), automated (Hgb, Hct, RBC, WBC and platelet count) and automated differential WBC count", "rvu": 0.0},
        {"code": "85027", "desc": "Blood count; complete (CBC), automated (Hgb, Hct, RBC, WBC and platelet count)", "rvu": 0.0},
        {"code": "85032", "desc": "Blood count; manual cell count (erythrocyte, leukocyte, or platelet) each", "rvu": 0.0},
        {"code": "85041", "desc": "Blood count; red blood cell (RBC), automated", "rvu": 0.0},
        {"code": "85044", "desc": "Blood count; reticulocyte, manual", "rvu": 0.0},
        {"code": "85045", "desc": "Blood count; reticulocyte, automated", "rvu": 0.0},
        {"code": "85046", "desc": "Blood count; reticulocyte, automated, including 1 or more cellular parameters", "rvu": 0.0},
        {"code": "85048", "desc": "Blood count; leukocyte (WBC), automated", "rvu": 0.0},
        {"code": "85049", "desc": "Blood count; platelet, automated", "rvu": 0.0},

        # Coagulation
        {"code": "85210", "desc": "Clotting; factor II, prothrombin, specific", "rvu": 0.0},
        {"code": "85220", "desc": "Clotting; factor V (AcG or proaccelerin), labile factor", "rvu": 0.0},
        {"code": "85230", "desc": "Clotting; factor VII (proconvertin, stable factor)", "rvu": 0.0},
        {"code": "85240", "desc": "Clotting; factor VIII (AHG), 1-stage", "rvu": 0.0},
        {"code": "85245", "desc": "Clotting; factor VIII, related antigen", "rvu": 0.0},
        {"code": "85250", "desc": "Clotting; factor IX (PTC or Christmas)", "rvu": 0.0},
        {"code": "85260", "desc": "Clotting; factor X (Stuart-Prower)", "rvu": 0.0},
        {"code": "85270", "desc": "Clotting; factor XI (PTA)", "rvu": 0.0},
        {"code": "85280", "desc": "Clotting; factor XII (Hageman)", "rvu": 0.0},
        {"code": "85290", "desc": "Clotting; factor XIII (fibrin stabilizing)", "rvu": 0.0},
        {"code": "85300", "desc": "Clotting inhibitors or anticoagulants; antithrombin III, activity", "rvu": 0.0},
        {"code": "85301", "desc": "Clotting inhibitors or anticoagulants; antithrombin III, antigen assay", "rvu": 0.0},
        {"code": "85302", "desc": "Clotting inhibitors or anticoagulants; protein C, antigen", "rvu": 0.0},
        {"code": "85303", "desc": "Clotting inhibitors or anticoagulants; protein C, activity", "rvu": 0.0},
        {"code": "85305", "desc": "Clotting inhibitors or anticoagulants; protein S, total", "rvu": 0.0},
        {"code": "85306", "desc": "Clotting inhibitors or anticoagulants; protein S, free", "rvu": 0.0},
        {"code": "85307", "desc": "Activated Protein C (APC) resistance assay", "rvu": 0.0},
        {"code": "85379", "desc": "Fibrin degradation products, D-dimer; quantitative", "rvu": 0.0},
        {"code": "85380", "desc": "Fibrin degradation products, D-dimer; semiquantitative", "rvu": 0.0},
        {"code": "85384", "desc": "Fibrinogen; activity", "rvu": 0.0},
        {"code": "85385", "desc": "Fibrinogen; antigen", "rvu": 0.0},
        {"code": "85610", "desc": "Prothrombin time", "rvu": 0.0},
        {"code": "85611", "desc": "Prothrombin time; substitution, plasma fractions, each", "rvu": 0.0},
        {"code": "85612", "desc": "Russell viper venom time (includes venom)", "rvu": 0.0},
        {"code": "85613", "desc": "Russell viper venom time; diluted", "rvu": 0.0},
        {"code": "85651", "desc": "Sedimentation rate, erythrocyte; non-automated", "rvu": 0.0},
        {"code": "85652", "desc": "Sedimentation rate, erythrocyte; automated", "rvu": 0.0},
        {"code": "85670", "desc": "Thrombin time; plasma", "rvu": 0.0},
        {"code": "85730", "desc": "Thromboplastin time, partial (PTT); plasma or whole blood", "rvu": 0.0},
        {"code": "85732", "desc": "Thromboplastin time, partial (PTT); substitution, plasma fractions, each", "rvu": 0.0},

        # Urinalysis
        {"code": "81000", "desc": "Urinalysis, by dip stick or tablet reagent; non-automated, with microscopy", "rvu": 0.0},
        {"code": "81001", "desc": "Urinalysis, by dip stick or tablet reagent; automated, with microscopy", "rvu": 0.0},
        {"code": "81002", "desc": "Urinalysis, by dip stick or tablet reagent; non-automated, without microscopy", "rvu": 0.0},
        {"code": "81003", "desc": "Urinalysis, by dip stick or tablet reagent; automated, without microscopy", "rvu": 0.0},
        {"code": "81005", "desc": "Urinalysis; qualitative or semiquantitative, except immunoassays", "rvu": 0.0},
        {"code": "81007", "desc": "Urinalysis; bacteriuria screen, except by culture or dipstick", "rvu": 0.0},
        {"code": "81015", "desc": "Urinalysis; microscopic only", "rvu": 0.0},
        {"code": "81020", "desc": "Urinalysis; 2 or 3 glass test", "rvu": 0.0},
        {"code": "81025", "desc": "Urine pregnancy test, by visual color comparison methods", "rvu": 0.0},
        {"code": "81050", "desc": "Volume measurement for timed collection, each", "rvu": 0.0},

        # Microbiology
        {"code": "87040", "desc": "Culture, bacterial; blood, aerobic, with isolation and presumptive identification of isolates", "rvu": 0.0},
        {"code": "87045", "desc": "Culture, bacterial; stool, aerobic, with isolation and preliminary examination", "rvu": 0.0},
        {"code": "87046", "desc": "Culture, bacterial; stool, aerobic, additional pathogens, isolation and presumptive identification", "rvu": 0.0},
        {"code": "87070", "desc": "Culture, bacterial; any other source except urine, blood or stool, aerobic", "rvu": 0.0},
        {"code": "87071", "desc": "Culture, bacterial; quantitative, aerobic with isolation and presumptive identification", "rvu": 0.0},
        {"code": "87073", "desc": "Culture, bacterial; quantitative, anaerobic with isolation and presumptive identification", "rvu": 0.0},
        {"code": "87075", "desc": "Culture, bacterial; any source, except blood, anaerobic with isolation and presumptive identification", "rvu": 0.0},
        {"code": "87076", "desc": "Culture, bacterial; anaerobic isolate, additional methods required for definitive identification", "rvu": 0.0},
        {"code": "87077", "desc": "Culture, bacterial; aerobic isolate, additional methods required for definitive identification", "rvu": 0.0},
        {"code": "87081", "desc": "Culture, presumptive, pathogenic organisms, screening only", "rvu": 0.0},
        {"code": "87086", "desc": "Culture, bacterial; quantitative colony count, urine", "rvu": 0.0},
        {"code": "87088", "desc": "Culture, bacterial; with isolation and presumptive identification of each isolate, urine", "rvu": 0.0},
        {"code": "87101", "desc": "Culture, fungi (mold or yeast) isolation, with presumptive identification of isolates; skin, hair, or nail", "rvu": 0.0},
        {"code": "87102", "desc": "Culture, fungi; isolation, with presumptive identification of isolates; other source (except blood)", "rvu": 0.0},
        {"code": "87103", "desc": "Culture, fungi; blood, isolation, with presumptive identification of isolates", "rvu": 0.0},
        {"code": "87106", "desc": "Culture, fungi; definitive identification, each organism; yeast", "rvu": 0.0},
        {"code": "87107", "desc": "Culture, fungi; definitive identification, each organism; mold", "rvu": 0.0},
        {"code": "87110", "desc": "Culture, chlamydia, any source", "rvu": 0.0},
        {"code": "87116", "desc": "Culture, tubercle or other acid-fast bacilli; any source, with concentration and enrichment", "rvu": 0.0},
        {"code": "87140", "desc": "Culture, typing; immunofluorescent method, each antiserum", "rvu": 0.0},
        {"code": "87143", "desc": "Culture, typing; gas liquid chromatography (GLC) or high pressure liquid chromatography (HPLC) method", "rvu": 0.0},
        {"code": "87147", "desc": "Culture, typing; immunologic method, other than immunofluorescence", "rvu": 0.0},
        {"code": "87149", "desc": "Culture, typing; identification by nucleic acid (DNA or RNA) probe, direct probe technique", "rvu": 0.0},
        {"code": "87150", "desc": "Culture, typing; identification by nucleic acid (DNA or RNA) probe, amplified probe technique", "rvu": 0.0},
        {"code": "87152", "desc": "Culture, typing; identification by pulse field gel typing", "rvu": 0.0},
        {"code": "87153", "desc": "Culture, typing; identification by nucleic acid sequencing method, each isolate", "rvu": 0.0},
        {"code": "87158", "desc": "Culture, typing; other methods", "rvu": 0.0},
        {"code": "87164", "desc": "Dark field examination, any source; includes specimen collection", "rvu": 0.0},
        {"code": "87166", "desc": "Dark field examination, any source; without collection", "rvu": 0.0},
        {"code": "87168", "desc": "Macroscopic examination; arthropod", "rvu": 0.0},
        {"code": "87169", "desc": "Macroscopic examination; parasite", "rvu": 0.0},
        {"code": "87172", "desc": "Pinworm exam (eg, cellophane tape prep)", "rvu": 0.0},
        {"code": "87176", "desc": "Homogenization, tissue, for culture", "rvu": 0.0},
        {"code": "87177", "desc": "Ova and parasites, direct smears, concentration and identification", "rvu": 0.0},
        {"code": "87181", "desc": "Susceptibility studies, antimicrobial agent; agar dilution method, per agent", "rvu": 0.0},
        {"code": "87184", "desc": "Susceptibility studies, antimicrobial agent; disk method, per plate", "rvu": 0.0},
        {"code": "87185", "desc": "Susceptibility studies, antimicrobial agent; enzyme detection", "rvu": 0.0},
        {"code": "87186", "desc": "Susceptibility studies, antimicrobial agent; microdilution or agar dilution (MIC or breakpoint)", "rvu": 0.0},
        {"code": "87187", "desc": "Susceptibility studies, antimicrobial agent; microdilution or agar dilution, minimum lethal concentration (MLC)", "rvu": 0.0},
        {"code": "87188", "desc": "Susceptibility studies, antimicrobial agent; macrobroth dilution method, each agent", "rvu": 0.0},
        {"code": "87190", "desc": "Susceptibility studies, antimicrobial agent; mycobacteria, proportion method, each agent", "rvu": 0.0},
        {"code": "87197", "desc": "Serum bactericidal titer (Schlichter test)", "rvu": 0.0},
        {"code": "87205", "desc": "Smear, primary source with interpretation; Gram or Giemsa stain for bacteria, fungi, or cell types", "rvu": 0.0},
        {"code": "87206", "desc": "Smear, primary source with interpretation; fluorescent and/or acid fast stain for bacteria, fungi, parasites, viruses or cell types", "rvu": 0.0},
        {"code": "87207", "desc": "Smear, primary source with interpretation; special stain for inclusion bodies or parasites", "rvu": 0.0},
        {"code": "87209", "desc": "Smear, primary source with interpretation; complex special stain", "rvu": 0.0},
        {"code": "87210", "desc": "Smear, primary source with interpretation; wet mount for infectious agents", "rvu": 0.0},
        {"code": "87220", "desc": "Tissue examination by KOH slide of samples from skin, hair, or nails for fungi or ectoparasite ova or mites", "rvu": 0.0},

        # Infectious Disease Testing
        {"code": "87340", "desc": "Infectious agent antigen detection by immunoassay technique; Hepatitis B surface antigen (HBsAg)", "rvu": 0.0},
        {"code": "87341", "desc": "Infectious agent antigen detection by immunoassay technique; Hepatitis B surface antigen (HBsAg) neutralization", "rvu": 0.0},
        {"code": "87350", "desc": "Infectious agent antigen detection by immunoassay technique; Hepatitis Be antigen (HBeAg)", "rvu": 0.0},
        {"code": "87380", "desc": "Infectious agent antigen detection by immunoassay technique; Hepatitis, delta agent", "rvu": 0.0},
        {"code": "87389", "desc": "Infectious agent antigen detection by immunoassay technique; HIV-1 antigen(s), with HIV-1 and HIV-2 antibodies, single result", "rvu": 0.0},
        {"code": "87390", "desc": "Infectious agent antigen detection by immunoassay technique; HIV-1", "rvu": 0.0},
        {"code": "87391", "desc": "Infectious agent antigen detection by immunoassay technique; HIV-2", "rvu": 0.0},
        {"code": "87400", "desc": "Infectious agent antigen detection by immunoassay technique; influenza, A or B, each", "rvu": 0.0},
        {"code": "87420", "desc": "Infectious agent antigen detection by immunoassay technique; respiratory syncytial virus", "rvu": 0.0},
        {"code": "87426", "desc": "Infectious agent antigen detection by immunoassay technique; SARS-CoV-2 (COVID-19)", "rvu": 0.0},
        {"code": "87449", "desc": "Infectious agent antigen detection by immunoassay technique; organism, multiple-step method, not otherwise specified", "rvu": 0.0},
        {"code": "87450", "desc": "Infectious agent antigen detection by immunoassay technique; organism, single-step method, not otherwise specified", "rvu": 0.0},
        {"code": "87480", "desc": "Infectious agent detection by nucleic acid (DNA or RNA); Candida species, direct probe technique", "rvu": 0.0},
        {"code": "87490", "desc": "Infectious agent detection by nucleic acid; Chlamydia trachomatis, direct probe technique", "rvu": 0.0},
        {"code": "87491", "desc": "Infectious agent detection by nucleic acid; Chlamydia trachomatis, amplified probe technique", "rvu": 0.0},
        {"code": "87510", "desc": "Infectious agent detection by nucleic acid; Gardnerella vaginalis, direct probe technique", "rvu": 0.0},
        {"code": "87511", "desc": "Infectious agent detection by nucleic acid; Gardnerella vaginalis, amplified probe technique", "rvu": 0.0},
        {"code": "87520", "desc": "Infectious agent detection by nucleic acid; Hepatitis B virus, quantification", "rvu": 0.0},
        {"code": "87521", "desc": "Infectious agent detection by nucleic acid; Hepatitis B virus, amplified probe technique", "rvu": 0.0},
        {"code": "87522", "desc": "Infectious agent detection by nucleic acid; Hepatitis B virus, quantification", "rvu": 0.0},
        {"code": "87528", "desc": "Infectious agent detection by nucleic acid; Herpes simplex virus, direct probe technique", "rvu": 0.0},
        {"code": "87529", "desc": "Infectious agent detection by nucleic acid; Herpes simplex virus, amplified probe technique", "rvu": 0.0},
        {"code": "87530", "desc": "Infectious agent detection by nucleic acid; Herpes simplex virus, quantification", "rvu": 0.0},
        {"code": "87534", "desc": "Infectious agent detection by nucleic acid; HIV-1, direct probe technique", "rvu": 0.0},
        {"code": "87535", "desc": "Infectious agent detection by nucleic acid; HIV-1, amplified probe technique, includes reverse transcription when performed", "rvu": 0.0},
        {"code": "87536", "desc": "Infectious agent detection by nucleic acid; HIV-1, quantification, includes reverse transcription when performed", "rvu": 0.0},
        {"code": "87537", "desc": "Infectious agent detection by nucleic acid; HIV-2, direct probe technique", "rvu": 0.0},
        {"code": "87538", "desc": "Infectious agent detection by nucleic acid; HIV-2, amplified probe technique, includes reverse transcription when performed", "rvu": 0.0},
        {"code": "87539", "desc": "Infectious agent detection by nucleic acid; HIV-2, quantification, includes reverse transcription when performed", "rvu": 0.0},
        {"code": "87590", "desc": "Infectious agent detection by nucleic acid; Neisseria gonorrhoeae, direct probe technique", "rvu": 0.0},
        {"code": "87591", "desc": "Infectious agent detection by nucleic acid; Neisseria gonorrhoeae, amplified probe technique", "rvu": 0.0},
        {"code": "87624", "desc": "Infectious agent detection by nucleic acid; HPV, high-risk types", "rvu": 0.0},
        {"code": "87625", "desc": "Infectious agent detection by nucleic acid; HPV, types 16 and 18 only", "rvu": 0.0},
        {"code": "87631", "desc": "Infectious agent detection by nucleic acid; respiratory virus, multiplex reverse transcription and amplified probe technique, 3-5 targets", "rvu": 0.0},
        {"code": "87632", "desc": "Infectious agent detection by nucleic acid; respiratory virus, multiplex reverse transcription and amplified probe technique, 6-11 targets", "rvu": 0.0},
        {"code": "87633", "desc": "Infectious agent detection by nucleic acid; respiratory virus, multiplex reverse transcription and amplified probe technique, 12-25 targets", "rvu": 0.0},
        {"code": "87634", "desc": "Infectious agent detection by nucleic acid; respiratory syncytial virus, amplified probe technique", "rvu": 0.0},
        {"code": "87635", "desc": "Infectious agent detection by nucleic acid; SARS-CoV-2 (COVID-19), amplified probe technique", "rvu": 0.0},
        {"code": "87640", "desc": "Infectious agent detection by nucleic acid; Staphylococcus aureus, amplified probe technique", "rvu": 0.0},
        {"code": "87641", "desc": "Infectious agent detection by nucleic acid; Staphylococcus aureus, methicillin resistant, amplified probe technique", "rvu": 0.0},
        {"code": "87650", "desc": "Infectious agent detection by nucleic acid; Streptococcus, group A, direct probe technique", "rvu": 0.0},
        {"code": "87651", "desc": "Infectious agent detection by nucleic acid; Streptococcus, group A, amplified probe technique", "rvu": 0.0},
        {"code": "87653", "desc": "Infectious agent detection by nucleic acid; Streptococcus, group B, amplified probe technique", "rvu": 0.0},
        {"code": "87660", "desc": "Infectious agent detection by nucleic acid; Trichomonas vaginalis, direct probe technique", "rvu": 0.0},
        {"code": "87661", "desc": "Infectious agent detection by nucleic acid; Trichomonas vaginalis, amplified probe technique", "rvu": 0.0},
        {"code": "87797", "desc": "Infectious agent detection by nucleic acid; not otherwise specified, direct probe technique, each organism", "rvu": 0.0},
        {"code": "87798", "desc": "Infectious agent detection by nucleic acid; not otherwise specified, amplified probe technique, each organism", "rvu": 0.0},
        {"code": "87799", "desc": "Infectious agent detection by nucleic acid; not otherwise specified, quantification, each organism", "rvu": 0.0},
        {"code": "87800", "desc": "Infectious agent detection by nucleic acid; multiple organisms, direct probe(s) technique", "rvu": 0.0},
        {"code": "87801", "desc": "Infectious agent detection by nucleic acid; multiple organisms, amplified probe(s) technique", "rvu": 0.0},
        {"code": "87802", "desc": "Infectious agent antigen detection by immunoassay with direct optical observation; Streptococcus, group B", "rvu": 0.0},
        {"code": "87804", "desc": "Infectious agent antigen detection by immunoassay with direct optical observation; influenza", "rvu": 0.0},
        {"code": "87806", "desc": "Infectious agent antigen detection by immunoassay with direct optical observation; HIV-1 antigen(s), with HIV-1 and HIV-2 antibodies", "rvu": 0.0},
        {"code": "87807", "desc": "Infectious agent antigen detection by immunoassay with direct optical observation; respiratory syncytial virus", "rvu": 0.0},
        {"code": "87808", "desc": "Infectious agent antigen detection by immunoassay with direct optical observation; Trichomonas vaginalis", "rvu": 0.0},
        {"code": "87809", "desc": "Infectious agent antigen detection by immunoassay with direct optical observation; adenovirus", "rvu": 0.0},
        {"code": "87811", "desc": "Infectious agent antigen detection by immunoassay with direct optical observation; SARS-CoV-2 (COVID-19)", "rvu": 0.0},
        {"code": "87880", "desc": "Infectious agent antigen detection by immunoassay with direct optical observation; Streptococcus, group A", "rvu": 0.0},
        {"code": "87899", "desc": "Infectious agent antigen detection by immunoassay with direct optical observation; not otherwise specified", "rvu": 0.0},

        # Anatomic Pathology
        {"code": "88104", "desc": "Cytopathology, fluids, washings or brushings; smears with interpretation", "rvu": 0.39},
        {"code": "88108", "desc": "Cytopathology, concentration technique, smears and interpretation", "rvu": 0.42},
        {"code": "88112", "desc": "Cytopathology, selective cellular enhancement technique with interpretation", "rvu": 0.97},
        {"code": "88141", "desc": "Cytopathology, cervical or vaginal; requiring interpretation by physician", "rvu": 0.39},
        {"code": "88142", "desc": "Cytopathology, cervical or vaginal; collected in preservative fluid, automated thin layer preparation", "rvu": 0.0},
        {"code": "88143", "desc": "Cytopathology, cervical or vaginal; with manual screening and rescreening under physician supervision", "rvu": 0.0},
        {"code": "88147", "desc": "Cytopathology, cervical or vaginal; collected in preservative fluid, automated thin layer preparation, with screening by automated system, under physician supervision", "rvu": 0.0},
        {"code": "88148", "desc": "Cytopathology, cervical or vaginal; collected in preservative fluid, automated thin layer preparation, with screening by automated system and target manual rescreening", "rvu": 0.0},
        {"code": "88150", "desc": "Cytopathology, slides, cervical or vaginal; manual screening under physician supervision", "rvu": 0.0},
        {"code": "88152", "desc": "Cytopathology, slides, cervical or vaginal; with manual screening and computer-assisted rescreening under physician supervision", "rvu": 0.0},
        {"code": "88153", "desc": "Cytopathology, slides, cervical or vaginal; with manual screening and rescreening under physician supervision", "rvu": 0.0},
        {"code": "88160", "desc": "Cytopathology, smears, any other source; screening and interpretation", "rvu": 0.39},
        {"code": "88161", "desc": "Cytopathology, smears, any other source; preparation, screening and interpretation", "rvu": 0.46},
        {"code": "88172", "desc": "Cytopathology, evaluation of fine needle aspirate; immediate cytohistologic study to determine adequacy for diagnosis", "rvu": 0.48},
        {"code": "88173", "desc": "Cytopathology, evaluation of fine needle aspirate; interpretation and report", "rvu": 0.97},
        {"code": "88175", "desc": "Cytopathology, cervical or vaginal; with screening by automated system and target manual rescreening", "rvu": 0.0},
        {"code": "88177", "desc": "Cytopathology, evaluation of fine needle aspirate; each separate additional evaluation episode", "rvu": 0.48},
        {"code": "88300", "desc": "Level I - Surgical pathology, gross examination only", "rvu": 0.11},
        {"code": "88302", "desc": "Level II - Surgical pathology, gross and microscopic examination", "rvu": 0.13},
        {"code": "88304", "desc": "Level III - Surgical pathology, gross and microscopic examination", "rvu": 0.22},
        {"code": "88305", "desc": "Level IV - Surgical pathology, gross and microscopic examination", "rvu": 0.75},
        {"code": "88307", "desc": "Level V - Surgical pathology, gross and microscopic examination", "rvu": 1.59},
        {"code": "88309", "desc": "Level VI - Surgical pathology, gross and microscopic examination", "rvu": 2.28},
        {"code": "88311", "desc": "Decalcification procedure", "rvu": 0.15},
        {"code": "88312", "desc": "Special stain including interpretation and report; Group I for microorganisms", "rvu": 0.61},
        {"code": "88313", "desc": "Special stain including interpretation and report; Group II, all other", "rvu": 0.45},
        {"code": "88314", "desc": "Special stain including interpretation and report; histochemical stain on frozen tissue block", "rvu": 0.48},
        {"code": "88319", "desc": "Determinative histochemistry to identify chemical components", "rvu": 0.97},
        {"code": "88321", "desc": "Consultation and report on referred slides prepared elsewhere", "rvu": 1.49},
        {"code": "88323", "desc": "Consultation and report on referred material requiring preparation of slides", "rvu": 1.83},
        {"code": "88325", "desc": "Consultation, comprehensive, with review of records and specimens, with report on referred material", "rvu": 2.78},
        {"code": "88329", "desc": "Pathology consultation during surgery; first tissue block", "rvu": 0.88},
        {"code": "88331", "desc": "Pathology consultation during surgery; first tissue block, with frozen section(s)", "rvu": 1.19},
        {"code": "88332", "desc": "Pathology consultation during surgery; each additional tissue block with frozen section(s)", "rvu": 0.88},
        {"code": "88333", "desc": "Pathology consultation during surgery; cytologic examination", "rvu": 0.88},
        {"code": "88334", "desc": "Pathology consultation during surgery; cytologic examination, each additional site", "rvu": 0.88},
        {"code": "88341", "desc": "Immunohistochemistry or immunocytochemistry, per specimen; each additional single antibody stain procedure", "rvu": 0.48},
        {"code": "88342", "desc": "Immunohistochemistry or immunocytochemistry, per specimen; initial single antibody stain procedure", "rvu": 0.70},
        {"code": "88346", "desc": "Immunofluorescence, per specimen; each additional single antibody stain procedure", "rvu": 0.62},
        {"code": "88347", "desc": "Immunofluorescence, per specimen; initial single antibody stain procedure", "rvu": 0.97},
        {"code": "88348", "desc": "Electron microscopy, diagnostic", "rvu": 3.23},
        {"code": "88350", "desc": "Immunofluorescence, per specimen; each multiplex antibody stain procedure", "rvu": 0.0},
        {"code": "88355", "desc": "Morphometric analysis; skeletal muscle", "rvu": 1.67},
        {"code": "88356", "desc": "Morphometric analysis; nerve", "rvu": 1.67},
        {"code": "88360", "desc": "Morphometric analysis, tumor immunohistochemistry; manual", "rvu": 0.83},
        {"code": "88361", "desc": "Morphometric analysis, tumor immunohistochemistry; using computer-assisted technology", "rvu": 0.83},
        {"code": "88365", "desc": "In situ hybridization (eg, FISH), per specimen; initial single probe stain procedure", "rvu": 1.06},
        {"code": "88366", "desc": "In situ hybridization (eg, FISH), per specimen; each additional single probe stain procedure", "rvu": 0.62},
        {"code": "88367", "desc": "Morphometric analysis, in situ hybridization; manual", "rvu": 0.83},
        {"code": "88368", "desc": "Morphometric analysis, in situ hybridization; using computer-assisted technology", "rvu": 0.83},
        {"code": "88369", "desc": "Morphometric analysis, in situ hybridization; each multiplex probe stain procedure", "rvu": 0.0},
        {"code": "88371", "desc": "Protein analysis of tissue by Western Blot, with interpretation and report", "rvu": 0.83},
        {"code": "88372", "desc": "Protein analysis of tissue by Western Blot, immunological probe for band identification", "rvu": 0.62},
        {"code": "88373", "desc": "Morphometric analysis, in situ hybridization; each multiplex probe stain procedure", "rvu": 0.62},
        {"code": "88374", "desc": "Morphometric analysis, in situ hybridization; each single probe stain procedure", "rvu": 0.62},
        {"code": "88375", "desc": "Optical endomicroscopic image(s), interpretation and report, real-time or referred, each endoscopic session", "rvu": 0.60},
        {"code": "88377", "desc": "Morphometric analysis, in situ hybridization; each multiplex probe stain procedure; using computer-assisted technology", "rvu": 0.83},
        {"code": "88380", "desc": "Microdissection; manual", "rvu": 1.06},
        {"code": "88381", "desc": "Microdissection; laser capture", "rvu": 1.67},
    ]

    for path in pathology_codes:
        codes.append({
            "concept_code": path["code"],
            "concept_name": path["desc"],
            "category": "Pathology and Laboratory",
            "work_rvu": path["rvu"],
            "synonyms": [],
        })

    return codes


# =============================================================================
# MEDICINE CODES (90000-99199)
# =============================================================================
def generate_medicine_codes() -> list[dict[str, Any]]:
    """Generate medicine codes (non-E/M)."""
    codes = []

    medicine_codes = [
        # Immunization Administration
        {"code": "90460", "desc": "Immunization administration through 18 years via any route, first vaccine/toxoid component", "rvu": 0.50},
        {"code": "90461", "desc": "Immunization administration through 18 years via any route, each additional vaccine/toxoid component", "rvu": 0.35},
        {"code": "90471", "desc": "Immunization administration (first vaccine/toxoid)", "rvu": 0.17},
        {"code": "90472", "desc": "Immunization administration (each additional vaccine/toxoid)", "rvu": 0.15},
        {"code": "90473", "desc": "Immunization administration by intranasal or oral route; 1 vaccine", "rvu": 0.17},
        {"code": "90474", "desc": "Immunization administration by intranasal or oral route; each additional vaccine", "rvu": 0.15},

        # Vaccines
        {"code": "90630", "desc": "Influenza virus vaccine, quadrivalent (IIV4), split virus, preservative free", "rvu": 0.0},
        {"code": "90632", "desc": "Hepatitis A vaccine, adult dosage", "rvu": 0.0},
        {"code": "90633", "desc": "Hepatitis A vaccine, pediatric/adolescent dosage, 2 dose schedule", "rvu": 0.0},
        {"code": "90636", "desc": "Hepatitis A and hepatitis B vaccine, adult dosage", "rvu": 0.0},
        {"code": "90647", "desc": "Haemophilus influenzae type b vaccine (Hib), PRP-OMP conjugate", "rvu": 0.0},
        {"code": "90648", "desc": "Haemophilus influenzae type b vaccine (Hib), PRP-T conjugate", "rvu": 0.0},
        {"code": "90649", "desc": "Human papillomavirus vaccine, types 6, 11, 16, 18, quadrivalent", "rvu": 0.0},
        {"code": "90651", "desc": "Human papillomavirus vaccine, 9-valent", "rvu": 0.0},
        {"code": "90653", "desc": "Influenza vaccine, inactivated (IIV), subunit, adjuvanted, 65 years and older", "rvu": 0.0},
        {"code": "90654", "desc": "Influenza virus vaccine, split virus, preservative-free, for intradermal use", "rvu": 0.0},
        {"code": "90655", "desc": "Influenza virus vaccine, split virus, preservative free, 6-35 months dosage", "rvu": 0.0},
        {"code": "90656", "desc": "Influenza virus vaccine, split virus, preservative free, 3 years and older", "rvu": 0.0},
        {"code": "90657", "desc": "Influenza virus vaccine, split virus, 6-35 months dosage", "rvu": 0.0},
        {"code": "90658", "desc": "Influenza virus vaccine, split virus, 3 years and older", "rvu": 0.0},
        {"code": "90662", "desc": "Influenza virus vaccine (IIV), split virus, preservative free, high dose, for use in 65 years and older", "rvu": 0.0},
        {"code": "90670", "desc": "Pneumococcal conjugate vaccine, 13 valent (PCV13)", "rvu": 0.0},
        {"code": "90671", "desc": "Pneumococcal conjugate vaccine, 15 valent (PCV15)", "rvu": 0.0},
        {"code": "90672", "desc": "Influenza virus vaccine, quadrivalent, live, intranasal", "rvu": 0.0},
        {"code": "90674", "desc": "Influenza virus vaccine, quadrivalent (ccIIV4), derived from cell cultures, preservative free", "rvu": 0.0},
        {"code": "90680", "desc": "Rotavirus vaccine, pentavalent, 3 dose schedule, live", "rvu": 0.0},
        {"code": "90681", "desc": "Rotavirus vaccine, human, attenuated, 2 dose schedule, live", "rvu": 0.0},
        {"code": "90682", "desc": "Influenza virus vaccine, quadrivalent (RIV4), recombinant, preservative free", "rvu": 0.0},
        {"code": "90685", "desc": "Influenza virus vaccine, quadrivalent (IIV4), split virus, preservative free, 0.25 mL dosage", "rvu": 0.0},
        {"code": "90686", "desc": "Influenza virus vaccine, quadrivalent (IIV4), split virus, preservative free, 0.5 mL dosage", "rvu": 0.0},
        {"code": "90687", "desc": "Influenza virus vaccine, quadrivalent (IIV4), split virus, 0.25 mL dosage", "rvu": 0.0},
        {"code": "90688", "desc": "Influenza virus vaccine, quadrivalent (IIV4), split virus, 0.5 mL dosage", "rvu": 0.0},
        {"code": "90696", "desc": "Diphtheria, tetanus toxoids, acellular pertussis vaccine, inactivated poliovirus vaccine (DTaP-IPV)", "rvu": 0.0},
        {"code": "90698", "desc": "Diphtheria, tetanus toxoids, acellular pertussis vaccine, Haemophilus influenzae type b vaccine, inactivated poliovirus vaccine (DTaP-IPV/Hib)", "rvu": 0.0},
        {"code": "90700", "desc": "Diphtheria, tetanus toxoids, and acellular pertussis vaccine (DTaP)", "rvu": 0.0},
        {"code": "90702", "desc": "Diphtheria and tetanus toxoids adsorbed (DT)", "rvu": 0.0},
        {"code": "90707", "desc": "Measles, mumps and rubella virus vaccine (MMR)", "rvu": 0.0},
        {"code": "90710", "desc": "Measles, mumps, rubella, and varicella vaccine (MMRV)", "rvu": 0.0},
        {"code": "90713", "desc": "Poliovirus vaccine, inactivated (IPV)", "rvu": 0.0},
        {"code": "90714", "desc": "Tetanus and diphtheria toxoids adsorbed (Td), preservative free", "rvu": 0.0},
        {"code": "90715", "desc": "Tetanus, diphtheria toxoids and acellular pertussis vaccine (Tdap)", "rvu": 0.0},
        {"code": "90716", "desc": "Varicella virus vaccine (VAR)", "rvu": 0.0},
        {"code": "90723", "desc": "Diphtheria, tetanus toxoids, acellular pertussis vaccine, hepatitis B, inactivated poliovirus vaccine (DTaP-HepB-IPV)", "rvu": 0.0},
        {"code": "90732", "desc": "Pneumococcal polysaccharide vaccine, 23-valent (PPSV23)", "rvu": 0.0},
        {"code": "90733", "desc": "Meningococcal polysaccharide vaccine, serogroups A, C, Y, W-135, quadrivalent (MPSV4)", "rvu": 0.0},
        {"code": "90734", "desc": "Meningococcal conjugate vaccine, serogroups A, C, Y and W-135, quadrivalent (MenACWY)", "rvu": 0.0},
        {"code": "90736", "desc": "Zoster (shingles) vaccine (HZV), live, for subcutaneous injection", "rvu": 0.0},
        {"code": "90740", "desc": "Hepatitis B vaccine, dialysis or immunosuppressed patient dosage, 3 dose schedule", "rvu": 0.0},
        {"code": "90743", "desc": "Hepatitis B vaccine, adolescent (2 dose schedule)", "rvu": 0.0},
        {"code": "90744", "desc": "Hepatitis B vaccine, pediatric/adolescent dosage, 3 dose schedule", "rvu": 0.0},
        {"code": "90746", "desc": "Hepatitis B vaccine, adult dosage", "rvu": 0.0},
        {"code": "90747", "desc": "Hepatitis B vaccine, dialysis or immunosuppressed patient dosage, 4 dose schedule", "rvu": 0.0},
        {"code": "90750", "desc": "Zoster (shingles) vaccine (HZV), recombinant, subunit, adjuvanted", "rvu": 0.0},
        {"code": "91300", "desc": "SARS-CoV-2 (COVID-19) vaccine, mRNA-LNP, spike protein, preservative free, 30 mcg/0.3mL dosage, diluent reconstituted, for intramuscular use", "rvu": 0.0},
        {"code": "91301", "desc": "SARS-CoV-2 (COVID-19) vaccine, mRNA-LNP, spike protein, preservative free, 100 mcg/0.5mL dosage, for intramuscular use", "rvu": 0.0},
        {"code": "91303", "desc": "SARS-CoV-2 (COVID-19) vaccine, DNA, spike protein, adenovirus type 26 vector, preservative free, 5x10^10 viral particles/0.5mL dosage, for intramuscular use", "rvu": 0.0},

        # Psychiatry
        {"code": "90785", "desc": "Interactive complexity (add-on to diagnostic evaluation or psychotherapy)", "rvu": 0.25},
        {"code": "90791", "desc": "Psychiatric diagnostic evaluation", "rvu": 3.00},
        {"code": "90792", "desc": "Psychiatric diagnostic evaluation with medical services", "rvu": 3.50},
        {"code": "90832", "desc": "Psychotherapy, 30 minutes with patient", "rvu": 1.12},
        {"code": "90833", "desc": "Psychotherapy, 30 minutes with patient when performed with E/M service", "rvu": 0.80},
        {"code": "90834", "desc": "Psychotherapy, 45 minutes with patient", "rvu": 1.51},
        {"code": "90836", "desc": "Psychotherapy, 45 minutes with patient when performed with E/M service", "rvu": 1.07},
        {"code": "90837", "desc": "Psychotherapy, 60 minutes with patient", "rvu": 2.17},
        {"code": "90838", "desc": "Psychotherapy, 60 minutes with patient when performed with E/M service", "rvu": 1.54},
        {"code": "90839", "desc": "Psychotherapy for crisis; first 60 minutes", "rvu": 2.48},
        {"code": "90840", "desc": "Psychotherapy for crisis; each additional 30 minutes", "rvu": 1.21},
        {"code": "90845", "desc": "Psychoanalysis", "rvu": 1.90},
        {"code": "90846", "desc": "Family psychotherapy without patient present, 50 minutes", "rvu": 1.51},
        {"code": "90847", "desc": "Family psychotherapy with patient present, 50 minutes", "rvu": 1.54},
        {"code": "90849", "desc": "Multiple-family group psychotherapy", "rvu": 0.65},
        {"code": "90853", "desc": "Group psychotherapy", "rvu": 0.48},
        {"code": "90867", "desc": "Therapeutic repetitive transcranial magnetic stimulation (TMS) treatment; initial, including cortical mapping, motor threshold determination, delivery and management", "rvu": 1.74},
        {"code": "90868", "desc": "Therapeutic repetitive transcranial magnetic stimulation (TMS) treatment; subsequent delivery and management, per session", "rvu": 0.51},
        {"code": "90869", "desc": "Therapeutic repetitive transcranial magnetic stimulation (TMS) treatment; subsequent motor threshold re-determination with delivery and management", "rvu": 0.71},
        {"code": "90870", "desc": "Electroconvulsive therapy (ECT)", "rvu": 2.57},
        {"code": "90875", "desc": "Individual psychophysiological therapy incorporating biofeedback training, 30 minutes", "rvu": 0.63},
        {"code": "90876", "desc": "Individual psychophysiological therapy incorporating biofeedback training, 45 minutes", "rvu": 0.85},
        {"code": "90880", "desc": "Hypnotherapy", "rvu": 1.05},
        {"code": "90882", "desc": "Environmental intervention for medical management purposes", "rvu": 0.86},
        {"code": "90885", "desc": "Psychiatric evaluation of hospital records, other psychiatric reports", "rvu": 0.86},
        {"code": "90887", "desc": "Interpretation or explanation of results of psychiatric examination to family or other responsible persons", "rvu": 0.75},
        {"code": "90889", "desc": "Preparation of report of patient's psychiatric status, history, treatment, or progress", "rvu": 0.75},

        # Dialysis
        {"code": "90935", "desc": "Hemodialysis procedure with single evaluation by a physician or other qualified health care professional", "rvu": 1.37},
        {"code": "90937", "desc": "Hemodialysis procedure requiring repeated evaluation(s) with or without substantial revision of dialysis prescription", "rvu": 2.19},
        {"code": "90945", "desc": "Dialysis procedure other than hemodialysis, with single evaluation by a physician or other qualified health care professional", "rvu": 1.31},
        {"code": "90947", "desc": "Dialysis procedure other than hemodialysis, requiring repeated physician evaluations, with or without substantial revision of dialysis prescription", "rvu": 2.04},
        {"code": "90951", "desc": "End-stage renal disease (ESRD) related services monthly, for patients younger than 2 years of age to include monitoring, per month; with 4 or more face-to-face visits", "rvu": 8.35},
        {"code": "90952", "desc": "ESRD related services monthly, for patients younger than 2 years of age; with 2-3 face-to-face visits", "rvu": 7.23},
        {"code": "90953", "desc": "ESRD related services monthly, for patients younger than 2 years of age; with 1 face-to-face visit", "rvu": 6.10},
        {"code": "90954", "desc": "ESRD related services monthly, for patients 2-11 years of age; with 4 or more face-to-face visits", "rvu": 7.68},
        {"code": "90955", "desc": "ESRD related services monthly, for patients 2-11 years of age; with 2-3 face-to-face visits", "rvu": 6.64},
        {"code": "90956", "desc": "ESRD related services monthly, for patients 2-11 years of age; with 1 face-to-face visit", "rvu": 5.60},
        {"code": "90957", "desc": "ESRD related services monthly, for patients 12-19 years of age; with 4 or more face-to-face visits", "rvu": 6.80},
        {"code": "90958", "desc": "ESRD related services monthly, for patients 12-19 years of age; with 2-3 face-to-face visits", "rvu": 5.88},
        {"code": "90959", "desc": "ESRD related services monthly, for patients 12-19 years of age; with 1 face-to-face visit", "rvu": 4.95},
        {"code": "90960", "desc": "ESRD related services monthly, for patients 20 years of age and older; with 4 or more face-to-face visits", "rvu": 5.45},
        {"code": "90961", "desc": "ESRD related services monthly, for patients 20 years of age and older; with 2-3 face-to-face visits", "rvu": 4.73},
        {"code": "90962", "desc": "ESRD related services monthly, for patients 20 years of age and older; with 1 face-to-face visit", "rvu": 4.00},

        # Cardiology
        {"code": "93000", "desc": "Electrocardiogram, routine ECG with at least 12 leads; with interpretation and report", "rvu": 0.17},
        {"code": "93005", "desc": "Electrocardiogram, routine ECG with at least 12 leads; tracing only, without interpretation and report", "rvu": 0.00},
        {"code": "93010", "desc": "Electrocardiogram, routine ECG with at least 12 leads; interpretation and report only", "rvu": 0.17},
        {"code": "93015", "desc": "Cardiovascular stress test using maximal or submaximal treadmill or bicycle exercise, with physician supervision, interpretation and report", "rvu": 0.75},
        {"code": "93016", "desc": "Cardiovascular stress test using maximal or submaximal treadmill or bicycle exercise; supervision only, without interpretation and report", "rvu": 0.40},
        {"code": "93017", "desc": "Cardiovascular stress test using maximal or submaximal treadmill or bicycle exercise; tracing only, without interpretation and report", "rvu": 0.00},
        {"code": "93018", "desc": "Cardiovascular stress test using maximal or submaximal treadmill or bicycle exercise; interpretation and report only", "rvu": 0.35},
        {"code": "93224", "desc": "External electrocardiographic recording up to 48 hours by continuous rhythm recording and storage; includes recording, scanning analysis with report, review and interpretation", "rvu": 0.52},
        {"code": "93225", "desc": "External electrocardiographic recording up to 48 hours; recording (includes connection, recording, and disconnection)", "rvu": 0.00},
        {"code": "93226", "desc": "External electrocardiographic recording up to 48 hours; scanning analysis with report", "rvu": 0.00},
        {"code": "93227", "desc": "External electrocardiographic recording up to 48 hours; review and interpretation", "rvu": 0.52},
        {"code": "93228", "desc": "External mobile cardiovascular telemetry with electrocardiographic recording, concurrent computerized real time data analysis and greater than 24 hours of accessible ECG data storage; review and interpretation", "rvu": 0.52},
        {"code": "93229", "desc": "External mobile cardiovascular telemetry with electrocardiographic recording; technical support for connection and patient instructions, attended surveillance, analysis and transmission", "rvu": 0.00},
        {"code": "93268", "desc": "External patient and, when performed, auto activated electrocardiographic rhythm derived event recording with symptom-related memory loop with remote download capability up to 30 days; includes transmission, review and interpretation", "rvu": 0.52},
        {"code": "93270", "desc": "External patient and, when performed, auto activated electrocardiographic rhythm derived event recording with symptom-related memory loop with remote download capability up to 30 days; recording (includes connection, recording, and disconnection)", "rvu": 0.00},
        {"code": "93271", "desc": "External patient and, when performed, auto activated electrocardiographic rhythm derived event recording with symptom-related memory loop with remote download capability up to 30 days; transmission and analysis", "rvu": 0.00},
        {"code": "93272", "desc": "External patient and, when performed, auto activated electrocardiographic rhythm derived event recording with symptom-related memory loop with remote download capability up to 30 days; review and interpretation", "rvu": 0.52},
        {"code": "93279", "desc": "Programming device evaluation with iterative adjustment of the implantable device to test the function of the device and select optimal permanent programmed values; single lead pacemaker system", "rvu": 0.49},
        {"code": "93280", "desc": "Programming device evaluation; dual lead pacemaker system", "rvu": 0.57},
        {"code": "93281", "desc": "Programming device evaluation; multiple lead pacemaker system", "rvu": 0.65},
        {"code": "93282", "desc": "Programming device evaluation; single lead implantable defibrillator system", "rvu": 0.82},
        {"code": "93283", "desc": "Programming device evaluation; dual lead implantable defibrillator system", "rvu": 0.90},
        {"code": "93284", "desc": "Programming device evaluation; multiple lead implantable defibrillator system", "rvu": 0.98},
        {"code": "93285", "desc": "Programming device evaluation; implantable loop recorder system", "rvu": 0.39},
        {"code": "93286", "desc": "Peri-procedural device evaluation and programming of device system parameters; single, dual, or multiple lead pacemaker system", "rvu": 0.41},
        {"code": "93287", "desc": "Peri-procedural device evaluation and programming of device system parameters; single, dual, or multiple lead implantable defibrillator system", "rvu": 0.57},
        {"code": "93288", "desc": "Interrogation device evaluation; single, dual, or multiple lead pacemaker system, in person", "rvu": 0.25},
        {"code": "93289", "desc": "Interrogation device evaluation; single, dual, or multiple lead implantable defibrillator system, in person", "rvu": 0.49},
        {"code": "93290", "desc": "Interrogation device evaluation; implantable cardiovascular physiologic monitor system, in person", "rvu": 0.25},
        {"code": "93291", "desc": "Interrogation device evaluation; implantable loop recorder system, in person", "rvu": 0.25},
        {"code": "93293", "desc": "Transtelephonic rhythm strip pacemaker evaluation(s) single, dual, or multiple lead pacemaker system; includes recording(s), review and interpretation", "rvu": 0.13},
        {"code": "93294", "desc": "Interrogation device evaluation(s), remote, up to 90 days; single, dual, or multiple lead pacemaker system", "rvu": 0.33},
        {"code": "93295", "desc": "Interrogation device evaluation(s), remote, up to 90 days; single, dual, or multiple lead implantable defibrillator system", "rvu": 0.57},
        {"code": "93296", "desc": "Interrogation device evaluation(s), remote, up to 90 days; single, dual, or multiple lead pacemaker system or implantable defibrillator system; remote data acquisition(s), technical support and data management", "rvu": 0.00},
        {"code": "93297", "desc": "Interrogation device evaluation(s), remote, up to 30 days; implantable cardiovascular physiologic monitor system", "rvu": 0.25},
        {"code": "93298", "desc": "Interrogation device evaluation(s), remote, up to 30 days; implantable loop recorder system", "rvu": 0.25},
        {"code": "93303", "desc": "Transthoracic echocardiography for congenital cardiac anomalies; complete", "rvu": 1.30},
        {"code": "93304", "desc": "Transthoracic echocardiography for congenital cardiac anomalies; follow-up or limited study", "rvu": 0.65},
        {"code": "93306", "desc": "Echocardiography, transthoracic, real-time with image documentation (2D), includes M-mode recording, when performed, complete, with spectral Doppler echocardiography, and with color flow Doppler echocardiography", "rvu": 1.50},
        {"code": "93307", "desc": "Echocardiography, transthoracic, real-time with image documentation (2D), includes M-mode recording, when performed, complete, without spectral or color flow Doppler echocardiography", "rvu": 0.92},
        {"code": "93308", "desc": "Echocardiography, transthoracic, real-time with image documentation (2D), includes M-mode recording, when performed, follow-up or limited study", "rvu": 0.46},
        {"code": "93312", "desc": "Echocardiography, transesophageal, real-time with image documentation (2D), including probe placement, image acquisition, interpretation and report", "rvu": 2.44},
        {"code": "93313", "desc": "Echocardiography, transesophageal, real-time with image documentation (2D), including probe placement, image acquisition, interpretation and report; placement of transesophageal probe only", "rvu": 0.57},
        {"code": "93314", "desc": "Echocardiography, transesophageal, real-time with image documentation (2D); image acquisition, interpretation and report only", "rvu": 1.87},
        {"code": "93315", "desc": "Transesophageal echocardiography for congenital cardiac anomalies; including probe placement, image acquisition, interpretation and report", "rvu": 2.60},
        {"code": "93316", "desc": "Transesophageal echocardiography for congenital cardiac anomalies; placement of transesophageal probe only", "rvu": 0.57},
        {"code": "93317", "desc": "Transesophageal echocardiography for congenital cardiac anomalies; image acquisition, interpretation and report only", "rvu": 2.03},
        {"code": "93318", "desc": "Echocardiography, transesophageal (TEE) for monitoring purposes, including probe placement, real time 2-dimensional image acquisition and interpretation leading to ongoing (continuous) assessment of hemodynamically unstable patients", "rvu": 1.87},
        {"code": "93320", "desc": "Doppler echocardiography, pulsed wave and/or continuous wave with spectral display; complete", "rvu": 0.32},
        {"code": "93321", "desc": "Doppler echocardiography, pulsed wave and/or continuous wave with spectral display; follow-up or limited study", "rvu": 0.17},
        {"code": "93325", "desc": "Doppler echocardiography color flow velocity mapping", "rvu": 0.20},
        {"code": "93350", "desc": "Echocardiography, transthoracic, real-time with image documentation (2D), includes M-mode recording, when performed, during rest and cardiovascular stress test using treadmill, bicycle exercise and/or pharmacologically induced stress, with interpretation and report", "rvu": 0.95},
        {"code": "93351", "desc": "Echocardiography, transthoracic, real-time with image documentation (2D), includes M-mode recording, when performed, during rest and cardiovascular stress test using treadmill, bicycle exercise and/or pharmacologically induced stress, with interpretation and report; including performance of continuous electrocardiographic monitoring", "rvu": 1.20},
        {"code": "93451", "desc": "Right heart catheterization including measurement(s) of oxygen saturation and cardiac output, when performed", "rvu": 2.99},
        {"code": "93452", "desc": "Left heart catheterization including intraprocedural injection(s) for left ventriculography, imaging supervision and interpretation, when performed", "rvu": 4.06},
        {"code": "93453", "desc": "Combined right and left heart catheterization including intraprocedural injection(s) for left ventriculography, imaging supervision and interpretation, when performed", "rvu": 4.99},
        {"code": "93454", "desc": "Catheter placement in coronary artery(s) for coronary angiography, including intraprocedural injection(s) for coronary angiography, imaging supervision and interpretation", "rvu": 4.69},
        {"code": "93455", "desc": "Catheter placement in coronary artery(s) for coronary angiography, including intraprocedural injection(s) for coronary angiography, imaging supervision and interpretation; with catheter placement(s) in bypass graft(s)", "rvu": 5.25},
        {"code": "93456", "desc": "Catheter placement in coronary artery(s) for coronary angiography, including intraprocedural injection(s) for coronary angiography, imaging supervision and interpretation; with right heart catheterization", "rvu": 5.62},
        {"code": "93457", "desc": "Catheter placement in coronary artery(s) for coronary angiography, including intraprocedural injection(s) for coronary angiography, imaging supervision and interpretation; with catheter placement(s) in bypass graft(s) and right heart catheterization", "rvu": 6.18},
        {"code": "93458", "desc": "Catheter placement in coronary artery(s) for coronary angiography, including intraprocedural injection(s) for coronary angiography and left ventriculography, imaging supervision and interpretation", "rvu": 6.37},
        {"code": "93459", "desc": "Catheter placement in coronary artery(s) for coronary angiography, including intraprocedural injection(s) for coronary angiography and left ventriculography, imaging supervision and interpretation; with catheter placement(s) in bypass graft(s)", "rvu": 6.93},
        {"code": "93460", "desc": "Catheter placement in coronary artery(s) for coronary angiography, including intraprocedural injection(s) for coronary angiography, left ventriculography, imaging supervision and interpretation; with right heart catheterization", "rvu": 7.30},
        {"code": "93461", "desc": "Catheter placement in coronary artery(s) for coronary angiography, including intraprocedural injection(s) for coronary angiography, left ventriculography, imaging supervision and interpretation; with catheter placement(s) in bypass graft(s) and right heart catheterization", "rvu": 7.86},

        # PCI
        {"code": "92920", "desc": "Percutaneous transluminal coronary angioplasty; single major coronary artery or branch", "rvu": 10.92},
        {"code": "92924", "desc": "Percutaneous transluminal coronary atherectomy, with coronary angioplasty when performed; single major coronary artery or branch", "rvu": 11.39},
        {"code": "92928", "desc": "Percutaneous transcatheter placement of intracoronary stent(s), with coronary angioplasty when performed; single major coronary artery or branch", "rvu": 12.43},
        {"code": "92933", "desc": "Percutaneous transluminal coronary atherectomy, with intracoronary stent, with coronary angioplasty when performed; single major coronary artery or branch", "rvu": 13.50},
        {"code": "92937", "desc": "Percutaneous transluminal revascularization of or through coronary artery bypass graft; single vessel", "rvu": 13.96},
        {"code": "92941", "desc": "Percutaneous transluminal revascularization of acute total/subtotal occlusion during acute myocardial infarction, coronary artery or coronary artery bypass graft; single vessel", "rvu": 16.61},
        {"code": "92943", "desc": "Percutaneous transluminal revascularization of chronic total occlusion, coronary artery, coronary artery branch, or coronary artery bypass graft; single vessel", "rvu": 17.00},

        # Pulmonary
        {"code": "94010", "desc": "Spirometry, including graphic record, total and timed vital capacity, expiratory flow rate measurement(s), with or without maximal voluntary ventilation", "rvu": 0.17},
        {"code": "94060", "desc": "Bronchodilation responsiveness, spirometry as in 94010, pre- and post-bronchodilator administration", "rvu": 0.17},
        {"code": "94070", "desc": "Bronchospasm provocation evaluation, multiple spirometric determinations as in 94010, with administered agents", "rvu": 0.75},
        {"code": "94375", "desc": "Respiratory flow volume loop", "rvu": 0.08},
        {"code": "94640", "desc": "Pressurized or nonpressurized inhalation treatment for acute airway obstruction", "rvu": 0.00},
        {"code": "94644", "desc": "Continuous inhalation treatment with aerosol medication for acute airway obstruction; first hour", "rvu": 0.00},
        {"code": "94645", "desc": "Continuous inhalation treatment with aerosol medication for acute airway obstruction; each additional hour", "rvu": 0.00},
        {"code": "94660", "desc": "Continuous positive airway pressure ventilation (CPAP), initiation and management", "rvu": 0.00},
        {"code": "94726", "desc": "Plethysmography for determination of lung volumes and, when performed, airway resistance", "rvu": 0.14},
        {"code": "94727", "desc": "Gas dilution or washout for determination of lung volumes and, when performed, distribution of ventilation and closing volumes", "rvu": 0.14},
        {"code": "94728", "desc": "Airway resistance by impulse oscillometry", "rvu": 0.14},
        {"code": "94729", "desc": "Diffusing capacity (eg, carbon monoxide, membrane) (List separately in addition to code for primary procedure)", "rvu": 0.11},
        {"code": "94760", "desc": "Noninvasive ear or pulse oximetry for oxygen saturation; single determination", "rvu": 0.00},
        {"code": "94761", "desc": "Noninvasive ear or pulse oximetry for oxygen saturation; multiple determinations", "rvu": 0.00},
        {"code": "94762", "desc": "Noninvasive ear or pulse oximetry for oxygen saturation; by continuous overnight monitoring", "rvu": 0.00},

        # Neurology
        {"code": "95004", "desc": "Percutaneous tests (scratch, puncture, prick) with allergenic extracts, immediate type reaction, including test interpretation and report, specify number of tests", "rvu": 0.04},
        {"code": "95024", "desc": "Intracutaneous (intradermal) tests with allergenic extracts, immediate type reaction, including test interpretation and report, specify number of tests", "rvu": 0.05},
        {"code": "95027", "desc": "Intracutaneous (intradermal) tests, sequential and incremental, with allergenic extracts for airborne allergens, immediate type reaction, including test interpretation and report, specify number of tests", "rvu": 0.06},
        {"code": "95810", "desc": "Polysomnography; age 6 years or older, sleep staging with 4 or more additional parameters of sleep, attended by a technologist", "rvu": 0.00},
        {"code": "95811", "desc": "Polysomnography; age 6 years or older, sleep staging with 4 or more additional parameters of sleep, with initiation of continuous positive airway pressure therapy or bilevel ventilation, attended by a technologist", "rvu": 0.00},
        {"code": "95812", "desc": "Electroencephalogram (EEG) extended monitoring; 41-60 minutes", "rvu": 1.04},
        {"code": "95813", "desc": "Electroencephalogram (EEG) extended monitoring; greater than 1 hour", "rvu": 1.22},
        {"code": "95816", "desc": "Electroencephalogram (EEG); including recording awake and drowsy", "rvu": 0.67},
        {"code": "95819", "desc": "Electroencephalogram (EEG); including recording awake and asleep", "rvu": 0.76},
        {"code": "95860", "desc": "Needle electromyography; 1 extremity with or without related paraspinal areas", "rvu": 0.91},
        {"code": "95861", "desc": "Needle electromyography; 2 extremities with or without related paraspinal areas", "rvu": 1.49},
        {"code": "95863", "desc": "Needle electromyography; 3 extremities with or without related paraspinal areas", "rvu": 2.13},
        {"code": "95864", "desc": "Needle electromyography; 4 extremities with or without related paraspinal areas", "rvu": 2.62},
        {"code": "95867", "desc": "Needle electromyography; cranial nerve supplied muscle(s), unilateral", "rvu": 0.85},
        {"code": "95868", "desc": "Needle electromyography; cranial nerve supplied muscles, bilateral", "rvu": 1.27},
        {"code": "95869", "desc": "Needle electromyography; thoracic paraspinal muscles (excluding T1 or T12)", "rvu": 0.55},
        {"code": "95870", "desc": "Needle electromyography; limited study of muscles in 1 extremity or non-limb (axial) muscles", "rvu": 0.55},
        {"code": "95885", "desc": "Needle electromyography, each extremity, with related paraspinal areas, when performed, done with nerve conduction, amplitude and latency/velocity study; limited", "rvu": 0.61},
        {"code": "95886", "desc": "Needle electromyography, each extremity, with related paraspinal areas, when performed, done with nerve conduction, amplitude and latency/velocity study; complete, 5 or more muscles studied, innervated by 3 or more nerves or 4 or more spinal levels", "rvu": 1.16},
        {"code": "95907", "desc": "Nerve conduction studies; 1-2 studies", "rvu": 0.46},
        {"code": "95908", "desc": "Nerve conduction studies; 3-4 studies", "rvu": 0.75},
        {"code": "95909", "desc": "Nerve conduction studies; 5-6 studies", "rvu": 0.96},
        {"code": "95910", "desc": "Nerve conduction studies; 7-8 studies", "rvu": 1.14},
        {"code": "95911", "desc": "Nerve conduction studies; 9-10 studies", "rvu": 1.35},
        {"code": "95912", "desc": "Nerve conduction studies; 11-12 studies", "rvu": 1.50},
        {"code": "95913", "desc": "Nerve conduction studies; 13 or more studies", "rvu": 1.68},

        # Physical Therapy/Rehab
        {"code": "97110", "desc": "Therapeutic procedure, 1 or more areas, each 15 minutes; therapeutic exercises to develop strength and endurance, range of motion and flexibility", "rvu": 0.45},
        {"code": "97112", "desc": "Therapeutic procedure, 1 or more areas, each 15 minutes; neuromuscular reeducation of movement, balance, coordination, kinesthetic sense, posture, and/or proprioception", "rvu": 0.45},
        {"code": "97113", "desc": "Therapeutic procedure, 1 or more areas, each 15 minutes; aquatic therapy with therapeutic exercises", "rvu": 0.44},
        {"code": "97116", "desc": "Therapeutic procedure, 1 or more areas, each 15 minutes; gait training (includes stair climbing)", "rvu": 0.40},
        {"code": "97124", "desc": "Therapeutic procedure, 1 or more areas, each 15 minutes; massage, including effleurage, petrissage and/or tapotement", "rvu": 0.35},
        {"code": "97140", "desc": "Manual therapy techniques (eg, mobilization/manipulation, manual lymphatic drainage, manual traction), 1 or more regions, each 15 minutes", "rvu": 0.43},
        {"code": "97150", "desc": "Therapeutic procedure(s), group (2 or more individuals)", "rvu": 0.27},
        {"code": "97161", "desc": "Physical therapy evaluation: low complexity, requiring 20 minutes total time", "rvu": 1.20},
        {"code": "97162", "desc": "Physical therapy evaluation: moderate complexity, requiring 30 minutes total time", "rvu": 1.50},
        {"code": "97163", "desc": "Physical therapy evaluation: high complexity, requiring 45 minutes total time", "rvu": 1.80},
        {"code": "97164", "desc": "Physical therapy re-evaluation", "rvu": 0.75},
        {"code": "97165", "desc": "Occupational therapy evaluation, low complexity, requiring 30 minutes total time", "rvu": 1.20},
        {"code": "97166", "desc": "Occupational therapy evaluation, moderate complexity, requiring 45 minutes total time", "rvu": 1.50},
        {"code": "97167", "desc": "Occupational therapy evaluation, high complexity, requiring 60 minutes total time", "rvu": 1.80},
        {"code": "97168", "desc": "Occupational therapy re-evaluation", "rvu": 0.75},
        {"code": "97530", "desc": "Therapeutic activities, direct (one-on-one) patient contact (use of dynamic activities to improve functional performance), each 15 minutes", "rvu": 0.44},
        {"code": "97535", "desc": "Self-care/home management training, direct one-on-one contact, each 15 minutes", "rvu": 0.45},
        {"code": "97542", "desc": "Wheelchair management, each 15 minutes", "rvu": 0.42},
        {"code": "97545", "desc": "Work hardening/conditioning; initial 2 hours", "rvu": 1.60},
        {"code": "97546", "desc": "Work hardening/conditioning; each additional hour", "rvu": 0.80},
        {"code": "97597", "desc": "Debridement (eg, high pressure waterjet with/without suction, sharp selective debridement with scissors, scalpel and forceps), open wound, per session; total wound(s) surface area; first 20 sq cm or less", "rvu": 0.62},
        {"code": "97598", "desc": "Debridement; each additional 20 sq cm", "rvu": 0.37},
        {"code": "97602", "desc": "Removal of devitalized tissue from wound(s), non-selective debridement, without anesthesia", "rvu": 0.00},
        {"code": "97605", "desc": "Negative pressure wound therapy (eg, vacuum assisted drainage collection), utilizing durable medical equipment (DME), including topical application(s), wound assessment, and instruction(s) for ongoing care, per session; total wound(s) surface area less than or equal to 50 square centimeters", "rvu": 0.59},
        {"code": "97606", "desc": "Negative pressure wound therapy (eg, vacuum assisted drainage collection), utilizing durable medical equipment (DME), including topical application(s), wound assessment, and instruction(s) for ongoing care, per session; total wound(s) surface area greater than 50 square centimeters", "rvu": 0.79},
        {"code": "97750", "desc": "Physical performance test or measurement (eg, musculoskeletal, functional capacity), with written report, each 15 minutes", "rvu": 0.45},
        {"code": "97755", "desc": "Assistive technology assessment (eg, to restore, augment or compensate for existing function, optimize functional tasks and/or maximize environmental accessibility), direct one-on-one contact, with written report, each 15 minutes", "rvu": 0.55},
        {"code": "97760", "desc": "Orthotic(s) management and training (including assessment and fitting when not otherwise reported), upper extremity(ies), lower extremity(ies) and/or trunk, initial orthotic(s) encounter, each 15 minutes", "rvu": 0.44},
        {"code": "97761", "desc": "Prosthetic(s) training, upper and/or lower extremity(ies), initial prosthetic(s) encounter, each 15 minutes", "rvu": 0.44},
        {"code": "97763", "desc": "Orthotic(s)/prosthetic(s) management and/or training, upper extremity(ies), lower extremity(ies), and/or trunk, subsequent orthotic(s)/prosthetic(s) encounter, each 15 minutes", "rvu": 0.44},

        # Injections/Infusions
        {"code": "96360", "desc": "Intravenous infusion, hydration; initial, 31 minutes to 1 hour", "rvu": 0.17},
        {"code": "96361", "desc": "Intravenous infusion, hydration; each additional hour", "rvu": 0.13},
        {"code": "96365", "desc": "Intravenous infusion, for therapy, prophylaxis, or diagnosis; initial, up to 1 hour", "rvu": 0.21},
        {"code": "96366", "desc": "Intravenous infusion, for therapy, prophylaxis, or diagnosis; each additional hour", "rvu": 0.15},
        {"code": "96367", "desc": "Intravenous infusion, for therapy, prophylaxis, or diagnosis; additional sequential infusion of a new drug/substance, up to 1 hour", "rvu": 0.15},
        {"code": "96368", "desc": "Intravenous infusion, for therapy, prophylaxis, or diagnosis; concurrent infusion", "rvu": 0.00},
        {"code": "96369", "desc": "Subcutaneous infusion for therapy or prophylaxis; initial, up to 1 hour", "rvu": 0.21},
        {"code": "96370", "desc": "Subcutaneous infusion for therapy or prophylaxis; each additional hour", "rvu": 0.10},
        {"code": "96371", "desc": "Subcutaneous infusion for therapy or prophylaxis; additional pump set-up with establishment of new subcutaneous infusion site(s)", "rvu": 0.13},
        {"code": "96372", "desc": "Therapeutic, prophylactic, or diagnostic injection (specify substance or drug); subcutaneous or intramuscular", "rvu": 0.17},
        {"code": "96373", "desc": "Therapeutic, prophylactic, or diagnostic injection (specify substance or drug); intra-arterial", "rvu": 0.17},
        {"code": "96374", "desc": "Therapeutic, prophylactic, or diagnostic injection (specify substance or drug); intravenous push, single or initial substance/drug", "rvu": 0.18},
        {"code": "96375", "desc": "Therapeutic, prophylactic, or diagnostic injection (specify substance or drug); each additional sequential intravenous push of a new substance/drug", "rvu": 0.14},
        {"code": "96376", "desc": "Therapeutic, prophylactic, or diagnostic injection (specify substance or drug); each additional sequential intravenous push of the same substance/drug provided in a facility", "rvu": 0.00},
        {"code": "96377", "desc": "Application of on-body injector (includes cannula insertion) for timed subcutaneous injection", "rvu": 0.00},

        # Chemotherapy
        {"code": "96401", "desc": "Chemotherapy administration, subcutaneous or intramuscular; non-hormonal anti-neoplastic", "rvu": 0.21},
        {"code": "96402", "desc": "Chemotherapy administration, subcutaneous or intramuscular; hormonal anti-neoplastic", "rvu": 0.17},
        {"code": "96405", "desc": "Chemotherapy administration; intralesional, up to and including 7 lesions", "rvu": 0.50},
        {"code": "96406", "desc": "Chemotherapy administration; intralesional, more than 7 lesions", "rvu": 1.00},
        {"code": "96409", "desc": "Chemotherapy administration; intravenous, push technique, single or initial substance/drug", "rvu": 0.32},
        {"code": "96411", "desc": "Chemotherapy administration; intravenous, push technique, each additional substance/drug", "rvu": 0.27},
        {"code": "96413", "desc": "Chemotherapy administration, intravenous infusion technique; up to 1 hour, single or initial substance/drug", "rvu": 0.39},
        {"code": "96415", "desc": "Chemotherapy administration, intravenous infusion technique; each additional hour", "rvu": 0.15},
        {"code": "96416", "desc": "Chemotherapy administration, intravenous infusion technique; initiation of prolonged chemotherapy infusion (more than 8 hours), requiring use of a portable or implantable pump", "rvu": 0.32},
        {"code": "96417", "desc": "Chemotherapy administration, intravenous infusion technique; each additional sequential infusion (different substance/drug), up to 1 hour", "rvu": 0.27},
        {"code": "96420", "desc": "Chemotherapy administration, intra-arterial; push technique", "rvu": 0.41},
        {"code": "96422", "desc": "Chemotherapy administration, intra-arterial; infusion technique, up to 1 hour", "rvu": 0.41},
        {"code": "96423", "desc": "Chemotherapy administration, intra-arterial; infusion technique, each additional hour", "rvu": 0.15},
        {"code": "96425", "desc": "Chemotherapy administration, intra-arterial; infusion technique, initiation of prolonged infusion (more than 8 hours), requiring the use of a portable or implantable pump", "rvu": 0.39},
        {"code": "96440", "desc": "Chemotherapy administration into pleural cavity, requiring and including thoracentesis", "rvu": 1.18},
        {"code": "96446", "desc": "Chemotherapy administration into the peritoneal cavity via indwelling port or catheter", "rvu": 0.47},
        {"code": "96450", "desc": "Chemotherapy administration, into CNS, including intrathecal or intraventricular via subcutaneous reservoir", "rvu": 1.13},
    ]

    for med in medicine_codes:
        codes.append({
            "concept_code": med["code"],
            "concept_name": med["desc"],
            "category": "Medicine",
            "work_rvu": med["rvu"],
            "synonyms": [],
        })

    return codes


# =============================================================================
# CATEGORY II CODES (Performance Measurement)
# =============================================================================
def generate_category_ii_codes() -> list[dict[str, Any]]:
    """Generate Category II performance measurement codes."""
    codes = []

    cat2_codes = [
        {"code": "0001F", "desc": "Heart failure assessed (includes assessment of appropriate interim history, physical examination, laboratory tests)"},
        {"code": "0500F", "desc": "Initial prenatal care visit (report at first prenatal encounter with health care professional)"},
        {"code": "0501F", "desc": "Prenatal flow sheet documented in medical record by first prenatal visit"},
        {"code": "0502F", "desc": "Subsequent prenatal care visit"},
        {"code": "0503F", "desc": "Postpartum care visit"},
        {"code": "1000F", "desc": "Tobacco use assessed"},
        {"code": "1002F", "desc": "Anginal symptoms and level of activity assessed"},
        {"code": "1003F", "desc": "Level of activity assessed"},
        {"code": "1004F", "desc": "Clinical symptoms of volume overload (excess) assessed"},
        {"code": "1005F", "desc": "Asthma symptoms evaluated"},
        {"code": "1006F", "desc": "Osteoarthritis symptoms and functional status assessed"},
        {"code": "1007F", "desc": "Use of anti-inflammatory or analgesic OTC medications assessed"},
        {"code": "1008F", "desc": "Gastrointestinal and renal risk factors assessed for patients on prescribed NSAID"},
        {"code": "1010F", "desc": "Severity of angina assessed by level of activity"},
        {"code": "1011F", "desc": "Angina present"},
        {"code": "1012F", "desc": "Angina absent"},
        {"code": "1015F", "desc": "Chronic obstructive pulmonary disease (COPD) symptoms assessed"},
        {"code": "1018F", "desc": "Dyspnea assessed, present"},
        {"code": "1019F", "desc": "Dyspnea assessed, absent"},
        {"code": "1022F", "desc": "Pneumococcus immunization status assessed"},
        {"code": "1026F", "desc": "Co-morbid conditions assessed"},
        {"code": "1030F", "desc": "Influenza immunization status assessed"},
        {"code": "1031F", "desc": "Smoking status and exposure to second hand smoke in the home assessed"},
        {"code": "1032F", "desc": "Current tobacco smoker or currently exposed to secondhand smoke"},
        {"code": "1033F", "desc": "Current tobacco non-smoker and target to secondhand smoke"},
        {"code": "1034F", "desc": "Current tobacco smoker"},
        {"code": "1035F", "desc": "Current smokeless tobacco user"},
        {"code": "1036F", "desc": "Current tobacco non-user"},
        {"code": "1038F", "desc": "Persistent asthma (mild, moderate, or severe)"},
        {"code": "1039F", "desc": "Intermittent asthma"},
        {"code": "1040F", "desc": "DSM-IV criteria for major depressive disorder documented at initial evaluation"},
        {"code": "1050F", "desc": "History obtained regarding new or changing moles"},
        {"code": "1052F", "desc": "Type, anatomic location, and activity all assessed"},
        {"code": "1055F", "desc": "Visual acuity assessed"},
        {"code": "1060F", "desc": "Documentation of permanent or persistent or paroxysmal atrial fibrillation"},
        {"code": "1061F", "desc": "Documentation of absence of permanent and persistent and paroxysmal atrial fibrillation"},
        {"code": "1065F", "desc": "Ischemic stroke symptom onset of less than 3 hours prior to arrival"},
        {"code": "1066F", "desc": "Symptom onset greater than or equal to 3 hours prior to arrival"},
        {"code": "1070F", "desc": "Alarm symptoms (involuntary weight loss, dysphagia, or gastrointestinal bleeding) assessed; none present"},
        {"code": "1071F", "desc": "One or more alarm symptoms present"},
        {"code": "1090F", "desc": "Presence or absence of urinary incontinence assessed"},
        {"code": "1091F", "desc": "Urinary incontinence characterized"},
        {"code": "1100F", "desc": "Patient screened for future fall risk; documentation of 2 or more falls in the past year or any fall with injury in the past year"},
        {"code": "1101F", "desc": "Patient screened for future fall risk; documentation of no falls in the past year or only 1 fall without injury in the past year"},
        {"code": "1110F", "desc": "Patient discharged from an inpatient facility (eg, hospital, skilled nursing facility, or rehabilitation facility) within the last 60 days"},
        {"code": "1111F", "desc": "Discharge medications reconciled with the current medication list in outpatient medical record"},
        {"code": "1116F", "desc": "Auricular or periauricular pain assessed"},
        {"code": "1118F", "desc": "GERD symptoms assessed after 12 months of therapy"},
        {"code": "1119F", "desc": "Initial evaluation for condition performed"},
        {"code": "1121F", "desc": "Subsequent evaluation for condition performed"},
        {"code": "1123F", "desc": "Advance Care Planning discussed and documented advance care plan or surrogate decision maker documented in the medical record"},
        {"code": "1124F", "desc": "Advance Care Planning discussed and documented in the medical record, patient did not wish or was not able to name a surrogate decision maker or provide an advance care plan"},
        {"code": "1125F", "desc": "Pain severity quantified; pain present"},
        {"code": "1126F", "desc": "Pain severity quantified; no pain present"},
        {"code": "1127F", "desc": "Pain assessed using a valid and reliable tool"},
        {"code": "1128F", "desc": "Patient asked about and screened for depression"},
        {"code": "1130F", "desc": "Hearing aid device assessed"},
        {"code": "1134F", "desc": "Episode of back pain lasting 6 weeks or less"},
        {"code": "1135F", "desc": "Episode of back pain lasting longer than 6 weeks"},
        {"code": "1136F", "desc": "Episode of back pain lasting 12 weeks or less"},
        {"code": "1137F", "desc": "Episode of back pain lasting longer than 12 weeks"},
        {"code": "1150F", "desc": "Documentation that a patient had a qualifying medical indication for not having a routine visit within 12 months"},
        {"code": "1157F", "desc": "Prior pneumococcal vaccination (PCV13) received"},
        {"code": "1158F", "desc": "Most recent blood pressure has a systolic measurement of less than 140 mmHg and a diastolic measurement of less than 90 mmHg"},
        {"code": "1159F", "desc": "Most recent systolic blood pressure greater than or equal to 140 mmHg and/or diastolic blood pressure greater than or equal to 90 mmHg"},
        {"code": "1160F", "desc": "Review of all medications by a prescribing practitioner or clinical pharmacist documented in the medical record"},
        {"code": "1170F", "desc": "Functional status assessed"},
        {"code": "1175F", "desc": "Functional status was not assessed, reason not otherwise specified"},
        {"code": "1180F", "desc": "All specified thromboembolic risk factors assessed"},
        {"code": "1181F", "desc": "Neuropsychiatric symptoms assessed and results reviewed"},
        {"code": "1182F", "desc": "Neuropsychiatric symptoms assessed and addressed, including depression symptoms and behavioral problems"},
        {"code": "1200F", "desc": "Seizure type(s) and current seizure frequency(ies) documented"},
        {"code": "1205F", "desc": "Etiology of epilepsy or epilepsy syndrome(s) reviewed and documented"},
        {"code": "1400F", "desc": "Parkinson's disease diagnosis reviewed"},
        {"code": "2000F", "desc": "Blood pressure measured"},
        {"code": "2001F", "desc": "Weight recorded"},
        {"code": "2002F", "desc": "Clinical signs of volume overload (excess) assessed"},
        {"code": "2004F", "desc": "Initial examination of the involved joint(s) (includes flares) documented"},
        {"code": "2010F", "desc": "Vital signs (temperature, pulse, respiratory rate, and blood pressure) documented"},
        {"code": "2014F", "desc": "Mental status assessed"},
        {"code": "2015F", "desc": "Asthma impairment assessed"},
        {"code": "2016F", "desc": "Asthma risk assessed"},
        {"code": "2018F", "desc": "Hydration status assessed"},
        {"code": "2019F", "desc": "Dilated macular or fundus exam performed"},
        {"code": "2020F", "desc": "Dilated retinal eye exam with interpretation by ophthalmologist or optometrist documented and reviewed"},
        {"code": "2021F", "desc": "Dilated eye exam with interpretation by ophthalmologist or optometrist documented and communicated to physician managing ongoing diabetes care"},
        {"code": "2022F", "desc": "Dilated macular exam performed, including documentation of the presence or absence of macular thickening or geographic atrophy or hemorrhage"},
        {"code": "2024F", "desc": "7 standard field stereoscopic photos with interpretation by an ophthalmologist or optometrist documented and reviewed"},
        {"code": "2026F", "desc": "Eye imaging validated to match diagnosis from seven standard field stereoscopic photos results documented and reviewed"},
        {"code": "2027F", "desc": "Optic nerve head evaluation performed"},
        {"code": "2028F", "desc": "Foot examination performed"},
        {"code": "2029F", "desc": "Complete physical skin exam performed"},
        {"code": "2030F", "desc": "Hydration status documented, normally hydrated"},
        {"code": "2031F", "desc": "Hydration status documented, dehydrated"},
        {"code": "2035F", "desc": "Tympanic membrane mobility assessed with pneumatic otoscopy or tympanometry"},
        {"code": "2040F", "desc": "Physical examination on date of initial visit for low back pain includes the following: notation of presence or absence of abnormal findings for (all 3 required): 1) inspection (abnormal curvature, asymmetry, or motor deformity), 2) palpation for paraspinal tenderness, 3) evaluation of neurological status"},
        {"code": "2044F", "desc": "Documentation of mental health assessment prior to intervention"},
        {"code": "2050F", "desc": "Wound characteristics including drainage, size and nature of wound base tissue, documented in the medical record"},
        {"code": "3006F", "desc": "Chest x-ray results documented and reviewed"},
        {"code": "3008F", "desc": "Body Mass Index (BMI), calculated and documented"},
        {"code": "3011F", "desc": "Lipid panel results documented and reviewed"},
        {"code": "3014F", "desc": "Screening mammography results documented and reviewed"},
        {"code": "3015F", "desc": "Cervical cancer screening results documented and reviewed"},
        {"code": "3016F", "desc": "Patient screened for unhealthy alcohol use using a systematic screening method and target documented as unhealthy alcohol use"},
        {"code": "3017F", "desc": "Patient screened for unhealthy alcohol use using a systematic screening method and not target documented as unhealthy alcohol use"},
        {"code": "3020F", "desc": "Left ventricular function (LVF) assessment results documented and reviewed"},
        {"code": "3021F", "desc": "Left ventricular ejection fraction (LVEF) less than 40%"},
        {"code": "3022F", "desc": "Left ventricular ejection fraction (LVEF) greater than or equal to 40% or documentation that LVEF is normal or mildly depressed"},
        {"code": "3023F", "desc": "Spirometry results documented and reviewed"},
        {"code": "3025F", "desc": "Spirometry test results demonstrate FEV1/FVC less than 70% with bronchodilator"},
        {"code": "3027F", "desc": "Spirometry test results demonstrate FEV1 greater than or equal to 60% predicted"},
        {"code": "3028F", "desc": "Spirometry test results demonstrate FEV1 less than 60% predicted"},
        {"code": "3035F", "desc": "Oxygen saturation results documented and reviewed"},
        {"code": "3040F", "desc": "Functional expiratory volume (FEV1) less than 40% predicted"},
        {"code": "3042F", "desc": "Functional expiratory volume (FEV1)/Forced vital capacity (FVC) less than 70%"},
        {"code": "3044F", "desc": "Most recent hemoglobin A1c (HbA1c) level less than 7.0%"},
        {"code": "3045F", "desc": "Most recent hemoglobin A1c (HbA1c) level is 7.0 - 9.0%"},
        {"code": "3046F", "desc": "Most recent hemoglobin A1c (HbA1c) level greater than 9.0%"},
        {"code": "3048F", "desc": "Most recent LDL-C less than 100 mg/dL"},
        {"code": "3049F", "desc": "Most recent LDL-C 100-129 mg/dL"},
        {"code": "3050F", "desc": "Most recent LDL-C greater than or equal to 130 mg/dL"},
        {"code": "3055F", "desc": "Most recent blood pressure has a systolic measurement of less than 130 mmHg"},
        {"code": "3060F", "desc": "Positive microalbuminuria test result documented and reviewed"},
        {"code": "3066F", "desc": "Documentation of treatment for nephropathy (eg, patient receiving angiotensin converting enzyme (ACE) inhibitor or angiotensin receptor blocker (ARB) therapy)"},
        {"code": "3072F", "desc": "Low risk for retinopathy (no evidence of retinopathy in the prior year)"},
        {"code": "3073F", "desc": "Pre-surgical (cataract) assessment completed and target determined prior to surgery"},
        {"code": "3074F", "desc": "Most recent IOP reduced by a value of greater than or equal to 15% from the pre-intervention level"},
        {"code": "3077F", "desc": "Most recent systolic blood pressure less than 140 mmHg"},
        {"code": "3078F", "desc": "Most recent diastolic blood pressure less than 90 mmHg"},
        {"code": "3079F", "desc": "Most recent systolic blood pressure greater than or equal to 140 mmHg"},
        {"code": "3080F", "desc": "Most recent diastolic blood pressure greater than or equal to 90 mmHg"},
        {"code": "4000F", "desc": "Tobacco use cessation intervention, counseling"},
        {"code": "4001F", "desc": "Tobacco use cessation intervention, pharmacologic therapy"},
        {"code": "4003F", "desc": "Patient receiving warfarin therapy for non-valvular atrial fibrillation or atrial flutter"},
        {"code": "4004F", "desc": "Patient receiving warfarin therapy for venous thromboembolism"},
        {"code": "4005F", "desc": "Patient receiving antiplatelet therapy"},
        {"code": "4008F", "desc": "Beta-blocker therapy prescribed or currently being taken"},
        {"code": "4010F", "desc": "Angiotensin converting enzyme (ACE) inhibitor or angiotensin receptor blocker (ARB) therapy prescribed or currently being taken"},
        {"code": "4011F", "desc": "Lipid lowering therapy prescribed or currently being taken"},
        {"code": "4012F", "desc": "Warfarin therapy prescribed"},
        {"code": "4013F", "desc": "Statin therapy prescribed or currently being taken"},
        {"code": "4014F", "desc": "Written discharge instructions provided to heart failure patients"},
        {"code": "4015F", "desc": "Persistent asthma, preferred long-term control medication or an acceptable alternative treatment prescribed"},
        {"code": "4016F", "desc": "Anti-inflammatory/analgesic agent prescribed"},
        {"code": "4017F", "desc": "Gastrointestinal prophylaxis for NSAID use prescribed"},
        {"code": "4018F", "desc": "Therapeutic exercise for low back pain prescribed or provided"},
        {"code": "4019F", "desc": "Documentation of discussion of treatment options with patient or caregiver"},
        {"code": "4025F", "desc": "Inhaled bronchodilator prescribed"},
        {"code": "4030F", "desc": "Long-term oxygen therapy prescribed"},
        {"code": "4033F", "desc": "Pulmonary rehabilitation prescribed"},
        {"code": "4035F", "desc": "Influenza vaccine administered or previously received"},
        {"code": "4037F", "desc": "Influenza vaccine not administered, patient allergy or other medical reason"},
        {"code": "4040F", "desc": "Pneumococcal vaccine administered or previously received"},
        {"code": "4041F", "desc": "Pneumococcal vaccine not administered, patient allergy or other medical reason"},
        {"code": "4042F", "desc": "Documentation that pneumococcal vaccine was administered prior to discharge"},
        {"code": "4043F", "desc": "Pneumococcal conjugate vaccine administered or previously received"},
        {"code": "4044F", "desc": "Documentation that pneumococcal conjugate vaccine was administered prior to discharge or within 6 months prior to episode date"},
        {"code": "4045F", "desc": "Pneumococcal polysaccharide vaccine (PPSV23) administered or previously received"},
        {"code": "4046F", "desc": "Ipratropium bromide prescribed as part of a discharge plan"},
        {"code": "4047F", "desc": "Documentation that patient received short-acting bronchodilator"},
        {"code": "4048F", "desc": "Documentation that patient received systemic corticosteroid"},
        {"code": "4049F", "desc": "Documentation that patient received antibiotics"},
        {"code": "4050F", "desc": "Hypertension plan of care documented"},
        {"code": "4051F", "desc": "Referred for an arthritis physical activity program"},
        {"code": "4055F", "desc": "Rehabilitation services were ordered within 3 months of cerebral infarction"},
        {"code": "4060F", "desc": "Psychotherapy services provided"},
        {"code": "4062F", "desc": "Patient assessed for presence of hallucinations, and delusions"},
        {"code": "4063F", "desc": "Antidepressant pharmacotherapy considered and not prescribed, patient reason"},
        {"code": "4064F", "desc": "Antidepressant pharmacotherapy prescribed"},
        {"code": "4065F", "desc": "Antipsychotic pharmacotherapy prescribed"},
        {"code": "4066F", "desc": "Electroconvulsive therapy (ECT) provided"},
        {"code": "4069F", "desc": "Venous thromboembolism (VTE) prophylaxis received"},
        {"code": "4070F", "desc": "Deep vein thrombosis (DVT) prophylaxis received by end of hospital day 2"},
        {"code": "4073F", "desc": "Oral anticoagulant therapy prescribed for atrial fibrillation"},
        {"code": "4075F", "desc": "Antibiotic treatment prescribed"},
        {"code": "4077F", "desc": "Antibiotic treatment prescribed within 24 hours of admission"},
        {"code": "4078F", "desc": "Empiric antibiotic prescribed"},
        {"code": "4079F", "desc": "Documentation of concurrent care with a specialist for AMD during the reporting period"},
        {"code": "4084F", "desc": "Aspirin received within 24 hours before or after hospital arrival"},
        {"code": "4086F", "desc": "Aspirin or clopidogrel prescribed or currently being taken"},
        {"code": "4090F", "desc": "Patient screened for injection drug use"},
        {"code": "4100F", "desc": "Osteoarthritis counseling for exercise provided"},
        {"code": "4110F", "desc": "Internal mammary artery used for primary bypass of the left anterior descending coronary artery"},
        {"code": "4115F", "desc": "Beta blocker administered within 24 hours prior to surgical incision"},
        {"code": "4116F", "desc": "Beta blocker continued for at least 24 hours post-operatively"},
        {"code": "4120F", "desc": "Antibiotic prescribed or dispensed"},
        {"code": "4124F", "desc": "Antibiotic neither prescribed nor dispensed"},
        {"code": "4130F", "desc": "Topical preparations (including OTC) prescribed for acute otitis externa (AOE)"},
        {"code": "4131F", "desc": "Systemic antimicrobial therapy prescribed"},
        {"code": "4132F", "desc": "Systemic antimicrobial therapy not prescribed"},
        {"code": "4133F", "desc": "Antihistamines or decongestants prescribed or recommended"},
        {"code": "4134F", "desc": "Antihistamines or decongestants neither prescribed nor recommended"},
        {"code": "4135F", "desc": "Systemic corticosteroids prescribed"},
        {"code": "4136F", "desc": "Systemic corticosteroids not prescribed"},
        {"code": "4140F", "desc": "Inhaled corticosteroids prescribed"},
        {"code": "4142F", "desc": "Corticosteroid sparing therapy prescribed"},
        {"code": "4144F", "desc": "Patient receiving anti-TNF therapy (e.g., adalimumab, certolizumab, etanercept, golimumab, infliximab)"},
        {"code": "4145F", "desc": "Documentation of current medications with dosages and start and stop dates"},
        {"code": "4148F", "desc": "Patient receiving anti-integrin therapy (eg, natalizumab)"},
        {"code": "4149F", "desc": "Documentation of at least two ocular examinations during the measure period"},
    ]

    for cat2 in cat2_codes:
        codes.append({
            "concept_code": cat2["code"],
            "concept_name": cat2["desc"],
            "category": "Category II",
            "work_rvu": 0.0,
            "synonyms": [],
        })

    return codes


# =============================================================================
# CATEGORY III CODES (Emerging Technology)
# =============================================================================
def generate_category_iii_codes() -> list[dict[str, Any]]:
    """Generate Category III emerging technology codes."""
    codes = []

    cat3_codes = [
        {"code": "0042T", "desc": "Cerebral perfusion analysis using computed tomography with contrast administration"},
        {"code": "0051T", "desc": "Implantation of a total replacement heart system"},
        {"code": "0052T", "desc": "Replacement or repair of thoracic unit of a total replacement heart system"},
        {"code": "0053T", "desc": "Replacement or repair of implantable component of total replacement heart system"},
        {"code": "0054T", "desc": "Computer-assisted musculoskeletal surgical navigational orthopedic procedure, with image guidance"},
        {"code": "0055T", "desc": "Computer-assisted musculoskeletal surgical navigational orthopedic procedure, without image guidance"},
        {"code": "0071T", "desc": "Focused ultrasound ablation of uterine leiomyomata"},
        {"code": "0072T", "desc": "Focused ultrasound ablation of uterine leiomyomata; MR guidance"},
        {"code": "0075T", "desc": "Transcatheter placement of extracranial vertebral artery stent(s)"},
        {"code": "0076T", "desc": "Transcatheter placement of extracranial vertebral or intrathoracic carotid artery stent(s)"},
        {"code": "0095T", "desc": "Removal of total disc arthroplasty, anterior approach, cervical"},
        {"code": "0098T", "desc": "Revision including replacement of total disc arthroplasty, anterior approach, cervical"},
        {"code": "0100T", "desc": "Placement of a subconjunctival retinal prosthesis receiver and pulse generator"},
        {"code": "0101T", "desc": "Extracorporeal shock wave involving musculoskeletal system, not otherwise specified, high energy"},
        {"code": "0102T", "desc": "Extracorporeal shock wave involving musculoskeletal system; lateral humeral epicondyle"},
        {"code": "0103T", "desc": "Holotranscobalamin, quantitative"},
        {"code": "0106T", "desc": "Quantitative sensory testing, per limb; testing and interpretation and report"},
        {"code": "0107T", "desc": "Quantitative sensory testing, per limb; testing only"},
        {"code": "0108T", "desc": "Quantitative sensory testing, per limb; interpretation and report only"},
        {"code": "0109T", "desc": "Heat-activated tumor ablation, ultrasound guidance"},
        {"code": "0110T", "desc": "Heat-activated tumor ablation, MRI guidance"},
        {"code": "0111T", "desc": "Long-chain (C20-22) omega-3 fatty acids"},
        {"code": "0126T", "desc": "Common carotid intima-media thickness (IMT) study for evaluation of atherosclerotic burden"},
        {"code": "0163T", "desc": "Total disc arthroplasty, anterior approach, including discectomy; cervical, 2 levels"},
        {"code": "0164T", "desc": "Total disc arthroplasty, anterior approach, including discectomy; cervical, 3 or more levels"},
        {"code": "0165T", "desc": "Revision of total disc arthroplasty, anterior approach; cervical, 2 levels"},
        {"code": "0166T", "desc": "Revision of total disc arthroplasty, anterior approach; cervical, 3 or more levels"},
        {"code": "0167T", "desc": "Removal of total disc arthroplasty, anterior approach; cervical, 2 levels"},
        {"code": "0168T", "desc": "Removal of total disc arthroplasty, anterior approach; cervical, 3 or more levels"},
        {"code": "0169T", "desc": "Stereotactic placement of infusion catheter(s) in the brain for delivery of therapeutic agent(s)"},
        {"code": "0170T", "desc": "Stereotactic placement of infusion catheter(s) in the brain for delivery of therapeutic agent(s), posterior fossa"},
        {"code": "0171T", "desc": "Insertion of posterior spinous process distraction device, without fusion, cervical"},
        {"code": "0172T", "desc": "Insertion of posterior spinous process distraction device, without fusion, lumbar"},
        {"code": "0174T", "desc": "Computer-aided detection (CAD) of intracranial vessel(s), diagnostic CT angiography"},
        {"code": "0175T", "desc": "Computer-aided detection (CAD) of intracranial vessel(s), MR angiography"},
        {"code": "0178T", "desc": "Electrocardiogram, 64 leads or greater, with graphic presentation"},
        {"code": "0179T", "desc": "Electrocardiogram, 64 leads or greater, with 3D mapping and target reconstruction"},
        {"code": "0180T", "desc": "Electrocardiogram, 64 leads or greater; review, interpretation and report only"},
        {"code": "0181T", "desc": "Automated analysis of digitized data from nuclear medicine procedure"},
        {"code": "0182T", "desc": "High dose rate electronic brachytherapy, per fraction"},
        {"code": "0184T", "desc": "Excision of rectal tumor, transanal endoscopic microsurgical approach (TEMS)"},
        {"code": "0188T", "desc": "Remote real-time interactive video-conferenced critical care, evaluation and management of the critically ill or critically injured patient"},
        {"code": "0191T", "desc": "Insertion of anterior segment aqueous drainage device, without extraocular reservoir"},
        {"code": "0195T", "desc": "Arthrodesis, pre-sacral interbody technique, including disc space preparation"},
        {"code": "0196T", "desc": "Arthrodesis, pre-sacral interbody technique, including disc space preparation, with bone graft"},
        {"code": "0200T", "desc": "Percutaneous sacral augmentation (sacroplasty), unilateral injection(s)"},
        {"code": "0201T", "desc": "Percutaneous sacral augmentation (sacroplasty), bilateral injections"},
        {"code": "0202T", "desc": "Posterior vertebral joint(s) arthroplasty (eg, facet joint(s) replacement), including facetectomy"},
        {"code": "0205T", "desc": "Intragastric restrictive device, including endoscopy, for weight loss"},
        {"code": "0206T", "desc": "Intragastric restrictive device; removal of balloon, includes endoscopy"},
        {"code": "0207T", "desc": "Evacuation of meibomian glands, automated, using heat and intermittent pressure, unilateral"},
        {"code": "0208T", "desc": "Pure tone audiometry, air only, automated"},
        {"code": "0209T", "desc": "Pure tone audiometry, air and bone, automated"},
        {"code": "0210T", "desc": "Speech audiometry, automated"},
        {"code": "0211T", "desc": "Speech audiometry, automated; with tympanometry"},
        {"code": "0212T", "desc": "Comprehensive audiometry, automated"},
        {"code": "0213T", "desc": "Injection(s), diagnostic or therapeutic agent, paravertebral facet (zygapophyseal) joint with ultrasound guidance, cervical or thoracic; single level"},
        {"code": "0214T", "desc": "Injection(s), diagnostic or therapeutic agent, paravertebral facet (zygapophyseal) joint with ultrasound guidance, cervical or thoracic; second level"},
        {"code": "0215T", "desc": "Injection(s), diagnostic or therapeutic agent, paravertebral facet (zygapophyseal) joint with ultrasound guidance, cervical or thoracic; third and any additional level(s)"},
        {"code": "0216T", "desc": "Injection(s), diagnostic or therapeutic agent, paravertebral facet (zygapophyseal) joint with ultrasound guidance, lumbar or sacral; single level"},
        {"code": "0217T", "desc": "Injection(s), diagnostic or therapeutic agent, paravertebral facet (zygapophyseal) joint with ultrasound guidance, lumbar or sacral; second level"},
        {"code": "0218T", "desc": "Injection(s), diagnostic or therapeutic agent, paravertebral facet (zygapophyseal) joint with ultrasound guidance, lumbar or sacral; third and any additional level(s)"},
        {"code": "0219T", "desc": "Placement of a posterior intrafacet implant(s), unilateral or bilateral, including imaging and placement of bone graft(s) or synthetic device(s), single level; cervical"},
        {"code": "0220T", "desc": "Placement of a posterior intrafacet implant(s), unilateral or bilateral, including imaging and placement of bone graft(s) or synthetic device(s), single level; thoracic"},
        {"code": "0221T", "desc": "Placement of a posterior intrafacet implant(s), unilateral or bilateral, including imaging and placement of bone graft(s) or synthetic device(s), single level; lumbar"},
        {"code": "0222T", "desc": "Placement of a posterior intrafacet implant(s), unilateral or bilateral, including imaging and placement of bone graft(s) or synthetic device(s), single level; each additional vertebral segment"},
        {"code": "0223T", "desc": "Acoustic cardiography, including automated analysis of combined acoustic and electrical signal data"},
        {"code": "0224T", "desc": "Acoustic cardiography; each additional recording"},
        {"code": "0225T", "desc": "Acoustic cardiography; review, interpretation and report only"},
        {"code": "0226T", "desc": "Anoscopy, high resolution with magnification, and target tissue sampling, any method"},
        {"code": "0227T", "desc": "Anoscopy, high resolution with magnification, and target tissue sampling, any method; with ablation of lesion(s)"},
        {"code": "0228T", "desc": "Injection(s), anesthetic agent and/or steroid, transforaminal epidural, with ultrasound guidance, cervical or thoracic; single level"},
        {"code": "0229T", "desc": "Injection(s), anesthetic agent and/or steroid, transforaminal epidural, with ultrasound guidance, cervical or thoracic; each additional level"},
        {"code": "0230T", "desc": "Injection(s), anesthetic agent and/or steroid, transforaminal epidural, with ultrasound guidance, lumbar or sacral; single level"},
        {"code": "0231T", "desc": "Injection(s), anesthetic agent and/or steroid, transforaminal epidural, with ultrasound guidance, lumbar or sacral; each additional level"},
        {"code": "0232T", "desc": "Injection(s), platelet rich plasma, any tissue, including image guidance, harvesting and preparation when performed"},
        {"code": "0234T", "desc": "Transluminal peripheral atherectomy, open or percutaneous, including radiological supervision and interpretation; renal artery"},
        {"code": "0235T", "desc": "Transluminal peripheral atherectomy, open or percutaneous, including radiological supervision and interpretation; visceral artery (except renal), each vessel"},
        {"code": "0236T", "desc": "Transluminal peripheral atherectomy, open or percutaneous, including radiological supervision and interpretation; abdominal aorta"},
        {"code": "0237T", "desc": "Transluminal peripheral atherectomy, open or percutaneous, including radiological supervision and interpretation; brachiocephalic trunk and branches, each vessel"},
        {"code": "0238T", "desc": "Transluminal peripheral atherectomy, open or percutaneous, including radiological supervision and interpretation; iliac artery, each vessel"},
        {"code": "0253T", "desc": "Insertion of anterior segment aqueous drainage device, with creation of intraocular reservoir"},
        {"code": "0254T", "desc": "Endovascular repair of iliac artery bifurcation using bifurcated endoprosthesis from the common iliac artery into both the external iliac artery and the internal iliac artery"},
        {"code": "0255T", "desc": "Audiometric speech-in-noise testing"},
        {"code": "0263T", "desc": "Intramuscular autologous bone marrow cell therapy, with preparation of harvested cells, multiple injections, one leg, including ultrasound guidance, if performed; complete procedure including unilateral or bilateral bone marrow harvest"},
        {"code": "0264T", "desc": "Intramuscular autologous bone marrow cell therapy, with preparation of harvested cells, multiple injections, one leg, including ultrasound guidance, if performed; complete procedure excluding bone marrow harvest"},
        {"code": "0265T", "desc": "Intramuscular autologous bone marrow cell therapy, with preparation of harvested cells, multiple injections, one leg, including ultrasound guidance, if performed; unilateral or bilateral bone marrow harvest only for intramuscular autologous bone marrow cell therapy"},
        {"code": "0266T", "desc": "Implantation or replacement of carotid sinus baroreflex activation device; total system (includes generator placement, unilateral or bilateral lead placement, intra-operative interrogation, programming, and repositioning, when performed)"},
        {"code": "0267T", "desc": "Implantation or replacement of carotid sinus baroreflex activation device; lead only, unilateral (includes intra-operative interrogation, programming, and repositioning, when performed)"},
        {"code": "0268T", "desc": "Implantation or replacement of carotid sinus baroreflex activation device; pulse generator only (includes intra-operative interrogation, programming, and repositioning, when performed)"},
        {"code": "0269T", "desc": "Revision or removal of carotid sinus baroreflex activation device; total system (includes generator placement, unilateral or bilateral lead placement, intra-operative interrogation, programming, and repositioning, when performed)"},
        {"code": "0270T", "desc": "Revision or removal of carotid sinus baroreflex activation device; lead only, unilateral (includes intra-operative interrogation, programming, and repositioning, when performed)"},
        {"code": "0271T", "desc": "Revision or removal of carotid sinus baroreflex activation device; pulse generator only (includes intra-operative interrogation, programming, and repositioning, when performed)"},
        {"code": "0272T", "desc": "Interrogation device evaluation (in person), carotid sinus baroreflex activation system, including telemetric iterative communication with the implantable device to monitor device diagnostics and programmed therapy values, with interpretation and report (eg, electromagnetic field, radiofrequency)"},
        {"code": "0273T", "desc": "Interrogation device evaluation (in person), carotid sinus baroreflex activation system, including telemetric iterative communication with the implantable device to monitor device diagnostics and programmed therapy values, with interpretation and report (eg, electromagnetic field, radiofrequency); with programming"},
        {"code": "0274T", "desc": "Percutaneous laminotomy/laminectomy (interlaminar approach) for decompression of neural elements, (with or without ligamentous resection, discectomy, facetectomy and/or foraminotomy) any method under indirect image guidance (eg, fluoroscopic, CT), with or without the use of an endoscope, single or multiple levels, unilateral or bilateral; cervical or thoracic"},
        {"code": "0275T", "desc": "Percutaneous laminotomy/laminectomy (interlaminar approach) for decompression of neural elements, (with or without ligamentous resection, discectomy, facetectomy and/or foraminotomy) any method under indirect image guidance (eg, fluoroscopic, CT), with or without the use of an endoscope, single or multiple levels, unilateral or bilateral; lumbar"},
        {"code": "0278T", "desc": "Transcutaneous electrical modulation pain reprocessing (eg, scrambler therapy), each treatment session"},
    ]

    for cat3 in cat3_codes:
        codes.append({
            "concept_code": cat3["code"],
            "concept_name": cat3["desc"],
            "category": "Category III",
            "work_rvu": 0.0,
            "synonyms": [],
        })

    return codes


# =============================================================================
# MAIN FUNCTION
# =============================================================================
def load_existing_codes() -> dict[str, dict]:
    """Load existing codes from the fixture file."""
    existing = {}

    if EXISTING_FILE.exists():
        try:
            with open(EXISTING_FILE, "r") as f:
                data = json.load(f)
            for concept in data.get("concepts", []):
                code = concept.get("concept_code", "")
                if code:
                    existing[code] = concept
            print(f"Loaded {len(existing)} existing codes from {EXISTING_FILE}")
        except Exception as e:
            print(f"Error loading existing codes: {e}")

    return existing


def add_synonyms(codes: list[dict[str, Any]]) -> None:
    """Add clinical synonyms to codes."""
    code_to_idx = {code["concept_code"]: i for i, code in enumerate(codes)}

    for synonym, code_list in CLINICAL_SYNONYMS.items():
        for code_str in code_list:
            if code_str in code_to_idx:
                idx = code_to_idx[code_str]
                if synonym not in codes[idx].get("synonyms", []):
                    if "synonyms" not in codes[idx]:
                        codes[idx]["synonyms"] = []
                    codes[idx]["synonyms"].append(synonym)


def main():
    """Main function to generate comprehensive CPT codes."""
    print("=" * 60)
    print("CPT-4 Code Database Generator")
    print("=" * 60)

    # Ensure fixtures directory exists
    FIXTURES_DIR.mkdir(exist_ok=True)

    # Load existing codes
    existing_codes = load_existing_codes()

    # Generate all code categories
    print("\nGenerating E/M codes...")
    em_codes = generate_em_codes()
    print(f"  Generated {len(em_codes)} E/M codes")

    print("Generating Surgery codes...")
    surgery_codes = generate_surgery_codes()
    print(f"  Generated {len(surgery_codes)} Surgery codes")

    print("Generating Radiology codes...")
    radiology_codes = generate_radiology_codes()
    print(f"  Generated {len(radiology_codes)} Radiology codes")

    print("Generating Pathology/Lab codes...")
    pathology_codes = generate_pathology_codes()
    print(f"  Generated {len(pathology_codes)} Pathology/Lab codes")

    print("Generating Medicine codes...")
    medicine_codes = generate_medicine_codes()
    print(f"  Generated {len(medicine_codes)} Medicine codes")

    print("Generating Category II codes...")
    cat2_codes = generate_category_ii_codes()
    print(f"  Generated {len(cat2_codes)} Category II codes")

    print("Generating Category III codes...")
    cat3_codes = generate_category_iii_codes()
    print(f"  Generated {len(cat3_codes)} Category III codes")

    # Combine all generated codes
    all_codes = em_codes + surgery_codes + radiology_codes + pathology_codes + medicine_codes + cat2_codes + cat3_codes

    # Merge with existing codes (keep existing if better data)
    merged = {}
    for code in all_codes:
        code_str = code["concept_code"]
        if code_str in existing_codes:
            # Merge: keep existing synonyms and add new ones
            existing = existing_codes[code_str]
            existing_syns = set(existing.get("synonyms", []))
            new_syns = set(code.get("synonyms", []))
            code["synonyms"] = list(existing_syns | new_syns)
            # Keep concept_id if exists
            if existing.get("concept_id"):
                code["concept_id"] = existing["concept_id"]
        merged[code_str] = code

    # Add remaining existing codes
    for code_str, code_data in existing_codes.items():
        if code_str not in merged:
            merged[code_str] = code_data

    # Convert to list
    all_codes = list(merged.values())

    # Add clinical synonyms
    print("\nAdding clinical synonyms...")
    add_synonyms(all_codes)

    # Sort by code
    all_codes.sort(key=lambda x: x.get("concept_code", ""))

    # Count statistics
    by_category: dict[str, int] = {}
    with_rvu = 0
    with_synonyms = 0

    for code in all_codes:
        cat = code.get("category", "Unknown")
        by_category[cat] = by_category.get(cat, 0) + 1
        if code.get("work_rvu", 0) > 0:
            with_rvu += 1
        if code.get("synonyms"):
            with_synonyms += 1

    # Create output
    output_data = {
        "metadata": {
            "source": "Generated CPT-4 Code Database",
            "total_codes": len(all_codes),
            "codes_with_rvu": with_rvu,
            "codes_with_synonyms": with_synonyms,
            "by_category": by_category,
            "modifiers": CPT_MODIFIERS,
        },
        "concepts": all_codes,
    }

    # Write to file
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output_data, f, indent=2)

    print()
    print("=" * 60)
    print(f"Generated: {OUTPUT_FILE}")
    print(f"Total codes: {len(all_codes):,}")
    print(f"Codes with RVU values: {with_rvu:,}")
    print(f"Codes with synonyms: {with_synonyms:,}")
    print()
    print("By category:")
    for cat, count in sorted(by_category.items()):
        print(f"  {cat}: {count:,}")
    print("=" * 60)


if __name__ == "__main__":
    main()
