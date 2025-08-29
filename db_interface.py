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
数据库操作统一接口
结合 ChromaDB（语义搜索）和 SQLite（精确查询）的优势
"""

import hashlib
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging
from pathlib import Path
from translation_object import TranslationObject
from vector_translation_memory import VectorTranslationMemory
from sqlite_translation_memory import SQLiteTranslationMemory

logger = logging.getLogger(__name__)


class DatabaseInterface:
    """数据库操作统一接口，结合向量数据库和关系数据库"""
    
    def __init__(self, workspace_dir: str = "hybrid_memory"):
        workspace_path = Path(workspace_dir)
        # 确保工作目录存在
        workspace_path.mkdir(exist_ok=True)
        self.vector_memory = VectorTranslationMemory(str(workspace_path / "vector"))
        self.sqlite_memory = SQLiteTranslationMemory(str(workspace_path / "sqlite"))
    
    def close(self):
        """关闭所有数据库连接"""
        self.sqlite_memory.close_all_connections()
    
    # ===================== 专有名词管理 =====================
    
    def add_terminology(self, term: str, translation: str, domain: str = "", notes: str = "") -> bool:
        """添加专有名词到两个数据库"""
        vector_success = self.vector_memory.add_terminology(term, translation, domain, notes)
        sqlite_success = self.sqlite_memory.add_terminology(term, translation, domain, notes)
        
        if vector_success and sqlite_success:
            return True
        elif sqlite_success:
            # 如果 SQLite 成功但向量数据库失败，以 SQLite 为准
            logger.warning(f"专有名词 {term} 在向量数据库中添加失败，但SQLite成功")
            return True
        else:
            logger.error(f"专有名词 {term} 添加失败")
            return False
    
    def add_terminology_batch(self, terms_data: List[Dict]) -> Tuple[int, int, List[str]]:
        """批量添加专有名词"""
        if not terms_data:
            return 0, 0, []
        
        # 使用 SQLite 的批量插入方法
        sqlite_success_count, sqlite_error_count = self.sqlite_memory.add_terminology_batch(terms_data)
        
        # 再在向量数据库中批量添加
        vector_success_count, vector_error_count, vector_errors = self.vector_memory.add_terminology_batch(terms_data)
        
        # 收集错误信息
        errors = []
        if sqlite_error_count > 0:
            errors.append(f"SQLite添加失败 {sqlite_error_count} 条记录")
        if vector_error_count > 0:
            errors.append(f"向量数据库添加失败 {vector_error_count} 条记录")
        
        # 添加向量数据库的具体错误信息
        errors.extend(vector_errors)
        
        logger.info(f"批量添加专有名词完成: SQLite成功 {sqlite_success_count}, 向量数据库成功 {vector_success_count}")
        
        # 返回综合结果，以 SQLite 为准
        return sqlite_success_count, sqlite_error_count, errors
    
    def search_terminology(self, text: str, threshold: float = 0.8) -> List[Dict]:
        """搜索专有名词，使用向量数据库的精确匹配"""
        return self.vector_memory.search_terminology(text, threshold)
    
    def get_terminology_list(self, search_text: str = "", domain: str = "") -> List[Dict]:
        """获取专有名词列表，使用 SQLite 查询"""
        return self.sqlite_memory.search_terminology(search_text, domain)
    
    def delete_terminology(self, term: str) -> bool:
        """删除专有名词"""
        vector_success = self.vector_memory.delete_terminology(term)
        sqlite_success = self.sqlite_memory.delete_terminology(term)
        
        # 只要有一个成功就认为成功
        return vector_success or sqlite_success
    
    # ===================== 翻译历史管理 =====================
    
    def add_translation_history(self, config_name: str, translation_obj: TranslationObject, sql_db = None) -> str:
        """添加翻译历史到两个数据库"""

        # 先添加到 SQLite（主要数据存储）
        sqlite_success = self.sqlite_memory.add_translation(config_name, translation_obj, sql_db)
        
        # 再添加到向量数据库（只存储用于语义搜索的字段）
        vector_key = ""
        if sqlite_success:
            vector_key = self.vector_memory.add_translation_history(config_name, translation_obj)
        
        if sqlite_success:
            return translation_obj.translation_key
        else:
            return ""
    
    def update_translation_history(self, config_name: str, translation_key: str, updated_translation_obj: TranslationObject) -> bool:
        """更新翻译历史"""
        # 先更新 SQLite
        sqlite_success = self.sqlite_memory.update_translation(config_name, translation_key, updated_translation_obj)
        
        return sqlite_success
    
    def get_exact_translation(self, config_name: str, source_text: str = "", translation_key: str = "", db = None) -> Optional[TranslationObject]:
        """获取精确匹配的翻译，直接使用 SQLite 查询"""
        if translation_key:
            return self.sqlite_memory.get_translation_by_key(config_name, translation_key, db)
        elif source_text:
            # 使用 SQLite 进行精确文本匹配
            return self.sqlite_memory.get_translation_by_original_text(config_name, source_text)
        return None
    
    def get_sqlite_connection(self, config_name: str):
        """获取指定配置的 SQLite 连接, 用户自行管理生命周期"""
        return self.sqlite_memory.get_translation_connection(config_name)
    
    def get_translation_by_key(self, config_name: str, translation_key: str) -> Optional[TranslationObject]:
        """根据 translation_key 获取翻译，直接使用 SQLite"""
        return self.sqlite_memory.get_translation_by_key(config_name, translation_key)
    
    def search_similar_translations(self, config_name: str, source_text: str, threshold: float, n_results: int = 3) -> List[Dict]:
        """搜索相似翻译，使用向量数据库进行语义搜索，然后用 SQLite 验证数据一致性"""
        # 1. 使用向量数据库进行语义搜索
        vector_results = self.vector_memory.search_similar_translations(config_name, source_text, threshold, n_results)
        
        # 2. 根据 translation_key 在 SQLite 中验证和获取完整数据
        verified_results = []
        for result in vector_results:
            translation_key = result.get('translation_key', '')
            if translation_key:
                # 从 SQLite 获取完整数据
                sqlite_obj = self.sqlite_memory.get_translation_by_key(config_name, translation_key)
                if sqlite_obj:
                    # 检查数据一致性
                    sqlite_dict = sqlite_obj.to_dict()
                    vector_source = result.get('source', '')
                    sqlite_source = sqlite_dict.get('original_text', '')
                    
                    if vector_source != self.vector_memory.escape_text(sqlite_source):
                        # 数据不一致，用 SQLite 数据同步向量数据库
                        logger.warning(f"数据不一致，同步向量数据库: {translation_key}, {vector_source} != {sqlite_source}")
                        self.vector_memory.update_history_translation(config_name, translation_key, sqlite_obj)
                    
                    # 使用 SQLite 中的数据构造返回结果
                    verified_results.append({
                        'type': 'similar',
                        'source': sqlite_dict.get('original_text', ''),
                        'target': sqlite_dict.get('translation', ''),
                        'context': sqlite_dict.get('context', ''),
                        'file_path': sqlite_dict.get('file_name', ''),
                        'similarity': result.get('similarity', 0.0),
                        'created_at': sqlite_dict.get('created_at', ''),
                        'approved': sqlite_dict.get('approved', False),
                        'approved_text': sqlite_dict.get('approved_text', ''),
                        'translation_key': translation_key
                    })
                else:
                    # SQLite 中没有对应记录，从向量数据库中删除
                    logger.warning(f"SQLite中缺少记录，从向量数据库删除: {translation_key}")
                    # 这里可以考虑删除向量数据库中的孤立记录
        
        return verified_results
    
    def search_translations(self, config_name: str, search_params: Dict) -> List[Dict]:
        """搜索翻译记录，使用 SQLite 进行条件查询"""
        return self.sqlite_memory.search_translations(config_name, search_params)
    
    def delete_translation(self, config_name: str, translation_key: str) -> bool:
        """删除翻译记录"""
        # 先从 SQLite 删除
        sqlite_success = self.sqlite_memory.delete_translation(config_name, translation_key)
        
        # 再从向量数据库删除
        vector_success = self.vector_memory.delete_translation_history(config_name, translation_key)
        
        if sqlite_success and not vector_success:
            logger.warning(f"翻译记录 {translation_key} 在向量数据库中删除失败，但SQLite成功")
        
        return sqlite_success
    
    def delete_translation_batch(self, config_name: str, translation_keys: List[str]) -> Tuple[int, int, List[str]]:
        """批量删除翻译记录
        
        Args:
            config_name: 配置名称
            translation_keys: 要删除的翻译记录键列表
        
        Returns:
            Tuple[成功删除数量, 失败数量, 错误信息列表]
        """
        if not translation_keys:
            return 0, 0, []
        
        # 先从 SQLite 批量删除
        sqlite_success_count, sqlite_error_count = self.sqlite_memory.delete_translation_batch(config_name, translation_keys)
        
        # 再从向量数据库批量删除
        vector_success_count, vector_error_count = self.vector_memory.delete_translation_batch(config_name, translation_keys)
        
        errors = []
        if sqlite_error_count > 0:
            errors.append(f"SQLite删除失败 {sqlite_error_count} 条记录")
        if vector_error_count > 0:
            errors.append(f"向量数据库删除失败 {vector_error_count} 条记录")
        
        # 以 SQLite 的结果为准
        return sqlite_success_count, sqlite_error_count, errors
    
    def get_translation_count(self, config_name: str) -> int:
        """获取翻译记录总数，使用 SQLite"""
        return self.sqlite_memory.get_translation_count(config_name)
    
    # ===================== 数据同步和一致性检查 =====================
    
    def sync_data_consistency(self, config_name: str) -> Tuple[int, int]:
        """同步数据一致性，以 SQLite 为准"""
        synced_count = 0
        error_count = 0
        
        try:
            # 获取 SQLite 中的所有记录
            all_translations = self.sqlite_memory.search_translations(config_name, {})
            
            for record in all_translations:
                translation_obj = record['translation_obj']
                translation_key = translation_obj.translation_key
                
                try:
                    # 更新向量数据库中的对应记录
                    self.vector_memory.update_history_translation(config_name, translation_key, translation_obj)
                    synced_count += 1
                except Exception as e:
                    logger.error(f"同步记录失败 {translation_key}: {e}")
                    error_count += 1
            
            logger.info(f"数据同步完成: 成功 {synced_count}, 失败 {error_count}")
            
        except Exception as e:
            logger.error(f"数据同步过程失败: {e}")
        
        return synced_count, error_count
    
    def update_translation_batch(self, config_name: str, translation_objects: List[TranslationObject], update_vector: bool = False) -> Tuple[int, int, List[str]]:
        """批量更新或插入翻译记录
        
        Args:
            config_name: 配置名称
            translation_objects: 要更新/插入的翻译对象列表
            update_vector: 是否同时更新向量数据库
        
        Returns:
            Tuple[成功数量, 失败数量, 错误信息列表]
        """
        if not translation_objects:
            return 0, 0, []
    
        
        # 先批量更新 SQLite（主要数据存储）
        sqlite_success_count, sqlite_error_count = self.sqlite_memory.update_translation_batch(config_name, translation_objects)
        
        errors = []
        if sqlite_error_count > 0:
            errors.append(f"SQLite更新失败 {sqlite_error_count} 条记录")
        
        vector_success_count = 0
        vector_error_count = 0
        
        # 如果需要更新向量数据库
        if update_vector:
            try:
                # 使用批量更新方法
                vector_success_count, vector_error_count = self.vector_memory.update_history_translation_batch(config_name, translation_objects)
                
                if vector_error_count > 0:
                    errors.append(f"向量数据库更新失败 {vector_error_count} 条记录")
                
                logger.info(f"批量更新完成: SQLite成功 {sqlite_success_count}, 向量数据库成功 {vector_success_count}")
                
            except Exception as vector_batch_error:
                logger.error(f"向量数据库批量更新过程失败: {str(vector_batch_error)}")
                errors.append(f"向量数据库批量更新过程失败: {str(vector_batch_error)}")
        else:
            logger.info(f"批量更新完成: SQLite成功 {sqlite_success_count} (跳过向量数据库)")
        
        # 以 SQLite 的结果为准
        return sqlite_success_count, sqlite_error_count, errors
