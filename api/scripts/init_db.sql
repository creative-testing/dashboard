-- Script d'initialisation Postgres
-- Exécuté automatiquement au premier démarrage du container

-- Créer l'extension pgcrypto pour chiffrement (si pas déjà présente)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Créer l'extension pour UUID
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Note: Les tables seront créées par Alembic migrations
-- Ce script prépare juste les extensions nécessaires

-- Log pour confirmation
DO $$
BEGIN
    RAISE NOTICE 'Database initialized with pgcrypto and uuid-ossp extensions';
END $$;
