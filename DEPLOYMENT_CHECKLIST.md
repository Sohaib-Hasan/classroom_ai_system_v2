
## Deployment prep (Aug 2026) — mentor ki recommendation par: item 7 se
## pehle, sab kuch live deploy karo

Mentor ka 16 Aug ka verdict: Sections 1-6 + Items 4-6 sab **local
sandbox** tak confirmed hain, koi bhi cheez real Turso/Streamlit Cloud
ke against kabhi nahi chali. Item 7 (diagnosis v1) shuru karne se
pehle, poora system deploy karo, kam se kam ek hafta real students ke
sath chalne do, phir data-driven decision lo (khaas kar: diagnosis-mode
adoption genuinely kitni hai — jo sirf real usage se pata chalega,
kisi sandbox se nahi).

**12. `verify_turso_migration.py` (naya) — Section 1 se pending
gap band kiya.** Kabhi live confirm nahi hua tha ke Turso ka "duplicate
column" error-wording sandbox ke SQLite se match karta hai —
`_apply_migrations()` sirf expected error-strings ignore karta hai,
baaki sab raise karta hai, isliye agar wording mismatch ho to production
mein crash ho sakta tha jahan sandbox mein pass hua tha. Ye script
explicitly ek OLD-schema table banata hai (bilkul wahi jo
`tests/test_question_log_store.py::TestSchemaMigration` sandbox mein
simulate karta hai), phir real Turso ke against migration chalata hai —
recommend karta hai pehle ek scratch/test Turso DB par chalayein,
production par nahi.

**13. `db_connection.py` docstring fix — chhota lekin real
inconsistency mila.** Docstring ka Turso-setup example
`TURSO_DATABASE_URL = "libsql://your-db-name.turso.io"` dikhata tha,
jabke `README.md` explicitly (aur sahi wajah ke sath) `https://` use
karne ko kehta hai — `libsql://` (WebSocket) Streamlit Cloud jaisi
sandboxed environment mein handshake fail kar sakta hai
(`WSServerHandshakeError`), jo README mein already documented tha lekin
docstring mein reflect nahi hua tha. Agar koi docstring literally
follow karta, wahi bug reproduce kar deta jo README specifically avoid
karne ke liye likha gaya tha. Fix kiya, README ko point kiya.

**14. `DEPLOYMENT_CHECKLIST.md` (naya)** — poora, ordered checklist:
Turso setup + scratch-DB migration verification, Streamlit Cloud
Secrets (dono apps), deploy sequence, post-deploy smoke tests (student
app + dashboard, step-by-step), trial-week monitoring, aur item-7
decision criteria (data-driven — diagnosis-mode adoption numbers
dekhein, guess na karein).

Verified: `verify_turso_migration.py` aur `DEPLOYMENT_CHECKLIST.md` khud
network/deployment nahi maangte is turn mein banane ke liye, lekin
`py_compile` + `pyflakes` clean hain. Poori suite abhi bhi 127/127 pass
(koi test-affecting code nahi badla, sirf docs + ek naya standalone
script).