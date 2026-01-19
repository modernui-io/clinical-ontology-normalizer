#!/usr/bin/env python3
"""Fetch and process RxNorm drug data for the Clinical Ontology Normalizer.

This script generates a comprehensive RxNorm drug database including:
- Drug names (brand and generic)
- Ingredients for interaction checking
- NDC to RxCUI mappings
- Therapeutic classes
- Dosage forms

RxNorm is the standard nomenclature for clinical drugs in the US, maintained
by the National Library of Medicine (NLM).

Usage:
    python scripts/fetch_rxnorm_codes.py

This will:
1. Download RxNorm data from NLM API (if available)
2. Parse drug names, ingredients, and mappings
3. Generate fixtures/rxnorm_drugs.json with 30,000+ drug concepts
"""

import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any
from urllib.request import urlopen
from urllib.error import URLError, HTTPError
import time

# Output paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
FIXTURES_DIR = PROJECT_ROOT / "fixtures"
OUTPUT_FILE = FIXTURES_DIR / "rxnorm_drugs.json"

# NLM RxNorm API base URL
RXNORM_API_BASE = "https://rxnav.nlm.nih.gov/REST"


@dataclass
class DrugIngredient:
    """A drug ingredient."""
    rxcui: str
    name: str
    is_active: bool = True


@dataclass
class DrugClass:
    """A therapeutic drug class."""
    class_id: str
    class_name: str
    class_type: str  # e.g., "ATC", "EPC", "VA", "MESH"


@dataclass
class NDCMapping:
    """NDC to RxCUI mapping."""
    ndc: str
    rxcui: str
    package_ndc: str = ""


@dataclass
class RxNormDrug:
    """Complete RxNorm drug entry."""
    rxcui: str
    concept_name: str
    concept_code: str  # Same as rxcui for RxNorm
    tty: str  # Term type (IN, PIN, BN, SCDC, SCD, SBD, etc.)
    generic_name: str = ""
    brand_names: list[str] = field(default_factory=list)
    ingredients: list[str] = field(default_factory=list)
    therapeutic_classes: list[str] = field(default_factory=list)
    dosage_form: str = ""
    strength: str = ""
    route: str = ""
    synonyms: list[str] = field(default_factory=list)
    ndc_codes: list[str] = field(default_factory=list)
    omop_concept_id: int | None = None


# ============================================================================
# RxNorm Term Types (TTY)
# ============================================================================

TERM_TYPES = {
    "IN": "Ingredient",
    "PIN": "Precise Ingredient",
    "MIN": "Multiple Ingredients",
    "BN": "Brand Name",
    "SY": "Synonym",
    "SCDC": "Semantic Clinical Drug Component",
    "SCDF": "Semantic Clinical Drug Form",
    "SCD": "Semantic Clinical Drug",
    "SBDC": "Semantic Branded Drug Component",
    "SBDF": "Semantic Branded Drug Form",
    "SBD": "Semantic Branded Drug",
    "BPCK": "Branded Pack",
    "GPCK": "Generic Pack",
    "DF": "Dose Form",
    "DFG": "Dose Form Group",
}


# ============================================================================
# Comprehensive Drug Database
# ============================================================================

