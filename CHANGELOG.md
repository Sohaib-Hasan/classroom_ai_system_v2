# Changelog — bug-fix pass (Aug 2026)

Ye sab fixes ek skeptical-engineer review ke baad kiye gaye — har ek ka
evidence hai (test, ya live simulation), guesswork nahi. Har fix ko
`tests/` mein ek regression test se cover kiya gaya hai.

## Critical fixes

**1. `response_format` Gemini Interactions API ke contract se match nahi
karta tha**
Pehle: `response_format=TutorAnswer.model_json_schema()` (raw dict).
Ab: `response_format=[{"type": "text", "mime_type": "application/json",
"schema": ...}]` — Google ki official migration docs ke exact example ke
mutabiq. Verified: `tests/test_generation_backend.py::test_calls_interactions_create_with_wrapped_response_format`,
aur live simulation mein `interactions.create` call ke args directly
inspect kiye gaye.

**2. SymPy verification sirf positive numbers se sample karta tha —
domain-sensitive galtiyan pakadta nahi tha**
Reproduced: `verify_computation('sqrt(x**2)', 'x')` → `True` (GALAT —
sirf x>=0 ke liye sach hai). Fix: sampling ab negative, positive, aur
near-zero — teenon regions se hoti hai. Verified:
`tests/test_core.py::TestVerifyComputationDomainBug` (20 trials, kam se
kam ek False expected).

**3. Cross-course fallback AI ko galat (apne kam-confidence course ke)
context ke saath call kar deta tha, quota waste karte hue**
Fix: `core.decide_retrieval_strategy()` — agar doosra course clearly
(diff > 0.15) behtar match karta ho, AI ko call hi nahi karte, seedha
redirect dikhate hain. Verified live (AppTest simulation):
`interactions.create` call na hone ki confirm ki gayi jab course clearly
galat tha.

## Scalability fixes

**4. Cache flat-JSON mein thi — har save par poori file (sab embeddings
samet) rewrite hoti thi**
Fix: SQLite (`cache_store.py`) — incremental inserts. Verified:
`tests/test_cache_store.py`, aur live simulation mein 2 alag sessions ke
beech cache-hit confirm kiya (paraphrase, same numbers → dusri baar
`interactions.create` call hi nahi hui).

**5. `requirements.txt` unpinned tha, ek actively-evolving beta SDK
(`google-genai`, jismein already ek breaking-change round ho chuka hai)
ke saath**
Fix: sab versions pin kiye (jo actually test hui).

## Security/hardening fixes

**6. PIN/teacher-password par koi rate-limiting/lockout nahi tha**
Fix: `auth_guard.py` — 5 galat attempts ke baad 60-second lockout.
Verified: `tests/test_auth_guard.py`, aur live simulation mein confirm
kiya ke 5 wrong attempts ke baad PIN input field hi gayab ho jata hai.

**7. Errors silently swallow ho rahe the — koi log nahi**
Fix: `logging_setup.py` — `logs/error.log` mein poora traceback likha
jata hai.

## Minor fixes

**8. `embed_chunks.py` mein ek chunk (2172 mein se 1) gemini-embedding-001
ki ~2048-token limit se upar tha**
Fix: `core.truncate_for_embedding()` — safe character-budget truncation,
aur console warning agar truncate hua.

**9. `chunk_notes.py` mein same-type nested boxes ka content leak ho jata
tha (discovered while writing tests — pehle se zyada messy nikla jitna
guess kiya tha)**
Fix: parsing logic nahi badli (real `.tex` fixtures nahi hain safe fix ke
liye), lekin ek loud warning add ki (`check_for_leaked_box_markup`) taake
ye chup-chaap knowledge base mein na jaye. Verified:
`tests/test_chunk_notes.py::TestSameTypeNestedBoxes`.

**10. `dashboard.py` mein `use_container_width` (Streamlit se deprecated,
already removal-date cross ho chuka tha) use ho raha tha**
Fix: `width='stretch'` mein badla — discovered via live AppTest simulation
(deprecation warning dikhi), guess se nahi.

## Naya (additive) — zero-budget resilience

