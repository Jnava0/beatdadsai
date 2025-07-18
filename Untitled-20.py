# File: backend/database.py
# Author: Gemini
# Date: July 17, 2025
# Description: Manages the PostgreSQL database connection and schema.
# This version adds support for storing agent tool permissions.

import psycopg2
from psycopg2 import pool
from psycopg2.extras import Json
import yaml
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    """
    A singleton class to manage a PostgreSQL connection pool.
    """
    _instance = None
    _connection_pool = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config_path="config.yaml"):
        if self._connection_pool is None:
            logger.info("Initializing DatabaseManager and connection pool.")
            try:
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)['database']
                
                self._connection_pool = psycopg2.pool.SimpleConnectionPool(
                    minconn=1, maxconn=10,
                    host=config['host'], port=config['port'],
                    user=config['user'], password=config['password'], dbname=config['dbname']
                )
                logger.info("Database connection pool created successfully.")
            except Exception as e:
                logger.critical(f"FATAL: Could not create database connection pool: {e}", exc_info=True)
                raise

    def get_connection(self):
        return self._connection_pool.getconn()

    def release_connection(self, conn):
        self._connection_pool.putconn(conn)

    def close_all_connections(self):
        if self._connection_pool:
            logger.info("Closing all database connections.")
            self._connection_pool.closeall()
            self._connection_pool = None

    def execute_query(self, query, params=None, fetch=None):
        conn = None
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute(query, params)
                if fetch == 'one': return cur.fetchone()
                if fetch == 'all': return cur.fetchall()
                conn.commit()
        except Exception as e:
            logger.error(f"Database query failed: {e}", exc_info=True)
            if conn: conn.rollback()
            raise
        finally:
            if conn: self.release_connection(conn)

def init_db():
    """
    Ensures the database schema is up-to-date.
    Creates the 'agents' table and adds the 'allowed_tools' column if they don't exist.
    """
    logger.info("Initializing the database schema...")
    db_manager = DatabaseManager()
    
    # Define the table structure
    create_table_query = """
    CREATE TABLE IF NOT EXISTS agents (
        agent_id UUID PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        role TEXT NOT NULL,
        model_id VARCHAR(255) NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """
    
    # Define the column to add for tool permissions
    # Using JSONB is highly flexible for storing lists of strings.
    add_column_query = """
    ALTER TABLE agents
    ADD COLUMN IF NOT EXISTS allowed_tools JSONB DEFAULT '[]'::jsonb;
    """
    
    try:
        db_manager.execute_query(create_table_query)
        db_manager.execute_query(add_column_query)
        logger.info("'agents' table is up-to-date.")
    except Exception as e:
        logger.critical(f"Could not initialize the database schema: {e}")
        exit(1)

if __name__ == '__main__':
    from logging_config import setup_logging
    setup_logging()
    init_db()
    print("Database initialization script finished.")
