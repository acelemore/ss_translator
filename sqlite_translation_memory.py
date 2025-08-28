# -*- coding: utf-8 -*-
"""
This file is part of ss_translator.

ss_translator is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

ss_translator is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with ss_translator.  If not, see <https://www.gnu.org/licenses/>.
"""
"""
基于 SQLite 的翻译记忆库系统
提供精确查询、模糊搜索和条件查询功能
"""

import sqlite3
import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging
from translation_object import TranslationObject

logger = logging.getLogger(__name__)


class SQLiteTranslationMemory:
    """基于 SQLite 的翻译记忆库"""
    
    def __init__(self, workspace_dir: str = "sqlite_memory"):
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(exist_ok=True)
        
        # 数据库连接字典（按配置名称区分）
        self.db_connections = {}
        
        # 专有名词数据库（全局共享）
        self.terminology_db_path = self.workspace_dir / "terminology.db"
        self._init_terminology_db()
    
    def _init_terminology_db(self):
        """初始化专有名词数据库"""
        try:
            conn = sqlite3.connect(str(self.terminology_db_path), timeout=5.0)
            conn.row_factory = sqlite3.Row  # 使结果可以按列名访问
            
            # 配置并发访问模式
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')
            conn.execute('PRAGMA cache_size=10000')
            conn.execute('PRAGMA temp_store=memory')
            
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS terminology (
                    term TEXT PRIMARY KEY,
                    translation TEXT NOT NULL,
                    domain TEXT DEFAULT 'general',
                    notes TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            ''')
            
            # 创建索引以提高查询性能
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_terminology_domain ON terminology(domain)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_terminology_translation ON terminology(translation)')
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"初始化专有名词数据库失败: {e}")
    
    def get_translation_db_path(self, config_name: str) -> Path:
        """获取特定配置的翻译数据库路径"""
        return self.workspace_dir / f"translations_{config_name}.db"
    
    def _init_translation_db(self, config_name: str):
        """初始化翻译历史数据库"""
        try:
            db_path = self.get_translation_db_path(config_name)
            conn = sqlite3.connect(str(db_path), timeout=5.0)
            conn.row_factory = sqlite3.Row
            
            # 配置并发访问模式
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')
            conn.execute('PRAGMA cache_size=10000')
            conn.execute('PRAGMA temp_store=memory')
            
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS translations (
                    translation_key TEXT PRIMARY KEY,
                    file_name TEXT NOT NULL,
                    original_text TEXT NOT NULL,
                    process_text TEXT DEFAULT '',
                    translation TEXT DEFAULT '',
                    context TEXT DEFAULT '',
                    dangerous BOOLEAN DEFAULT FALSE,
                    is_translated BOOLEAN DEFAULT FALSE,
                    is_suggested_to_translate BOOLEAN DEFAULT TRUE,
                    llm_reason TEXT DEFAULT '',
                    approved BOOLEAN DEFAULT FALSE,
                    approved_text TEXT DEFAULT '',
                    config_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            ''')
            
            # 创建索引以提高查询性能
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_translations_file_name ON translations(file_name)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_translations_original_text ON translations(original_text)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_translations_translation ON translations(translation)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_translations_approved ON translations(approved)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_translations_created_at ON translations(created_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_translations_updated_at ON translations(updated_at)')
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"初始化翻译数据库失败 {config_name}: {e}")
    
    def get_translation_connection(self, config_name: str) -> sqlite3.Connection:
        """获取特定配置的数据库连接 - 每次创建新连接避免锁问题"""
        # 确保数据库存在
        self._init_translation_db(config_name)
        
        # 每次创建新连接，避免连接池导致的锁问题
        db_path = self.get_translation_db_path(config_name)
        conn = sqlite3.connect(str(db_path), check_same_thread=False, timeout=5.0)
        conn.row_factory = sqlite3.Row
        
        # 配置并发访问模式
        conn.execute('PRAGMA journal_mode=WAL')  # 写前日志模式，支持并发读写
        conn.execute('PRAGMA synchronous=NORMAL')  # 平衡性能和安全
        conn.execute('PRAGMA cache_size=10000')  # 增加缓存
        conn.execute('PRAGMA temp_store=memory')  # 临时存储在内存中
        
        return conn
    
    def close_all_connections(self):
        """关闭所有数据库连接"""
        for conn in self.db_connections.values():
            try:
                conn.close()
            except Exception as e:
                logger.error(f"关闭数据库连接失败: {e}")
        self.db_connections.clear()
    
    # ===================== 专有名词管理 =====================
    
    def add_terminology(self, term: str, translation: str, domain: str = "general", notes: str = "") -> bool:
        """添加专有名词"""
        try:
            conn = sqlite3.connect(str(self.terminology_db_path), timeout=5.0)
            conn.row_factory = sqlite3.Row
            
            current_time = datetime.now().isoformat()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO terminology 
                (term, translation, domain, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (term, translation, domain, notes, current_time, current_time))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"添加专有名词失败: {e}")
            return False
    
    def search_terminology(self, search_text: str = "", domain: str = "") -> List[Dict]:
        """搜索专有名词"""
        try:
            conn = sqlite3.connect(str(self.terminology_db_path), timeout=5.0)
            conn.row_factory = sqlite3.Row
            
            cursor = conn.cursor()
            
            # 构建查询条件
            where_conditions = []
            params = []
            
            if search_text:
                where_conditions.append("(term LIKE ? OR translation LIKE ?)")
                search_pattern = f"%{search_text}%"
                params.extend([search_pattern, search_pattern])
            
            if domain:
                where_conditions.append("domain = ?")
                params.append(domain)
            
            # 构建完整查询
            query = "SELECT * FROM terminology"
            if where_conditions:
                query += " WHERE " + " AND ".join(where_conditions)
            query += " ORDER BY term"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            result = []
            for row in rows:
                result.append({
                    'term': row['term'],
                    'translation': row['translation'],
                    'domain': row['domain'],
                    'notes': row['notes'],
                    'created_at': row['created_at']
                })
            
            conn.close()
            return result
        except Exception as e:
            logger.error(f"搜索专有名词失败: {e}")
            return []
    
    def delete_terminology(self, term: str) -> bool:
        """删除专有名词"""
        try:
            conn = sqlite3.connect(str(self.terminology_db_path), timeout=5.0)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM terminology WHERE term = ?", (term,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"删除专有名词失败: {e}")
            return False
    
    # ===================== 翻译历史管理 =====================
    
    def add_translation(self, config_name: str, translation_obj: TranslationObject) -> bool:
        """添加翻译记录"""
        try:
            conn = self.get_translation_connection(config_name)
            cursor = conn.cursor()
            
            current_time = datetime.now().isoformat()
            translation_dict = translation_obj.to_dict()
            
            cursor.execute('''
                INSERT OR REPLACE INTO translations 
                (translation_key, file_name, original_text, process_text, translation, context,
                 dangerous, is_translated, is_suggested_to_translate, llm_reason, approved, 
                 approved_text, config_name, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                translation_dict.get('translation_key', ''),
                translation_dict.get('file_name', ''),
                translation_dict.get('original_text', ''),
                translation_dict.get('process_text', ''),
                translation_dict.get('translation', ''),
                translation_dict.get('context', ''),
                translation_dict.get('dangerous', False),
                translation_dict.get('is_translated', False),
                translation_dict.get('is_suggested_to_translate', True),
                translation_dict.get('llm_reason', ''),
                translation_dict.get('approved', False),
                translation_dict.get('approved_text', ''),
                config_name,
                current_time,
                current_time
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"添加翻译记录失败: {e}")
            try:
                conn.close()
            except:
                pass
            return False
    
    def update_translation(self, config_name: str, translation_key: str, translation_obj: TranslationObject) -> bool:
        """更新翻译记录，如果不存在则插入新的"""
        conn = None
        try:
            conn = self.get_translation_connection(config_name)
            cursor = conn.cursor()
            
            current_time = datetime.now().isoformat()
            translation_dict = translation_obj.to_dict()
            
            # 使用 INSERT OR REPLACE 直接插入或更新记录
            cursor.execute('''
                INSERT OR REPLACE INTO translations 
                (translation_key, file_name, original_text, process_text, translation, context,
                 dangerous, is_translated, is_suggested_to_translate, llm_reason, approved, 
                 approved_text, config_name, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 
                        COALESCE((SELECT created_at FROM translations WHERE translation_key = ?), ?), ?)
            ''', (
                translation_key,
                translation_dict.get('file_name', ''),
                translation_dict.get('original_text', ''),
                translation_dict.get('process_text', ''),
                translation_dict.get('translation', ''),
                translation_dict.get('context', ''),
                translation_dict.get('dangerous', False),
                translation_dict.get('is_translated', False),
                translation_dict.get('is_suggested_to_translate', True),
                translation_dict.get('llm_reason', ''),
                translation_dict.get('approved', False),
                translation_dict.get('approved_text', ''),
                translation_dict.get('config_name', config_name),
                translation_key,  # 用于 COALESCE 查询
                current_time,     # 如果是新记录，创建时间
                current_time      # 更新时间
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"更新/插入翻译记录失败: {e}")
            if conn:
                try:
                    conn.close()
                except:
                    pass
            return False
    
    def get_translation_by_key(self, config_name: str, translation_key: str) -> Optional[TranslationObject]:
        """根据translation_key获取翻译记录"""
        conn = None
        try:
            conn = self.get_translation_connection(config_name)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM translations WHERE translation_key = ?", (translation_key,))
            row = cursor.fetchone()
            
            if row:
                result = TranslationObject(
                    file_name=row['file_name'],
                    original_text=row['original_text'],
                    process_text=row['process_text'],
                    translation=row['translation'],
                    context=row['context'],
                    dangerous=row['dangerous'],
                    is_translated=row['is_translated'],
                    is_suggested_to_translate=row['is_suggested_to_translate'],
                    llm_reason=row['llm_reason'],
                    translation_key=row['translation_key'],
                    approved=row['approved'],
                    approved_text=row['approved_text']
                )
                conn.close()
                return result
            conn.close()
            return None
        except Exception as e:
            logger.error(f"获取翻译记录失败: {e}")
            if conn:
                try:
                    conn.close()
                except:
                    pass
            return None
    
    def get_translation_by_original_text(self, config_name: str, original_text: str) -> Optional[TranslationObject]:
        """根据原文精确查询翻译记录"""
        conn = None
        try:
            conn = self.get_translation_connection(config_name)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM translations WHERE original_text = ? LIMIT 1", (original_text,))
            row = cursor.fetchone()
            
            if row:
                result = TranslationObject(
                    file_name=row['file_name'],
                    original_text=row['original_text'],
                    process_text=row['process_text'],
                    translation=row['translation'],
                    context=row['context'],
                    dangerous=row['dangerous'],
                    is_translated=row['is_translated'],
                    is_suggested_to_translate=row['is_suggested_to_translate'],
                    llm_reason=row['llm_reason'],
                    translation_key=row['translation_key'],
                    approved=row['approved'],
                    approved_text=row['approved_text']
                )
                conn.close()
                return result
            conn.close()
            return None
        except Exception as e:
            logger.error(f"根据原文获取翻译记录失败: {e}")
            if conn:
                try:
                    conn.close()
                except:
                    pass
            return None
    
    def search_translations(self, config_name: str, search_params: Dict) -> List[Dict]:
        """搜索翻译记录"""
        conn = None
        try:
            conn = self.get_translation_connection(config_name)
            cursor = conn.cursor()
            
            # 设置查询超时（SQLite 查询级别）
            cursor.execute('PRAGMA busy_timeout = 3000')  # 3秒超时
            
            # 构建查询条件
            where_conditions = []
            params = []
            
            # 文件名模糊匹配
            if search_params.get('file_name'):
                where_conditions.append("file_name LIKE ?")
                params.append(f"%{search_params['file_name']}%")
            
            # 原文模糊匹配
            if search_params.get('original_text'):
                where_conditions.append("original_text LIKE ?")
                params.append(f"%{search_params['original_text']}%")
            
            # 译文模糊匹配
            if search_params.get('translation'):
                where_conditions.append("translation LIKE ?")
                params.append(f"%{search_params['translation']}%")
            
            # 审核文本模糊匹配
            if search_params.get('approved_text'):
                where_conditions.append("approved_text LIKE ?")
                params.append(f"%{search_params['approved_text']}%")
            
            # 上下文模糊匹配
            if search_params.get('context'):
                where_conditions.append("context LIKE ?")
                params.append(f"%{search_params['context']}%")
            
            # 审核状态精确匹配
            if 'approved' in search_params and search_params['approved'] is not None:
                where_conditions.append("approved = ?")
                params.append(search_params['approved'])
            
            # 构建完整查询
            query = "SELECT * FROM translations"
            if where_conditions:
                query += " WHERE " + " AND ".join(where_conditions)
            query += " ORDER BY updated_at DESC"
            
            # 添加分页支持
            if search_params.get('limit'):
                query += " LIMIT ?"
                params.append(search_params['limit'])
                
                if search_params.get('offset'):
                    query += " OFFSET ?"
                    params.append(search_params['offset'])
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            result = []
            for row in rows:
                translation_obj = TranslationObject(
                    file_name=row['file_name'],
                    original_text=row['original_text'],
                    process_text=row['process_text'],
                    translation=row['translation'],
                    context=row['context'],
                    dangerous=row['dangerous'],
                    is_translated=row['is_translated'],
                    is_suggested_to_translate=row['is_suggested_to_translate'],
                    llm_reason=row['llm_reason'],
                    translation_key=row['translation_key'],
                    approved=row['approved'],
                    approved_text=row['approved_text']
                )
                
                result.append({
                    'metadata': dict(row),
                    'translation_obj': translation_obj
                })
            
            conn.close()
            return result
        except Exception as e:
            logger.error(f"搜索翻译记录失败: {e}")
            if conn:
                try:
                    conn.close()
                except:
                    pass
            return []
    
    def delete_translation(self, config_name: str, translation_key: str) -> bool:
        """删除翻译记录"""
        conn = None
        try:
            conn = self.get_translation_connection(config_name)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM translations WHERE translation_key = ?", (translation_key,))
            conn.commit()
            result = cursor.rowcount > 0
            conn.close()
            return result
        except Exception as e:
            logger.error(f"删除翻译记录失败: {e}")
            if conn:
                try:
                    conn.close()
                except:
                    pass
            return False
    
    def delete_translation_batch(self, config_name: str, translation_keys: List[str]) -> Tuple[int, int]:
        """批量删除翻译记录
        
        Args:
            config_name: 配置名称
            translation_keys: 要删除的翻译记录键列表
        
        Returns:
            Tuple[成功删除数量, 失败数量]
        """
        if not translation_keys:
            return 0, 0
        
        conn = None
        try:
            conn = self.get_translation_connection(config_name)
            cursor = conn.cursor()
            
            # 使用 IN 操作进行批量删除
            placeholders = ','.join(['?' for _ in translation_keys])
            query = f"DELETE FROM translations WHERE translation_key IN ({placeholders})"
            cursor.execute(query, translation_keys)
            conn.commit()
            
            success_count = cursor.rowcount
            error_count = len(translation_keys) - success_count
            conn.close()
            return success_count, error_count
            
        except Exception as e:
            logger.error(f"批量删除翻译记录失败: {e}")
            if conn:
                try:
                    conn.close()
                except:
                    pass
            return 0, len(translation_keys)
    
    def get_translation_count(self, config_name: str) -> int:
        """获取翻译记录总数"""
        conn = None
        try:
            conn = self.get_translation_connection(config_name)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM translations")
            row = cursor.fetchone()
            result = row['count'] if row else 0
            conn.close()
            return result
        except Exception as e:
            logger.error(f"获取翻译记录总数失败: {e}")
            if conn:
                try:
                    conn.close()
                except:
                    pass
            return 0
    
    def update_translation_batch(self, config_name: str, translation_objects: List[TranslationObject]) -> Tuple[int, int]:
        """批量更新或插入翻译记录
        
        Args:
            config_name: 配置名称
            translation_objects: 要更新/插入的翻译对象列表
        
        Returns:
            Tuple[成功更新数量, 失败数量]
        """
        if not translation_objects:
            return 0, 0
        
        conn = None
        try:
            conn = self.get_translation_connection(config_name)
            cursor = conn.cursor()
            
            current_time = datetime.now().isoformat()
            success_count = 0
            error_count = 0
            
            # 准备批量插入的数据
            batch_data = []
            for translation_obj in translation_objects:
                try:
                    translation_dict = translation_obj.to_dict()
                    
                    # 为每条记录准备数据元组
                    data_tuple = (
                        translation_dict.get('translation_key', ''),
                        translation_dict.get('file_name', ''),
                        translation_dict.get('original_text', ''),
                        translation_dict.get('process_text', ''),
                        translation_dict.get('translation', ''),
                        translation_dict.get('context', ''),
                        translation_dict.get('dangerous', False),
                        translation_dict.get('is_translated', False),
                        translation_dict.get('is_suggested_to_translate', True),
                        translation_dict.get('llm_reason', ''),
                        translation_dict.get('approved', False),
                        translation_dict.get('approved_text', ''),
                        config_name,
                        translation_dict.get('translation_key', ''),  # 用于 COALESCE 查询
                        current_time,     # 如果是新记录，创建时间
                        current_time      # 更新时间
                    )
                    batch_data.append(data_tuple)
                    
                except Exception as prepare_error:
                    logger.error(f"准备批量数据失败: {str(prepare_error)}")
                    error_count += 1
                    continue
            
            if batch_data:
                # 使用 executemany 进行批量插入/更新
                cursor.executemany('''
                    INSERT OR REPLACE INTO translations 
                    (translation_key, file_name, original_text, process_text, translation, context,
                     dangerous, is_translated, is_suggested_to_translate, llm_reason, approved, 
                     approved_text, config_name, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 
                            COALESCE((SELECT created_at FROM translations WHERE translation_key = ?), ?), ?)
                ''', batch_data)
                
                success_count = len(batch_data)
                conn.commit()
                logger.info(f"批量更新/插入完成: 成功 {success_count}, 失败 {error_count}")
            
            conn.close()
            return success_count, error_count
            
        except Exception as e:
            logger.error(f"批量更新/插入翻译记录失败: {e}")
            if conn:
                try:
                    conn.close()
                except:
                    pass
            return 0, len(translation_objects)