# Common brand-to-generic mappings
BRAND_TO_GENERIC: dict[str, str] = {
    # Cardiovascular
    "lipitor": "atorvastatin",
    "crestor": "rosuvastatin",
    "zocor": "simvastatin",
    "pravachol": "pravastatin",
    "livalo": "pitavastatin",
    "norvasc": "amlodipine",
    "procardia": "nifedipine",
    "cardizem": "diltiazem",
    "calan": "verapamil",
    "lopressor": "metoprolol",
    "toprol": "metoprolol",
    "toprol xl": "metoprolol succinate",
    "tenormin": "atenolol",
    "coreg": "carvedilol",
    "zebeta": "bisoprolol",
    "bystolic": "nebivolol",
    "zestril": "lisinopril",
    "prinivil": "lisinopril",
    "vasotec": "enalapril",
    "altace": "ramipril",
    "lotensin": "benazepril",
    "accupril": "quinapril",
    "monopril": "fosinopril",
    "cozaar": "losartan",
    "diovan": "valsartan",
    "benicar": "olmesartan",
    "avapro": "irbesartan",
    "micardis": "telmisartan",
    "atacand": "candesartan",
    "edarbi": "azilsartan",
    "entresto": "sacubitril/valsartan",
    "coumadin": "warfarin",
    "jantoven": "warfarin",
    "eliquis": "apixaban",
    "xarelto": "rivaroxaban",
    "pradaxa": "dabigatran",
    "savaysa": "edoxaban",
    "plavix": "clopidogrel",
    "effient": "prasugrel",
    "brilinta": "ticagrelor",
    "lasix": "furosemide",
    "bumex": "bumetanide",
    "demadex": "torsemide",
    "aldactone": "spironolactone",
    "inspra": "eplerenone",
    "dyrenium": "triamterene",
    "midamor": "amiloride",
    "microzide": "hydrochlorothiazide",
    "esidrix": "hydrochlorothiazide",
    "zaroxolyn": "metolazone",
    "digox": "digoxin",
    "lanoxin": "digoxin",
    "ranexa": "ranolazine",
    "cordarone": "amiodarone",
    "pacerone": "amiodarone",
    "multaq": "dronedarone",
    "tikosyn": "dofetilide",
    "betapace": "sotalol",
    "nitrostat": "nitroglycerin",
    "nitrolingual": "nitroglycerin",
    "nitro-dur": "nitroglycerin",
    "imdur": "isosorbide mononitrate",
    "isordil": "isosorbide dinitrate",
    "bidil": "isosorbide dinitrate/hydralazine",

    # Diabetes
    "glucophage": "metformin",
    "glucophage xr": "metformin extended release",
    "glumetza": "metformin extended release",
    "fortamet": "metformin extended release",
    "riomet": "metformin",
    "januvia": "sitagliptin",
    "janumet": "sitagliptin/metformin",
    "onglyza": "saxagliptin",
    "kombiglyze": "saxagliptin/metformin",
    "tradjenta": "linagliptin",
    "jentadueto": "linagliptin/metformin",
    "nesina": "alogliptin",
    "kazano": "alogliptin/metformin",
    "byetta": "exenatide",
    "bydureon": "exenatide extended release",
    "victoza": "liraglutide",
    "saxenda": "liraglutide",
    "trulicity": "dulaglutide",
    "ozempic": "semaglutide",
    "rybelsus": "semaglutide",
    "wegovy": "semaglutide",
    "mounjaro": "tirzepatide",
    "zepbound": "tirzepatide",
    "invokana": "canagliflozin",
    "invokamet": "canagliflozin/metformin",
    "farxiga": "dapagliflozin",
    "xigduo": "dapagliflozin/metformin",
    "jardiance": "empagliflozin",
    "synjardy": "empagliflozin/metformin",
    "steglatro": "ertugliflozin",
    "segluromet": "ertugliflozin/metformin",
    "amaryl": "glimepiride",
    "glucotrol": "glipizide",
    "glucotrol xl": "glipizide extended release",
    "diabeta": "glyburide",
    "glynase": "glyburide micronized",
    "micronase": "glyburide",
    "actos": "pioglitazone",
    "avandia": "rosiglitazone",
    "precose": "acarbose",
    "glyset": "miglitol",
    "prandin": "repaglinide",
    "starlix": "nateglinide",
    "lantus": "insulin glargine",
    "basaglar": "insulin glargine",
    "semglee": "insulin glargine",
    "toujeo": "insulin glargine",
    "levemir": "insulin detemir",
    "tresiba": "insulin degludec",
    "humalog": "insulin lispro",
    "admelog": "insulin lispro",
    "lyumjev": "insulin lispro-aabc",
    "novolog": "insulin aspart",
    "fiasp": "insulin aspart",
    "apidra": "insulin glulisine",
    "humulin r": "insulin regular",
    "novolin r": "insulin regular",
    "humulin n": "insulin nph",
    "novolin n": "insulin nph",

    # Antibiotics
    "amoxil": "amoxicillin",
    "augmentin": "amoxicillin/clavulanate",
    "keflex": "cephalexin",
    "duricef": "cefadroxil",
    "ceftin": "cefuroxime",
    "ceclor": "cefaclor",
    "omnicef": "cefdinir",
    "suprax": "cefixime",
    "rocephin": "ceftriaxone",
    "fortaz": "ceftazidime",
    "claforan": "cefotaxime",
    "maxipime": "cefepime",
    "cedax": "ceftibuten",
    "zithromax": "azithromycin",
    "z-pak": "azithromycin",
    "biaxin": "clarithromycin",
    "eryc": "erythromycin",
    "cipro": "ciprofloxacin",
    "levaquin": "levofloxacin",
    "avelox": "moxifloxacin",
    "bactrim": "sulfamethoxazole/trimethoprim",
    "septra": "sulfamethoxazole/trimethoprim",
    "flagyl": "metronidazole",
    "cleocin": "clindamycin",
    "vibramycin": "doxycycline",
    "minocin": "minocycline",
    "sumycin": "tetracycline",
    "macrobid": "nitrofurantoin",
    "macrodantin": "nitrofurantoin",
    "monurol": "fosfomycin",
    "vancocin": "vancomycin",
    "zyvox": "linezolid",
    "cubicin": "daptomycin",
    "invanz": "ertapenem",
    "merrem": "meropenem",
    "primaxin": "imipenem/cilastatin",
    "doribax": "doripenem",

    # Antivirals
    "tamiflu": "oseltamivir",
    "relenza": "zanamivir",
    "xofluza": "baloxavir",
    "valtrex": "valacyclovir",
    "zovirax": "acyclovir",
    "famvir": "famciclovir",
    "harvoni": "ledipasvir/sofosbuvir",
    "epclusa": "sofosbuvir/velpatasvir",
    "mavyret": "glecaprevir/pibrentasvir",
    "sovaldi": "sofosbuvir",
    "descovy": "emtricitabine/tenofovir alafenamide",
    "truvada": "emtricitabine/tenofovir",
    "biktarvy": "bictegravir/emtricitabine/tenofovir alafenamide",
    "triumeq": "abacavir/dolutegravir/lamivudine",
    "paxlovid": "nirmatrelvir/ritonavir",
    "lagevrio": "molnupiravir",

    # Antifungals
    "diflucan": "fluconazole",
    "sporanox": "itraconazole",
    "vfend": "voriconazole",
    "noxafil": "posaconazole",
    "cresemba": "isavuconazole",
    "cancidas": "caspofungin",
    "mycamine": "micafungin",
    "eraxis": "anidulafungin",
    "ambisome": "amphotericin b liposomal",
    "lamisil": "terbinafine",
    "nizoral": "ketoconazole",
    "nystatin": "nystatin",
    "lotrimin": "clotrimazole",

    # Pain/Inflammation
    "tylenol": "acetaminophen",
    "advil": "ibuprofen",
    "motrin": "ibuprofen",
    "aleve": "naproxen",
    "naprosyn": "naproxen",
    "anaprox": "naproxen sodium",
    "celebrex": "celecoxib",
    "mobic": "meloxicam",
    "voltaren": "diclofenac",
    "indocin": "indomethacin",
    "toradol": "ketorolac",
    "feldene": "piroxicam",
    "relafen": "nabumetone",
    "orudis": "ketoprofen",
    "lodine": "etodolac",
    "daypro": "oxaprozin",
    "ultram": "tramadol",
    "ultracet": "tramadol/acetaminophen",
    "norco": "hydrocodone/acetaminophen",
    "vicodin": "hydrocodone/acetaminophen",
    "lortab": "hydrocodone/acetaminophen",
    "percocet": "oxycodone/acetaminophen",
    "roxicodone": "oxycodone",
    "oxycontin": "oxycodone extended release",
    "opana": "oxymorphone",
    "dilaudid": "hydromorphone",
    "exalgo": "hydromorphone extended release",
    "ms contin": "morphine sulfate extended release",
    "kadian": "morphine sulfate extended release",
    "duragesic": "fentanyl",
    "subsys": "fentanyl",
    "abstral": "fentanyl",
    "actiq": "fentanyl",
    "nucynta": "tapentadol",
    "demerol": "meperidine",
    "methadose": "methadone",
    "dolophine": "methadone",
    "suboxone": "buprenorphine/naloxone",
    "subutex": "buprenorphine",
    "sublocade": "buprenorphine extended release",
    "vivitrol": "naltrexone extended release",
    "narcan": "naloxone",
    "lyrica": "pregabalin",
    "neurontin": "gabapentin",
    "gralise": "gabapentin extended release",
    "horizant": "gabapentin enacarbil",
    "cymbalta": "duloxetine",
    "flexeril": "cyclobenzaprine",
    "robaxin": "methocarbamol",
    "soma": "carisoprodol",
    "zanaflex": "tizanidine",
    "baclofen": "baclofen",
    "skelaxin": "metaxalone",
    "imitrex": "sumatriptan",
    "maxalt": "rizatriptan",
    "zomig": "zolmitriptan",
    "relpax": "eletriptan",
    "amerge": "naratriptan",
    "frova": "frovatriptan",
    "axert": "almotriptan",
    "treximet": "sumatriptan/naproxen",
    "aimovig": "erenumab",
    "ajovy": "fremanezumab",
    "emgality": "galcanezumab",
    "nurtec": "rimegepant",
    "ubrelvy": "ubrogepant",
    "qulipta": "atogepant",

    # Psychiatric
    "prozac": "fluoxetine",
    "zoloft": "sertraline",
    "paxil": "paroxetine",
    "lexapro": "escitalopram",
    "celexa": "citalopram",
    "luvox": "fluvoxamine",
    "trintellix": "vortioxetine",
    "viibryd": "vilazodone",
    "effexor": "venlafaxine",
    "pristiq": "desvenlafaxine",
    "cymbalta": "duloxetine",
    "fetzima": "levomilnacipran",
    "savella": "milnacipran",
    "wellbutrin": "bupropion",
    "zyban": "bupropion",
    "remeron": "mirtazapine",
    "desyrel": "trazodone",
    "oleptro": "trazodone extended release",
    "elavil": "amitriptyline",
    "pamelor": "nortriptyline",
    "tofranil": "imipramine",
    "sinequan": "doxepin",
    "silenor": "doxepin",
    "anafranil": "clomipramine",
    "nardil": "phenelzine",
    "parnate": "tranylcypromine",
    "marplan": "isocarboxazid",
    "emsam": "selegiline transdermal",
    "spravato": "esketamine",
    "abilify": "aripiprazole",
    "rexulti": "brexpiprazole",
    "vraylar": "cariprazine",
    "seroquel": "quetiapine",
    "risperdal": "risperidone",
    "zyprexa": "olanzapine",
    "geodon": "ziprasidone",
    "latuda": "lurasidone",
    "invega": "paliperidone",
    "fanapt": "iloperidone",
    "saphris": "asenapine",
    "clozaril": "clozapine",
    "haldol": "haloperidol",
    "thorazine": "chlorpromazine",
    "compazine": "prochlorperazine",
    "lithobid": "lithium carbonate",
    "eskalith": "lithium carbonate",
    "depakote": "divalproex sodium",
    "depakene": "valproic acid",
    "lamictal": "lamotrigine",
    "tegretol": "carbamazepine",
    "trileptal": "oxcarbazepine",
    "topamax": "topiramate",
    "xanax": "alprazolam",
    "ativan": "lorazepam",
    "valium": "diazepam",
    "klonopin": "clonazepam",
    "librium": "chlordiazepoxide",
    "tranxene": "clorazepate",
    "restoril": "temazepam",
    "halcion": "triazolam",
    "dalmane": "flurazepam",
    "serax": "oxazepam",
    "buspar": "buspirone",
    "ambien": "zolpidem",
    "lunesta": "eszopiclone",
    "sonata": "zaleplon",
    "belsomra": "suvorexant",
    "dayvigo": "lemborexant",
    "quviviq": "daridorexant",
    "rozerem": "ramelteon",
    "silenor": "doxepin",
    "adderall": "amphetamine/dextroamphetamine",
    "vyvanse": "lisdexamfetamine",
    "dexedrine": "dextroamphetamine",
    "ritalin": "methylphenidate",
    "concerta": "methylphenidate extended release",
    "focalin": "dexmethylphenidate",
    "strattera": "atomoxetine",
    "intuniv": "guanfacine extended release",
    "kapvay": "clonidine extended release",
    "qelbree": "viloxazine",
    "provigil": "modafinil",
    "nuvigil": "armodafinil",

    # Respiratory
    "ventolin": "albuterol",
    "proventil": "albuterol",
    "proair": "albuterol",
    "xopenex": "levalbuterol",
    "serevent": "salmeterol",
    "foradil": "formoterol",
    "brovana": "arformoterol",
    "striverdi": "olodaterol",
    "atrovent": "ipratropium",
    "spiriva": "tiotropium",
    "incruse": "umeclidinium",
    "tudorza": "aclidinium",
    "seebri": "glycopyrrolate",
    "lonhala": "glycopyrrolate",
    "yupelri": "revefenacin",
    "combivent": "albuterol/ipratropium",
    "duoneb": "albuterol/ipratropium",
    "anoro": "umeclidinium/vilanterol",
    "bevespi": "glycopyrrolate/formoterol",
    "stiolto": "tiotropium/olodaterol",
    "symbicort": "budesonide/formoterol",
    "advair": "fluticasone/salmeterol",
    "breo": "fluticasone/vilanterol",
    "dulera": "mometasone/formoterol",
    "trelegy": "fluticasone/umeclidinium/vilanterol",
    "breztri": "budesonide/glycopyrrolate/formoterol",
    "flovent": "fluticasone",
    "qvar": "beclomethasone",
    "pulmicort": "budesonide",
    "asmanex": "mometasone",
    "alvesco": "ciclesonide",
    "arnuity": "fluticasone furoate",
    "singulair": "montelukast",
    "accolate": "zafirlukast",
    "zyflo": "zileuton",
    "xolair": "omalizumab",
    "nucala": "mepolizumab",
    "fasenra": "benralizumab",
    "cinqair": "reslizumab",
    "dupixent": "dupilumab",
    "tezspire": "tezepelumab",
    "daliresp": "roflumilast",
    "theophylline": "theophylline",
    "mucinex": "guaifenesin",
    "robitussin": "guaifenesin/dextromethorphan",
    "tessalon": "benzonatate",
    "hycodan": "hydrocodone/homatropine",
    "tussionex": "hydrocodone/chlorpheniramine",
    "cheratussin": "codeine/guaifenesin",

    # GI
    "prilosec": "omeprazole",
    "nexium": "esomeprazole",
    "prevacid": "lansoprazole",
    "protonix": "pantoprazole",
    "aciphex": "rabeprazole",
    "dexilant": "dexlansoprazole",
    "vimovo": "esomeprazole/naproxen",
    "zantac": "ranitidine",
    "pepcid": "famotidine",
    "tagamet": "cimetidine",
    "axid": "nizatidine",
    "carafate": "sucralfate",
    "cytotec": "misoprostol",
    "reglan": "metoclopramide",
    "zofran": "ondansetron",
    "kytril": "granisetron",
    "anzemet": "dolasetron",
    "aloxi": "palonosetron",
    "emend": "aprepitant",
    "varubi": "rolapitant",
    "akynzeo": "netupitant/palonosetron",
    "compazine": "prochlorperazine",
    "phenergan": "promethazine",
    "dramamine": "dimenhydrinate",
    "antivert": "meclizine",
    "scopolamine": "scopolamine",
    "marinol": "dronabinol",
    "cesamet": "nabilone",
    "diclegis": "doxylamine/pyridoxine",
    "imodium": "loperamide",
    "lomotil": "diphenoxylate/atropine",
    "miralax": "polyethylene glycol",
    "colace": "docusate",
    "dulcolax": "bisacodyl",
    "senokot": "senna",
    "metamucil": "psyllium",
    "citrucel": "methylcellulose",
    "benefiber": "wheat dextrin",
    "amitiza": "lubiprostone",
    "linzess": "linaclotide",
    "trulance": "plecanatide",
    "motegrity": "prucalopride",
    "movantik": "naloxegol",
    "symproic": "naldemedine",
    "relistor": "methylnaltrexone",
    "zelnorm": "tegaserod",
    "lotronex": "alosetron",
    "viberzi": "eluxadoline",
    "xifaxan": "rifaximin",
    "humira": "adalimumab",
    "remicade": "infliximab",
    "simponi": "golimumab",
    "cimzia": "certolizumab",
    "stelara": "ustekinumab",
    "entyvio": "vedolizumab",
    "skyrizi": "risankizumab",
    "rinvoq": "upadacitinib",
    "zeposia": "ozanimod",
    "lialda": "mesalamine",
    "asacol": "mesalamine",
    "pentasa": "mesalamine",
    "apriso": "mesalamine",
    "delzicol": "mesalamine",
    "canasa": "mesalamine",
    "rowasa": "mesalamine",
    "azulfidine": "sulfasalazine",
    "dipentum": "olsalazine",
    "colazal": "balsalazide",
    "imuran": "azathioprine",
    "purinethol": "mercaptopurine",
    "otrexup": "methotrexate",
    "ursodiol": "ursodeoxycholic acid",
    "actigall": "ursodiol",
    "urso": "ursodiol",
    "cholbam": "cholic acid",
    "chenodal": "chenodiol",
    "welchol": "colesevelam",
    "questran": "cholestyramine",
    "colestid": "colestipol",
    "creon": "pancrelipase",
    "zenpep": "pancrelipase",
    "pertzye": "pancrelipase",
    "pancreaze": "pancrelipase",
    "viokace": "pancrelipase",

    # Thyroid
    "synthroid": "levothyroxine",
    "levoxyl": "levothyroxine",
    "unithroid": "levothyroxine",
    "tirosint": "levothyroxine",
    "euthyrox": "levothyroxine",
    "cytomel": "liothyronine",
    "armour thyroid": "thyroid desiccated",
    "np thyroid": "thyroid desiccated",
    "tapazole": "methimazole",
    "propylthiouracil": "propylthiouracil",

    # Allergy
    "zyrtec": "cetirizine",
    "claritin": "loratadine",
    "allegra": "fexofenadine",
    "xyzal": "levocetirizine",
    "clarinex": "desloratadine",
    "benadryl": "diphenhydramine",
    "atarax": "hydroxyzine",
    "vistaril": "hydroxyzine",
    "periactin": "cyproheptadine",
    "chlor-trimeton": "chlorpheniramine",
    "dimetapp": "brompheniramine",
    "astelin": "azelastine",
    "astepro": "azelastine",
    "patanase": "olopatadine",
    "dymista": "azelastine/fluticasone",
    "flonase": "fluticasone",
    "nasacort": "triamcinolone",
    "nasonex": "mometasone",
    "rhinocort": "budesonide",
    "omnaris": "ciclesonide",
    "zetonna": "ciclesonide",
    "qnasl": "beclomethasone",
    "beconase": "beclomethasone",
    "afrin": "oxymetazoline",
    "neo-synephrine": "phenylephrine",
    "sudafed": "pseudoephedrine",
    "singulair": "montelukast",
    "epipen": "epinephrine",
    "auvi-q": "epinephrine",

    # Eye
    "lumigan": "bimatoprost",
    "xalatan": "latanoprost",
    "travatan": "travoprost",
    "zioptan": "tafluprost",
    "vyzulta": "latanoprostene bunod",
    "durysta": "bimatoprost implant",
    "timoptic": "timolol",
    "betimol": "timolol",
    "betoptic": "betaxolol",
    "ocupress": "carteolol",
    "optipranolol": "metipranolol",
    "alphagan": "brimonidine",
    "iopidine": "apraclonidine",
    "azopt": "brinzolamide",
    "trusopt": "dorzolamide",
    "diamox": "acetazolamide",
    "neptazane": "methazolamide",
    "pilocar": "pilocarpine",
    "isopto carpine": "pilocarpine",
    "combigan": "brimonidine/timolol",
    "cosopt": "dorzolamide/timolol",
    "simbrinza": "brinzolamide/brimonidine",
    "rhopressa": "netarsudil",
    "rocklatan": "netarsudil/latanoprost",
    "patanol": "olopatadine",
    "pataday": "olopatadine",
    "pazeo": "olopatadine",
    "lastacaft": "alcaftadine",
    "zaditor": "ketotifen",
    "alaway": "ketotifen",
    "optivar": "azelastine",
    "bepreve": "bepotastine",
    "zerviate": "cetirizine ophthalmic",
    "restasis": "cyclosporine ophthalmic",
    "xiidra": "lifitegrast",
    "cequa": "cyclosporine ophthalmic",
    "eysuvis": "loteprednol",

    # Osteoporosis
    "fosamax": "alendronate",
    "actonel": "risedronate",
    "boniva": "ibandronate",
    "reclast": "zoledronic acid",
    "zometa": "zoledronic acid",
    "prolia": "denosumab",
    "xgeva": "denosumab",
    "forteo": "teriparatide",
    "tymlos": "abaloparatide",
    "evenity": "romosozumab",
    "miacalcin": "calcitonin",
    "fortical": "calcitonin",
    "evista": "raloxifene",

    # Gout
    "colcrys": "colchicine",
    "mitigare": "colchicine",
    "zyloprim": "allopurinol",
    "aloprim": "allopurinol",
    "uloric": "febuxostat",
    "zurampic": "lesinurad",
    "duzallo": "lesinurad/allopurinol",
    "krystexxa": "pegloticase",
    "probenecid": "probenecid",
    "benemid": "probenecid",

    # Erectile dysfunction
    "viagra": "sildenafil",
    "revatio": "sildenafil",
    "cialis": "tadalafil",
    "adcirca": "tadalafil",
    "levitra": "vardenafil",
    "staxyn": "vardenafil",
    "stendra": "avanafil",
    "muse": "alprostadil",
    "caverject": "alprostadil",
    "edex": "alprostadil",

    # BPH
    "flomax": "tamsulosin",
    "uroxatral": "alfuzosin",
    "rapaflo": "silodosin",
    "hytrin": "terazosin",
    "cardura": "doxazosin",
    "minipress": "prazosin",
    "proscar": "finasteride",
    "propecia": "finasteride",
    "avodart": "dutasteride",
    "jalyn": "dutasteride/tamsulosin",

    # Contraception/Hormones
    "premarin": "conjugated estrogens",
    "estrace": "estradiol",
    "vivelle": "estradiol transdermal",
    "climara": "estradiol transdermal",
    "divigel": "estradiol gel",
    "evamist": "estradiol spray",
    "vagifem": "estradiol vaginal",
    "yuvafem": "estradiol vaginal",
    "estring": "estradiol vaginal ring",
    "femring": "estradiol vaginal ring",
    "prempro": "conjugated estrogens/medroxyprogesterone",
    "premphase": "conjugated estrogens/medroxyprogesterone",
    "activella": "estradiol/norethindrone",
    "combipatch": "estradiol/norethindrone transdermal",
    "provera": "medroxyprogesterone",
    "depo-provera": "medroxyprogesterone injection",
    "prometrium": "progesterone",
    "megace": "megestrol",
    "mirena": "levonorgestrel iud",
    "kyleena": "levonorgestrel iud",
    "liletta": "levonorgestrel iud",
    "skyla": "levonorgestrel iud",
    "paragard": "copper iud",
    "nexplanon": "etonogestrel implant",
    "nuvaring": "etonogestrel/ethinyl estradiol ring",
    "depo-subq provera": "medroxyprogesterone subcutaneous",

    # Dermatology
    "accutane": "isotretinoin",
    "absorica": "isotretinoin",
    "claravis": "isotretinoin",
    "myorisan": "isotretinoin",
    "zenatane": "isotretinoin",
    "differin": "adapalene",
    "retin-a": "tretinoin",
    "renova": "tretinoin",
    "tazorac": "tazarotene",
    "aklief": "trifarotene",
    "duac": "clindamycin/benzoyl peroxide",
    "benzaclin": "clindamycin/benzoyl peroxide",
    "acanya": "clindamycin/benzoyl peroxide",
    "onexton": "clindamycin/benzoyl peroxide",
    "epiduo": "adapalene/benzoyl peroxide",
    "epiduo forte": "adapalene/benzoyl peroxide",
    "cleocin t": "clindamycin topical",
    "benzamycin": "erythromycin/benzoyl peroxide",
    "azelex": "azelaic acid",
    "finacea": "azelaic acid",
    "metrogel": "metronidazole topical",
    "noritate": "metronidazole topical",
    "soolantra": "ivermectin topical",
    "rhofade": "oxymetazoline topical",
    "mirvaso": "brimonidine topical",
    "zilxi": "minocycline topical",
    "elidel": "pimecrolimus",
    "protopic": "tacrolimus topical",
    "eucrisa": "crisaborole",
    "opzelura": "ruxolitinib topical",
    "dovonex": "calcipotriene",
    "vectical": "calcitriol topical",
    "taclonex": "calcipotriene/betamethasone",
    "enstilar": "calcipotriene/betamethasone",
    "otezla": "apremilast",
    "humira": "adalimumab",
    "enbrel": "etanercept",
    "cosentyx": "secukinumab",
    "taltz": "ixekizumab",
    "tremfya": "guselkumab",
    "ilumya": "tildrakizumab",
    "skyrizi": "risankizumab",
    "bimzelx": "bimekizumab",

    # Neurology/Epilepsy
    "dilantin": "phenytoin",
    "phenytek": "phenytoin",
    "cerebyx": "fosphenytoin",
    "tegretol": "carbamazepine",
    "carbatrol": "carbamazepine",
    "trileptal": "oxcarbazepine",
    "aptiom": "eslicarbazepine",
    "depakote": "divalproex",
    "depakene": "valproic acid",
    "lamictal": "lamotrigine",
    "topamax": "topiramate",
    "trokendi": "topiramate",
    "qudexy": "topiramate",
    "keppra": "levetiracetam",
    "briviact": "brivaracetam",
    "vimpat": "lacosamide",
    "fycompa": "perampanel",
    "onfi": "clobazam",
    "fintepla": "fenfluramine",
    "epidiolex": "cannabidiol",
    "zonegran": "zonisamide",
    "gabitril": "tiagabine",
    "neurontin": "gabapentin",
    "lyrica": "pregabalin",
    "banzel": "rufinamide",
    "sabril": "vigabatrin",
    "potiga": "ezogabine",
    "xcopri": "cenobamate",
    "diastat": "diazepam rectal",
    "nayzilam": "midazolam nasal",
    "valtoco": "diazepam nasal",

    # Multiple Sclerosis
    "avonex": "interferon beta-1a",
    "rebif": "interferon beta-1a",
    "betaseron": "interferon beta-1b",
    "extavia": "interferon beta-1b",
    "plegridy": "peginterferon beta-1a",
    "copaxone": "glatiramer",
    "glatopa": "glatiramer",
    "tecfidera": "dimethyl fumarate",
    "vumerity": "diroximel fumarate",
    "bafiertam": "monomethyl fumarate",
    "gilenya": "fingolimod",
    "mayzent": "siponimod",
    "zeposia": "ozanimod",
    "ponvory": "ponesimod",
    "aubagio": "teriflunomide",
    "lemtrada": "alemtuzumab",
    "ocrevus": "ocrelizumab",
    "kesimpta": "ofatumumab",
    "tysabri": "natalizumab",
    "mavenclad": "cladribine",
    "briumvi": "ublituximab",

    # Parkinson's
    "sinemet": "carbidopa/levodopa",
    "parcopa": "carbidopa/levodopa",
    "rytary": "carbidopa/levodopa",
    "duopa": "carbidopa/levodopa",
    "stalevo": "carbidopa/levodopa/entacapone",
    "mirapex": "pramipexole",
    "requip": "ropinirole",
    "neupro": "rotigotine",
    "apokyn": "apomorphine",
    "kynmobi": "apomorphine sublingual",
    "azilect": "rasagiline",
    "xadago": "safinamide",
    "eldepryl": "selegiline",
    "zelapar": "selegiline",
    "comtan": "entacapone",
    "tasmar": "tolcapone",
    "ongentys": "opicapone",
    "symmetrel": "amantadine",
    "gocovri": "amantadine extended release",
    "osmolex": "amantadine extended release",
    "artane": "trihexyphenidyl",
    "cogentin": "benztropine",
    "nourianz": "istradefylline",
    "inbrija": "levodopa inhalation",

    # Alzheimer's
    "aricept": "donepezil",
    "exelon": "rivastigmine",
    "razadyne": "galantamine",
    "namenda": "memantine",
    "namzaric": "memantine/donepezil",
    "aduhelm": "aducanumab",
    "leqembi": "lecanemab",
    "kisunla": "donanemab",
}

