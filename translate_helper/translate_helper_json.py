import json
import re
import hashlib
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging
from .translate_helper_base import TranslateHelper
from translation_object import TranslationObject


class JSONTranslateHelper(TranslateHelper):
    """
    JSON文件翻译助手
    处理JSON文件的文本提取、翻译和应用
    """
    
    # 类变量：支持的文件类型
    support_file_type = "json"
    
    def __init__(self, logger: logging.Logger, translate_config: Dict[str, Any]):
        super().__init__(logger, translate_config)
        self.extract_functions = {
            "extract_json_leaf_values": self._extract_json_leaf_values # 目前只有一个方法, 没啥用, 但还是加上, 作为开发模板
        }
        
    
    @classmethod
    def get_support_parse_func(cls) -> Dict[str, str]:
        """获取支持的解析函数"""
        return {
            "extract_json_leaf_values": "提取json文件字典内容的叶子节点字符串"
        }
    
    def extract_translate_objects(self, file_path: str) -> List[TranslationObject]:
        """
        从JSON文件中提取需要翻译的对象
        """
        
        
        abs_path = str(self.ensure_translated_file(file_path))
        
        try:
            with open(abs_path, 'r', encoding='utf-8') as f:
                json_content = f.read()
            
            return self._extract_json_leaf_values(file_path, json_content)
            
                
        except Exception as e:
            self.logger.error(f"提取JSON文件失败 {file_path}: {e}")
            return []
    
    def _extract_json_leaf_values(self, file_path: str, json_content: str) -> List[TranslationObject]:
        """
        从JSON内容中提取所有叶子节点的字符串值用于翻译
        支持带注释和尾随逗号的非标准JSON
        """
        try:
            # 预处理JSON内容，移除注释和多余的逗号
            cleaned_json = self._clean_json_content(json_content)
            
            # 解析JSON
            data = json.loads(cleaned_json)
            
            # 提取叶子节点的字符串值
            result = []
            self._extract_leaf_strings(data, result, file_path)
            
            return result
            
        except Exception as e:
            self.logger.error(f"解析JSON内容失败: {e}")
            return []
    
    def _clean_json_content(self, content: str) -> str:
        """
        清理JSON内容，移除注释和处理尾随逗号
        同时处理非标准JSON内容（如未引用的常量、数字后缀等）
        """
        # 存储原始的非标准内容，用于后续恢复
        self._non_standard_placeholders = {}
        
        lines = content.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # 移除行内注释（#开头的注释）
            if '#' in line:
                # 检查#是否在字符串内
                in_string = False
                escape_next = False
                comment_pos = -1
                
                for i, char in enumerate(line):
                    if escape_next:
                        escape_next = False
                        continue
                        
                    if char == '\\':
                        escape_next = True
                    elif char == '"':
                        in_string = not in_string
                    elif char == '#' and not in_string:
                        comment_pos = i
                        break
                
                if comment_pos >= 0:
                    line = line[:comment_pos].rstrip()
            
            # 处理带f后缀的数字（如 -1f, 0.5f, 2f 等）
            # 匹配在对象值或数组元素位置的带f后缀的数字
            def replace_f_numbers(match):
                prefix = match.group(1)
                number_with_f = match.group(2)
                suffix = match.group(3)
                # 去掉f后缀，保留纯数字
                number_str = number_with_f.rstrip('f')
                
                # 如果是以点开头的小数（如.3），前面加0
                if number_str.startswith('.'):
                    number_str = '0' + number_str
                elif number_str.startswith('-.'):
                    number_str = '-0.' + number_str[2:]
                
                try:
                    # 验证是否为有效数字
                    float(number_str)
                    return f'{prefix}{number_str}{suffix}'
                except ValueError:
                    # 如果不是有效数字，创建占位符
                    placeholder = self._create_placeholder(number_with_f)
                    return f'{prefix}"{placeholder}"{suffix}'
            
            # 匹配对象值位置的f后缀数字: "key": -1f,
            line = re.sub(r'(:\s*)(-?\d*\.?\d+f)(\s*[,}\]])', replace_f_numbers, line)
            # 匹配数组中的f后缀数字: [-1f, 0.5f]
            line = re.sub(r'(\[\s*)(-?\d*\.?\d+f)(\s*[,\]])', replace_f_numbers, line)
            line = re.sub(r'(,\s*)(-?\d*\.?\d+f)(\s*[,\]])', replace_f_numbers, line)
            
            # 处理没有f后缀但以点开头的小数（如 .3, -.5）
            def fix_decimal_numbers(match):
                prefix = match.group(1)
                number_str = match.group(2)
                suffix = match.group(3)
                
                # 如果是以点开头的小数，前面加0
                if number_str.startswith('.'):
                    number_str = '0' + number_str
                elif number_str.startswith('-.'):
                    number_str = '-0.' + number_str[2:]
                
                return f'{prefix}{number_str}{suffix}'
            
            # 匹配以点开头的小数
            line = re.sub(r'(:\s*)(-?\.\d+)(\s*[,}\]])', fix_decimal_numbers, line)
            line = re.sub(r'(\[\s*)(-?\.\d+)(\s*[,\]])', fix_decimal_numbers, line)
            line = re.sub(r'(,\s*)(-?\.\d+)(\s*[,\]])', fix_decimal_numbers, line)
            
            # 处理非标准JSON内容（如 [STATIONS], [BACKGROUND] 等）
            # 匹配模式：[大写字母、下划线、数字的组合]
            def replace_bracket_constants(match):
                return self._create_placeholder(match.group(0))
            
            line = re.sub(r'\[([A-Z_][A-Z0-9_]*)\]', replace_bracket_constants, line)
            
            # 处理单独的未引用常量（如在数组中的 STATIONS）
            # 匹配在数组或对象值位置的未引用标识符
            def replace_object_constants(match):
                placeholder = self._create_placeholder(match.group(1))
                return f': "{placeholder}"{match.group(2)}'
            
            def replace_array_constants(match):
                placeholder = self._create_placeholder(match.group(1))
                return f'["{placeholder}"]'
            
            line = re.sub(r':\s*([A-Z_][A-Z0-9_]*)\s*([,}\]])', replace_object_constants, line)
            line = re.sub(r'\[\s*([A-Z_][A-Z0-9_]*)\s*\]', replace_array_constants, line)
            
            cleaned_lines.append(line)
        
        cleaned_content = '\n'.join(cleaned_lines)
        
        # 处理尾随逗号（在}或]前的逗号）- 更强力的处理
        # 处理多层嵌套的尾随逗号
        while True:
            old_content = cleaned_content
            # 移除对象末尾的逗号
            cleaned_content = re.sub(r',(\s*})', r'\1', cleaned_content)
            # 移除数组末尾的逗号
            cleaned_content = re.sub(r',(\s*])', r'\1', cleaned_content)
            # 如果没有变化，说明处理完毕
            if cleaned_content == old_content:
                break
        
        return cleaned_content
    
    def _create_placeholder(self, original_value: str) -> str:
        """
        为非标准JSON内容创建占位符
        """
        placeholder = f"__NON_STANDARD_JSON_PLACEHOLDER_{len(self._non_standard_placeholders)}__"
        self._non_standard_placeholders[placeholder] = original_value
        return placeholder
    
    def _extract_leaf_strings(self, obj, result_list: List[TranslationObject], 
                             file_path: str, path: str = ""):
        """
        递归提取JSON对象中的叶子节点字符串值
        """
        if isinstance(obj, dict):
            for key, value in obj.items():
                current_path = self.get_current_node_path(path, key)
                self._extract_leaf_strings(value, result_list, file_path, current_path)
        elif isinstance(obj, list):
            # 检查是否为字符串数组（叶子节点）
            if all(isinstance(item, str) for item in obj):
                # 这是一个字符串数组，将每个符合条件的字符串加入翻译列表
                for index, item in enumerate(obj):
                    if self._should_include_string(item):
                        array_path = self.get_current_node_path(path, index)
                        translation_obj = TranslationObject(
                            file_name=file_path,
                            original_text=item,
                            context=path,  # 使用数组的路径作为上下文
                            dangerous=self._is_dangerous_text(item),
                            is_translated=False
                        )
                        
                        # 使用统一的key生成方法
                        key = self.generate_translation_key_for_text(item, array_path)
                        translation_obj.translation_key = key
                        
                        result_list.append(translation_obj)
            else:
                # 混合类型数组，继续递归处理每个元素
                for i, item in enumerate(obj):
                    current_path = self.get_current_node_path(path, i)
                    self._extract_leaf_strings(item, result_list, file_path, current_path)
        elif isinstance(obj, str):
            # 只有符合条件的字符串才加入翻译列表
            if self._should_include_string(obj):
                context = path.split('.')[-1] if '.' in path else path
                
                translation_obj = TranslationObject(
                    file_name=file_path,
                    original_text=obj,
                    context=context,
                    dangerous=self._is_dangerous_text(obj),
                    is_translated=False
                )
                
                # key生成方法
                key = self.generate_translation_key_for_text(obj, path)
                translation_obj.translation_key = key
                
                result_list.append(translation_obj)
    
    def generate_translation_key(self, translation_obj: TranslationObject, 
                                index: str) -> str:
        """
        为JSON翻译对象生成唯一标识key（向后兼容方法）
        现在内部调用统一的key生成方法
        """
        return self.generate_translation_key_for_text(translation_obj.original_text, index)
    
    def get_current_node_path(self, base_path: str, key_or_index) -> str:
        """
        获取当前节点的路径字符串
        统一的路径生成逻辑，确保提取和应用时的一致性
        
        Args:
            base_path: 基础路径
            key_or_index: 字典的key或数组的索引
            
        Returns:
            完整的节点路径
        """
        if isinstance(key_or_index, int):
            # 数组索引
            return f"{base_path}[{key_or_index}]" if base_path else f"[{key_or_index}]"
        else:
            # 字典key
            return f"{base_path}.{key_or_index}" if base_path else str(key_or_index)
    
    def generate_translation_key_for_text(self, text: str, node_path: str) -> str:
        """
        为指定文本和节点路径生成翻译key
        统一的key生成逻辑
        使用MD5确保跨进程一致性
        
        Args:
            text: 原始文本
            node_path: 节点路径
            
        Returns:
            翻译key
        """
        # 使用MD5确保哈希值在不同进程间保持一致
        text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()[:16]
        return f"{node_path}:{text_hash}"
    
    def _should_include_string(self, text: str) -> bool:
        """
        判断字符串是否应该被包含在翻译列表中
        """
        # 去除首尾空白
        text = text.strip()
        
        # 空字符串不包含
        if not text:
            return False
        
        # 跳过非标准JSON占位符
        if "__NON_STANDARD_JSON_PLACEHOLDER_" in text:
            return False
        
        # 不能含有下划线
        if '_' in text:
            return False
        
        # 不能是路径字符串
        if ('/' in text or '\\' in text):
            return False
        
        return True
    
    def _is_dangerous_text(self, text: str) -> bool:
        """
        判断文本是否为危险文本（可能是变量名）
        """
        text = text.strip()
        
        # 检查是否为单词（除了头尾外不包含空格）
        if len(text) > 0 and ' ' not in text.strip():
            return True
        
        return False
    
    def get_llm_user_prompt(self, translation_obj: TranslationObject,
                           similar_translations: Optional[List[Dict]] = None,
                           found_terms: Optional[List[Dict]] = None) -> str:
        """
        获取JSON文件专用的LLM用户提示语
        """
        user_prompt_parts = []
        
        # 添加JSON特定的上下文信息
        user_prompt_parts.append(f"【文件类型】字典的叶子节点字符串")
        user_prompt_parts.append(f"【key路径】{translation_obj.context}")
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
        应用翻译对象到JSON文件
        """
        if not translate_objects:
            return True
        
        try:
            # 按translation_key组织翻译对象
            translations_by_key = {}
            for obj in translate_objects:
                if hasattr(obj, 'translation_key') and obj.translation:
                    translations_by_key[obj.translation_key] = obj
            
            original_file_path = self.ensure_translated_file(file_path)
            # 读取原始文件内容
            with open(original_file_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            # 应用翻译到内容
            translated_content = self._apply_translations_to_json_content(
                original_content, translations_by_key
            )
            final_file_path = str(original_file_path).replace('.json', '.json.translated')
            # 写回文件
            with open(final_file_path, 'w', encoding='utf-8') as f:
                f.write(translated_content)
            
            self.logger.info(f"成功应用翻译到JSON文件: {final_file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"应用JSON翻译失败 {file_path}: {e}")
            return False
    
    def _apply_translations_to_json_content(self, content: str, 
                                          translations_by_key: Dict[str, TranslationObject]) -> str:
        """
        将翻译应用到JSON内容中，基于key精确定位
        递归遍历JSON结构，为每个叶子节点生成key并查找对应翻译
        """
        try:
            # 预处理JSON内容，移除注释和多余的逗号
            cleaned_json = self._clean_json_content(content)
            
            # 解析JSON
            data = json.loads(cleaned_json)
            
            # 递归应用翻译
            translated_data = self._apply_translations_recursive(data, translations_by_key)
            
            # 将翻译后的数据转换回JSON字符串，保持格式
            return self._format_json_with_original_style(translated_data, content)
            
        except Exception as e:
            self.logger.error(f"应用翻译到JSON内容失败: {e}")
            # 如果解析失败，回退到原始的字符串替换方法
            return self._fallback_string_replacement(content, translations_by_key)
    
    def _apply_translations_recursive(self, obj, translations_by_key: Dict[str, TranslationObject], 
                                    path: str = ""):
        """
        递归遍历JSON对象，应用翻译到叶子节点
        """
        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                current_path = self.get_current_node_path(path, key)
                result[key] = self._apply_translations_recursive(value, translations_by_key, current_path)
            return result
        elif isinstance(obj, list):
            # 检查是否为字符串数组（叶子节点）
            if all(isinstance(item, str) for item in obj):
                # 这是一个字符串数组，处理每个字符串
                result = []
                for index, item in enumerate(obj):
                    if self._should_include_string(item):
                        array_path = self.get_current_node_path(path, index)
                        # 使用统一的key生成方法
                        key = self.generate_translation_key_for_text(item, array_path)
                        
                        # 查找翻译
                        if key in translations_by_key:
                            result.append(translations_by_key[key].approved_text if translations_by_key[key].approved else translations_by_key[key].original_text)
                        else:
                            result.append(item)  # 保持原文
                    else:
                        result.append(item)  # 不需要翻译的字符串
                return result
            else:
                # 混合类型数组，继续递归处理每个元素
                result = []
                for i, item in enumerate(obj):
                    current_path = self.get_current_node_path(path, i)
                    result.append(self._apply_translations_recursive(item, translations_by_key, current_path))
                return result
        elif isinstance(obj, str):
            # 只有符合条件的字符串才尝试翻译
            if self._should_include_string(obj):
                # 使用统一的key生成方法
                key = self.generate_translation_key_for_text(obj, path)
                
                # 查找翻译
                if key in translations_by_key:
                    return translations_by_key[key].approved_text if translations_by_key[key].approved else translations_by_key[key].original_text
            
            return obj  # 保持原文
        else:
            # 其他类型（数字、布尔值、null等）直接返回
            return obj
    
    def _format_json_with_original_style(self, data, original_content: str) -> str:
        """
        将翻译后的数据格式化为JSON字符串，尽量保持原始格式风格
        """
        # 检测原始内容的缩进风格
        indent = self._detect_json_indent(original_content)
        
        # 格式化JSON
        formatted_json = json.dumps(data, ensure_ascii=False, indent=indent, separators=(',', ': '))
        
        # 恢复非标准JSON内容
        formatted_json = self._restore_non_standard_content(formatted_json)
        
        # 如果原始内容有注释，尝试保留一些通用注释
        # if '#' in original_content:
        #     formatted_json = self._preserve_comments(formatted_json, original_content)
        
        return formatted_json
    
    def _restore_non_standard_content(self, formatted_json: str) -> str:
        """
        恢复非标准JSON内容（将占位符替换回原始内容）
        需要反向处理，确保嵌套的占位符也能正确恢复
        """
        if not hasattr(self, '_non_standard_placeholders'):
            return formatted_json
        
        result = formatted_json
        
        # 反复替换直到没有更多占位符需要替换
        max_iterations = 10  # 防止无限循环
        iteration = 0
        
        while iteration < max_iterations:
            old_result = result
            
            for placeholder, original_value in self._non_standard_placeholders.items():
                # 移除占位符周围的引号并替换为原始值
                result = result.replace(f'"{placeholder}"', original_value)
                # 也处理没有引号的情况（如果已经被前面的替换处理过）
                result = result.replace(placeholder, original_value)
            
            # 如果这一轮没有发生任何替换，说明完成了
            if result == old_result:
                break
                
            iteration += 1
        
        return result
    
    def _detect_json_indent(self, content: str) -> Optional[int]:
        """
        检测JSON内容的缩进风格
        """
        lines = content.split('\n')
        for line in lines:
            stripped = line.lstrip()
            if stripped and line != stripped:
                # 计算缩进长度
                indent = len(line) - len(stripped)
                if indent > 0:
                    return indent
        return 2  # 默认2个空格
    
    def _preserve_comments(self, formatted_json: str, original_content: str) -> str:
        """
        尝试在格式化的JSON中保留一些注释
        """
        # 这是一个简化的实现，可以根据需要扩展
        lines = original_content.split('\n')
        comment_lines = []
        
        for i, line in enumerate(lines):
            if line.strip().startswith('#'):
                comment_lines.append((i, line))
        
        # 如果有文件头注释，添加到格式化JSON的开头
        if comment_lines and comment_lines[0][0] < 5:  # 前5行内的注释认为是文件头注释
            header_comments = []
            for line_num, comment in comment_lines:
                if line_num < 5:
                    header_comments.append(comment)
                else:
                    break
            
            if header_comments:
                formatted_json = '\n'.join(header_comments) + '\n' + formatted_json
        
        return formatted_json
    
    def _fallback_string_replacement(self, content: str, 
                                   translations_by_key: Dict[str, TranslationObject]) -> str:
        """
        回退方法：使用简单的字符串替换（当JSON解析失败时使用）
        """
        result = content
        
        # 按字符串长度倒序排序，避免短字符串匹配到长字符串的一部分
        sorted_translations = []
        for key, obj in translations_by_key.items():
            if obj.translation:  # 确保有翻译内容
                final_text = obj.approved_text if obj.approved else obj.translation
                sorted_translations.append((obj.original_text, final_text))
        
        sorted_translations.sort(key=lambda x: len(x[0]), reverse=True)
        
        for original, translation in sorted_translations:
            # 转义特殊字符以用于正则表达式
            escaped_original = re.escape(original)
            escaped_translation = self._escape_json_string(translation)
            
            # 匹配JSON字符串格式的原文
            pattern = f'"{escaped_original}"'
            replacement = f'"{escaped_translation}"'
            
            result = re.sub(pattern, replacement, result)
        
        # 恢复非标准JSON内容
        result = self._restore_non_standard_content(result)
        
        return result
    
    def _escape_json_string(self, text: str) -> str:
        """转义JSON字符串中的特殊字符"""
        # 转义必要的字符
        text = text.replace('\\', '\\\\')  # 反斜杠
        text = text.replace('"', '\\"')    # 双引号
        text = text.replace('\n', '\\n')   # 换行符
        text = text.replace('\r', '\\r')   # 回车符
        text = text.replace('\t', '\\t')   # 制表符
        
        return text
