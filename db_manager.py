"""Database Manager for Fund Leader Tracker."""
import json
import logging
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

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
            logger.info('Created database directory: %s', db_dir)

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
        self.conn.executescript(
            """
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
            CREATE TABLE IF NOT EXISTS sector_strategy_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sector_name TEXT NOT NULL,
                review_date TEXT NOT NULL,
                active_symbol TEXT,
                active_name TEXT,
                active_kind TEXT,
                active_avg_weight REAL,
                active_prevalence REAL,
                pending_symbol TEXT,
                pending_name TEXT,
                pending_confirmations INTEGER DEFAULT 0,
                status TEXT,
                last_action TEXT,
                last_action_reason TEXT,
                data_status TEXT,
                sector_freshness_json TEXT,
                evidence_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS strategy_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                review_date TEXT NOT NULL,
                run_timestamp TEXT NOT NULL,
                summary_json TEXT,
                portfolio_json TEXT,
                report_text_path TEXT,
                report_json_path TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_funds_sector ON funds(sector_id);
            CREATE INDEX IF NOT EXISTS idx_holdings_fund ON holdings(fund_id);
            CREATE INDEX IF NOT EXISTS idx_holdings_symbol ON holdings(company_symbol);
            CREATE INDEX IF NOT EXISTS idx_leaders_sector ON industry_leaders(sector_id);
            CREATE INDEX IF NOT EXISTS idx_tracked_funds_sector ON tracked_funds(sector_name);
            CREATE INDEX IF NOT EXISTS idx_strategy_state_sector_date ON sector_strategy_state(sector_name, review_date);
            """
        )
        self.conn.commit()

    def _run_migrations(self):
        cursor = self.conn.cursor()

        cursor.execute('PRAGMA table_info(tracked_funds)')
        tracked_columns = {row['name'] for row in cursor.fetchall()}
        if 'selection_source' not in tracked_columns:
            self.conn.execute('ALTER TABLE tracked_funds ADD COLUMN selection_source TEXT')
        if 'selection_score' not in tracked_columns:
            self.conn.execute('ALTER TABLE tracked_funds ADD COLUMN selection_score REAL')

        cursor.execute('PRAGMA table_info(industry_leaders)')
        leader_columns = {row['name'] for row in cursor.fetchall()}
        if 'prevalence' not in leader_columns:
            self.conn.execute('ALTER TABLE industry_leaders ADD COLUMN prevalence REAL')

        cursor.execute('PRAGMA table_info(sector_strategy_state)')
        strategy_columns = {row['name'] for row in cursor.fetchall()}
        if 'sector_freshness_json' not in strategy_columns:
            self.conn.execute('ALTER TABLE sector_strategy_state ADD COLUMN sector_freshness_json TEXT')

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
        cursor.execute('SELECT id FROM sectors WHERE name = ?', (name,))
        return cursor.fetchone()[0]

    def save_fund(self, symbol, name, sector_name, performance_3year=None, aum=None):
        cursor = self.conn.cursor()
        cursor.execute('SELECT id FROM sectors WHERE name = ?', (sector_name,))
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
        cursor.execute('SELECT id FROM funds WHERE symbol = ?', (symbol,))
        return cursor.fetchone()[0]

    def delete_holdings_for_fund(self, fund_symbol):
        cursor = self.conn.cursor()
        cursor.execute('SELECT id FROM funds WHERE symbol = ?', (fund_symbol,))
        fund_row = cursor.fetchone()
        if not fund_row:
            return 0
        cursor.execute('DELETE FROM holdings WHERE fund_id = ?', (fund_row[0],))
        self.conn.commit()
        return cursor.rowcount

    def save_holding(self, fund_symbol, company_symbol, company_name, weight, shares=None):
        cursor = self.conn.cursor()
        cursor.execute('SELECT id FROM funds WHERE symbol = ?', (fund_symbol,))
        fund_row = cursor.fetchone()
        if not fund_row:
            logger.warning('Fund %s not found in database', fund_symbol)
            return None
        cursor.execute(
            'INSERT INTO holdings (fund_id, company_symbol, company_name, weight, shares) VALUES (?, ?, ?, ?, ?)',
            (fund_row[0], company_symbol, company_name, weight, shares),
        )
        self.conn.commit()
        return cursor.lastrowid

    def save_leader(self, sector_name, company_symbol, company_name, times_held, total_weight, avg_weight, prevalence=None):
        cursor = self.conn.cursor()
        cursor.execute('SELECT id FROM sectors WHERE name = ?', (sector_name,))
        sector_row = cursor.fetchone()
        if not sector_row:
            logger.warning('Sector %s not found', sector_name)
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

    def save_analysis_run(self, sectors_analyzed, funds_analyzed, leaders_found, status='completed', notes=''):
        cursor = self.conn.cursor()
        cursor.execute(
            'INSERT INTO analysis_runs (run_date, sectors_analyzed, funds_analyzed, leaders_found, status, notes) VALUES (?, ?, ?, ?, ?, ?)',
            (get_timestamp(), sectors_analyzed, funds_analyzed, leaders_found, status, notes),
        )
        self.conn.commit()
        return cursor.lastrowid

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
        cursor.execute('SELECT COUNT(*) as count FROM tracked_funds WHERE sector_name = ?', (sector_name,))
        return cursor.fetchone()['count'] > 0

    def clear_tracked_funds(self, sector_name=None):
        cursor = self.conn.cursor()
        if sector_name:
            cursor.execute('DELETE FROM tracked_funds WHERE sector_name = ?', (sector_name,))
        else:
            cursor.execute('DELETE FROM tracked_funds')
        self.conn.commit()
        return cursor.rowcount

    def get_latest_strategy_state(self, sector_name: str) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT *
            FROM sector_strategy_state
            WHERE sector_name = ?
            ORDER BY review_date DESC, id DESC
            LIMIT 1
            """,
            (sector_name,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        data = dict(row)
        if data.get('evidence_json'):
            data['evidence'] = json.loads(data['evidence_json'])
        if data.get('sector_freshness_json'):
            data['sector_freshness'] = json.loads(data['sector_freshness_json'])
        return data

    def save_sector_strategy_state(self, decision: Dict[str, Any], review_date: str):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO sector_strategy_state (
                sector_name, review_date, active_symbol, active_name, active_kind, active_avg_weight,
                active_prevalence, pending_symbol, pending_name, pending_confirmations, status,
                last_action, last_action_reason, data_status, sector_freshness_json, evidence_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                decision['sector'],
                review_date,
                decision['target_symbol'],
                decision['target_name'],
                decision['target_kind'],
                decision.get('candidate_avg_weight') if decision['target_kind'] == 'stock' else None,
                decision.get('candidate_prevalence') if decision['target_kind'] == 'stock' else None,
                decision.get('pending_symbol'),
                decision.get('pending_name'),
                decision.get('pending_confirmations', 0),
                decision.get('review_status'),
                decision.get('action'),
                decision.get('action_reason'),
                decision.get('data_status'),
                json.dumps(decision.get('sector_freshness', {})),
                json.dumps(decision.get('evidence', {})),
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    def save_strategy_run(self, review_date: str, run_timestamp: str, summary: Dict[str, Any], portfolio: Dict[str, Any], report_paths: Dict[str, str]):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO strategy_runs (review_date, run_timestamp, summary_json, portfolio_json, report_text_path, report_json_path)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                review_date,
                run_timestamp,
                json.dumps(summary),
                json.dumps(portfolio),
                report_paths.get('text_report'),
                report_paths.get('json_report'),
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_latest_strategy_run(self) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM strategy_runs ORDER BY id DESC LIMIT 1')
        row = cursor.fetchone()
        if not row:
            return None
        data = dict(row)
        data['summary'] = json.loads(data.get('summary_json') or '{}')
        data['portfolio'] = json.loads(data.get('portfolio_json') or '{}')
        return data
