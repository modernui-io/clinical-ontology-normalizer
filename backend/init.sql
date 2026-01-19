-- Clinical Ontology Normalizer - Database Initialization
-- This script runs automatically when the PostgreSQL container starts for the first time

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- Create schemas for organization
CREATE SCHEMA IF NOT EXISTS omop;
CREATE SCHEMA IF NOT EXISTS vocabularies;
CREATE SCHEMA IF NOT EXISTS audit;

-- Grant permissions
GRANT ALL PRIVILEGES ON SCHEMA omop TO postgres;
GRANT ALL PRIVILEGES ON SCHEMA vocabularies TO postgres;
GRANT ALL PRIVILEGES ON SCHEMA audit TO postgres;

-- Create vocabulary tables in the vocabularies schema
CREATE TABLE IF NOT EXISTS vocabularies.concept (
    concept_id BIGINT PRIMARY KEY,
    concept_name VARCHAR(500) NOT NULL,
    domain_id VARCHAR(50),
    vocabulary_id VARCHAR(50) NOT NULL,
    concept_class_id VARCHAR(50),
    standard_concept VARCHAR(1),
    concept_code VARCHAR(100) NOT NULL,
    valid_start_date DATE,
    valid_end_date DATE,
    invalid_reason VARCHAR(1)
);

CREATE TABLE IF NOT EXISTS vocabularies.concept_relationship (
    concept_id_1 BIGINT NOT NULL,
    concept_id_2 BIGINT NOT NULL,
    relationship_id VARCHAR(50) NOT NULL,
    valid_start_date DATE,
    valid_end_date DATE,
    invalid_reason VARCHAR(1),
    PRIMARY KEY (concept_id_1, concept_id_2, relationship_id)
);

CREATE TABLE IF NOT EXISTS vocabularies.concept_synonym (
    concept_id BIGINT NOT NULL,
    concept_synonym_name VARCHAR(1000) NOT NULL,
    language_concept_id BIGINT
);

CREATE TABLE IF NOT EXISTS vocabularies.concept_ancestor (
    ancestor_concept_id BIGINT NOT NULL,
    descendant_concept_id BIGINT NOT NULL,
    min_levels_of_separation INT,
    max_levels_of_separation INT,
    PRIMARY KEY (ancestor_concept_id, descendant_concept_id)
);

-- Create indexes for vocabulary tables
CREATE INDEX IF NOT EXISTS idx_concept_code ON vocabularies.concept(concept_code);
CREATE INDEX IF NOT EXISTS idx_concept_vocabulary ON vocabularies.concept(vocabulary_id);
CREATE INDEX IF NOT EXISTS idx_concept_domain ON vocabularies.concept(domain_id);
CREATE INDEX IF NOT EXISTS idx_concept_name_trgm ON vocabularies.concept USING gin(concept_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_concept_synonym_name_trgm ON vocabularies.concept_synonym USING gin(concept_synonym_name gin_trgm_ops);

-- Create audit logging table
CREATE TABLE IF NOT EXISTS audit.activity_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255),
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100),
    resource_id VARCHAR(255),
    details JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_user ON audit.activity_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit.activity_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit.activity_log(created_at);

-- Create function for updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Print completion message
DO $$
BEGIN
    RAISE NOTICE 'Database initialization complete.';
    RAISE NOTICE 'Schemas created: omop, vocabularies, audit';
    RAISE NOTICE 'Extensions enabled: uuid-ossp, pg_trgm, btree_gist';
END $$;