- `embedding_backend.py` — pluggable embedding provider (Gemini + free
  local model via `sentence-transformers`).
- `generation_backend.py` — pluggable generation provider (Gemini +
  optional OpenAI-compatible fallback, jaise AgentRouter, sirf backup ke
  tor par).

## Post-deployment fixes (Aug 2026) — real bugs found in production use

**11. LaTeX commands in AI answers corrupted to garbled text**
Reported: student saw text like "imes" instead of "×", "uildrel" instead
of part of a LaTeX command, in the Roman Urdu explanation. Root cause
(confirmed by reproduction): Gemini sometimes writes LaTeX commands
(`\times`, `\buildrel`, `\pmod`) in the JSON response without properly
double-escaping the backslash. JSON then interprets `\t`/`\b`/etc. as
actual control characters (tab, backspace), silently eating the first
letter — or, for letters that aren't valid JSON escapes, crashes the
whole answer. Fix: `core.repair_json_escaping()` repairs the raw text
before parsing (matches a curated list of known LaTeX command names,
deliberately NOT a blanket regex — a blanket approach would have
corrupted legitimate `\n` newlines followed by ordinary words, which a
test caught). Also strengthened `SYSTEM_INSTRUCTION` to ask the model to
avoid LaTeX/backslash notation in prose fields entirely, using plain
symbols (×, ≡, √) instead — defense in depth alongside the repair
function. Verified: `tests/test_core.py::TestRepairJsonEscaping`,
reproducing the exact reported corruption pattern.

**12. Teacher dashboard showed no questions despite students using the app**
Reported: dashboard empty even after students asked questions. Root
cause: `app.py` and `dashboard.py` were deployed as two SEPARATE
Streamlit Cloud apps — each gets its own isolated, ephemeral container,
so local files written by one are invisible to the other (and don't
survive restarts even for the same app). Fix: `db_connection.py` — a
pluggable connection that uses local SQLite by default (unchanged
behaviour for single-app setups) or a shared, hosted Turso database when
`TURSO_DATABASE_URL`/`TURSO_AUTH_TOKEN` are configured in BOTH apps'
secrets. `question_log_store.py` replaces the CSV-based logging (which
had the same cross-app-invisibility problem) with a SQL table on the
same shared connection. Verified: mocked unit tests for the Turso
adapter (`tests/test_db_connection.py`), plus a live simulation proving
one AppTest instance's logged question was correctly read by a
completely separate AppTest instance via a shared local file (same
mechanism Turso uses, minus the network hop).
⚠️ The actual Turso network connection was NOT live-tested (turso.tech
not reachable from the development sandbox) — run
`python3 verify_turso_connection.py` with real credentials before
relying on it.

## Verification summary (kya actually test hua)

- ✅ `pytest tests/` — 91/91 pass
- ✅ `py_compile` — sab files, koi syntax error nahi
- ✅ `pyflakes` — clean
- ✅ Live Streamlit simulation (`streamlit.testing.v1.AppTest`, mocked
  network) — PIN gate, lockout, question→answer full pipeline, cache
  hit/miss, not_found path, cross_course_redirect path, dashboard.py —
  sab 0 exceptions ke saath
- ⚠️ Live Gemini API call — NAHI test hua (sandbox mein network
  restricted, koi Google domain allowed nahi)
- ⚠️ Live AgentRouter/fallback call — NAHI test hua (same wajah). Deploy
  se pehle `python3 verify_fallback_provider.py` khud chalayein.

## Next-phase build — Section 1: schema migration (Aug 2026)