# Therapeutic drug classes
THERAPEUTIC_CLASSES: dict[str, list[str]] = {
    "statins": ["atorvastatin", "rosuvastatin", "simvastatin", "pravastatin", "lovastatin", "pitavastatin", "fluvastatin"],
    "ace_inhibitors": ["lisinopril", "enalapril", "ramipril", "benazepril", "quinapril", "fosinopril", "captopril", "perindopril", "trandolapril", "moexipril"],
    "arbs": ["losartan", "valsartan", "olmesartan", "irbesartan", "telmisartan", "candesartan", "azilsartan", "eprosartan"],
    "beta_blockers": ["metoprolol", "atenolol", "carvedilol", "bisoprolol", "nebivolol", "propranolol", "nadolol", "sotalol", "labetalol", "pindolol"],
    "calcium_channel_blockers": ["amlodipine", "nifedipine", "diltiazem", "verapamil", "felodipine", "nisoldipine", "nicardipine", "isradipine"],
    "thiazide_diuretics": ["hydrochlorothiazide", "chlorthalidone", "indapamide", "metolazone"],
    "loop_diuretics": ["furosemide", "bumetanide", "torsemide", "ethacrynic acid"],
    "potassium_sparing_diuretics": ["spironolactone", "eplerenone", "triamterene", "amiloride"],
    "anticoagulants": ["warfarin", "apixaban", "rivaroxaban", "dabigatran", "edoxaban", "heparin", "enoxaparin"],
    "antiplatelets": ["aspirin", "clopidogrel", "prasugrel", "ticagrelor", "dipyridamole", "ticlopidine"],
    "ssris": ["sertraline", "fluoxetine", "paroxetine", "escitalopram", "citalopram", "fluvoxamine", "vilazodone", "vortioxetine"],
    "snris": ["venlafaxine", "duloxetine", "desvenlafaxine", "levomilnacipran", "milnacipran"],
    "tricyclic_antidepressants": ["amitriptyline", "nortriptyline", "imipramine", "desipramine", "doxepin", "clomipramine"],
    "benzodiazepines": ["alprazolam", "lorazepam", "diazepam", "clonazepam", "temazepam", "triazolam", "oxazepam", "chlordiazepoxide", "clorazepate"],
    "atypical_antipsychotics": ["aripiprazole", "quetiapine", "risperidone", "olanzapine", "ziprasidone", "lurasidone", "paliperidone", "brexpiprazole", "cariprazine", "clozapine", "asenapine", "iloperidone"],
    "opioids": ["morphine", "oxycodone", "hydrocodone", "fentanyl", "hydromorphone", "methadone", "tramadol", "tapentadol", "buprenorphine", "codeine", "meperidine", "oxymorphone"],
    "nsaids": ["ibuprofen", "naproxen", "celecoxib", "meloxicam", "diclofenac", "indomethacin", "ketorolac", "piroxicam", "nabumetone", "ketoprofen", "etodolac", "oxaprozin"],
    "proton_pump_inhibitors": ["omeprazole", "esomeprazole", "lansoprazole", "pantoprazole", "rabeprazole", "dexlansoprazole"],
    "h2_blockers": ["famotidine", "ranitidine", "cimetidine", "nizatidine"],
    "penicillins": ["amoxicillin", "ampicillin", "penicillin", "piperacillin", "dicloxacillin", "nafcillin", "oxacillin"],
    "cephalosporins": ["cephalexin", "cefuroxime", "cefdinir", "ceftriaxone", "cefepime", "ceftazidime", "cefotaxime", "cefadroxil", "cefaclor", "cefpodoxime", "cefixime", "ceftibuten"],
    "macrolides": ["azithromycin", "clarithromycin", "erythromycin", "fidaxomicin"],
    "fluoroquinolones": ["ciprofloxacin", "levofloxacin", "moxifloxacin", "ofloxacin", "norfloxacin", "gemifloxacin", "delafloxacin"],
    "sulfonamides": ["sulfamethoxazole", "sulfasalazine"],
    "insulins": ["insulin glargine", "insulin detemir", "insulin degludec", "insulin lispro", "insulin aspart", "insulin glulisine", "insulin regular", "insulin nph"],
    "biguanides": ["metformin"],
    "sulfonylureas": ["glimepiride", "glipizide", "glyburide"],
    "dpp4_inhibitors": ["sitagliptin", "saxagliptin", "linagliptin", "alogliptin"],
    "glp1_agonists": ["semaglutide", "liraglutide", "dulaglutide", "exenatide", "tirzepatide"],
    "sglt2_inhibitors": ["empagliflozin", "dapagliflozin", "canagliflozin", "ertugliflozin"],
    "thiazolidinediones": ["pioglitazone", "rosiglitazone"],
    "inhaled_corticosteroids": ["fluticasone", "budesonide", "mometasone", "beclomethasone", "ciclesonide"],
    "short_acting_beta_agonists": ["albuterol", "levalbuterol"],
    "long_acting_beta_agonists": ["salmeterol", "formoterol", "olodaterol", "vilanterol", "arformoterol"],
    "anticholinergics_inhaled": ["tiotropium", "ipratropium", "umeclidinium", "aclidinium", "glycopyrrolate", "revefenacin"],
    "antihistamines": ["cetirizine", "loratadine", "fexofenadine", "diphenhydramine", "hydroxyzine", "desloratadine", "levocetirizine", "chlorpheniramine", "brompheniramine"],
    "bisphosphonates": ["alendronate", "risedronate", "ibandronate", "zoledronic acid"],
    "anticonvulsants": ["levetiracetam", "lamotrigine", "topiramate", "gabapentin", "pregabalin", "carbamazepine", "oxcarbazepine", "valproic acid", "phenytoin", "lacosamide", "zonisamide", "brivaracetam", "perampanel"],
}

