# Changelog

This documents what pii-scrubber actually covers today, how that coverage
was verified, and what's explicitly still missing. It isn't a
version-by-version release log (see `git log` for that) - it's a status
report, written so a reader doesn't have to reconstruct coverage by
grepping source files.

## Document formats

`scrub_file` / `redact_file` support seven formats, with `redact_file`
preserving the original file structure rather than returning flattened
text:

| Format | Notes |
|---|---|
| `.txt` / `.md` | plain text |
| `.html` / `.htm` | tags/scripts/styles untouched, only visible text redacted |
| `.pdf` | layout/images kept; PII is truly removed (not just covered) via black-box redaction; optional OCR (`ocr=True`) for PII baked into images |
| `.docx` | paragraphs and table cells |
| `.csv` | redacted per cell, rows/columns intact |
| `.json` | string values redacted, keys/numbers/bools untouched |

A CLI (`pii-scrubber scrub` / `pii-scrubber redact`) wraps all of this.
`redact_file(..., open_after=True)` / `pii-scrubber redact --open` launches
the redacted file once written, so you can immediately check the result -
opt-in, since silently launching an app would be surprising in an
unattended script/CI context. `pii-scrubber scrub --open` does the same
for `scrub` (which normally only prints to stdout): it writes the
redacted text to `--output` if given, otherwise a temp file, then opens
that. On Windows this shows the native "How do you want to open this
file?" chooser instead of silently picking the OS default app - added
after a real user preferred to choose the app each time rather than
always get Notepad. macOS/Linux still launch the OS default app (no
scriptable equivalent of that chooser without extra dependencies).

## Languages tested

The regex rules are largely language-agnostic (email, phone, credit card,
national IDs). The NER model (`en_core_web_sm`) is English-only. Tested
directly, across 19 languages and 22 document types (business email,
resume/CV, medical record, legal contract, invoice, customer support
chat, social media post, news article, academic abstract, and more - see
`tools/audit_corpus.py`):

Arabic, Chinese (Simplified), Dutch, English, French, German, Hindi,
Italian, Japanese, Korean, Polish, Portuguese, Russian, Spanish, Swedish,
Thai, Turkish, Vietnamese, plus mixed English+Spanish text.

**Result:** email addresses were reliably redacted in every language
tested. Name/location/organization detection was not - it depends on the
English NER model, which routinely misreads ordinary foreign words as
PERSON or ORGANIZATION (documented per-language in the corpus output) and
just as often misses real names outside English. Treat NER output as
noisy for non-English text; the regex rules (including all national ID
formats below) don't have this limitation.

## PII entity types

| Category | Labels | Detection |
|---|---|---|
| Contact/network | `EMAIL`, `PHONE`, `IP_ADDRESS`, `MAC_ADDRESS`, `URL`, `FILE_PATH`, `SOCIAL_PROFILE` | regex |
| Financial | `CREDIT_CARD`, `IBAN` | regex, Luhn / mod-97 |
| Structural | `ADDRESS` | regex, bounded context window |
| People/places/orgs | `PERSON`, `LOCATION`, `ORGANIZATION`, `AFFILIATION` | spaCy NER, plus a title-prefixed regex fallback (`Mr./Dr./MRS` + name) for cases NER misses |
| National IDs | 39 countries - see below | regex, checksum-validated where a real algorithm exists |
| Passports | `PASSPORT_MRZ` - any issuing country | regex, ICAO 9303 checksum-validated |
| Health insurance | `DE_KVNR`, `UK_NHS_NUMBER`, `CA_ON_HEALTH` | regex, checksum-validated |

A curated exclusion list (`nonpii_terms.py`) stops common tech/business
jargon (Docker, jQuery, Node.js, Jira, ...) from being misread as
PERSON/ORGANIZATION - found by testing against a real technical resume,
which had 25 false PERSON matches before this fix.

## National ID coverage: 39 countries

