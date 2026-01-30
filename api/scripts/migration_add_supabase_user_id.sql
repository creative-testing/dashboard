-- Migration: Add supabase_user_id column to users table
-- This links Insights users to Supabase Auth users for unified authentication
-- Run this BEFORE deploying the new code

-- Add the column (nullable to allow existing users without Supabase link)
ALTER TABLE users
ADD COLUMN IF NOT EXISTS supabase_user_id VARCHAR(36) UNIQUE;

-- Create index for fast lookups by supabase_user_id
CREATE INDEX IF NOT EXISTS ix_users_supabase_user_id ON users(supabase_user_id);

-- Verify the column was added
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'users' AND column_name = 'supabase_user_id';