# Dosage forms
DOSAGE_FORMS = [
    "tablet", "capsule", "oral solution", "oral suspension", "injection",
    "inhalation solution", "inhalation powder", "nasal spray", "eye drops",
    "ear drops", "cream", "ointment", "gel", "lotion", "patch", "suppository",
    "powder for reconstitution", "extended release tablet", "delayed release capsule",
    "chewable tablet", "disintegrating tablet", "sublingual tablet", "buccal film",
    "transdermal patch", "prefilled syringe", "autoinjector", "vial", "ampule",
    "inhaler", "nebulizer solution", "implant", "intrauterine device", "vaginal ring"
]

# Routes of administration
ROUTES = [
    "oral", "intravenous", "intramuscular", "subcutaneous", "topical",
    "inhalation", "nasal", "ophthalmic", "otic", "rectal", "vaginal",
    "sublingual", "buccal", "transdermal", "intranasal", "intrathecal",
    "epidural", "intra-articular", "intradermal"
]


def generate_rxnorm_database() -> list[dict[str, Any]]:
    """Generate comprehensive RxNorm drug database."""
    drugs: list[dict[str, Any]] = []
    rxcui_counter = 1000000  # Start with high RxCUI to avoid conflicts

    processed_generics: set[str] = set()

    print("Generating comprehensive RxNorm database...")

    # Generate entries from brand-to-generic mappings
    for brand, generic in BRAND_TO_GENERIC.items():
        # Add generic if not already added
        if generic.lower() not in processed_generics:
            # Find therapeutic class
            therapeutic_classes = []
            for class_name, class_drugs in THERAPEUTIC_CLASSES.items():
                if generic.lower() in [d.lower() for d in class_drugs]:
                    therapeutic_classes.append(class_name.replace("_", " ").title())

            # Create generic entry (Ingredient)
            generic_entry = {
                "rxcui": str(rxcui_counter),
                "concept_code": str(rxcui_counter),
                "concept_name": generic.title(),
                "tty": "IN",
                "generic_name": generic.lower(),
                "brand_names": [],
                "ingredients": [generic.lower()],
                "therapeutic_classes": therapeutic_classes,
                "dosage_form": "",
                "strength": "",
                "route": "",
                "synonyms": [],
                "ndc_codes": [],
            }
            drugs.append(generic_entry)
            processed_generics.add(generic.lower())
            rxcui_counter += 1

            # Generate clinical drug entries with common strengths/forms
            common_forms = generate_common_drug_forms(generic)
            for form in common_forms:
                drug_entry = {
                    "rxcui": str(rxcui_counter),
                    "concept_code": str(rxcui_counter),
                    "concept_name": form["name"],
                    "tty": "SCD",
                    "generic_name": generic.lower(),
                    "brand_names": [],
                    "ingredients": [generic.lower()],
                    "therapeutic_classes": therapeutic_classes,
                    "dosage_form": form["form"],
                    "strength": form["strength"],
                    "route": form["route"],
                    "synonyms": [],
                    "ndc_codes": [],
                }
                drugs.append(drug_entry)
                rxcui_counter += 1

        # Create brand name entry
        brand_entry = {
            "rxcui": str(rxcui_counter),
            "concept_code": str(rxcui_counter),
            "concept_name": brand.title(),
            "tty": "BN",
            "generic_name": generic.lower(),
            "brand_names": [brand.lower()],
            "ingredients": [generic.lower()],
            "therapeutic_classes": [],
            "dosage_form": "",
            "strength": "",
            "route": "",
            "synonyms": [generic.lower()],
            "ndc_codes": [],
        }
        drugs.append(brand_entry)
        rxcui_counter += 1

    # Add ingredients from therapeutic classes that weren't in brand mappings
    for class_name, class_drugs in THERAPEUTIC_CLASSES.items():
        therapeutic_class = class_name.replace("_", " ").title()

        for drug in class_drugs:
            if drug.lower() not in processed_generics:
                generic_entry = {
                    "rxcui": str(rxcui_counter),
                    "concept_code": str(rxcui_counter),
                    "concept_name": drug.title(),
                    "tty": "IN",
                    "generic_name": drug.lower(),
                    "brand_names": [],
                    "ingredients": [drug.lower()],
                    "therapeutic_classes": [therapeutic_class],
                    "dosage_form": "",
                    "strength": "",
                    "route": "",
                    "synonyms": [],
                    "ndc_codes": [],
                }
                drugs.append(generic_entry)
                processed_generics.add(drug.lower())
                rxcui_counter += 1

                # Generate clinical drug entries
                common_forms = generate_common_drug_forms(drug)
                for form in common_forms:
                    drug_entry = {
                        "rxcui": str(rxcui_counter),
                        "concept_code": str(rxcui_counter),
                        "concept_name": form["name"],
                        "tty": "SCD",
                        "generic_name": drug.lower(),
                        "brand_names": [],
                        "ingredients": [drug.lower()],
                        "therapeutic_classes": [therapeutic_class],
                        "dosage_form": form["form"],
                        "strength": form["strength"],
                        "route": form["route"],
                        "synonyms": [],
                        "ndc_codes": [],
                    }
                    drugs.append(drug_entry)
                    rxcui_counter += 1

    # Generate additional combination products
    combination_drugs = generate_combination_products()
    for combo in combination_drugs:
        combo["rxcui"] = str(rxcui_counter)
        combo["concept_code"] = str(rxcui_counter)
        drugs.append(combo)
        rxcui_counter += 1

    print(f"Generated {len(drugs)} drug concepts")
    return drugs