| Country | Label | Checksum |
|---|---|---|
| Ireland | `PPS_NUMBER` | letter checksum |
| Ireland (postal code) | `EIRCODE` | format only |
| United Kingdom | `UK_NINO` | format only |
| United States | `SSN` | format only |
| France | `FR_INSEE` | mod 97 |
| Germany | `DE_RVNR` | weighted digit-sum |
| Spain | `ES_NIF` / `ES_NIE` | mod 23 letter lookup |
| Italy | `IT_CODICE_FISCALE` | position-weighted mod 26 |
| Netherlands | `NL_BSN` | elfproef (mod 11) |
| Poland | `PL_PESEL` | weighted mod 10 |
| Sweden | `SE_PERSONNUMMER` | Luhn |
| Norway | `NO_FODSELSNUMMER` | two-stage mod 11 |
| Portugal | `PT_NIF` | weighted mod 11 |
| Russia | `RU_INN` | two-stage weighted mod 11 |
| Turkey | `TR_TCKN` | weighted mod 10 |
| Romania | `RO_CNP` | weighted mod 11 |
| Hungary | `HU_SZEMELYI` | weighted mod 11 |
| Brazil | `BR_CPF` | two-stage weighted mod 11 |
| Canada | `CA_SIN` | Luhn |
| China | `CN_RESIDENT_ID` | ISO 7064 MOD 11-2 |
| South Korea | `KR_RRN` | weighted mod 11 |
| Australia | `AU_TFN` | weighted mod 11 |
| Algeria | `DZ_NIN` | modified Luhn |
| Austria | `AT_SVNR` | weighted mod 11 |
| Greece | `EL_AMKA` | Luhn |
| Mexico | `MX_IMSS` | digital-root weighted sum |
| Estonia | `EE_ISIKUKOOD` | two-scale mod 11 |
| Finland | `FI_HETU` | mod 31 letter lookup |
| Switzerland | `CH_AHV` | EAN-13-style, fixed `756` prefix |
| Israel | `IL_TZ` | Luhn-family |
| Croatia | `HR_OIB` | ISO 7064 MOD 11,10 |
| Latvia | `LV_PERSONAS_KODS` | weighted mod 11 |
| North Macedonia | `MK_EMBG` | weighted mod 11 |
| Belgium | `BE_RRN` | mod 97 |
| Bosnia and Herzegovina | `BA_JMB` | weighted mod 11 |
| Ukraine | `UA_RNOKPP` | weighted mod 11 mod 10 |
| Taiwan | `TW_ID` | letter-weighted positional sum |
| India | `IN_AADHAAR` | Luhn |
| Chile | `CL_RUT` | mod 11, cycling weights |
| Czech Republic / Slovakia | `CZ_SK_RODNE_CISLO` | divisible by 11 |

Every rule above was validated against hundreds of locale-appropriate
synthetic documents generated with [Faker](https://faker.readthedocs.io/)
(`tools/audit_national_ids.py`); where Faker can't produce a real
checksum-valid example for a country, the rule is instead verified with a
hand-computed test vector (`tests/test_national_ids.py`).

## Passports

`PASSPORT_MRZ` detects the two-line Machine Readable Zone printed on
every passport (ICAO 9303 TD3 standard), rather than a per-country
passport-*number* pattern. Passport number formats vary hugely by country
and, as far as could be verified, none of them have a public checksum -
so a "letters + digits" pattern would be far too collision-prone. The MRZ
is identical in structure across every issuing country and carries four
real check digits, verified against ICAO's own published worked example.

## Health insurance IDs

Three countries: Germany (`DE_KVNR`, nested double-Luhn), UK
(`UK_NHS_NUMBER`, weighted mod-11, verified against the NHS Data
Dictionary's published worked example), Ontario/Canada (`CA_ON_HEALTH`,
Luhn). These were the only ones found with a real, publicly documented
checksum after checking Faker's provider set plus targeted research.

## Deliberately NOT implemented

- **Driver's licences.** Researched the UK format (the most
  well-documented one) specifically: it deterministically encodes
  surname/DOB/initials, but its own documentation describes the final
  characters as "computer-generated"/random - no real checksum. US
  licences vary by state with no federal standard and no checksum found
  either. A format-only pattern would reintroduce the same collision risk
  that an early, unwired `_US_PASSPORT` regex had (removed - see git
  history) - matching ordinary alphanumeric codes throughout a document.