**5. `question_log` mein 3 naye columns (`student_id`, `used_full_reveal`,
`mode`) add — per-student identity, scaffolding-engagement tracking, aur
question-vs-diagnosis mode ke liye foundation. Schema-only phase; koi
caller in columns ko abhi populate nahi karta.**
Pehle: `_SCHEMA` sirf `CREATE TABLE IF NOT EXISTS` tha — production Turso
DB mein table already exist karti hai (dono live apps ise share karte
hain), isliye sirf naye columns schema-string mein add karna production
ko crash karta (`no column named student_id` pehle INSERT par).
Ab: `_SCHEMA` (fresh DBs ke liye) aur `_apply_migrations()` — idempotent
`ALTER TABLE ADD COLUMN` list (existing production tables ke liye) —
dono ek saath. `_apply_migrations()` sirf "duplicate column"/"already
exists" errors ko ignore karta hai, baaki sab raise karta hai (Turso
connection-fail jaisi cheezein chup nahi honi chahiyein). `log_question()`
naye params optional hain, defaults ke saath (`student_id=None`,
`used_full_reveal=None`, `mode="question"`) — purane call sites (`app.py`,
`dashboard.py`) bina badle chalte rehte hain.
Verified: `tests/test_question_log_store.py::TestSchemaMigration` — 4 naye
tests, jisme sabse important scenario explicitly cover hota hai: ek
purani (pre-migration) table simulate ki gayi, `QuestionLogStore` usse
connect kiya gaya, confirm kiya gaya ke naye columns add hue bina crash
ya purana data khoye. Poora suite: `pytest tests/` — 95/95 pass.
⚠️ Deploy se pehle production Turso DB ka backup lein
(`turso db shell <db-name> ".dump" > backup.sql`) aur khud confirm karein
ke Turso ka "duplicate column" error-wording is sandbox ke SQLite
wording se match karta hai (is sandbox mein live Turso test nahi ho
saka — same restriction jo Bug pattern mein pehle bhi note hui hai).

## Next-phase build — Section 2: per-student identity capture (Aug 2026)