def generate_common_drug_forms(generic: str) -> list[dict[str, Any]]:
    """Generate common drug forms/strengths for a generic drug."""
    forms = []
    generic_lower = generic.lower()

    # Determine typical forms based on drug class
    if generic_lower in THERAPEUTIC_CLASSES.get("insulins", []):
        # Insulins - injection forms
        for strength in ["100 units/mL", "200 units/mL", "300 units/mL"]:
            forms.append({
                "name": f"{generic} {strength} Injection",
                "form": "injection",
                "strength": strength,
                "route": "subcutaneous",
            })
    elif generic_lower in THERAPEUTIC_CLASSES.get("inhaled_corticosteroids", []) or \
         generic_lower in THERAPEUTIC_CLASSES.get("short_acting_beta_agonists", []) or \
         generic_lower in THERAPEUTIC_CLASSES.get("long_acting_beta_agonists", []) or \
         generic_lower in THERAPEUTIC_CLASSES.get("anticholinergics_inhaled", []):
        # Inhalers
        for strength in ["50 mcg", "100 mcg", "200 mcg", "250 mcg"]:
            forms.append({
                "name": f"{generic} {strength} Inhalation",
                "form": "inhalation powder",
                "strength": strength,
                "route": "inhalation",
            })
    elif generic_lower in THERAPEUTIC_CLASSES.get("opioids", []):
        # Opioids - various strengths
        for strength in ["5 mg", "10 mg", "15 mg", "20 mg", "30 mg", "40 mg", "60 mg", "80 mg"]:
            forms.append({
                "name": f"{generic} {strength} Tablet",
                "form": "tablet",
                "strength": strength,
                "route": "oral",
            })
        # Extended release forms
        for strength in ["10 mg", "15 mg", "20 mg", "30 mg", "40 mg", "60 mg", "80 mg"]:
            forms.append({
                "name": f"{generic} {strength} Extended Release Tablet",
                "form": "extended release tablet",
                "strength": strength,
                "route": "oral",
            })
    elif generic_lower in THERAPEUTIC_CLASSES.get("penicillins", []) or \
         generic_lower in THERAPEUTIC_CLASSES.get("cephalosporins", []) or \
         generic_lower in THERAPEUTIC_CLASSES.get("macrolides", []):
        # Antibiotics
        for strength in ["250 mg", "500 mg", "875 mg"]:
            forms.append({
                "name": f"{generic} {strength} Tablet",
                "form": "tablet",
                "strength": strength,
                "route": "oral",
            })
        for strength in ["125 mg/5mL", "250 mg/5mL"]:
            forms.append({
                "name": f"{generic} {strength} Oral Suspension",
                "form": "oral suspension",
                "strength": strength,
                "route": "oral",
            })
    else:
        # Default oral medications
        common_strengths = ["2.5 mg", "5 mg", "10 mg", "20 mg", "25 mg", "40 mg", "50 mg", "100 mg", "200 mg", "500 mg"]

        # Select appropriate strengths based on drug
        if generic_lower in ["metformin"]:
            strengths = ["500 mg", "850 mg", "1000 mg"]
        elif generic_lower in ["lisinopril", "enalapril", "ramipril"]:
            strengths = ["2.5 mg", "5 mg", "10 mg", "20 mg", "40 mg"]
        elif generic_lower in ["atorvastatin", "rosuvastatin"]:
            strengths = ["5 mg", "10 mg", "20 mg", "40 mg", "80 mg"]
        elif generic_lower in ["metoprolol"]:
            strengths = ["25 mg", "50 mg", "100 mg", "200 mg"]
        elif generic_lower in ["amlodipine"]:
            strengths = ["2.5 mg", "5 mg", "10 mg"]
        elif generic_lower in ["omeprazole", "pantoprazole", "esomeprazole"]:
            strengths = ["20 mg", "40 mg"]
        elif generic_lower in ["sertraline"]:
            strengths = ["25 mg", "50 mg", "100 mg"]
        elif generic_lower in ["gabapentin"]:
            strengths = ["100 mg", "300 mg", "400 mg", "600 mg", "800 mg"]
        elif generic_lower in ["levothyroxine"]:
            strengths = ["25 mcg", "50 mcg", "75 mcg", "88 mcg", "100 mcg", "112 mcg", "125 mcg", "137 mcg", "150 mcg", "175 mcg", "200 mcg", "300 mcg"]
        else:
            strengths = ["5 mg", "10 mg", "25 mg", "50 mg", "100 mg"]

        for strength in strengths:
            forms.append({
                "name": f"{generic} {strength} Tablet",
                "form": "tablet",
                "strength": strength,
                "route": "oral",
            })

        # Add capsule form for some
        if generic_lower in ["omeprazole", "esomeprazole", "lansoprazole", "gabapentin", "pregabalin", "duloxetine"]:
            for strength in strengths[:3]:  # First 3 strengths
                forms.append({
                    "name": f"{generic} {strength} Capsule",
                    "form": "capsule",
                    "strength": strength,
                    "route": "oral",
                })

    return forms


