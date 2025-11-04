"""
Database Manager for Fund Leader Tracker
Handles SQLite database operations for storing fund data and analysis results
"""
import sqlite3
import os
import logging
from datetime import datetime
from utils import get_timestamp

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database operations for the Fund Leader Tracker"""

    def __init__(self, db_path='data/fund_leaders.db'):
        """Initialize database connection"""
        self.db_path = db_path
        self.conn = None
        self._ensure_database_directory()
        self._initialize_database()

    def _ensure_database_directory(self):
        """Ensure the database directory exists"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
            logger.info(f"Created database directory: {db_dir}")

    def connect(self):
        """Establish database connection"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            logger.info(f"Connected to database: {self.db_path}")
            return self.conn
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")
            raise

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    def _initialize_database(self):
        """Create database tables if they don't exist"""
        self.connect()

        create_tables_sql = """
        -- Sectors table
        CREATE TABLE IF NOT EXISTS sectors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            keywords TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        -- Funds table
        CREATE TABLE IF NOT EXISTS funds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT UNIQUE NOT NULL,
            name TEXT,
            sector_id INTEGER,
            performance_3year REAL,
            aum REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sector_id) REFERENCES sectors(id)
        );

        -- Holdings table
        CREATE TABLE IF NOT EXISTS holdings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fund_id INTEGER NOT NULL,
            company_symbol TEXT NOT NULL,
            company_name TEXT,
            weight REAL,
            shares INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (fund_id) REFERENCES funds(id)
        );

        -- Industry Leaders table
        CREATE TABLE IF NOT EXISTS industry_leaders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sector_id INTEGER NOT NULL,
            company_symbol TEXT NOT NULL,
            company_name TEXT,
            times_held INTEGER DEFAULT 1,
            total_weight REAL,
            avg_weight REAL,
            analysis_date TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sector_id) REFERENCES sectors(id)
        );

        -- Analysis Runs table
        CREATE TABLE IF NOT EXISTS analysis_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date TEXT NOT NULL,
            sectors_analyzed INTEGER,
            funds_analyzed INTEGER,
            leaders_found INTEGER,
            status TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        -- Create indexes for better performance
        CREATE INDEX IF NOT EXISTS idx_funds_sector ON funds(sector_id);
        CREATE INDEX IF NOT EXISTS idx_holdings_fund ON holdings(fund_id);
        CREATE INDEX IF NOT EXISTS idx_holdings_symbol ON holdings(company_symbol);
        CREATE INDEX IF NOT EXISTS idx_leaders_sector ON industry_leaders(sector_id);
        """

        try:
            self.conn.executescript(create_tables_sql)
            self.conn.commit()
            logger.info("Database tables initialized successfully")
        except sqlite3.Error as e:
            logger.error(f"Error initializing database: {e}")
            raise

    def save_sector(self, name, keywords):
        """Save or update sector information"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO sectors (name, keywords)
                VALUES (?, ?)
                ON CONFLICT(name) DO UPDATE SET keywords = excluded.keywords
            """, (name, ','.join(keywords)))
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"Error saving sector {name}: {e}")
            return None

    def save_fund(self, symbol, name, sector_name, performance_3year=None, aum=None):
        """Save or update fund information"""
        try:
            # Get sector_id
            cursor = self.conn.cursor()
            cursor.execute("SELECT id FROM sectors WHERE name = ?", (sector_name,))
            sector_row = cursor.fetchone()

            if not sector_row:
                sector_id = self.save_sector(sector_name, [])
            else:
                sector_id = sector_row[0]

            cursor.execute("""
                INSERT INTO funds (symbol, name, sector_id, performance_3year, aum, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    name = excluded.name,
                    sector_id = excluded.sector_id,
                    performance_3year = excluded.performance_3year,
                    aum = excluded.aum,
                    updated_at = excluded.updated_at
            """, (symbol, name, sector_id, performance_3year, aum, get_timestamp()))
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"Error saving fund {symbol}: {e}")
            return None

    def save_holding(self, fund_symbol, company_symbol, company_name, weight, shares=None):
        """Save holding information"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT id FROM funds WHERE symbol = ?", (fund_symbol,))
            fund_row = cursor.fetchone()

            if not fund_row:
                logger.warning(f"Fund {fund_symbol} not found in database")
                return None

            fund_id = fund_row[0]
            cursor.execute("""
                INSERT INTO holdings (fund_id, company_symbol, company_name, weight, shares)
                VALUES (?, ?, ?, ?, ?)
            """, (fund_id, company_symbol, company_name, weight, shares))
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"Error saving holding {company_symbol} for fund {fund_symbol}: {e}")
            return None

    def save_leader(self, sector_name, company_symbol, company_name, times_held, total_weight, avg_weight):
        """Save industry leader information"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT id FROM sectors WHERE name = ?", (sector_name,))
            sector_row = cursor.fetchone()

            if not sector_row:
                logger.warning(f"Sector {sector_name} not found")
                return None

            sector_id = sector_row[0]
            analysis_date = datetime.now().strftime('%Y-%m-%d')

            cursor.execute("""
                INSERT INTO industry_leaders
                (sector_id, company_symbol, company_name, times_held, total_weight, avg_weight, analysis_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (sector_id, company_symbol, company_name, times_held, total_weight, avg_weight, analysis_date))
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"Error saving leader {company_symbol}: {e}")
            return None

    def get_leaders_by_sector(self, sector_name, limit=10):
        """Retrieve top leaders for a specific sector"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT il.company_symbol, il.company_name, il.times_held,
                       il.total_weight, il.avg_weight, il.analysis_date
                FROM industry_leaders il
                JOIN sectors s ON il.sector_id = s.id
                WHERE s.name = ?
                ORDER BY il.times_held DESC, il.avg_weight DESC
                LIMIT ?
            """, (sector_name, limit))
            return cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Error retrieving leaders for {sector_name}: {e}")
            return []

    def get_all_leaders(self, limit=50):
        """Retrieve all industry leaders across all sectors"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT s.name as sector, il.company_symbol, il.company_name,
                       il.times_held, il.total_weight, il.avg_weight, il.analysis_date
                FROM industry_leaders il
                JOIN sectors s ON il.sector_id = s.id
                ORDER BY s.name, il.times_held DESC, il.avg_weight DESC
                LIMIT ?
            """, (limit,))
            return cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Error retrieving all leaders: {e}")
            return []

    def save_analysis_run(self, sectors_analyzed, funds_analyzed, leaders_found, status='completed', notes=''):
        """Save analysis run metadata"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO analysis_runs
                (run_date, sectors_analyzed, funds_analyzed, leaders_found, status, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (get_timestamp(), sectors_analyzed, funds_analyzed, leaders_found, status, notes))
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"Error saving analysis run: {e}")
            return None

    def get_latest_leaders_by_sector(self):
        """Get the most recent leader for each sector (from previous analysis)"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT s.name as sector, il.company_symbol, il.company_name,
                       il.times_held, il.total_weight, il.avg_weight, il.analysis_date
                FROM industry_leaders il
                JOIN sectors s ON il.sector_id = s.id
                WHERE il.id IN (
                    SELECT MAX(id)
                    FROM industry_leaders
                    GROUP BY sector_id
                )
                ORDER BY s.name
            """)
            results = cursor.fetchall()

            # Convert to dictionary for easy lookup
            leaders_dict = {}
            for row in results:
                leaders_dict[row['sector']] = {
                    'symbol': row['company_symbol'],
                    'name': row['company_name'],
                    'times_held': row['times_held'],
                    'total_weight': row['total_weight'],
                    'avg_weight': row['avg_weight'],
                    'analysis_date': row['analysis_date']
                }

            return leaders_dict
        except sqlite3.Error as e:
            logger.error(f"Error retrieving latest leaders: {e}")
            return {}

    def clear_old_data(self, days=30):
        """Clear old analysis data"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                DELETE FROM industry_leaders
                WHERE created_at < datetime('now', '-' || ? || ' days')
            """, (days,))
            deleted = cursor.rowcount
            self.conn.commit()
            logger.info(f"Cleared {deleted} old leader records")
            return deleted
        except sqlite3.Error as e:
            logger.error(f"Error clearing old data: {e}")
            return 0
