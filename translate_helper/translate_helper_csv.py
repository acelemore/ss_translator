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
                    delimiter = sniffer.sniff(sample).delimiter
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
        应用翻译对象到CSV文件，使用重建方式保证准确性
        """
        if not translate_objects:
            return True
        
        try:
            # 按translation_key组织翻译对象
            translations_by_key = {}
            for obj in translate_objects:
                if obj.approved and obj.approved_text:
                    translations_by_key[obj.translation_key] = obj.approved_text
            
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
                    delimiter = sniffer.sniff(sample).delimiter
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
                            
                            # 重建提取过程，找到需要翻译的文本片段
                            if extract_method in self.extract_functions:
                                extract_func = self.extract_functions[extract_method]
                                extracted_objects = extract_func([cell_value])
                                
                                # 应用翻译到每个提取的对象
                                modified_cell_value = cell_value
                                for obj in extracted_objects:
                                    key = self.generate_translation_key(obj, row_index, field_name)
                                    if key in translations_by_key:
                                        # 直接替换原始文本
                                        modified_cell_value = modified_cell_value.replace(
                                            obj.original_text, 
                                            translations_by_key[key]
                                        )
                                
                                row[field_name] = modified_cell_value
                    
                    rows.append(row)
            
            # 写入翻译后的CSV文件
            final_file_path = str(actual_file_path).replace('.csv', '.csv.translated')
            with open(final_file_path, 'w', encoding='utf-8', newline='') as csvfile:
                if fieldnames:
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)
            
            self.logger.info(f"成功应用 {len(translations_by_key)} 个翻译到CSV文件: {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(traceback.format_exc())
            self.logger.error(f"应用CSV翻译失败 {file_path}: {e}")
            if os.path.exists(final_file_path):
                os.remove(final_file_path)  # 删除失败的文件
            return False
        
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
        # 尝试匹配OR分隔的内容
        matches = text.split('OR')
        # 为每个匹配的字符串创建TranslationObject
        for match in matches:
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