"""Database Manager for Fund Leader Tracker."""
import logging
import os
import sqlite3
from datetime import datetime

from utils import get_timestamp

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self, db_path='data/fund_leaders.db'):
        self.db_path = db_path
        self.conn = None
        self._ensure_database_directory()
        self._initialize_database()
        self._run_migrations()

    def _ensure_database_directory(self):
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
            logger.info("Created database directory: %s", db_dir)

    def connect(self):
        if self.conn:
            return self.conn
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        return self.conn

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def _initialize_database(self):
        self.connect()
        create_tables_sql = """
        CREATE TABLE IF NOT EXISTS sectors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            keywords TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
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
        CREATE TABLE IF NOT EXISTS industry_leaders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sector_id INTEGER NOT NULL,
            company_symbol TEXT NOT NULL,
            company_name TEXT,
            times_held INTEGER DEFAULT 1,
            total_weight REAL,
            avg_weight REAL,
            prevalence REAL,
            analysis_date TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sector_id) REFERENCES sectors(id)
        );
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
        CREATE TABLE IF NOT EXISTS tracked_funds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sector_name TEXT NOT NULL,
            fund_symbol TEXT NOT NULL,
            fund_name TEXT,
            performance_3year REAL,
            rank_in_sector INTEGER,
            selection_source TEXT,
            selection_score REAL,
            initialized_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(sector_name, fund_symbol)
        );
        CREATE INDEX IF NOT EXISTS idx_funds_sector ON funds(sector_id);
        CREATE INDEX IF NOT EXISTS idx_holdings_fund ON holdings(fund_id);
        CREATE INDEX IF NOT EXISTS idx_holdings_symbol ON holdings(company_symbol);
        CREATE INDEX IF NOT EXISTS idx_leaders_sector ON industry_leaders(sector_id);
        CREATE INDEX IF NOT EXISTS idx_tracked_funds_sector ON tracked_funds(sector_name);
        """
        self.conn.executescript(create_tables_sql)
        self.conn.commit()

    def _run_migrations(self):
        cursor = self.conn.cursor()
        cursor.execute("PRAGMA table_info(tracked_funds)")
        tracked_columns = {row['name'] for row in cursor.fetchall()}
        if 'selection_source' not in tracked_columns:
            self.conn.execute("ALTER TABLE tracked_funds ADD COLUMN selection_source TEXT")
        if 'selection_score' not in tracked_columns:
            self.conn.execute("ALTER TABLE tracked_funds ADD COLUMN selection_score REAL")

        cursor.execute("PRAGMA table_info(industry_leaders)")
        leader_columns = {row['name'] for row in cursor.fetchall()}
        if 'prevalence' not in leader_columns:
            self.conn.execute("ALTER TABLE industry_leaders ADD COLUMN prevalence REAL")
        self.conn.commit()

    def save_sector(self, name, keywords):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO sectors (name, keywords)
            VALUES (?, ?)
            ON CONFLICT(name) DO UPDATE SET keywords = excluded.keywords
            """,
            (name, ','.join(keywords)),
        )
        self.conn.commit()
        cursor.execute("SELECT id FROM sectors WHERE name = ?", (name,))
        return cursor.fetchone()[0]

    def save_fund(self, symbol, name, sector_name, performance_3year=None, aum=None):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM sectors WHERE name = ?", (sector_name,))
        sector_row = cursor.fetchone()
        sector_id = sector_row[0] if sector_row else self.save_sector(sector_name, [])
        cursor.execute(
            """
            INSERT INTO funds (symbol, name, sector_id, performance_3year, aum, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                name = excluded.name,
                sector_id = excluded.sector_id,
                performance_3year = COALESCE(excluded.performance_3year, funds.performance_3year),
                aum = COALESCE(excluded.aum, funds.aum),
                updated_at = excluded.updated_at
            """,
            (symbol, name, sector_id, performance_3year, aum, get_timestamp()),
        )
        self.conn.commit()
        cursor.execute("SELECT id FROM funds WHERE symbol = ?", (symbol,))
        return cursor.fetchone()[0]

    def save_holding(self, fund_symbol, company_symbol, company_name, weight, shares=None):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM funds WHERE symbol = ?", (fund_symbol,))
        fund_row = cursor.fetchone()
        if not fund_row:
            logger.warning("Fund %s not found in database", fund_symbol)
            return None
        cursor.execute(
            "INSERT INTO holdings (fund_id, company_symbol, company_name, weight, shares) VALUES (?, ?, ?, ?, ?)",
            (fund_row[0], company_symbol, company_name, weight, shares),
        )
        self.conn.commit()
        return cursor.lastrowid

    def save_leader(self, sector_name, company_symbol, company_name, times_held, total_weight, avg_weight, prevalence=None):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM sectors WHERE name = ?", (sector_name,))
        sector_row = cursor.fetchone()
        if not sector_row:
            logger.warning("Sector %s not found", sector_name)
            return None
        cursor.execute(
            """
            INSERT INTO industry_leaders
            (sector_id, company_symbol, company_name, times_held, total_weight, avg_weight, prevalence, analysis_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (sector_row[0], company_symbol, company_name, times_held, total_weight, avg_weight, prevalence, datetime.now().strftime('%Y-%m-%d')),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_leaders_by_sector(self, sector_name, limit=10):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT il.company_symbol, il.company_name, il.times_held,
                   il.total_weight, il.avg_weight, il.prevalence, il.analysis_date
            FROM industry_leaders il
            JOIN sectors s ON il.sector_id = s.id
            WHERE s.name = ?
            ORDER BY il.analysis_date DESC, il.times_held DESC, il.avg_weight DESC
            LIMIT ?
            """,
            (sector_name, limit),
        )
        return cursor.fetchall()

    def get_all_leaders(self, limit=50):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT s.name as sector, il.company_symbol, il.company_name,
                   il.times_held, il.total_weight, il.avg_weight, il.prevalence, il.analysis_date
            FROM industry_leaders il
            JOIN sectors s ON il.sector_id = s.id
            ORDER BY il.analysis_date DESC, s.name, il.times_held DESC, il.avg_weight DESC
            LIMIT ?
            """,
            (limit,),
        )
        return cursor.fetchall()

    def save_analysis_run(self, sectors_analyzed, funds_analyzed, leaders_found, status='completed', notes=''):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO analysis_runs (run_date, sectors_analyzed, funds_analyzed, leaders_found, status, notes) VALUES (?, ?, ?, ?, ?, ?)",
            (get_timestamp(), sectors_analyzed, funds_analyzed, leaders_found, status, notes),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_latest_leaders_by_sector(self):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT s.name as sector, il.company_symbol, il.company_name,
                   il.times_held, il.total_weight, il.avg_weight, il.prevalence, il.analysis_date
            FROM industry_leaders il
            JOIN sectors s ON il.sector_id = s.id
            WHERE il.id IN (SELECT MAX(id) FROM industry_leaders GROUP BY sector_id)
            ORDER BY s.name
            """
        )
        results = cursor.fetchall()
        return {
            row['sector']: {
                'symbol': row['company_symbol'],
                'name': row['company_name'],
                'times_held': row['times_held'],
                'total_weight': row['total_weight'],
                'avg_weight': row['avg_weight'],
                'prevalence': row['prevalence'],
                'analysis_date': row['analysis_date'],
            }
            for row in results
        }

    def clear_old_data(self, days=30):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM industry_leaders WHERE created_at < datetime('now', '-' || ? || ' days')", (days,))
        deleted = cursor.rowcount
        self.conn.commit()
        return deleted

    def save_tracked_fund(self, sector_name, fund_symbol, fund_name, performance_3year, rank, selection_source=None, selection_score=None):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO tracked_funds (sector_name, fund_symbol, fund_name, performance_3year, rank_in_sector, selection_source, selection_score)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(sector_name, fund_symbol) DO UPDATE SET
                fund_name = excluded.fund_name,
                performance_3year = excluded.performance_3year,
                rank_in_sector = excluded.rank_in_sector,
                selection_source = excluded.selection_source,
                selection_score = excluded.selection_score,
                initialized_at = CURRENT_TIMESTAMP
            """,
            (sector_name, fund_symbol, fund_name, performance_3year, rank, selection_source, selection_score),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_tracked_funds(self, sector_name):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT fund_symbol, fund_name, performance_3year, rank_in_sector, selection_source, selection_score, initialized_at
            FROM tracked_funds
            WHERE sector_name = ?
            ORDER BY rank_in_sector ASC
            """,
            (sector_name,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def has_tracked_funds(self, sector_name):
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM tracked_funds WHERE sector_name = ?", (sector_name,))
        return cursor.fetchone()['count'] > 0

    def clear_tracked_funds(self, sector_name=None):
        cursor = self.conn.cursor()
        if sector_name:
            cursor.execute("DELETE FROM tracked_funds WHERE sector_name = ?", (sector_name,))
        else:
            cursor.execute("DELETE FROM tracked_funds")
        self.conn.commit()
        return cursor.rowcount