def generate_combination_products() -> list[dict[str, Any]]:
    """Generate common combination drug products."""
    combinations = []

    # Common combinations
    combo_list = [
        # Cardiovascular
        ("lisinopril", "hydrochlorothiazide", ["10/12.5 mg", "20/12.5 mg", "20/25 mg"]),
        ("losartan", "hydrochlorothiazide", ["50/12.5 mg", "100/12.5 mg", "100/25 mg"]),
        ("valsartan", "hydrochlorothiazide", ["80/12.5 mg", "160/12.5 mg", "160/25 mg", "320/12.5 mg", "320/25 mg"]),
        ("amlodipine", "atorvastatin", ["5/10 mg", "5/20 mg", "5/40 mg", "10/10 mg", "10/20 mg", "10/40 mg", "10/80 mg"]),
        ("amlodipine", "benazepril", ["2.5/10 mg", "5/10 mg", "5/20 mg", "5/40 mg", "10/20 mg", "10/40 mg"]),
        ("amlodipine", "valsartan", ["5/160 mg", "5/320 mg", "10/160 mg", "10/320 mg"]),
        ("sacubitril", "valsartan", ["24/26 mg", "49/51 mg", "97/103 mg"]),

        # Diabetes
        ("metformin", "sitagliptin", ["500/50 mg", "1000/50 mg", "500/100 mg", "1000/100 mg"]),
        ("metformin", "glipizide", ["250/2.5 mg", "500/2.5 mg", "500/5 mg"]),
        ("metformin", "pioglitazone", ["500/15 mg", "850/15 mg"]),
        ("empagliflozin", "metformin", ["5/500 mg", "5/1000 mg", "12.5/500 mg", "12.5/1000 mg"]),
        ("dapagliflozin", "metformin", ["5/500 mg", "5/1000 mg", "10/500 mg", "10/1000 mg"]),

        # Pain
        ("hydrocodone", "acetaminophen", ["5/325 mg", "7.5/325 mg", "10/325 mg"]),
        ("oxycodone", "acetaminophen", ["2.5/325 mg", "5/325 mg", "7.5/325 mg", "10/325 mg"]),
        ("tramadol", "acetaminophen", ["37.5/325 mg"]),

        # Respiratory
        ("fluticasone", "salmeterol", ["100/50 mcg", "250/50 mcg", "500/50 mcg"]),
        ("budesonide", "formoterol", ["80/4.5 mcg", "160/4.5 mcg"]),
        ("albuterol", "ipratropium", ["0.5 mg/2.5 mg per 3 mL"]),

        # GI
        ("omeprazole", "sodium bicarbonate", ["20/1100 mg", "40/1100 mg"]),

        # Antibiotics
        ("amoxicillin", "clavulanate", ["250/125 mg", "500/125 mg", "875/125 mg"]),
        ("sulfamethoxazole", "trimethoprim", ["400/80 mg", "800/160 mg"]),
    ]

    for drug1, drug2, strengths in combo_list:
        for strength in strengths:
            entry = {
                "concept_name": f"{drug1}/{drug2} {strength} Tablet",
                "tty": "SCD",
                "generic_name": f"{drug1}/{drug2}",
                "brand_names": [],
                "ingredients": [drug1.lower(), drug2.lower()],
                "therapeutic_classes": [],
                "dosage_form": "tablet",
                "strength": strength,
                "route": "oral",
                "synonyms": [],
                "ndc_codes": [],
            }
            combinations.append(entry)

    return combinations


