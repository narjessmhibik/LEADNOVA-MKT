-- Génère ~20 opportunités de démonstration liées aux leads existants.
-- Répartit les deals dans les 5 étapes du pipeline avec des valeurs réalistes.
-- Usage : psql -U leadpilot -d leadpilot_db -f backend/scripts/seed_deals.sql

WITH picked AS (
  SELECT id, company,
         row_number() OVER (ORDER BY lead_score DESC NULLS LAST) AS rn
  FROM leads
  WHERE company IS NOT NULL AND company <> ''
  ORDER BY lead_score DESC NULLS LAST
  LIMIT 20
)
INSERT INTO opportunities (title, company, lead_id, value, stage, probability, risk, expected_close, created_at)
SELECT
  'Projet ' || company,
  company,
  id,
  (5000 + (random() * 75000))::int,
  (ARRAY['Prospection','Qualification','Proposition','Négociation','Gagné'])[1 + (rn % 5)],
  (ARRAY[20,40,60,80,100])[1 + (rn % 5)],
  (rn % 7 = 0),
  NOW() + ((10 + random() * 80) * interval '1 day'),
  NOW() - ((random() * 40) * interval '1 day')
FROM picked;