**6. `app.py` mein lightweight, pseudonymous student-identity gate — PIN
ke baad, ek dafa naam/roll-number poochta hai, `st.session_state` mein
rakhta hai, aur har `log_question()` call ke saath `student_id` pass
karta hai.**
Pehle: `question_log` mein koi student-level identity nahi thi — sirf
class-level PIN. Matlab "kaun struggle kar raha hai" sirf class-average
ke tor par pata chal sakta tha, kisi individual student ke tor par nahi.
Ab: PIN gate ke turant baad ek chhota, PIN jaisa hi single-step gate —
naam/roll-number required hai (khali nahi ja sakta), lekin koi
password/roster-verification nahi (jaan-boojh kar — goal *consistency*
hai, authentication nahi). Sidebar mein current naam dikhta hai aur ek
"Not you? Change name" button hai — agar koi shared/lab computer use ho
raha ho to ek student ka data doosre ke naam se log na ho.
`log_question()` (dono wrapper aur `QuestionLogStore.log_question()`)
ab `student_id` accept karte hain — Section 1 mein ye already
optional/backward-compatible bana diya gaya tha, isliye ye sirf ek
naya required positional argument add karna tha, koi aur jagah nahi
tooti.
Scope note: `dashboard.py` ko is turn mein jaan-boojh kar nahi chheda —
per-student mastery view alag, baad ka item hai (build order #6) jo
identity + diagnosis data dono chahta hai meaningful hone ke liye.
Verified: poori suite `pytest tests/` — 95/95 pass (Section 1 ke
`test_new_columns_store_provided_values` mein already `student_id`
value store hone ka coverage hai). `py_compile` + `pyflakes` clean on
`app.py`. Koi naya test file nahi chahiye tha — `app.py` khud is repo
mein unit-tested nahi hai (Streamlit UI layer), uski underlying logic
already `question_log_store.py` ke tests se covered hai.
Limitation, honestly stated: ye identity **browser-session-scoped**
hai, cross-device ya cross-day verified nahi — agar student kal alag
naam type kare, system usse alag learner samjhega. Ye jaan-boojh kar
hai (pseudonymous, no-auth design), lekin dashboard analysis karte
waqt yaad rakhna.

## Bug fix — "Change name" ke baad purani chat reh jati thi (16 Aug 2026)

**7. Mentor ne review mein catch kiya:** "Not you? Change name" button
sirf `student_id` clear karta tha, `st.session_state.messages` nahi.
Exactly usi shared/lab-computer scenario mein jiske liye ye button bana
tha — Student A poochta, "Change name" dabata, Student B apna naam
likhta — Student B ko Student A ki poori purani chat screen par dikhti
rehti thi, jab tak course na badle ya "Start a new topic" na dabaya
jaye. Database-level logging sahi thi (naya sawaal sahi naye
`student_id` ke sath log hota), lekin UI-level privacy leak thi — jo
button ka poora point hi undermine kar rahi thi.
Important note jo mentor ne khud kaha: pichle commit ka "95/95 pass"
is bug ko catch **nahi** karta tha — koi test is specific scenario ko
cover nahi karta tha, isliye green suite hona iske na-hone ka proof
nahi tha.
Fix: `session_helpers.py` (nayi file) mein `reset_identity()` — chhota,
Streamlit-independent, pure function jo `student_id` AUR `messages`
dono clear karta hai. Alag file mein isliye banaya kyunke `app.py` khud
top-level Streamlit script hai (import hote hi PIN gate/`st.secrets`
chal jate hain) — seedha `app.py` se import karke test karna fragile
hai. `session_helpers.py` mein koi Streamlit-dependency nahi, isliye
plain pytest se test hota hai.
Verified: `tests/test_session_helpers.py` — 3 naye tests, jisme se ek
explicitly ye check karta hai ke agar `messages`-clear wali line hata
di jaye to test fail ho jata hai (khud verify kiya, purana buggy
version reproduce kar ke). Poori suite: 98/98 pass.

## Next-phase build — Section 3: Scaffolded Answering Mode (Aug 2026)

**8. Har jawab ab default hint → guiding question → full-solution reveal
hota hai, seedha poora jawab nahi — mentor ke plan ke top-priority
research-aligned feature.**
`core.py`: `TutorAnswer` mein `hint`/`guiding_question` (Optional[str])
add kiye; `SYSTEM_INSTRUCTION` ab inhe hamesha bharne ko kehta hai (naya
point 3/4, baaki points renumber hue).
`question_log_store.py`: `log_question()` ab insert kiya gaya row ka id
return karta hai (SQLite aur Turso dono se `.lastrowid` milta hai —
`db_connection.py` mein pehle se hi consistent tha, ye piece already
tayyar thi). Naya `mark_revealed(row_id)` method us row ka
`used_full_reveal` baad mein update karta hai — jab student turant nahi,
kuch der baad "Show full solution" click kare, to NAYI row nahi banti,
wahi row update hoti hai (ek sawaal = ek row, chahe reveal turant ho ya
baad mein).
`app.py`: `show_answer()` ab `(turn, lang_pref, key, always_full)` leta
hai — pehle sirf `(answer, lang_pref)` leta tha. `turn` dict mein
`revealed`/`log_row_id` bhi hain, aur mutate hone par persist hote hain
(`st.session_state.messages` ka SAME object hai, copy nahi). `key` har
turn ke liye UNIQUE hai (`f"reveal_{i}"`) — Streamlit har interaction
par POORA script rerun karta hai, isliye per-turn state na ho to ek
turn ka reveal doosre turns ke render ko confuse kar sakta tha (isi
CLASS ka bug jo 16 Aug ke "Change name" fix mein tha). Turn dict ab
question-flow ke SHURU mein banta hai aur turant `st.session_state.
messages` mein append hota hai (pehle sirf block ke bilkul aakhir mein
banta tha) — taake live turn aur history-loop turn dono EK HI interface
(`turn` dict) se guzrein.
Sidebar mein "Always show full solutions (skip hints)" checkbox —
mentor ke plan ke mutabiq scaffolding *default* hai, *only mode* nahi.
Backward compatibility (khud verify kiya, sirf claim nahi): purane
cached answers (feature se pehle cache hue, `hint`/`guiding_question`
keys hi nahi) aur `not_found` grounding (manually construct hoti hai,
AI call se nahi guzarti) — dono cases mein `has_scaffold` False ban
jata hai, seedha full answer dikhta hai, khaali scaffold screen nahi.
`TutorAnswer(**old_cached_dict)` khud chala kar confirm kiya crash nahi
hota.
Verified: `tests/test_question_log_store.py::TestRevealTracking` (3
naye tests — row id return hona, `mark_revealed` sirf targeted row
update kare, `None` ke sath safe rahe) + `tests/test_core.py::
TestTutorAnswerScaffoldingBackwardCompat` (3 naye tests — purana cache,
`not_found`, naya scaffold-wala answer). Poori suite: 104/104 pass.
`py_compile` + `pyflakes` clean on `app.py`, `core.py`,
`question_log_store.py`.
Open decision jo abhi tak nahi li gayi (dekhein plan doc Section 11,
open decision #1): purana cache clear karna hai ya gradually replace
hone dena hai — abhi gradually-replace default rakha hai (koi cache
invalidation code nahi likha), kyunke backward-compat fallback already
graceful hai. Agar zyada tezi se sab answers scaffold-wale chahiye hon,
cache clear karna ek explicit, chhota alag step hoga.

## Next-phase build — Item 4: image-input capability spike (Aug 2026)

**9. `GeminiGenerationBackend.generate_from_image()` — mistake-diagnosis
mode (build-order item 5, "Check my work") ka shared prerequisite,
dono v0 aur v1 ke liye (plan doc mein correction: v0 bhi isse chahiye,
sirf v1 nahi, jaisa mentor ke original build-order mein tha).**
`generation_backend.py`: `generate()` se `_parse_response()` (LaTeX-
escaping repair + schema parsing) aur `_response_format()` (schema-
wrapping) nikaal kar shared helpers bana diye — `generate_from_image()`
inhe reuse karta hai, koi duplicate logic nahi. Naya method sirf
`GeminiGenerationBackend` par hai, base `GenerationBackend` abstract
class ka hissa NAHI — jaan-boojh kar: `OpenAICompatibleGenerationBackend`
(fallback provider) image input support nahi karta, aur diagnosis mode
ise use hi nahi karega (agar primary Gemini fail ho, clear "abhi
unavailable" message dega, poora system down nahi hoga — plan doc
Section 5).
Technical shape (current, verified Aug 2026 Gemini Interactions API
docs se): inline base64 image data (Files API upload NAHI — student
phone-photo jaisi chhoti, ek-baar-use hone wali image ke liye overkill
hai), `input` ek list `[{"type": "text", "text": ...}, {"type": "image",
"data": <base64>, "mime_type": ...}]`.
Genuinely khula sawaal (docs ne explicitly confirm nahi kiya):
structured JSON output (`response_format`) multimodal input ke saath
reliably combine hota hai ya nahi — dono cheezein docs ke ALAG examples
mein hain, saath kabhi nahi dikhayi gayin. Isliye ye abhi "SPIKE" hai.
Naya manual smoke-test script: `verify_image_input.py` (existing
`verify_turso_connection.py`/`verify_fallback_provider.py` convention
follow karta hai) — koi image path na diya jaye to khud ek chhoti
synthetic test-image (matplotlib se "2 + 2 = 4") bana leta hai, ya
apni asli photo se test kiya ja sakta hai. Deploy/build-order item 5
se PEHLE ye khud chalayein — is sandbox mein koi Google/Gemini domain
allowed nahi tha, isliye live confirm NAHI ho saka.
Verified: `tests/test_generation_backend.py::
TestGeminiGenerationBackendImageInput` — 6 naye tests (request shape,
base64 encoding round-trips to original bytes, response_format shape
match, client-rotation-on-failure same as text `generate()`, all-
clients-fail raises, LaTeX-escaping repair applies same way). Poori
suite: 110/110 pass. `py_compile` + `pyflakes` clean. Synthetic test-
image generation (matplotlib path) khud chala kar confirm kiya —
valid PNG banta hai.

**SPIKE RESULT — LIVE CONFIRMED (16 Aug 2026):** Sohaib ne
`verify_image_input.py` ek real handwritten notes ki photo ke sath
chalaya — real Gemini API call, is sandbox ke bahar. Result:
structured JSON output multimodal image input ke sath reliably
combine hua. Description genuinely specific/accurate thi (epsilon-N
notation, convergent/divergent sequences, ek chhota graph — real page
ka content, generic/hallucinated jawab nahi). **Spike band, khula
sawaal band — build-order item 5 (diagnosis v0) is confidence ke sath
build kiya ja sakta hai.**

## Next-phase build — Item 5: mistake diagnosis v0 (Aug 2026)

**10. "Check your final answer" — student ek EXISTING answered turn
(grounding="adapted_by_ai", computation_result set) ke neeche apna
final answer photograph karta hai, system usse compare karta hai
already-computed correct result se. Design (a) jaisa plan doc mein
tha — standalone cold-upload nahi.**

`core.py`: `DiagnosisTranscription` (transcribed_answer,
could_read_clearly) — deliberately NARROW schema, vision call sirf
transcribe karta hai, khud diagnose/hint nahi karta. Alag
`DIAGNOSIS_SYSTEM_INSTRUCTION` (SYSTEM_INSTRUCTION se bilkul separate)
taake model "helpfully" solve karne ki koshish na kare, sirf jo likha
hai wahi transcribe kare.

**Comparison — koi naya function nahi likha:** `verify_computation()`
already `diff = simplify(lhs - rhs)` karta hai — isi ko
`verify_computation(student_transcribed, correct_result)` ke tor par
call kiya, jo "kya dono equal hain" ke liye bhi utna hi sahi kaam
karta hai jitna "expression == result" ke liye (khud verify kiya —
constant-vs-constant, symbolic-vs-symbolic, alag forms, sab cases).

**Mismatch guidance — research-backed decision:** naya hint AI se
mangwane ke bajaye, us TURN ka pehle-se-mojood `hint`/`guiding_question`
(Section 3) re-surface kiya. Wajah: mentor ki Aug 15 research find —
sirf mistake identify karna perceived-helpfulness ko NEGATIVE affect
karta hai, guidance ke saath pair karna POSITIVE. v0 ke paas beshak
sirf final-answer context hai (poora kaam nahi dekha), isliye naya
hint generate karwana kam-reliable hota — existing hint reuse karna
zyada sound hai.

**Real Streamlit bug pehle hi pakda gaya (ship se pehle, review mein
nahi):** `st.file_uploader` poora script rerun hone ke bawajood SAME
file object return karta rehta hai jab tak widget change na ho — is
guard ke bina, koi bhi UNRELATED click app mein kahin bhi ek nayi
(billed) diagnosis API call AUR ek duplicate DB log row bana deta,
usi upload ke liye baar baar. Isi CLASS ka bug jo "Change name" mein
tha (16 Aug). Fix: `session_helpers.is_new_diagnosis_upload()` —
turn ke `diag_processed_file_id` se compare karta hai, tested.

Naye modules (`session_helpers.py`/`image_helpers.py` jaisa pattern —
Streamlit-independent, plain pytest se testable):
- `image_helpers.py::resize_image_for_upload()` — student phone
  photos (10+ MB tak) resize karta hai (max 1600px width, JPEG q80)
  upload se pehle, cost/speed ke liye.
- `session_helpers.py::is_new_diagnosis_upload()` — upar wala guard.

`app.py`: `diagnose_answer()` (`generate_answer()` jaisa retry+timeout
pattern, lekin FALLBACK provider NAHI use karta — jaan-boojh kar,
AgentRouter image input support nahi karta), `show_diagnosis_check()`
(poora UI flow — upload, resize, transcribe, compare, log, display),
alag `DIAGNOSIS_RATE_LIMIT=4` (60s window) — diagnosis calls text Q&A
se bhaari hain (multimodal tokens) AUR kabhi cache-hit nahi hote (har
photo unique hai). `log_question()` wrapper mein naya `mode` param
add kiya (`"question"` default — koi purana call-site nahi tuta).

`requirements.txt`: `pillow==12.1.1` explicitly pin kiya — pehle sirf
matplotlib ki transitive dependency thi, ab seedha import ho raha hai.

Verified: `tests/test_image_helpers.py` (5 tests — resize/no-upscale/
boundary/PNG-transparency/valid-JPEG-output, real PIL operations, koi
mocking nahi), `tests/test_session_helpers.py::TestIsNewDiagnosisUpload`
(4 tests — same-file-not-reprocessed sabse important), `tests/
test_core.py::TestVerifyComputationForDiagnosisReuse` (6 tests — reuse
pattern explicitly protect karte hain, khaaskar constant-vs-constant
jo pehle kam exercise hota tha). Poori suite: 125/125 pass. `py_compile`
+ `pyflakes` clean on `app.py`, `core.py`, `image_helpers.py`,
`session_helpers.py`.

Scope note (jaan-boojh kar): dashboard.py mein diagnosis_v0 rows ko
alag se dikhane wala koi UI nahi — raw data table mein `mode` column
ke zariye visible hain, lekin dedicated view build-order item 6
(per-student mastery dashboard) ka hissa hai, is turn ka nahi.

## Next-phase build — Item 6: per-student mastery dashboard (Aug 2026)

**11. `dashboard.py` mein naya "Per-student view" section — student
selector, questions asked, photo answer-checks, hint-engagement %,
diagnosis match rate, struggle-topics. Sath hi ek latent bug fix jo
mentor ne review mein pehle hi flag kar diya tha.**

**Latent bug fix (mentor ne 16 Aug ko explicitly warn kiya tha) —
existing sections bhi affected thay, sirf naya tab nahi:** `verified`
column ka meaning `mode` ke hisaab se badalta hai (`"question"` mode
mein "AI ne apna computation khud verify kiya," `"diagnosis_v0"` mode
mein "student ka answer match hua"). Dashboard ka **existing** "Answer
grounding & verification" section `grounding == "adapted_by_ai"` se
filter karta tha, `mode` se nahi — matlab diagnosis_v0 rows (jo design
ke mutabiq ORIGINAL turn ka grounding reuse karti hain) is filter mein
already aa rahi thi, aur combined "verified %" ko silently corrupt kar
rahi thi. Yehi issue topic-heatmap (double-counting), time-trend, gap-
alert, aur cache/repeat-rate sections mein bhi tha (sab reused fields
par depend karte hain). Fix: course-filter ke turant baad ek
`question_df`/`diagnosis_df` split — `df["mode"].fillna("question")`
(purani, pre-migration rows ko "question" treat karte hain, diagnosis
mode unse pehle exist hi nahi karta tha) phir `mode` se split. Sections
1-5 (existing) ab `question_df` use karte hain, `df` nahi.

**Naya schema addition, is turn discover hua:** `had_scaffold INTEGER`
column — Section 1 ka wahi idempotent-migration pattern reuse kiya
(`_MIGRATIONS` list mein ek aur statement). Wajah: `used_full_reveal`
akela ye distinguish nahi kar sakta ke "student ne scaffold skip kiya"
vs "scaffold available hi nahi tha" (app.py `used_full_reveal =
(always_full or not has_scaffold)` compute karta hai — has_scaffold
False hone par used_full_reveal FORCE True hota hai). Dashboard ka
engagement-metric (evaluation-trap research se, Section 10.2) accurate
nahi ban sakta tha is ambiguity ke sath. `app.py` ab `had_scaffold`
explicitly pass karta hai; purani rows (is column se pehle) NULL
rahengi aur engagement-metric se automatically exclude hoti hain
(guess nahi karte, honestly exclude karte hain).

Per-student section design: `student_id` NULL rows "(name not given)"
bucket mein group hoti hain (crash/silent-drop nahi). Engagement %
sirf `had_scaffold == 1` rows par compute hota hai. Diagnosis match
rate ALAG metric hai, kabhi combine nahi hota AI-self-verification
wale % se. Struggle-topics: rephrased-repeats + diagnosis mismatches
dono se, per-student.

Verified: `tests/test_question_log_store.py::TestHadScaffold` (2 naye
tests) + updated migration test. Poori suite: 127/127 pass. `dashboard.py`
khud unit-tested nahi hai (app.py jaisa top-level Streamlit script) —
iski core pandas logic (mode-split, NULL handling, engagement-calc,
struggle-topics) ek realistic synthetic 6-row dataset (2 students, mixed
modes, NULL student_id, NULL had_scaffold) ke against manually run kar
ke verify ki — sab assertions pass hue. `py_compile` + `pyflakes` clean
on `dashboard.py`, `app.py`, `question_log_store.py`.