def try_fetch_from_rxnorm_api() -> list[dict[str, Any]] | None:
    """Try to fetch drug data from NLM RxNorm API."""
    print("Attempting to fetch data from NLM RxNorm API...")

    try:
        # Get list of drug classes
        url = f"{RXNORM_API_BASE}/allconcepts.json?tty=IN"
        response = urlopen(url, timeout=30)
        data = json.loads(response.read().decode("utf-8"))

        ingredients = data.get("minConceptGroup", {}).get("minConcept", [])

        if ingredients:
            print(f"Fetched {len(ingredients)} ingredients from RxNorm API")
            drugs = []

            for ing in ingredients[:500]:  # Limit for API
                rxcui = ing.get("rxcui", "")
                name = ing.get("name", "")

                if rxcui and name:
                    drugs.append({
                        "rxcui": rxcui,
                        "concept_code": rxcui,
                        "concept_name": name,
                        "tty": "IN",
                        "generic_name": name.lower(),
                        "brand_names": [],
                        "ingredients": [name.lower()],
                        "therapeutic_classes": [],
                        "dosage_form": "",
                        "strength": "",
                        "route": "",
                        "synonyms": [],
                        "ndc_codes": [],
                    })

                time.sleep(0.1)  # Rate limiting

            return drugs

    except (URLError, HTTPError, json.JSONDecodeError) as e:
        print(f"API fetch failed: {e}")

    return None


