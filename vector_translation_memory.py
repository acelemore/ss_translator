
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
基于向量数据库的翻译记忆库系统
使用 ChromaDB 实现语义相似性搜索和专有名词管理
"""

import os
import sys
import json
import hashlib
import re
from pathlib import Path
import traceback
from typing import Dict, List, Optional, Tuple, Set
from datetime import datetime
from collections import Counter
import chromadb
from chromadb.config import Settings
import ahocorasick
import logging
from translation_object import TranslationObject

logger = logging.getLogger(__name__)


class VectorTranslationMemory:
    """基于向量数据库的翻译记忆库"""
    
    def __init__(self, workspace_dir: str = "vector_memory"):
        
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(exist_ok=True)
        
        # 初始化ChromaDB客户端
        try:
            self.client = chromadb.PersistentClient(
                path=str(self.workspace_dir),
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
        except Exception:
            # 兼容老版本 ChromaDB
            self.client = chromadb.Client(
                settings=Settings(
                    chroma_db_impl="duckdb+parquet",
                    persist_directory=str(self.workspace_dir),
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
        
        # 专有名词库（全局共享）
        self.terminology_collection = self._get_or_create_collection("terminology")
        
        # 翻译历史库字典（按模组配置区分）
        self.translation_collections = {}
        
        # 初始化 Aho-Corasick 自动机用于快速专有名词匹配
        self.terminology_automaton = None
        self.terminology_cache = {}  # 缓存专有名词数据 {term: term_info}
        self._init_terminology_automaton()
        
    
    def _get_or_create_collection(self, collection_name: str):
        """获取或创建集合"""
        try:
            return self.client.get_collection(collection_name)
        except Exception:
            return self.client.create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
    
    def _init_terminology_automaton(self):
        """初始化 Aho-Corasick 自动机"""
        
        try:
            # 创建新的自动机
            self.terminology_automaton = ahocorasick.Automaton()
            self.terminology_cache = {}
            
            # 从数据库加载所有专有名词
            terms = self.get_terminology_list()
            
            for term_info in terms:
                term = term_info['term']
                if term:
                    # 添加原始术语（区分大小写）
                    self.terminology_automaton.add_word(term, (term, term_info))
                    # 添加小写版本（不区分大小写匹配）
                    self.terminology_automaton.add_word(term.lower(), (term, term_info))
                    # 缓存术语信息
                    self.terminology_cache[term.lower()] = term_info
            
            # 构建自动机
            self.terminology_automaton.make_automaton()
            
        except Exception as e:
            logger.error(f"初始化 Aho-Corasick 自动机失败: {e}")
            self.terminology_automaton = None
    
    def _rebuild_terminology_automaton(self):
        """重建 Aho-Corasick 自动机"""
        self._init_terminology_automaton()
    
    def _add_term_to_automaton(self, term: str, term_info: Dict):
        """向自动机添加单个术语"""
        
        try:
            # 由于 ahocorasick 不支持动态添加，需要重建自动机
            self._rebuild_terminology_automaton()
        except Exception as e:
            logger.error(f"添加术语到自动机失败: {e}")
    
    def _remove_term_from_automaton(self, term: str):
        """从自动机移除术语"""
        
        try:
            # 由于 ahocorasick 不支持动态删除，需要重建自动机
            self._rebuild_terminology_automaton()
        except Exception as e:
            logger.error(f"从自动机移除术语失败: {e}")
    
    def get_translation_collection(self, config_name: str):
        """获取特定配置的翻译历史库"""
        if config_name not in self.translation_collections:
            collection_name = f"translations_{config_name}"
            self.translation_collections[config_name] = self._get_or_create_collection(collection_name)
        return self.translation_collections[config_name]
    
    def add_terminology(self, term: str, translation: str, domain: str = "", notes: str = "") -> bool:
        """添加专有名词到向量数据库"""
        try:
            term_id = hashlib.md5(term.encode('utf-8')).hexdigest()
            term = self.escape_text(term)
            metadata = {
                "term": term,
                "translation": translation,
                "domain": domain or "general",
                "notes": notes or "",
                "created_at": datetime.now().isoformat(),
                "type": "terminology"
            }
            
            # 添加到专有名词库
            self.terminology_collection.upsert(
                ids=[term_id],
                documents=[term],
                metadatas=[metadata]
            )
            
            # 更新自动机
            term_info = {
                'term': term,
                'translation': translation,
                'domain': domain or "general",
                'notes': notes or "",
                'created_at': metadata['created_at']
            }
            self._add_term_to_automaton(term, term_info)
            
            return True
        except Exception as e:
            logger.error(f"添加专有名词失败: {e}")
            return False
    
    def add_terminology_batch(self, terms_data: List[Dict]) -> Tuple[int, int, List[str]]:
        """批量添加专有名词到向量数据库
        
        Args:
            terms_data: 包含专有名词数据的列表，每个元素应包含:
                - term: 英文术语
                - translation: 中文翻译
                - domain: 领域（可选，默认为 "general"）
                - notes: 备注（可选）
        
        Returns:
            Tuple[成功数量, 失败数量, 错误信息列表]
        """
        success_count = 0
        error_count = 0
        error_messages = []
        
        if not terms_data:
            return 0, 0, ["没有数据需要导入"]
        
        # 准备批量数据
        batch_ids = []
        batch_documents = []
        batch_metadatas = []
        current_time = datetime.now().isoformat()
        
        for i, item in enumerate(terms_data):
            try:
                # 验证数据
                if not isinstance(item, dict):
                    error_count += 1
                    error_messages.append(f"第 {i+1} 项数据格式错误")
                    continue
                
                term = item.get('term', '').strip()
                translation = item.get('translation', '').strip()
                domain = item.get('domain', 'general')
                notes = item.get('notes', '')
                
                if not term or not translation:
                    error_count += 1
                    error_messages.append(f"第 {i+1} 项术语或翻译为空")
                    continue
                
                # 准备数据
                term_id = hashlib.md5(term.encode('utf-8')).hexdigest()
                escaped_term = self.escape_text(term)
                
                metadata = {
                    "term": escaped_term,
                    "translation": translation,
                    "domain": domain or "general",
                    "notes": notes or "",
                    "created_at": current_time,
                    "type": "terminology"
                }
                
                batch_ids.append(term_id)
                batch_documents.append(escaped_term)
                batch_metadatas.append(metadata)
                
            except Exception as e:
                error_count += 1
                error_messages.append(f"第 {i+1} 项处理失败: {str(e)}")
        
        # 执行批量插入
        if batch_ids:
            try:
                self.terminology_collection.upsert(
                    ids=batch_ids,
                    documents=batch_documents,
                    metadatas=batch_metadatas
                )
                success_count = len(batch_ids)
                
                # 批量添加后重建自动机
                self._rebuild_terminology_automaton()
                
            except Exception as e:
                error_count += len(batch_ids)
                error_messages.append(f"批量插入失败: {str(e)}")
                success_count = 0
        
        return success_count, error_count, error_messages
    
    def search_terminology(self, text: str, threshold: float = 0.8) -> List[Dict]:
        """搜索文本中包含的专有名词"""
        found_terms = []
        try:
            text = self.escape_text(text)
            
            # 策略1: 精确匹配 - 检查专有名词是否直接出现在文本中
            exact_matches = self._find_exact_terminology_matches(text)
            found_terms.extend(exact_matches)
            
            # 策略2: 分段搜索 - 将长文本分解为更小的片段进行语义搜索
            if len(text) > 10:  # 对于较长的文本使用分段搜索
                semantic_matches = self._find_terminology_by_segments(text, threshold)
                found_terms.extend(semantic_matches)
            else:
                # 策略3: 整体语义搜索 - 对于较短的文本直接搜索
                semantic_matches = self._find_terminology_by_semantic_search(text, threshold)
                found_terms.extend(semantic_matches)
            
            # 去重和排序
            found_terms = self._deduplicate_and_sort_terms(found_terms)
            
        except Exception as e:
            logger.error(f"搜索专有名词失败: {e}")
        return found_terms
    
    def _find_exact_terminology_matches(self, text: str) -> List[Dict]:
        """精确匹配专有名词 - 使用 Aho-Corasick 自动机优化"""
        exact_matches = []
        
            # 使用 Aho-Corasick 自动机进行快速匹配
        try:
            text_lower = text.lower()
            found_terms = set()  # 用于去重
            
            # 在原始文本和小写文本中搜索
            for end_index, (original_term, term_info) in self.terminology_automaton.iter(text):
                start_index = end_index - len(original_term) + 1
                matched_text = text[start_index:end_index + 1]
                
                # 检查是否是完整单词匹配（避免部分匹配）
                # if self._is_whole_word_match(text, start_index, end_index, original_term):
                if True: # 部分匹配感觉也没什么问题, 反正最后是提交到LLM
                    term_key = original_term.lower()
                    if term_key not in found_terms:
                        found_terms.add(term_key)
                        exact_matches.append({
                            'term': term_info['term'],
                            'translation': term_info['translation'],
                            'domain': term_info['domain'],
                            'notes': term_info['notes'],
                            'similarity': 1.0,
                            'match_type': 'exact'
                        })
            
            # 在小写文本中再次搜索（不区分大小写）
            for end_index, (original_term, term_info) in self.terminology_automaton.iter(text_lower):
                start_index = end_index - len(original_term) + 1
                
                # 检查是否是完整单词匹配
                # if self._is_whole_word_match(text_lower, start_index, end_index, original_term):
                if True:
                    term_key = original_term.lower()
                    if term_key not in found_terms:
                        found_terms.add(term_key)
                        exact_matches.append({
                            'term': term_info['term'],
                            'translation': term_info['translation'],
                            'domain': term_info['domain'],
                            'notes': term_info['notes'],
                            'similarity': 1.0,
                            'match_type': 'exact'
                        })
                
        except Exception as e:
            pass
        
        return exact_matches
    
    def _is_whole_word_match(self, text: str, start_index: int, end_index: int, term: str) -> bool:
        """检查是否是完整单词匹配"""
        
        # 检查匹配位置前后是否是单词边界
        before_char = text[start_index - 1] if start_index > 0 else ' '
        after_char = text[end_index + 1] if end_index + 1 < len(text) else ' '
        
        # 如果前后都是非字母数字字符，则认为是完整单词
        return (not before_char.isalnum() and before_char != '_') and \
               (not after_char.isalnum() and after_char != '_')
    
    
    def _find_terminology_by_segments(self, text: str, threshold: float) -> List[Dict]:
        """通过分段搜索专有名词"""
        segment_matches = []
        try:
            # 将文本分解为更小的片段
            segments = self._split_text_into_segments(text)
            
            for segment in segments:
                if len(segment.strip()) < 3:  # 跳过过短的片段
                    continue
                    
                # 对每个片段进行语义搜索
                matches = self._find_terminology_by_semantic_search(segment, threshold * 0.8)  # 稍微降低阈值
                for match in matches:
                    match['match_type'] = 'segment'
                    match['matched_segment'] = segment
                segment_matches.extend(matches)
        except Exception as e:
            logger.error(f"分段搜索专有名词失败: {e}")
        
        return segment_matches
    
    def _find_terminology_by_semantic_search(self, text: str, threshold: float) -> List[Dict]:
        """使用语义搜索查找专有名词"""
        semantic_matches = []
        try:
            search_results = self.terminology_collection.query(
                query_texts=[text],
                n_results=20  # 增加搜索结果数量
            )
            
            if search_results['distances'] and search_results['metadatas']:
                for distance, metadata in zip(search_results['distances'][0], search_results['metadatas'][0]):
                    similarity = 1 - distance
                    if similarity >= threshold:
                        semantic_matches.append({
                            'term': metadata.get('term', ''),
                            'translation': metadata.get('translation', ''),
                            'domain': metadata.get('domain', ''),
                            'notes': metadata.get('notes', ''),
                            'similarity': similarity,
                            'match_type': 'semantic'
                        })
        except Exception as e:
            logger.error(f"语义搜索专有名词失败: {e}")
        
        return semantic_matches
    
    def _split_text_into_segments(self, text: str, max_segment_length: int = 10) -> List[str]:
        """将文本分解为更小的片段"""
        segments = []
        
        # 方法1: 按句子分割
        sentences = re.split(r'[.!?;]\s*', text)
        for sentence in sentences:
            if len(sentence.strip()) > 0:
                if len(sentence) <= max_segment_length:
                    segments.append(sentence.strip())
                else:
                    # 对于过长的句子，按短语分割
                    phrases = re.split(r'[,]\s*', sentence)
                    for phrase in phrases:
                        if len(phrase.strip()) > 0:
                            segments.append(phrase.strip())
        
        # 方法2: 滑动窗口分割（作为补充）
        words = text.split()
        window_size = 5  # 5个单词为一个窗口
        for i in range(0, len(words), window_size // 2):  # 50%重叠
            window = ' '.join(words[i:i + window_size])
            if len(window.strip()) > 0:
                segments.append(window.strip())
        
        return list(set(segments))  # 去重
    
    def _deduplicate_and_sort_terms(self, found_terms: List[Dict]) -> List[Dict]:
        """去重和排序专有名词结果"""
        # 按专有名词去重，保留相似度最高的
        term_dict = {}
        for term_info in found_terms:
            term = term_info['term']
            if term not in term_dict or term_info['similarity'] > term_dict[term]['similarity']:
                term_dict[term] = term_info
        
        # 按相似度排序，精确匹配优先
        unique_terms = list(term_dict.values())
        unique_terms.sort(key=lambda x: (x['similarity'], x['match_type'] == 'exact'), reverse=True)
        
        return unique_terms
    

    def add_translation_history(self, config_name: str, translation_obj: TranslationObject) -> str:
        """添加翻译历史到特定配置的库中
        
        Args:
            config_name: 配置名称
            translation_obj: 翻译对象
        
        Returns:
            翻译记录的translation_key，失败返回空字符串
        """
        try:
            collection = self.get_translation_collection(config_name)
            source_text = self.escape_text(translation_obj.original_text)
            
            # 使用translation_key作为ID，如果没有则生成一个
            translation_key = translation_obj.translation_key
            if not translation_key:
                # 如果translation_key为空，生成一个新的
                translation_key = hashlib.md5((source_text + translation_obj.file_name + str(datetime.now())).encode('utf-8')).hexdigest()
            
            # 精简metadata，只存储语义搜索必需的字段
            metadata = {
                "original_text": source_text,
                "translation_key": translation_key,
                "config_name": config_name,
                "created_at": datetime.now().isoformat(),
                "type": "translation"
            }
            
            # 添加到翻译历史库
            # documents字段只存储原文，用于语义搜索
            collection.upsert(
                ids=[translation_key],
                documents=[source_text],  # 只存储原文用于语义搜索
                metadatas=[metadata]
            )
            
            return translation_key
        except Exception as e:
            logger.error(f"添加翻译历史失败: {e}")
            return ""
        
    def update_history_translation(self, config_name: str, translation_key: str, updated_translation_obj: TranslationObject) -> bool:
        """更新翻译历史记录
        
        Args:
            config_name: 配置名称
            translation_key: 翻译记录的唯一标识
            updated_translation_obj: 更新后的翻译对象
        
        Returns:
            更新是否成功
        """
        try:
            collection = self.get_translation_collection(config_name)
            results = collection.get(ids=[translation_key])
            if not results or not results.get('metadatas') or not results['metadatas']:
                return False
            
            # 获取原有记录
            original_metadata = results['metadatas'][0]
            
            # 精简metadata，只保留语义搜索必需的字段
            updated_metadata = {
                "original_text": self.escape_text(updated_translation_obj.original_text),
                "translation_key": translation_key,
                "config_name": config_name,
                "created_at": original_metadata.get("created_at", datetime.now().isoformat()),
                "updated_at": datetime.now().isoformat(),
                "type": "translation"
            }

            document = self.escape_text(updated_translation_obj.original_text)  # 只存储原文
            
            # 重新插入更新后的数据
            collection.upsert(
                ids=[translation_key],
                documents=[document],
                metadatas=[updated_metadata]
            )
            return True
        except Exception as e:
            logger.error(f"更新翻译历史失败: {e}")
            return False
        
    def get_combine_document(self, metadata) -> str:
        """获取组合后的文档字符串，包含关键搜索字段"""
        file_name = metadata.get('file_name', '')
        original_text = metadata.get('original_text', '')
        translation = metadata.get('translation', '')
        approved_text = metadata.get('approved_text', '')
        context = metadata.get('context', '')
        
        # 组合关键搜索字段，使用标识符分隔
        return f"FILE:{file_name} ORIGINAL:{original_text} TRANSLATION:{translation} APPROVED:{approved_text} CONTEXT:{context}"
        
    def get_exact_translation(self, config_name: str, source_text: str = "", translation_key: str = "") -> Optional[TranslationObject]:
        """获取精确匹配的翻译，返回完整的TranslationObject
        
        Args:
            config_name: 配置名称
            source_text: 原文文本（可选）
            translation_key: 翻译的唯一标识（可选）
        
        Returns:
            匹配的TranslationObject，如果没有找到则返回None
        """
        try:
            collection = self.get_translation_collection(config_name)
            
            # 优先使用translation_key查询
            if translation_key:
                results = collection.get(ids=[translation_key])
            elif source_text:
                # 使用原文查询
                escaped_source_text = self.escape_text(source_text)
                results = collection.get(where={"original_text": escaped_source_text})
            else:
                return None
            
            if results['metadatas']:
                metadata = results['metadatas'][0]
                
                # 从metadata构造TranslationObject
                translation_obj = TranslationObject(
                    file_name=metadata.get('file_name', ''),
                    original_text=metadata.get('original_text', ''),
                    process_text=metadata.get('process_text', ''),
                    translation=metadata.get('translation', ''),
                    context=metadata.get('context', ''),
                    dangerous=metadata.get('dangerous', False),
                    is_translated=metadata.get('is_translated', False),
                    is_suggested_to_translate=metadata.get('is_suggested_to_translate', True),
                    llm_reason=metadata.get('llm_reason', ''),
                    translation_key=metadata.get('translation_key', ''),
                    approved=metadata.get('approved', False),
                    approved_text=metadata.get('approved_text', '')
                )
                
                return translation_obj
            return None
        except Exception as e:
            logger.error(f"获取精确翻译失败: {e}")
            return None
    
    def get_translation_by_key(self, config_name: str, translation_key: str) -> Optional[TranslationObject]:
        """根据translation_key获取翻译对象
        
        Args:
            config_name: 配置名称
            translation_key: 翻译的唯一标识
        
        Returns:
            匹配的TranslationObject，如果没有找到则返回None
        """
        return self.get_exact_translation(config_name, translation_key=translation_key)
    
    def search_similar_translations(self, config_name: str, source_text: str, threshold: float, n_results: int = 3) -> List[Dict]:
        """搜索相似的历史翻译
        
        Args:
            config_name: 配置名称
            source_text: 原文文本
            threshold: 相似度阈值
            n_results: 返回结果数量
        
        Returns:
            相似翻译记录列表，返回格式兼容旧版本调用方
        """
        try:
            collection = self.get_translation_collection(config_name)
            source_text = self.escape_text(source_text)
            
            try:
                # 使用语义搜索查找相似的翻译记录
                search_results = collection.query(
                    query_texts=[source_text],
                    n_results=n_results
                )
                
                similar_translations = []
                if search_results['distances'] and search_results['metadatas']:
                    for distance, metadata in zip(search_results['distances'][0], search_results['metadatas'][0]):
                        similarity = 1 - distance
                        if similarity > threshold:  # 相似度阈值
                            # 返回简化的结果，只包含语义搜索相关信息
                            similar_translations.append({
                                'type': 'similar',
                                'source': metadata.get('original_text', ''),
                                'similarity': similarity,
                                'translation_key': metadata.get('translation_key', ''),
                                'created_at': metadata.get('created_at', '')
                            })
                
                return similar_translations
                
            except Exception as e:
                logger.error(traceback.format_exc())
                logger.error(f"语义搜索翻译历史失败: {e}")
            
            return []
        except Exception as e:
            logger.error(f"搜索相似翻译失败: {e}")
            return []
    
    def efficient_search_translations(self, config_name: str, search_params: Dict) -> List[Dict]:
        """高效搜索翻译记录，结合where_document和metadata精确匹配
        
        Args:
            config_name: 配置名称
            search_params: 搜索参数，支持：
                - file_name: 文件名模糊匹配
                - original_text: 原文模糊匹配
                - translation: 译文模糊匹配
                - approved_text: 审核文本模糊匹配
                - context: 上下文模糊匹配
                - approved: 审核状态（True/False/None）
        
        Returns:
            匹配的翻译记录列表
        """
        try:
            collection = self.get_translation_collection(config_name)
            
            # 第一步：收集所有可能的候选记录
            candidate_ids = set()
            
            # 对于original_text字段，可以直接使用document搜索（因为document就是original_text）
            if search_params.get('original_text'):
                try:
                    field_results = collection.get(where_document={"$contains": str(search_params['original_text'])})
                    if field_results['ids']:
                        candidate_ids.update(field_results['ids'])
                except Exception as e:
                    logger.warning(f"原文搜索失败: {e}")
            
            # 对于其他字段，使用metadata精确搜索
            for field, search_value in search_params.items():
                if field == 'approved' or field == 'original_text' or not search_value:
                    continue  # 跳过已处理的字段和空值
                
                try:
                    # 对于非原文字段，需要获取所有记录进行字段匹配
                    # 这里可以优化：如果没有其他搜索条件，直接跳过
                    pass
                except Exception as e:
                    logger.warning(f"字段 {field} 搜索失败: {e}")
                    continue
            
            # 如果没有文本搜索条件，获取所有记录进行metadata过滤
            if not candidate_ids:
                if 'approved' in search_params and search_params['approved'] is not None:
                    try:
                        # 只有审核状态查询
                        results = collection.get(where={'approved': search_params['approved']})
                        if results['ids']:
                            candidate_ids.update(results['ids'])
                    except Exception:
                        # 如果where查询失败，获取所有记录
                        results = collection.get()
                        if results['ids']:
                            candidate_ids.update(results['ids'])
                else:
                    # 如果有非原文的字段搜索，需要获取所有记录进行过滤
                    has_other_fields = any(field not in ['original_text', 'approved'] and search_value 
                                         for field, search_value in search_params.items())
                    if has_other_fields:
                        results = collection.get()
                        if results['ids']:
                            candidate_ids.update(results['ids'])
                    else:
                        return []
            
            if not candidate_ids:
                return []
            
            # 第二步：获取候选记录的详细信息
            candidate_results = collection.get(ids=list(candidate_ids))
            
            if not candidate_results['metadatas']:
                return []
            
            # 第三步：在内存中进行精确的字段匹配
            matched_records = []
            
            for i, metadata in enumerate(candidate_results['metadatas']):
                is_match = True
                
                # 检查每个搜索条件
                for field, search_value in search_params.items():
                    if not search_value and search_value != False:  # 允许 False 值
                        continue  # 跳过空条件
                    
                    field_value = metadata.get(field, '')
                    
                    if field == 'approved':
                        # 布尔字段精确匹配
                        if metadata.get('approved', False) != search_value:
                            is_match = False
                            break
                    else:
                        # 字符串字段模糊匹配（不区分大小写）
                        if isinstance(field_value, str) and isinstance(search_value, str):
                            if search_value.lower() not in field_value.lower():
                                is_match = False
                                break
                        else:
                            # 非字符串字段转换为字符串后匹配
                            if str(search_value).lower() not in str(field_value).lower():
                                is_match = False
                                break
                
                if is_match:
                    # 构造结果记录
                    record = {
                        'metadata': metadata,
                        'document': candidate_results['documents'][i] if i < len(candidate_results['documents']) else '',
                        'translation_obj': self._metadata_to_translation_obj(metadata)
                    }
                    matched_records.append(record)
            
            # 按更新时间降序排序
            matched_records.sort(key=lambda x: x['metadata'].get('updated_at', ''), reverse=True)
            
            return matched_records
            
        except Exception as e:
            logger.error(f"高效搜索翻译记录失败: {e}")
            return []
       

    def _metadata_to_translation_obj(self, metadata) -> TranslationObject:
        """将metadata转换为TranslationObject"""
        return TranslationObject(
            file_name=metadata.get('file_name', ''),
            original_text=metadata.get('original_text', ''),
            process_text=metadata.get('process_text', ''),
            translation=metadata.get('translation', ''),
            context=metadata.get('context', ''),
            dangerous=metadata.get('dangerous', False),
            is_translated=metadata.get('is_translated', False),
            is_suggested_to_translate=metadata.get('is_suggested_to_translate', True),
            llm_reason=metadata.get('llm_reason', ''),
            translation_key=metadata.get('translation_key', ''),
            approved=metadata.get('approved', False),
            approved_text=metadata.get('approved_text', '')
        )

    
    def get_terminology_list(self) -> List[Dict]:
        """获取所有专有名词列表"""
        try:
            results = self.terminology_collection.get()
            terminology_list = []
            
            if results['metadatas']:
                for metadata in results['metadatas']:
                    terminology_list.append({
                        'term': metadata['term'],
                        'translation': metadata['translation'],
                        'domain': metadata['domain'],
                        'notes': metadata['notes'],
                        'created_at': metadata['created_at']
                    })
            
            return sorted(terminology_list, key=lambda x: x['term'])
        except Exception as e:
            logger.error(f"获取专有名词列表失败: {e}")
            return []
    
    def delete_terminology(self, term: str) -> bool:
        """删除专有名词"""
        try:
            term_id = hashlib.md5(term.encode('utf-8')).hexdigest()
            self.terminology_collection.delete(ids=[term_id])
            
            # 更新自动机
            self._remove_term_from_automaton(term)
            
            return True
        except Exception as e:
            logger.error(f"删除专有名词失败: {e}")
            return False
    
    def delete_translation_history(self, config_name: str, translation_key: str) -> bool:
        """删除翻译历史记录"""
        try:
            collection = self.get_translation_collection(config_name)
            collection.delete(ids=[translation_key])
            return True
        except Exception as e:
            logger.error(f"删除翻译历史失败 {translation_key}: {e}")
            return False
    
    def delete_translation_batch(self, config_name: str, translation_keys: List[str]) -> Tuple[int, int]:
        """批量删除翻译历史记录
        
        Args:
            config_name: 配置名称
            translation_keys: 要删除的翻译记录键列表
        
        Returns:
            Tuple[成功删除数量, 失败数量]
        """
        success_count = 0
        error_count = 0
        
        try:
            collection = self.get_translation_collection(config_name)
            
            # ChromaDB 支持批量删除
            try:
                collection.delete(ids=translation_keys)
                success_count = len(translation_keys)
            except Exception as e:
                logger.error(f"批量删除失败，尝试逐个删除: {e}")
                # 如果批量删除失败，逐个删除
                for translation_key in translation_keys:
                    try:
                        collection.delete(ids=[translation_key])
                        success_count += 1
                    except Exception as single_error:
                        logger.error(f"删除单个翻译记录失败 {translation_key}: {single_error}")
                        error_count += 1
                        
        except Exception as e:
            logger.error(f"删除翻译记录失败: {e}")
            error_count = len(translation_keys)
        
        return success_count, error_count
        
    def escape_text(self, text: str) -> str:
        """转义文本中的特殊字符"""
        if not isinstance(text, str):
            return str(text)
        
        escaped_text = text.replace("'", "").replace('"', '')
        return escaped_text
    
    def update_history_translation_batch(self, config_name: str, translation_objects: List[TranslationObject]) -> Tuple[int, int]:
        """批量更新翻译历史记录
        
        Args:
            config_name: 配置名称
            translation_objects: 要更新的翻译对象列表
        
        Returns:
            Tuple[成功数量, 失败数量]
        """
        if not translation_objects:
            return 0, 0
        
        success_count = 0
        error_count = 0
        
        try:
            collection = self.get_translation_collection(config_name)
            
            # 准备批量数据
            ids = []
            documents = []
            metadatas = []
            
            for translation_obj in translation_objects:
                try:
                    translation_key = translation_obj.translation_key
                    if not translation_key:
                        logger.warning("翻译对象缺少 translation_key，跳过")
                        error_count += 1
                        continue
                    
                    # 准备文档数据（只存储用于语义搜索的字段）
                    original_text = self.escape_text(translation_obj.original_text)
                    
                    ids.append(translation_key)
                    documents.append(original_text)
                    metadatas.append({
                        'translation_key': translation_key,
                        'config_name': config_name,
                        'created_at': datetime.now().isoformat(),
                        'type': 'translation'
                    })
                    
                except Exception as prepare_error:
                    logger.error(f"准备批量更新数据失败: {str(prepare_error)}")
                    error_count += 1
                    continue
            
            if ids:
                try:
                    # 使用 upsert 进行批量插入/更新
                    collection.upsert(
                        ids=ids,
                        documents=documents,
                        metadatas=metadatas
                    )
                    success_count = len(ids)
                    logger.info(f"批量更新向量数据库完成: 成功 {success_count} 条记录")
                    
                except Exception as upsert_error:
                    logger.error(f"向量数据库批量 upsert 失败: {str(upsert_error)}")
                    # 如果批量操作失败，尝试逐个更新
                    for i, translation_obj in enumerate(translation_objects[:len(ids)]):
                        try:
                            if self.update_history_translation(config_name, translation_obj.translation_key, translation_obj):
                                success_count += 1
                            else:
                                error_count += 1
                        except Exception:
                            error_count += 1
                            
        except Exception as e:
            logger.error(f"批量更新翻译历史失败: {e}")
            error_count = len(translation_objects)
        
        return success_count, error_count
    