- **Passport numbers as a standalone field** (as opposed to the MRZ
  block) - same reasoning: no public checksum for most countries.
- **~150+ countries without a national ID rule** - the 39 above cover
  every country where Faker (or independent research, for the health/
  passport rules) provided a way to verify a real checksum. Most of
  Africa, the Middle East beyond Israel, Southeast Asia beyond
  Taiwan/Thailand's contact-card testing, and Central/South America
  beyond Brazil/Mexico/Chile/Colombia-adjacent research are not covered.

## Known, real bugs found and fixed during this work

Documented in detail in code comments and `README.md`'s Known
Limitations, summarized here since they show what "verified" actually
caught:

1. **`ADDRESS` regex false positive** - "close" (the common English word,
   e.g. "at the close of the meeting") matched as the street-suffix
   "Close", with a wide enough context window to swallow a real nearby
   email/phone. Found via the multilingual corpus, fixed by requiring
   Title Case/ALL CAPS instead of case-insensitive matching.
2. **IBAN, UK NINO, French INSEE, Swedish personnummer** all initially
   missed their conventional spaced/grouped display format (e.g. `GB29
   NWBK 6016 1331 9268 19`), matching only the compact unbroken-digit
   form - found one at a time via real documents and a systematic re-check
   after the first instance was found.
3. **Tech-jargon over-redaction** - a real technical resume had 25 false
   PERSON + 17 false ORGANIZATION matches from framework/tool names
   (Docker, jQuery, Node.js, ...) looking like proper nouns to the NER
   model. Fixed with a curated exclusion list.
4. **North Macedonia vs. Bosnia checksum** - both former-Yugoslav JMBG
   numbers share the same weights and were wrongly assumed identical;
   they diverge at one edge case (weighted sum mod 11 == 1), which
   silently rejected ~1/11 of otherwise-valid North Macedonian numbers.
5. **Dead code** - a `_US_PASSPORT` regex existed but was never wired
   into detection; removed rather than silently activated, since its
   shape was too collision-prone to ship.
6. **`EIRCODE` regex used bare `\s`** instead of a literal space, so it
   matched across newlines - found by running the tool on a real CV where
   the employer name "G4S" (a real security company) was immediately
   followed by a line break and then a year ("G4S\n2019"), which false-
   matched as an Irish postal code and hid a real company name under a
   misleading label. Fixed by requiring a literal space.
7. **`ADDRESS` regex was fully case-sensitive** - found via a real bank
   statement whose extracted PDF text rendered the account holder's
   address in lowercase ("47 quins cottages", " road"), which sailed
   through completely unredacted (twice - once in the address block,
   once inside a payment reference string). Fixed by splitting suffix
   words into an unambiguous group (Road, Cottages, Terrace, ...) matched
   case-insensitively, and an ambiguous group (Close, Court, Park, Row,
   Way, Place - all common English words) that stays Title-Case/ALL-CAPS
   only, preserving the original false-positive fix for those.
8. **Masked card numbers weren't detected at all** - found via the same
   real bank statement, which displays cards as `416598******4764`
   rather than a contiguous digit run. `CREDIT_CARD`'s Luhn check never
   even considered it a candidate since the asterisks break up the
   digits. Added a separate pattern for the masked format.

## How to extend this

- New regex rule: see `CONTRIBUTING.md` § "Adding a detection rule".
- New national ID: see `CONTRIBUTING.md` § "Adding a national ID format" -
  check Faker's provider source for a real checksum before trusting its
  generator, add the check function, and validate with
  `tools/audit_national_ids.py`.
- New language coverage: add cases to `tools/audit_corpus.py` and see
  what breaks.
