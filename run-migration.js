import pg from 'pg';
import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';
import dotenv from 'dotenv';

dotenv.config();

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const pool = new pg.Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: false, // Set to true if using SSL
});

async function runMigration(migrationFile) {
  const client = await pool.connect();
  try {
    const sqlPath = path.isAbsolute(migrationFile) 
      ? migrationFile 
      : path.join(__dirname, 'migrations', migrationFile);
    
    console.log(`\n📄 Reading migration: ${sqlPath}`);
    const sql = await fs.readFile(sqlPath, 'utf-8');
    
    console.log('🚀 Executing migration...');
    await client.query(sql);
    
    console.log('✅ Migration completed successfully!\n');
  } catch (error) {
    console.error('❌ Migration failed:', error.message);
    throw error;
  } finally {
    client.release();
  }
}

async function verifySchema() {
  const client = await pool.connect();
  try {
    console.log('\n🔍 Verifying database schema...\n');
    
    // Check tables
    const tablesResult = await client.query(`
      SELECT tablename 
      FROM pg_tables 
      WHERE schemaname = 'public'
      ORDER BY tablename
    `);
    
    console.log('📊 TABLES:');
    tablesResult.rows.forEach(row => console.log(`  ✓ ${row.tablename}`));
    
    // Check views
    const viewsResult = await client.query(`
      SELECT viewname 
      FROM pg_views 
      WHERE schemaname = 'public'
      ORDER BY viewname
    `);
    
    console.log('\n👁️  VIEWS:');
    if (viewsResult.rows.length === 0) {
      console.log('  (none)');
    } else {
      viewsResult.rows.forEach(row => console.log(`  ✓ ${row.viewname}`));
    }
    
    // Expected schema
    const expectedTables = ['file_extractions', 'run_summaries', 'processing_jobs', 'system_alerts'];
    const expectedViews = [
      'batch_status_summary', 
      'failed_files_report', 
      'processing_performance_metrics',
      'active_batches_monitor',
      'batch_history_summary',
      'error_summary_by_type'
    ];
    
    const actualTables = tablesResult.rows.map(r => r.tablename);
    const actualViews = viewsResult.rows.map(r => r.viewname);
    
    const missingTables = expectedTables.filter(t => !actualTables.includes(t));
    const missingViews = expectedViews.filter(v => !actualViews.includes(v));
    
    if (missingTables.length > 0 || missingViews.length > 0) {
      console.log('\n⚠️  MISSING SCHEMA OBJECTS:');
      if (missingTables.length > 0) {
        console.log('  Missing tables:', missingTables.join(', '));
      }
      if (missingViews.length > 0) {
        console.log('  Missing views:', missingViews.join(', '));
      }
      return false;
    } else {
      console.log('\n✅ All expected tables and views are present!\n');
      return true;
    }
  } finally {
    client.release();
  }
}

async function main() {
  const args = process.argv.slice(2);
  
  if (args.length === 0) {
    console.log('Usage: node run-migration.js <migration-file>');
    console.log('   or: node run-migration.js verify');
    console.log('\nExample: node run-migration.js 001_002_003_005_consolidated_idempotent.sql');
    process.exit(1);
  }
  
  if (args[0] === 'verify') {
    await verifySchema();
  } else {
    await runMigration(args[0]);
    console.log('Running verification...');
    await verifySchema();
  }
  
  await pool.end();
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
