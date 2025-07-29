
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
from typing import Dict, List, Optional, Tuple, Set
from datetime import datetime
from collections import Counter
import chromadb
from chromadb.config import Settings


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
        
    
    def _get_or_create_collection(self, collection_name: str):
        """获取或创建集合"""
        try:
            return self.client.get_collection(collection_name)
        except Exception:
            return self.client.create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
    
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
            
            return True
        except Exception as e:
            print(f"添加专有名词失败: {e}")
            return False
    
    def search_terminology(self, text: str, threshold: float = 0.8) -> List[Dict]:
        """搜索文本中包含的专有名词"""
        found_terms = []
        try:
            text = self.escape_text(text)
            
            # 策略1: 精确匹配 - 检查专有名词是否直接出现在文本中
            exact_matches = self._find_exact_terminology_matches(text)
            found_terms.extend(exact_matches)
            
            # 策略2: 分段搜索 - 将长文本分解为更小的片段进行语义搜索
            if len(text) > 30:  # 对于较长的文本使用分段搜索
                semantic_matches = self._find_terminology_by_segments(text, threshold)
                found_terms.extend(semantic_matches)
            else:
                # 策略3: 整体语义搜索 - 对于较短的文本直接搜索
                semantic_matches = self._find_terminology_by_semantic_search(text, threshold)
                found_terms.extend(semantic_matches)
            
            # 去重和排序
            found_terms = self._deduplicate_and_sort_terms(found_terms)
            
        except Exception as e:
            print(f"搜索专有名词失败: {e}")
        return found_terms
    
    def _find_exact_terminology_matches(self, text: str) -> List[Dict]:
        """精确匹配专有名词"""
        exact_matches = []
        try:
            # 获取所有专有名词
            all_terms = self.get_terminology_list()
            text_lower = text.lower()
            
            for term_info in all_terms:
                term = term_info['term']
                if not term:
                    continue
                    
                # 检查是否在文本中出现（不区分大小写）
                if term.lower() in text_lower:
                    # 进一步检查是否是完整单词匹配（避免部分匹配）
                    import re
                    pattern = r'\b' + re.escape(term) + r'\b'
                    if re.search(pattern, text, re.IGNORECASE):
                        exact_matches.append({
                            'term': term,
                            'translation': term_info['translation'],
                            'domain': term_info['domain'],
                            'notes': term_info['notes'],
                            'similarity': 1.0,  # 精确匹配给最高相似度
                            'match_type': 'exact'
                        })
        except Exception as e:
            print(f"精确匹配专有名词失败: {e}")
        
        return exact_matches
    
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
            print(f"分段搜索专有名词失败: {e}")
        
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
            print(f"语义搜索专有名词失败: {e}")
        
        return semantic_matches
    
    def _split_text_into_segments(self, text: str, max_segment_length: int = 30) -> List[str]:
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
    

    def add_translation_history(self, config_name: str, source_text: str, target_text: str, 
                              context: str = "", llm_reason: str = "", file_path: str = "") -> bool:
        """添加翻译历史到特定配置的库中"""
        try:
            collection = self.get_translation_collection(config_name)
            source_text = self.escape_text(source_text)
            translation_id = hashlib.md5((source_text + target_text + str(datetime.now())).encode('utf-8')).hexdigest()
            
            metadata = {
                "source": source_text,
                "target": target_text,
                "context": context or "",
                "llm_reason": llm_reason or "",
                "file_path": file_path or "",
                "config_name": config_name,
                "created_at": datetime.now().isoformat(),
                "type": "translation"
            }
            
            # 添加到翻译历史库
            combined_document = self.get_combine_document(metadata)
            collection.upsert(
                ids=[translation_id],
                documents=[combined_document],
                metadatas=[metadata]
            )
            
            return True
        except Exception as e:
            print(f"添加翻译历史失败: {e}")
            return False
        
    def update_history_translation(self, config_name: str, translation_id: str, new_target:str) -> bool:
        collection = self.get_translation_collection(config_name)
        results = collection.get(ids=[translation_id])
        if not results or not results.get('metadatas') or not results['metadatas']:
            return False
        
        # 更新记录
        metadata = results['metadatas'][0]
        metadata['target'] = new_target

        document = self.get_combine_document(metadata)
        
        # 重新插入更新后的数据
        collection.upsert(
            ids=[translation_id],
            documents=[document],
            metadatas=[metadata]
        )
        return True
        
    def get_combine_document(self, metadata) -> str:
        """获取组合后的文档字符串"""
        source = metadata.get('source', '')
        target = metadata.get('target', '')
        context = metadata.get('context', '')
        file_path = metadata.get('file_path', '')
        
        return f"SOURCE:{source} TARGET:{target} CONTEXT:{context} FILE:{file_path}"
        
    def get_exact_translation(self, config_name: str, source_text: str):
        """获取精确匹配的翻译"""
        try:
            collection = self.get_translation_collection(config_name)
            
            # 使用安全的where查询，支持特殊字符转义
            source_text = self.escape_text(source_text)
            results = collection.get(where={"source": source_text})
            
            if results['metadatas']:
                return results['metadatas'][0]
            return None
        except Exception as e:
            print(f"获取精确翻译失败: {e}")
            return None
    
    def search_similar_translations(self, config_name: str, source_text: str, threshold: float, n_results: int = 3) -> List[Dict]:
        """搜索相似的历史翻译"""
        try:
            collection = self.get_translation_collection(config_name)
            source_text = self.escape_text(source_text)
            try:
                search_results = collection.query(
                    query_texts=[source_text],
                    n_results=n_results
                )
                
                similar_translations = []
                if search_results['distances'] and search_results['metadatas']:
                    for distance, metadata in zip(search_results['distances'][0], search_results['metadatas'][0]):
                        similarity = 1 - distance
                        if similarity > threshold:  # 相似度阈值
                            similar_translations.append({
                                'type': 'similar',
                                'source': metadata['source'],
                                'target': metadata['target'],
                                'context': metadata['context'],
                                'file_path': metadata['file_path'],
                                'similarity': similarity,
                                'created_at': metadata['created_at']
                            })
                
                return similar_translations
            except Exception as e:
                print(f"语义搜索翻译历史失败: {e}")
            
            return []
        except Exception as e:
            print(f"搜索相似翻译失败: {e}")
            return []
    
    def fuzzy_search_translations(self, config_name: str, search_text: str):
        """模糊搜索翻译历史（类似 MySQL 的 %s% 搜索）
        
        Args:
            config_name: 配置名称
            search_text: 搜索文本
        
        Returns:
            匹配的翻译记录列表
        """
        collection = self.get_translation_collection(config_name)
        search_results = collection.get(
                                where_document={"$contains": search_text}
                            )
        return search_results

    
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
            print(f"获取专有名词列表失败: {e}")
            return []
    
    def delete_terminology(self, term: str) -> bool:
        """删除专有名词"""
        try:
            term_id = hashlib.md5(term.encode('utf-8')).hexdigest()
            self.terminology_collection.delete(ids=[term_id])
            return True
        except Exception as e:
            print(f"删除专有名词失败: {e}")
            return False
    
    def analyze_high_frequency_words(self, translations: List[str], min_frequency: int = 2) -> List[Dict]:
        """分析文本列表中的高频词，作为潜在专有名词建议"""
        try:
            if not translations:
                return []
            
            # 合并所有文本
            all_text = " ".join(translations)
            
            # 提取英文单词
            words = re.findall(r'\b[A-Za-z]+(?:\s+[A-Za-z]+)*\b', all_text)
            word_freq = Counter(words)
            
            # 过滤高频词
            high_freq_words = []
            existing_terms = {term['term'].lower() for term in self.get_terminology_list()}
            
            # 常见停用词
            stop_words = {
                'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
                'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does',
                'did', 'will', 'would', 'could', 'should', 'this', 'that', 'these', 'those'
            }
            
            for word, freq in word_freq.most_common():
                word_clean = word.strip()
                if (freq >= min_frequency and 
                    len(word_clean) > 2 and  # 过滤过短的词
                    word_clean.lower() not in existing_terms and  # 不在现有专有名词中
                    word_clean.lower() not in stop_words):  # 过滤常见停用词
                    
                    # 检查是否已存在于专有名词库
                    exists_in_terminology = word_clean.lower() in existing_terms
                    
                    high_freq_words.append({
                        'word': word_clean,
                        'frequency': freq,
                        'exists_in_terminology': exists_in_terminology,
                        'suggested_chinese': '' if not exists_in_terminology else self._get_term_translation(word_clean)
                    })
            
            return high_freq_words[:20]  # 返回前20个建议
        except Exception as e:
            print(f"分析高频词失败: {e}")
            return []
        
    def escape_text(self, text: str) -> str:
        """转义文本中的特殊字符"""
        if not isinstance(text, str):
            return str(text)
        
        escaped_text = text.replace("'", "").replace('"', '')
        return escaped_text
    
    def _get_term_translation(self, term: str) -> str:
        """获取专有名词的翻译"""
        try:
            term_list = self.get_terminology_list()
            for term_info in term_list:
                if term_info['term'].lower() == term.lower():
                    return term_info['translation']
            return ''
        except:
            return ''
    
    def get_statistics(self, config_name: str = "") -> Dict:
        """获取统计信息"""
        try:
            stats = {
                'terminology_count': 0,
                'translation_history_count': 0,
                'config_collections': []
            }
            
            # 专有名词统计
            terminology_results = self.terminology_collection.get()
            if terminology_results['metadatas']:
                stats['terminology_count'] = len(terminology_results['metadatas'])
            
            # 翻译历史统计
            if config_name:
                collection = self.get_translation_collection(config_name)
                translation_results = collection.get()
                if translation_results['metadatas']:
                    stats['translation_history_count'] = len(translation_results['metadatas'])
            else:
                # 统计所有配置的翻译历史
                for collection_name in self.translation_collections:
                    collection = self.translation_collections[collection_name]
                    translation_results = collection.get()
                    count = len(translation_results['metadatas']) if translation_results['metadatas'] else 0
                    stats['config_collections'].append({
                        'config_name': collection_name,
                        'translation_count': count
                    })
            
            return stats
        except Exception as e:
            print(f"获取统计信息失败: {e}")
            return {}
    
    def export_data(self, output_path: str, config_name: str = ""):
        """导出数据"""
        try:
            export_data = {
                'exported_at': datetime.now().isoformat(),
                'terminology': [],
                'translations': {}
            }
            
            # 导出专有名词
            terminology_list = self.get_terminology_list()
            export_data['terminology'] = terminology_list
            
            # 导出翻译历史
            if config_name:
                collection = self.get_translation_collection(config_name)
                translation_results = collection.get()
                if translation_results['metadatas']:
                    export_data['translations'][config_name] = [
                        {
                            'source': metadata['source'],
                            'target': metadata['target'],
                            'context': metadata['context'],
                            'file_path': metadata['file_path'],
                            'created_at': metadata['created_at']
                        }
                        for metadata in translation_results['metadatas']
                    ]
            else:
                # 导出所有配置的翻译历史
                for collection_name in self.translation_collections:
                    collection = self.translation_collections[collection_name]
                    translation_results = collection.get()
                    if translation_results['metadatas']:
                        export_data['translations'][collection_name] = [
                            {
                                'source': metadata['source'],
                                'target': metadata['target'],
                                'context': metadata['context'],
                                'file_path': metadata['file_path'],
                                'created_at': metadata['created_at']
                            }
                            for metadata in translation_results['metadatas']
                        ]
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            print(f"导出数据失败: {e}")
            return False