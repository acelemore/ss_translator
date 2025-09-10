
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
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging
import subprocess
import tempfile
import json
import os
import re
from .translate_helper_base import TranslateHelper
from translation_object import TranslationObject


class JARTranslateHelper(TranslateHelper):
    """
    JAR文件翻译助手
    处理JAR文件中Java类文件的文本提取、翻译和应用
    """
    
    # 类变量：支持的文件类型
    support_file_type = "jar"
    
    def __init__(self, logger: logging.Logger, translate_config: Dict[str, Any]):
        super().__init__(logger, translate_config)
        self.extract_functions = {
            "extract_jar_strings": self._extract_jar_strings
        }
    
    @classmethod
    def get_support_parse_func(cls) -> Dict[str, str]:
        """获取支持的解析函数及说明"""
        return {
            "extract_jar_strings": "jar文件专用文本提取器"
        }
    
    def extract_translate_objects(self, file_path: str) -> List[TranslationObject]:
        """
        从JAR文件中提取需要翻译的对象
        """
        actual_file_path = str(self.ensure_translated_file(file_path))

        # 检查文件是否存在
        if not Path(actual_file_path).exists():
            self.logger.error(f"JAR文件不存在: {actual_file_path}")
            return []
        
        try:
            return self._extract_jar_strings(actual_file_path, file_path)
        except Exception as e:
            self.logger.error(f"提取JAR文件失败 {actual_file_path}: {e}")
            return []
    
    def _extract_jar_strings(self, jar_path: str, file_key_path) -> List[TranslationObject]:
        """
        从JAR文件中提取可翻译的文本
        直接使用JavaScript提取器进行文本提取
        """
        try:
            # 使用JavaScript提取器提取文本
            extracted_texts = self._extract_text_content_with_js(jar_path)
            
            if not extracted_texts:
                self.logger.warning(f"未能从JAR文件提取到文本: {jar_path}")
                return []
            
            # 收集所有TranslationObject
            result = []
            for category, files in extracted_texts.items():
                if category == 'class_strings':  # 只处理class文件中的字符串
                    for filename, string_objects in files.items():
                        # 检查是否为新格式（包含上下文信息的对象数组）
                        if string_objects and isinstance(string_objects[0], dict) and 'text' in string_objects[0]:
                            # 新格式：包含上下文信息和translation_key
                            for index, string_obj in enumerate(string_objects):
                                translation_obj = TranslationObject(
                                    file_name=file_key_path,
                                    original_text=string_obj['text'],
                                    context=string_obj['context'],  # 函数名作为上下文
                                    is_translated=False
                                )
                                
                                # 使用JavaScript提取器生成的translation_key，如果没有则生成
                                if 'translation_key' in string_obj:
                                    translation_obj.translation_key = string_obj['translation_key']
                                else:
                                    key = self.generate_translation_key(translation_obj, filename, index)
                                    translation_obj.translation_key = key
                                
                                result.append(translation_obj)
                        else:
                            # 旧格式：字符串数组
                            for index, text in enumerate(string_objects):
                                translation_obj = TranslationObject(
                                    file_name=file_key_path,
                                    original_text=text,
                                    context=filename,  # 使用类文件名作为context
                                    dangerous=self._is_dangerous_text(text),
                                    is_translated=False
                                )
                                
                                # 生成唯一key
                                key = self.generate_translation_key(translation_obj, filename, index)
                                translation_obj.translation_key = key
                                
                                result.append(translation_obj)
            
            self.logger.info(f"从JAR文件 {jar_path} 提取了 {len(result)} 个翻译对象")
            return result
            
        except Exception as e:
            self.logger.error(f"JAR文件提取失败 {jar_path}: {e}")
            return []
    
    def generate_translation_key(self, translation_obj: TranslationObject, 
                                class_name: str, text_index: int) -> str:
        """
        为JAR翻译对象生成唯一标识key
        格式：类名:函数名:文本索引:原文哈希
        """
        text_hash = str(self._hash_string_js_compatible(translation_obj.original_text))
        context = translation_obj.context or "unknown"
        return f"{class_name}:{context}:{text_index}:{text_hash}"
    
    def _hash_string_js_compatible(self, text: str) -> int:
        """
        JavaScript兼容的字符串哈希函数
        使用与jar_text_extractor.js中相同的算法
        """
        hash_value = 0
        if len(text) == 0:
            return hash_value
        for char in text:
            char_code = ord(char)
            hash_value = ((hash_value << 5) - hash_value) + char_code
            hash_value = hash_value & 0xFFFFFFFF  # 转换为32位整数
            if hash_value >= 0x80000000:  # 处理符号位
                hash_value -= 0x100000000
        return abs(hash_value)
    
    def _is_dangerous_text(self, text: str) -> bool:
        """
        判断文本是否为危险文本（可能是变量名、类名等）
        与_is_user_visible_text保持相反的逻辑
        """
        # 直接使用相反的逻辑
        return not self._is_user_visible_text(text)
    
    def get_llm_user_prompt(self, translation_obj: TranslationObject,
                           similar_translations: Optional[List[Dict]] = None,
                           found_terms: Optional[List[Dict]] = None) -> str:
        """
        获取JAR文件专用的LLM用户提示语
        """
        user_prompt_parts = []
        
        # 添加JAR特定的上下文信息
        user_prompt_parts.append(f"【文件类型】Java代码文件中硬编码字符串")
        user_prompt_parts.append(f"【调用该文本的函数】{translation_obj.context}")
        user_prompt_parts.append("")
        
        # 添加特殊提示
        user_prompt_parts.append("【特别注意】")
        user_prompt_parts.append("- 这是从Java代码中提取的字符串")
        user_prompt_parts.append("- 如果是错误消息、用户提示、界面文本，应该翻译")
        user_prompt_parts.append("- 如果是类名、变量名、配置键名、文件路径等，不应该翻译")
        user_prompt_parts.append("- 如果是日志输出、调试信息，不应该翻译")
        user_prompt_parts.append("- 你还需要根据【调用该文本的函数】进行推测, 这个文本是不是属于字符串类变量或者枚举类型, 比如字典的key, 这类文本也不应该翻译")
        user_prompt_parts.append("")
        
        # 调用父类方法添加其他信息
        parent_prompt = super().get_llm_user_prompt(translation_obj, similar_translations, found_terms)
        user_prompt_parts.append(parent_prompt)
        
        return "\n".join(user_prompt_parts)
    
    def apply_translate_objects(self, translate_objects: List[TranslationObject], 
                              file_path: str) -> bool:
        """
        应用翻译对象到JAR文件
        """
        if not translate_objects:
            return True
        
        try:
            # 按translation_key组织翻译对象
            translations_by_key = {}
            for obj in translate_objects:
                if hasattr(obj, 'translation_key') and obj.translation:
                    translations_by_key[obj.translation_key] = obj
            
            # 使用JavaScript翻译器应用翻译
            file_path = str(self.ensure_translated_file(file_path))
            success = self._apply_translations_with_js(file_path, translations_by_key)
            
            if success:
                self.logger.info(f"成功应用翻译到JAR文件: {file_path}")
            else:
                self.logger.error(f"应用JAR翻译失败: {file_path}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"应用JAR翻译失败 {file_path}: {e}")
            return False
    
    def _apply_translations_with_js(self, jar_path: str, translations_by_key: Dict[str, TranslationObject]) -> bool:
        """
        使用JavaScript翻译器应用翻译
        """
        
        # JavaScript翻译器路径
        js_dir = Path(__file__).parent / "js"
        js_script = js_dir / "simple_jar_translator.js"
        
        if not js_script.exists():
            self.logger.error(f"JavaScript翻译器不存在: {js_script}")
            return False
        
        # 准备翻译数据 - 转换为JS需要的格式
        js_translations = []
        for key, obj in translations_by_key.items():
            if obj.translation and obj.translation.strip():
                # 获取待应用的文本
                approved_text = obj.approved_text if obj.approved else obj.original_text
                # 对approved_text进行二次处理，处理控制字符与中文字符的空格问题
                processed_text = self._process_control_chars_with_chinese(approved_text)
                
                js_translations.append({
                    'original': obj.original_text,
                    'translation': processed_text,
                    'translation_key': obj.translation_key,
                    'context': obj.context
                })
        
        if not js_translations:
            self.logger.warning("没有需要应用的翻译")
            return True
        
        # 创建临时翻译文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False, encoding='utf-8') as f:
            for trans in js_translations:
                f.write(json.dumps(trans, ensure_ascii=False) + '\n')
            temp_file = f.name
        
        try:
            # 生成输出文件路径
            output_path = jar_path.replace('.jar', '.jar.translated')
            
            # 执行JavaScript翻译器
            cmd = [
                'node',
                str(js_script),
                jar_path,
                output_path,
                temp_file
            ]
            
            self.logger.info(f"执行JavaScript翻译器: {len(js_translations)} 条翻译")
            
            result = subprocess.run(
                cmd,
                cwd=js_dir,
                capture_output=True,
                text=True,
                timeout=300,
                encoding='utf-8'
            )
            
            if result.returncode == 0:
                self.logger.info("JavaScript翻译器执行成功")
                return True
            else:
                self.logger.error(f"JavaScript翻译器执行失败: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"执行JavaScript翻译器出错: {e}")
            return False
        finally:
            # 清理临时文件
            try:
                Path(temp_file).unlink()
            except:
                pass
    
    def _extract_text_content_with_js(self, jar_path: str) -> Dict[str, Any]:
        """
        使用JavaScript方法提取JAR中的文本内容
        """
        # JavaScript文本提取器路径
        js_extractor_dir = Path(__file__).parent / "js"
        js_extractor_script = js_extractor_dir / "jar_text_extractor.js"
        
        if not js_extractor_script.exists():
            self.logger.error(f"JavaScript文本提取器不存在: {js_extractor_script}")
            return {}
        
        # 创建临时输出文件
        temp_output = js_extractor_dir / "temp_extracted_texts.json"
        
        try:
            # 构建JavaScript命令
            abs_jar_path = os.path.abspath(jar_path)
            abs_output_path = os.path.abspath(temp_output)
            
            cmd = [
                'node',
                str(js_extractor_script),
                abs_jar_path,
                abs_output_path
            ]
            
            # 执行JavaScript提取器
            result = subprocess.run(
                cmd,
                cwd=js_extractor_dir,
                capture_output=True,
                text=True,
                timeout=300,  # 5分钟超时
                encoding='utf-8'
            )
            
            if result.returncode == 0:
                # 读取提取结果
                if temp_output.exists():
                    with open(temp_output, 'r', encoding='utf-8') as f:
                        js_extracted = json.load(f)
                    
                    # 应用Python的过滤规则
                    filtered_texts = self._apply_text_filters(js_extracted)
                    
                    return filtered_texts
            else:
                self.logger.error(f"JavaScript文本提取器执行失败 (退出码: {result.returncode})")
                if result.stderr:
                    self.logger.error(f"错误输出: {result.stderr}")
                return {}
                
        except subprocess.TimeoutExpired:
            self.logger.error("JavaScript文本提取器执行超时")
            return {}
        except Exception as e:
            self.logger.error(f"执行JavaScript文本提取器出错: {e}")
            return {}
        finally:
            # 清理临时文件
            if temp_output.exists():
                try:
                    temp_output.unlink()
                except Exception as e:
                    self.logger.warning(f"清理临时文件失败: {e}")
    
    def _apply_text_filters(self, js_extracted: Dict[str, Any]) -> Dict[str, Any]:
        """对JavaScript提取的文本应用Python的过滤规则"""
        filtered_texts = {
            'properties_files': js_extracted.get('properties_files', {}),
            'json_files': js_extracted.get('json_files', {}),
            'class_strings': {},
            'other_text_files': js_extracted.get('other_text_files', {})
        }
        
        # 对class文件中的字符串应用过滤规则
        class_strings = js_extracted.get('class_strings', {})
        total_before = 0
        total_after = 0
        
        for filename, strings in class_strings.items():
            total_before += len(strings)
            filtered_strings = []
            
            for text in strings:
                if self._is_user_visible_text(text):
                    filtered_strings.append(text)
            
            if filtered_strings:
                filtered_texts['class_strings'][filename] = filtered_strings
                total_after += len(filtered_strings)
        
        self.logger.info(f"过滤前: {total_before} 个字符串，过滤后: {total_after} 个字符串，过滤比例: {(total_after/max(1, total_before)*100):.1f}%")
        
        return filtered_texts
    
    def _is_user_visible_text(self, text: str) -> bool:
        """
        判断是否为用户可见的文本
        优化后的筛选规则（放宽要求）：
        1. 长度大于3
        2. 不含斜杠（通常是文件路径）
        3. 不是纯数字
        4. 不是纯大写常量名
        5. 不包含下划线（通常是变量名）
        6. 不是大小驼峰风格（HappyMan, happyMan等）
        """
        
        # 提取实际文本内容
        if isinstance(text, dict):
            actual_text = text.get('text', '')
        else:
            actual_text = str(text)
        
        actual_text = actual_text.strip()
        
        # 1. 最小长度要求
        if len(actual_text) <= 3:
            return False
        
        # 2. 包含斜杠的通常是文件路径，排除
        if '/' in actual_text or '\\' in actual_text:
            return False
        
        # 3. 纯数字排除
        if actual_text.isdigit():
            return False
        
        # 4. 全大写且包含下划线的可能是常量名
        if actual_text.isupper() and ' ' not in actual_text:
            return False
        
        if '_' in actual_text:
            return False
        
        # 5. 检查是否为驼峰风格（大驼峰或小驼峰）
        if self._is_camel_case(actual_text):
            return False
        
        # 6. 明显的技术性模式
        technical_patterns = [
            r'^[a-z]+\.[a-z]+\.',  # 包名
            r'^L[A-Z]',  # 类引用
            r'^\[',  # 数组类型
            r'^[IV]$',  # 单独的I或V（方法签名参数类型）
            r'^\([LIV\[\;]*\)[LIV\[\;]*$',  # 方法签名：(参数)返回值
            r'^[A-Z_]+$',  # 全大写常量名（无空格）
        ]
        
        for pattern in technical_patterns:
            if re.match(pattern, actual_text):
                return False
        
        # 其他情况都认为是可能的用户文本
        return True
    
    def _is_camel_case(self, text: str) -> bool:
        """
        检测是否为驼峰命名风格
        包括大驼峰（PascalCase）和小驼峰（camelCase）
        """
        # 排除包含空格、特殊字符的文本
        if ' ' in text:
            return False
        
        # 长度小于2的不考虑驼峰
        if len(text) < 2:
            return False
        
        # 检查是否包含大写字母（驼峰的基本特征）
        has_upper = any(c.isupper() for c in text)
        has_lower = any(c.islower() for c in text)
        
        # 必须同时包含大小写字母
        if not (has_upper and has_lower):
            return False
        
        # 大驼峰：首字母大写，后面有小写字母，然后有大写字母
        # 小驼峰：首字母小写，后面有大写字母
        
        # 检查是否符合驼峰模式：字母后跟大写字母
        
        camel_pattern = r'[a-z][A-Z]|[A-Z][a-z][A-Z]'
        if re.search(camel_pattern, text):
            return True
        
        return False
    
    def _process_control_chars_with_chinese(self, text: str) -> str:
        """
        处理控制字符与中文字符之间的空格问题
        当ord(char) < 32时，说明是个控制字符，这个字符不能直接与中文字符连接，要加空格
        如果控制字符的前一个是中文字符，则在前面加空格
        如果控制字符的后面是中文字符，则后面要加空格
        前后都是中文则前后都要加个空格
        """
        if not text:
            return text
        
        result = []
        chars = list(text)
        
        for i, char in enumerate(chars):
            if ord(char) < 32:  # 控制字符
                # 检查前一个字符是否为中文
                prev_is_chinese = False
                if i > 0:
                    prev_char = chars[i - 1]
                    prev_is_chinese = self._is_chinese_char(prev_char)
                
                # 检查后一个字符是否为中文
                next_is_chinese = False
                if i < len(chars) - 1:
                    next_char = chars[i + 1]
                    next_is_chinese = self._is_chinese_char(next_char)
                
                # 根据前后字符情况添加空格
                if prev_is_chinese:
                    result.append(' ')
                
                result.append(char)
                
                if next_is_chinese:
                    result.append(' ')
            else:
                result.append(char)
        
        return ''.join(result)
    
    def _is_chinese_char(self, char: str) -> bool:
        """
        判断字符是否为中文字符
        包括汉字、中文标点符号等
        """
        if not char:
            return False
        
        # 中文字符的Unicode范围
        chinese_ranges = [
            (0x4E00, 0x9FFF),   # 汉字基本区
            (0x3400, 0x4DBF),   # 汉字扩展A区
            (0x20000, 0x2A6DF), # 汉字扩展B区
            (0x2A700, 0x2B73F), # 汉字扩展C区
            (0x2B740, 0x2B81F), # 汉字扩展D区
            (0x2B820, 0x2CEAF), # 汉字扩展E区
            (0x3000, 0x303F),   # 中文标点符号
            (0xFF00, 0xFFEF),   # 全角字符
        ]
        
        char_code = ord(char)
        for start, end in chinese_ranges:
            if start <= char_code <= end:
                return True
        
        return False