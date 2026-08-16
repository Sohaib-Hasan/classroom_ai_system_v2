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
