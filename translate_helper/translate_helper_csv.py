
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
import csv
import os
import re
import traceback
import hashlib
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging
from .translate_helper_base import TranslateHelper
from translation_object import TranslationObject
import io



class TranslateHelperCSV(TranslateHelper):
    """
    CSV文件翻译助手
    支持用户详细定义每个字段用哪个文字提取方法
    """
    
    # 类变量：支持的文件类型
    support_file_type = "csv"
    
    def __init__(self, logger: logging.Logger, translate_config: Dict[str, Any]):
        super().__init__(logger, translate_config)
        
        # 导入文字提取函数
        self.extract_functions = {
            "get_raw_text": get_raw_text,
            "get_script_text": get_script_text,
            "get_options_text": get_options_text,
            "get_text_with_OR": get_text_with_or
        }

        # 文字应用函数
        self.apply_functions = {
            "get_raw_text": self._apply_raw_translations,
            "get_script_text": self._apply_script_translations,
            "get_options_text": self._apply_options_translations,
            "get_text_with_OR": self._apply_or_translations
        }
    
    @classmethod
    def get_support_parse_func(cls) -> Dict[str, str]:
        """获取支持的解析函数及说明"""
        return {
            "get_raw_text": "从CSV单元格中提取原始文本",
            "get_script_text": "从CSV单元格中提取脚本文本",
            "get_options_text": "从CSV单元格中提取选项文本",
            "get_text_with_OR": "从CSV单元格中提取OR分隔的内容"
        }
    

    
    def extract_translate_objects(self, file_path: str) -> List[TranslationObject]:
        """
        从CSV文件中提取需要翻译的对象
        """
        
        field_config = self.translate_config[file_path]
        translate_objects = []
        actual_file_path = self.ensure_translated_file(file_path)
        
        try:
            # 直接使用CSV reader读取文件
            with open(actual_file_path, 'r', encoding='utf-8', newline='') as csvfile:
                # 使用sniffer检测CSV格式
                sniffer = csv.Sniffer()
                delimiter = ','
                try:
                    sample = csvfile.read(1024)
                    csvfile.seek(0)
                    # delimiter = sniffer.sniff(sample).delimiter
                except Exception as e:
                    self.logger.warning(f"无法自动检测CSV分隔符，使用默认逗号: {e}")
                
                reader = csv.DictReader(csvfile, delimiter=delimiter)
                
                for row_index, row in enumerate(reader):
                    for field_name, extract_method in field_config.items():
                        if field_name in row:
                            cell_value = row[field_name]
                            if not cell_value or not cell_value.strip():
                                continue
                            
                            # 使用指定的提取方法处理文本
                            if extract_method in self.extract_functions:
                                extract_func = self.extract_functions[extract_method]
                                extracted_objects:list[TranslationObject] = extract_func([cell_value])
                                
                                # 为每个提取的对象设置正确的标识信息
                                for obj in extracted_objects:
                                    obj.file_name = file_path
                                    obj.context = field_name  # CSV字段名作为上下文
                                    
                                    # 生成唯一key：字段名+行号+原文哈希
                                    key = self.generate_translation_key(obj, row_index, field_name)
                                    obj.translation_key = key
                                    
                                    translate_objects.append(obj)
        
            self.logger.info(f"从CSV文件 {file_path} 提取了 {len(translate_objects)} 个翻译对象")
            return translate_objects
            
        except Exception as e:
            self.logger.error(f"提取CSV文件失败 {file_path}: {e}")
            return []
    
    def generate_translation_key(self, translation_obj: TranslationObject, 
                                row_index: int, field_name: str) -> str:
        """
        为CSV翻译对象生成唯一标识key
        格式：字段名:行号:原文哈希
        使用MD5确保跨进程一致性
        """
        # 使用MD5确保哈希值在不同进程间保持一致
        text_hash = hashlib.md5(translation_obj.original_text.encode('utf-8')).hexdigest()[:16]
        return f"{field_name}:{row_index}:{text_hash}"
    
    def get_llm_user_prompt(self, translation_obj: TranslationObject,
                           similar_translations: Optional[List[Dict]] = None,
                           found_terms: Optional[List[Dict]] = None) -> str:
        """
        获取CSV文件专用的LLM用户提示语
        """
        user_prompt_parts = []
        
        # 添加CSV特定的上下文信息
        user_prompt_parts.append(f"【文件类型】CSV数据文件")
        user_prompt_parts.append(f"【字段名称】{translation_obj.context}")
        user_prompt_parts.append("")
        
        # 调用父类方法添加其他信息
        parent_prompt = super().get_llm_user_prompt(
            translation_obj, 
            similar_translations or [], 
            found_terms or []
        )
        user_prompt_parts.append(parent_prompt)
        
        return "\n".join(user_prompt_parts)
    
    def apply_translate_objects(self, translate_objects: List[TranslationObject], 
                              file_path: str) -> bool:
        """
        应用翻译对象到CSV文件，使用精确替换方式保证准确性
        """
        if not translate_objects:
            return True
        
        try:
            # 按translation_key组织翻译对象
            translations_by_key = {}
            for obj in translate_objects:
                if obj.approved and obj.approved_text:
                    translations_by_key[obj.translation_key] = obj
            
            if not translations_by_key:
                self.logger.info(f"没有已审核的翻译需要应用到 {file_path}")
                return True
            
            field_config = self.translate_config[file_path]
            actual_file_path = self.ensure_translated_file(file_path)
            
            # 读取原始CSV文件
            rows = []
            fieldnames = None
            
            with open(actual_file_path, 'r', encoding='utf-8', newline='') as csvfile:
                # 使用sniffer检测CSV格式
                sniffer = csv.Sniffer()
                delimiter = ','
                try:
                    sample = csvfile.read(1024)
                    csvfile.seek(0)
                    # delimiter = sniffer.sniff(sample).delimiter
                except Exception as e:
                    self.logger.warning(f"无法自动检测CSV分隔符，使用默认逗号: {e}")
                
                reader = csv.DictReader(csvfile, delimiter=delimiter)
                fieldnames = reader.fieldnames
                
                for row_index, row in enumerate(reader):
                    # 为每个配置的字段应用翻译
                    for field_name, extract_method in field_config.items():
                        if field_name in row:
                            cell_value = row[field_name]
                            if not cell_value or not cell_value.strip():
                                continue
                            
                            # 使用精确替换方法应用翻译
                            if extract_method in self.extract_functions:
                                # 收集此单元格需要翻译的对象
                                cell_translations = {}
                                extract_func = self.extract_functions[extract_method]
                                extracted_objects = extract_func([cell_value])
                                
                                for obj in extracted_objects:
                                    key = self.generate_translation_key(obj, row_index, field_name)
                                    if key in translations_by_key:
                                        cell_translations[obj.original_text] = translations_by_key[key].approved_text
                                
                                # 使用精确替换函数应用翻译
                                if cell_translations:
                                    apply_func = self.apply_functions.get(extract_method)
                                    if apply_func:
                                        modified_cell_value = apply_func(cell_value, cell_translations)
                                        row[field_name] = modified_cell_value
                                    else:
                                        self.logger.error(f"未知的提取方法 {extract_method}，无法应用翻译")
                    rows.append(row)
            
            # 写入翻译后的CSV文件
            final_file_path = str(actual_file_path).replace('.csv', '.csv.translated')
            with open(final_file_path, 'w', encoding='utf-8', newline='') as csvfile:
                if fieldnames:
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)
            
            applied_count = len([t for t in translations_by_key.values() if t.approved])
            self.logger.info(f"成功应用 {applied_count} 个翻译到CSV文件: {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(traceback.format_exc())
            self.logger.error(f"应用CSV翻译失败 {file_path}: {e}")
            if 'final_file_path' in locals() and os.path.exists(final_file_path):
                os.remove(final_file_path)  # 删除失败的文件
            return False
    
    def _apply_raw_translations(self, text: str, translations: dict) -> str:
        """直接替换原始文本中的内容"""
        if text in translations:
            return translations[text]
        return text
    
    def _apply_script_translations(self, text: str, translations: Dict[str, str]) -> str:
        """精确替换双引号中的脚本文本"""
        def replace_quoted_text(match):
            quoted_content = match.group(1)
            if quoted_content in translations:
                return f'"{translations[quoted_content]}"'
            return match.group(0)
        
        return re.sub(r'"((?:[^"\\]|\\.|[\r\n])*?)"', replace_quoted_text, text, flags=re.DOTALL)
    
    def _apply_options_translations(self, text: str, translations: Dict[str, str]) -> str:
        """精确替换选项文本中的内容"""
        lines = text.split('\n')
        result_lines = []
        
        for line in lines:
            original_line = line
            line = line.strip()
            if not line:
                result_lines.append(original_line)
                continue
            
            # 检查是否为数字:标识符:文本内容格式
            three_part_match = re.match(r'^(\d+:[^:]+:)(.+)$', line)
            if three_part_match:
                prefix = three_part_match.group(1)
                content = three_part_match.group(2)
                if content in translations:
                    result_lines.append(prefix + translations[content])
                else:
                    result_lines.append(original_line)
                continue
                
            # 检查是否为标识符:文本内容格式
            two_part_match = re.match(r'^([^:]+:)(.+)$', line)
            if two_part_match:
                prefix = two_part_match.group(1)
                content = two_part_match.group(2)
                if content in translations:
                    result_lines.append(prefix + translations[content])
                else:
                    result_lines.append(original_line)
                continue
            
            result_lines.append(original_line)
        
        return '\n'.join(result_lines)
    
    def _apply_or_translations(self, text: str, translations: Dict[str, str]) -> str:
        """精确替换OR分隔的文本"""
        # 检测原文使用的分隔符格式
        if '\r\nOR\r\n' in text:
            separator = '\r\nOR\r\n'
        elif '\nOR\n' in text:
            separator = '\nOR\n'
        else:
            # 如果没有OR分隔符，直接查找整个文本的翻译
            if text in translations:
                return translations[text]
            return text
            
        parts = text.split(separator)
        translated_parts = []
        
        for part in parts:
            if part in translations:
                translated_parts.append(translations[part])
            else:
                translated_parts.append(part)
        
        return separator.join(translated_parts)
        
def get_raw_text(text_list: list) -> list:
    """
    直接处理文本列表
    
    Args:
        text_list: 文本字符串列表
        
    Returns:
        list: TranslationObject列表
    """
    result = []
    
    for i, text in enumerate(text_list):
        translation_obj = TranslationObject(
            file_name="",  # 将在helper中设置
            original_text=text,
            context="",
            is_translated=False
        )
        result.append(translation_obj)
    
    return result

def get_text_with_or(text_list: list) -> list:
    """
    处理文本列表，匹配双引号中的内容或OR分隔的内容
    
    Args:
        text_list: 文本字符串列表
        
    Returns:
        list: TranslationObject列表
    """
    result = []
    
    for i, text in enumerate(text_list):
        # 尝试匹配OR分隔的内容，支持多种换行符格式
        # 先尝试 \r\nOR\r\n，再尝试 \nOR\n
        if '\r\nOR\r\n' in text:
            matches = text.split('\r\nOR\r\n')
        elif '\nOR\n' in text:
            matches = text.split('\nOR\n')
        else:
            # 如果没有OR分隔符，整个文本作为一个匹配项
            matches = [text]
            
        # 为每个匹配的字符串创建TranslationObject
        for match in matches:
            if match.strip():  # 过滤空字符串
                translation_obj = TranslationObject(
                    file_name="",  # 将在helper中设置
                    original_text=match,
                    context="",
                    is_translated=False
                )
                result.append(translation_obj)
    
    return result

def get_script_text(text_list: list) -> list:
    """
    处理脚本文本，从每个字符串中匹配双引号中的内容
    
    Args:
        file_path: 文件路径
        text_list: 文本字符串列表
        
    Returns:
        list: TranslationObject列表
    """
    result = []
    
    for i, text in enumerate(text_list):
        # 匹配任何双引号中的内容，支持转义引号和多行文本
        matches = re.findall(r'"((?:[^"\\]|\\.|[\r\n])*?)"', text, re.DOTALL)
        # 过滤掉空字符串
        filtered_matches = [match for match in matches if match.strip()]
        

        
        
        # 为每个匹配的字符串创建TranslationObject
        for match in filtered_matches:
            translation_obj = TranslationObject(
                file_name="",  # 将在helper中设置
                original_text=match,
                context="",
                is_translated=False
            )
            result.append(translation_obj)
    
    return result

def get_options_text(text_list: list) -> list:
    """
    处理选项文本，匹配两种格式的字符串
    
    Args:
        file_path: 文件路径
        text_list: 文本字符串列表
        
    Returns:
        list: TranslationObject列表
    """
    result = []
    
    for i, text in enumerate(text_list):
        matches = []
        
        # 按行分割文本
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # 检查是否为数字:标识符:文本内容格式
            three_part_match = re.match(r'^\d+:[^:]+:(.+)$', line)
            if three_part_match:
                matches.append(three_part_match.group(1))
                continue
                
            # 检查是否为标识符:文本内容格式
            two_part_match = re.match(r'^[^:]+:(.+)$', line)
            if two_part_match:
                matches.append(two_part_match.group(1))
        
        # 生成上下文（这里简化处理，实际应该根据文件路径生成）
        
        # 为每个匹配的字符串创建TranslationObject
        for match in matches:
            translation_obj = TranslationObject(
                file_name="",
                original_text=match,
                context="",
                is_translated=False
            )
            result.append(translation_obj)
    
    return result