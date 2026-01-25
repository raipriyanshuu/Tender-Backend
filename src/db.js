import pg from 'pg';
import dotenv from 'dotenv';

dotenv.config();

const { Pool } = pg;

const resolveSslOption = () => {
  const databaseUrl = process.env.DATABASE_URL || '';
  const sslModeDisabled = databaseUrl.includes('sslmode=disable');
  const isLocalhost =
    databaseUrl.includes('localhost') || databaseUrl.includes('127.0.0.1');

  if (sslModeDisabled || isLocalhost) {
    return false;
  }
  if (process.env.DATABASE_SSL === 'true') {
    return { rejectUnauthorized: false };
  }
  return { rejectUnauthorized: false }; // Default for Supabase-style connections
};

// Create PostgreSQL connection pool
const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: resolveSslOption(),
  max: 20, // Maximum number of clients in the pool
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000,
});

// Test database connection
pool.on('connect', () => {
  console.log('✅ Connected to PostgreSQL database');
});

pool.on('error', (err) => {
  console.error('❌ Unexpected error on idle client', err);
  process.exit(-1);
});

// Helper function to execute queries
export const query = async (text, params) => {
  const start = Date.now();
  try {
    const res = await pool.query(text, params);
    const duration = Date.now() - start;
    if (process.env.NODE_ENV === 'development') {
      const truncatedText = text.length > 100 ? text.substring(0, 100) + '...' : text;
      console.log('Executed query', { text: truncatedText, duration, rows: res.rowCount });
    } else {
      console.log('Executed query', { duration, rows: res.rowCount });
    }
    return res;
  } catch (error) {
    console.error('Database query error:', error.message);
    throw error;
  }
};

// Helper function to get a client from the pool
export const getClient = () => pool.connect();

export default pool;