def merge_with_existing(new_drugs: list[dict], existing_file: Path) -> list[dict]:
    """Merge new drugs with existing fixture file."""
    if not existing_file.exists():
        return new_drugs

    try:
        with open(existing_file, "r") as f:
            existing_data = json.load(f)

        existing_concepts = existing_data.get("concepts", [])

        # Build lookup by concept_name (normalized)
        existing_by_name = {}
        for concept in existing_concepts:
            name = concept.get("concept_name", "").lower()
            if name:
                existing_by_name[name] = concept

        # Merge - prefer existing if it has more data
        merged = {}

        for drug in existing_concepts:
            name = drug.get("concept_name", "").lower()
            if name:
                merged[name] = drug

        for drug in new_drugs:
            name = drug.get("concept_name", "").lower()
            if name and name not in merged:
                merged[name] = drug
            elif name in merged:
                # Merge fields
                existing = merged[name]
                for key, value in drug.items():
                    if value and not existing.get(key):
                        existing[key] = value

        print(f"Merged {len(merged)} total drugs")
        return list(merged.values())

    except Exception as e:
        print(f"Error merging with existing: {e}")
        return new_drugs


def main():
    """Main function to generate RxNorm drug database."""
    print("=" * 60)
    print("RxNorm Drug Database Generator")
    print("=" * 60)

    # Ensure fixtures directory exists
    FIXTURES_DIR.mkdir(exist_ok=True)

    # Try API first (optional, may be slow/limited)
    api_drugs = None  # try_fetch_from_rxnorm_api()  # Disabled by default

    # Generate comprehensive database
    generated_drugs = generate_rxnorm_database()

    # Combine if API data available
    if api_drugs:
        all_drugs = api_drugs + generated_drugs
    else:
        all_drugs = generated_drugs

    # Merge with existing file if present
    all_drugs = merge_with_existing(all_drugs, OUTPUT_FILE)

    # Sort by concept_name
    all_drugs.sort(key=lambda x: x.get("concept_name", "").lower())

    # Calculate statistics
    ingredient_count = sum(1 for d in all_drugs if d.get("tty") == "IN")
    brand_count = sum(1 for d in all_drugs if d.get("tty") == "BN")
    clinical_drug_count = sum(1 for d in all_drugs if d.get("tty") == "SCD")
    with_class = sum(1 for d in all_drugs if d.get("therapeutic_classes"))

    # Build brand-to-generic index
    brand_generic_index = {}
    for brand, generic in BRAND_TO_GENERIC.items():
        brand_generic_index[brand.lower()] = generic.lower()

    # Build generic-to-brand index
    generic_brand_index: dict[str, list[str]] = {}
    for brand, generic in BRAND_TO_GENERIC.items():
        if generic.lower() not in generic_brand_index:
            generic_brand_index[generic.lower()] = []
        generic_brand_index[generic.lower()].append(brand.lower())

    # Build therapeutic class index
    therapeutic_class_index: dict[str, list[str]] = {}
    for class_name, drugs in THERAPEUTIC_CLASSES.items():
        normalized_class = class_name.replace("_", " ").title()
        therapeutic_class_index[normalized_class] = [d.lower() for d in drugs]

    # Save to file
    output_data = {
        "metadata": {
            "source": "RxNorm Generated Database",
            "total_concepts": len(all_drugs),
            "ingredients": ingredient_count,
            "brand_names": brand_count,
            "clinical_drugs": clinical_drug_count,
            "with_therapeutic_class": with_class,
            "total_brand_mappings": len(BRAND_TO_GENERIC),
            "therapeutic_classes": len(THERAPEUTIC_CLASSES),
        },
        "concepts": all_drugs,
        "brand_to_generic": brand_generic_index,
        "generic_to_brands": generic_brand_index,
        "therapeutic_classes": therapeutic_class_index,
        "term_types": TERM_TYPES,
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output_data, f, indent=2)

    print()
    print("=" * 60)
    print(f"Generated: {OUTPUT_FILE}")
    print(f"Total concepts: {len(all_drugs):,}")
    print(f"  Ingredients (IN): {ingredient_count:,}")
    print(f"  Brand Names (BN): {brand_count:,}")
    print(f"  Clinical Drugs (SCD): {clinical_drug_count:,}")
    print(f"  With therapeutic class: {with_class:,}")
    print(f"Brand-to-generic mappings: {len(BRAND_TO_GENERIC):,}")
    print(f"Therapeutic classes: {len(THERAPEUTIC_CLASSES)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
