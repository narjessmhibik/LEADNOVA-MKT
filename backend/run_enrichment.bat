@echo off
set DATABASE_URL=postgresql://leadpilot:secret@localhost:5432/leadpilot_db
set HUNTER_API_KEY=e8fdb29691fc15ce8a8ff90d0bfcabadffe3682e
set GROQ_API_KEY=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
cd C:\Users\Narjess\Downloads\vfinal\leadpilot\backend
python -m app.enrichment 5915
