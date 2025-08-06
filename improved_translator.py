
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
改进的翻译器 - 负责LLM调用和翻译流程管理
分离关注点，使用helper类处理不同文件类型的具体逻辑
"""
import json
import logging
import os
import shutil
import threading
from pathlib import Path
import traceback
from typing import Dict, List, Any, Optional, Tuple
from openai import OpenAI

from translation_object import TranslationObject
from translate_helper.translate_helper_base import TranslateHelper
from config_manager import config_manager
from progress_manager import ProgressManager
import global_values
import re


class InterruptedError(Exception):
    """自定义异常，用于处理翻译中断"""
    pass


class ImprovedTranslator:
    """
    改进的翻译器类
    负责LLM调用和翻译流程管理
    """
    
    def __init__(self, config_name: str):
        """
        初始化翻译器
        使用config_manager加载配置
        """
        self.config_name = config_name
        
        # 从config_manager加载配置
        self.config = config_manager.load_config(config_name)
        
        
        self.work_dir, self.mod_path, self.mod_work_dir = TranslateHelper.init_workspace(self.config)
        
        # 初始化向量翻译记忆库
        self.vector_memory = global_values.vdb
        
        # 设置日志
        self._setup_logging()
        
        # 初始化进度管理器
        self.progress_manager = ProgressManager(self.config, self.mod_work_dir, self.logger)
        
        # 翻译状态
        
        self.logger.info(f"初始化改进翻译器，配置: {config_name}")
        self.client = None
        
    def _init_llm_api(self):
        print("Initializing LLM API...")
        if self.config["api_key"] == "your_api_key_here":
            self.logger.info("未配置api key, 仅导出原文文本")
            return

        if not self.client:
            # 初始化OpenAI客户端
            try:
                self.client = OpenAI(
                    api_key=self.config["api_key"], 
                    base_url=self.config.get("base_url", "https://api.deepseek.com")
                )
                self.logger.info("LLM API客户端初始化成功")
            except Exception as e:
                self.logger.error(f"LLM API客户端初始化失败: {e}")
                raise RuntimeError("无法初始化LLM API客户端，请检查配置和网络连接") from e
    
    def _setup_logging(self):
        """设置日志"""
        log_file = str(self.mod_work_dir / "translation.log")
        
        # 为当前实例创建专用logger
        self.logger = logging.getLogger(f"{__name__}.{id(self)}")
        self.logger.setLevel(logging.INFO)
        
        # 清除已有的处理器
        self.logger.handlers.clear()
        
        # 添加文件处理器
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(file_handler)
        
        # 添加控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(console_handler)

    
    def extract_translate_objects(self, file_path: str) -> List[TranslationObject]:
        """
        提取需要翻译的对象
        """
        file_type = TranslateHelper.get_file_type(file_path, self.config)

        helper = TranslateHelper.get_helper_by_file_type(file_type, self.logger, self.config)
        
        if not helper:
            self.logger.error(f"不支持的文件类型: {file_path} -> {file_type}")
            return []
        
        # 传递配置键而不是实际文件路径
        return helper.extract_translate_objects(file_path)
    
    def translate_text(self, translation_obj: TranslationObject) -> TranslationObject:
        """
        翻译单个文本对象
        """
        if not translation_obj.original_text or not translation_obj.original_text.strip():
            return translation_obj
        
        processed_text, placeholders_map = self.process_text_placeholder(translation_obj.original_text)
        # 检查是否有完全匹配的翻译记忆
        if self.vector_memory:
            exact_match = self.vector_memory.get_exact_translation(self.config_name, processed_text)
            if exact_match:
                self.logger.info(f"找到完全匹配的翻译记忆: {processed_text}, {exact_match['target']}")
                tt = self.validate_placeholders_and_parse(exact_match['target'], placeholders_map)
                tt = tt.replace("”", "\"").replace("’", "\'").replace("“", "\"").replace("‘", "\'").replace(",", "，")  # 替换引号
                translation_obj.translation = tt
                translation_obj.is_translated = True
                translation_obj.is_suggested_to_translate = True
                translation_obj.llm_reason = exact_match.get('llm_reason', "使用翻译记忆库的完全匹配")
                return translation_obj
        
        # 处理占位符
        tmp_i = 1
        translation_obj.process_text = processed_text
        if processed_text == f"${{{tmp_i}}}":
            # 纯占位符文本
            translation_obj.translation = translation_obj.original_text
            translation_obj.is_suggested_to_translate = False
            translation_obj.is_translated = True
            translation_obj.llm_reason = "纯占位符文本，无需翻译"
            return translation_obj
        # 长度大于4000的不翻译, 容易出错
        if len(processed_text) > 4000:
            self.logger.warning(f"文本长度超过4000字符，跳过翻译: {processed_text[:50]}...")
            translation_obj.translation = processed_text
            translation_obj.is_translated = False
            translation_obj.is_suggested_to_translate = False
            translation_obj.llm_reason = "文本长度超过4000字符，跳过翻译"
            return translation_obj
        
        # 搜索相似的历史翻译
        similar_translations = []
        if self.vector_memory:
            similar_translations = self.vector_memory.search_similar_translations(
                self.config_name, translation_obj.original_text, n_results=3, threshold=0.7
            )
        
        # 搜索文本中的专有名词
        found_terms = []
        if self.vector_memory:
            found_terms = self.vector_memory.search_terminology(translation_obj.original_text)
        
        self.logger.info(f"找到以下专有名词: {found_terms}")
        # 获取文件类型对应的helper
        file_type = TranslateHelper.get_file_type(translation_obj.file_name, self.config)
        helper = TranslateHelper.get_helper_by_file_type(file_type, self.logger, self.config)
        
        if not helper:
            self.logger.error(f"找不到文件类型 {file_type} 的helper")
            return translation_obj
        
        # 构建提示词
        system_prompt = helper.get_llm_system_prompt()
        user_prompt = helper.get_llm_user_prompt(translation_obj, similar_translations, found_terms)
        
        # 调用LLM
        max_retries = self.config.get("max_retries", 3)
        
        if not self.client:
            self.logger.error("LLM客户端未初始化")
            translation_obj.llm_reason = "LLM客户端未初始化"
            translation_obj.is_translated = False
            translation_obj.is_suggested_to_translate = False
            translation_obj.translation = translation_obj.original_text
            return translation_obj
        
        for attempt in range(max_retries):
            try:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
                
                response = self.client.chat.completions.create(
                    model=self.config.get("model", "deepseek-chat"),
                    messages=messages, # type: ignore
                    temperature=self.config.get("temperature", 0.3),
                    max_tokens=self.config.get("max_tokens", 8000),
                    response_format={'type': 'json_object'}
                )

                # self.logger.info(f"temperature:{self.config.get('temperature', 0.3)}, max_tokens:{self.config.get('max_tokens', 8000)}")
                
                message = response.choices[0].message.content
                
                # 解析JSON响应
                result = {}
                try:
                    # 尝试直接解析
                    result = json.loads(message) # type: ignore
                    
                except json.JSONDecodeError:
                    # 如果直接解析失败，尝试修复JSON
                    self.logger.warning(f"JSON解析失败，尝试修复: {message}")
                    try:
                        fixed_message = self._fix_json_response(message) # type: ignore
                        result = json.loads(fixed_message)
                        self.logger.info("JSON修复成功")
                    except Exception as fix_error:
                        self.logger.error(f"JSON修复也失败: {fix_error}")
                        self.logger.warning(f"解析LLM响应失败 (尝试 {attempt + 1})")
                        if attempt == max_retries - 1:
                            # 最后一次尝试，尝试提取纯文本作为翻译结果
                            translation_obj.translation = message # type: ignore
                            translation_obj.is_translated = True
                            translation_obj.is_suggested_to_translate = False
                            translation_obj.llm_reason = "LLM响应格式不正确，此为原始响应"
                            return translation_obj
                        continue


                org_translation = result.get("translation", "")
                should_translate = result.get("should_translate", True)
                reason = result.get("reason", "")
                
                translation = org_translation
                # 恢复占位符
                if org_translation and placeholders_map:
                    translation = self.validate_placeholders_and_parse(translation, placeholders_map)

                # 将响应内容里的英文引号替换为中文引号
                translation = translation.replace("”", "\"").replace("’", "\'").replace("“", "\"").replace("‘", "\'").replace(",", "，")
                
                translation_obj.translation = translation
                translation_obj.is_translated = bool(translation)
                translation_obj.is_suggested_to_translate = should_translate
                translation_obj.llm_reason = reason
                
                # 如果翻译成功，保存到翻译记忆库
                if translation and self.vector_memory and should_translate:
                    self.vector_memory.add_translation_history(
                        self.config_name,
                        processed_text,
                        org_translation,
                        translation_obj.context,
                        translation_obj.llm_reason,
                        translation_obj.file_name
                    )
                
                self.logger.info(f"翻译完成: {translation_obj.original_text[:50]}...")
                return translation_obj
                
            except Exception as e:
                self.logger.error(f"LLM调用失败 (尝试 {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    translation_obj.llm_reason = f"翻译失败: {str(e)}"
                    translation_obj.is_translated = False
                    translation_obj.is_suggested_to_translate = False
                    translation_obj.translation = translation_obj.original_text
        
        return translation_obj
    
    def _fix_json_response(self, message: str) -> str:
        """
        修复LLM返回的JSON响应中的格式问题
        主要处理translation字段中包含未转义引号的问题
        """
        try:
            # 尝试找到JSON的基本结构
            if not message.strip().startswith('{') or not message.strip().endswith('}'):
                raise ValueError("不是有效的JSON格式")
            
            
            # 匹配 "translation": "..." 的模式，考虑到值中可能包含引号
            pattern = r'"translation"\s*:\s*"(.*?)",\s*"should_translate"'
            match = re.search(pattern, message, re.DOTALL)
            
            if match:
                translation_value = match.group(1)
                # 转义translation值中的引号
                escaped_translation = translation_value.replace('"', '\\"')
                
                # 替换原始消息中的translation值
                fixed_message = message.replace(
                    f'"translation": "{translation_value}"',
                    f'"translation": "{escaped_translation}"'
                )
                
                return fixed_message
            else:
                # 如果找不到匹配，尝试另一种方法
                # 找到第一个 "translation": " 和最后一个 ", "should_translate" 之间的内容
                start_marker = '"translation": "'
                end_marker = '", "should_translate"'
                
                start_pos = message.find(start_marker)
                end_pos = message.find(end_marker)
                
                if start_pos != -1 and end_pos != -1:
                    start_pos += len(start_marker)
                    translation_value = message[start_pos:end_pos]
                    escaped_translation = translation_value.replace('"', '\\"')
                    
                    fixed_message = (
                        message[:start_pos] + 
                        escaped_translation + 
                        message[end_pos:]
                    )
                    
                    return fixed_message
                
                raise ValueError("无法找到translation字段")
                
        except Exception as e:
            self.logger.error(f"修复JSON失败: {e}")
            raise
    
    def process_text_placeholder(self, text: str):
        """
        将文本的占位符统一处理成LLM易读的${1}, ${2}格式
        """
        result = text
        placeholder_index = 1
        placeholders_map = {}
#         "!$entity.patrolAllowTOff
            # $entity.missileUseCaughtConv score:100
            # !$entity.knowsWhoPlayerIs"

        # 逐个字符检查并替换控制字符
        for i in range(len(text)):
            char = text[i]
            if ord(char) == 0x00a:  # '\n'
                result = result.replace(char, '\n')
            elif ord(char) == 0x00d:  # '\r' # 略过这个, 没意义
                result = result.replace(char, '\r')
            elif ord(char) < 32:
                # 找到控制字符，替换为${index}
                placeholder = f"${{{placeholder_index}}}"
                result = result.replace(char, placeholder, 1)
                placeholder_index += 1
                placeholders_map[placeholder] = char
            elif char == '%' and (i + 1 < len(text) and (text[i + 1].isdigit() or text[i + 1] in ["s", "d", "x", "f", "v"])):
                # 找到百分号占位符，替换为${index}
                placeholder = f"${{{placeholder_index}}}"
                result = result.replace(char + text[i + 1], placeholder, 1)
                placeholder_index += 1
                placeholders_map[placeholder] = char + text[i + 1]
                i = i + 1  # 跳过下一个字符
            elif char == '$':
                # 寻找到空格为止
                end_index = i + 1
                while end_index < len(text) and text[end_index] != ' ' and text[end_index] != '\n' and text[end_index] != '\r':
                    end_index += 1
                placeholder = f"${{{placeholder_index}}}"
                result = result.replace(char + text[i + 1:end_index], placeholder, 1)
                placeholder_index += 1
                placeholders_map[placeholder] =char + text[i + 1:end_index]
                i = end_index - 1  # 更新索引
        self.logger.info(f"处理后的带占位符文本: {result}, {placeholders_map}")
        return (result, placeholders_map)
    
    def validate_placeholders_and_parse(self, text:str, placeholders_map:dict):
        """
        验证文本中的占位符，并将其解析为实际值
        """
        for placeholder, original in placeholders_map.items():
            if placeholder not in text:
                raise ValueError(f"占位符缺失:{placeholder}, {original}, {text}") # 抛回给上层重试
            text = text.replace(placeholder, original)
        return text
    
    def translate_file(self, file_path: str, do_not_chage_state = False) -> List[TranslationObject]:
        """
        翻译单个文件
        """
        self._init_llm_api()
        self.logger.info(f"开始翻译文件: {file_path}")
        self.progress_manager.set_translated_status(ProgressManager.STATUS_RUNNING, file_path)
        
        try:
            # 提取翻译对象
            translate_objects = self.extract_translate_objects(file_path)
            file_progress = self.progress_manager.get_file_progress(file_path)
            if not file_progress:
                raise ValueError(f"文件 {file_path} 未在进度管理器中找到")
            
            if not translate_objects:
                self.logger.warning(f"未找到需要翻译的内容: {file_path}")
                file_progress.no_contents = True
                return []
            
            helper = TranslateHelper.get_helper_by_file_type(TranslateHelper.get_file_type(file_path, self.config), self.logger, self.config)
            if not helper:
                self.logger.error(f"找不到文件 {file_path} 的helper")
                return []
            temp_file = helper.get_translated_temp_file_path(file_path)
            
            total_count = len(translate_objects)
            self.logger.info(f"找到 {total_count} 个需要翻译的对象")
            
            
            
            start_index = 0
            
            if file_progress.total_count != total_count:
                # 和记录的数量不同则重置进度计数, 清除历史翻译
                self.progress_manager.set_file_total_count(file_path, total_count)
                self.progress_manager.update_translation_progress(file_path, 0)
                if temp_file.exists():
                    self.logger.info(f"清除旧的临时翻译文件: {temp_file}")
                    temp_file.unlink()
            else:
                start_index = file_progress.translated_count
            
            with open(temp_file, 'a', encoding='utf-8') as f:
                # 从指定位置开始翻译
                for i in range(start_index, total_count):
                    if self.progress_manager.is_interrupted():
                        raise InterruptedError("翻译被中断")
                    
                    obj = translate_objects[i]
                    
                    self.logger.info(f"翻译进度: {i + 1}/{total_count}")
                    
                    # 翻译单个对象
                    translated_obj = self.translate_text(obj)
                    translate_objects[i] = translated_obj
                    
                    # 如果翻译成功，立即更新进度管理器
                    self.progress_manager.increment_translation_progress(file_path)
                    
                    # 保存临时翻译结果
                    f.write(json.dumps(translated_obj.to_dict(), ensure_ascii=False) + '\n')
                    f.flush()
                    
                self.logger.info(f"文件翻译完成: {file_path}")
            return translate_objects
        except InterruptedError as e:
            self.logger.warning(f"翻译已中断: {e}")
            return []
            
        except Exception as e:
            self.logger.error(traceback.format_exc())
            self.logger.error(f"翻译文件失败 {file_path}: {e}")
            return []
        finally:
            if not do_not_chage_state:
                self.progress_manager.set_translated_status(ProgressManager.STATUS_IDLE, file_path)
            
    
    def apply_translations(self, file_path: str) -> bool:
        """
        应用翻译到原始文件
        """
        # 读取临时翻译文件
        helper = TranslateHelper.get_helper_by_file_type(TranslateHelper.get_file_type(file_path, self.config), self.logger, self.config)
        if not helper:
            self.logger.error(f"找不到文件 {file_path} 的helper")
            return False
        temp_file = helper.get_translated_temp_file_path(file_path)
        
        if not temp_file.exists():
            self.logger.error(f"临时翻译文件不存在: {temp_file}")
            return False
        
        try:
            translate_objects = []
            with open(temp_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line.strip())
                        obj = TranslationObject.from_dict(data)
                        translate_objects.append(obj)
            
            return helper.apply_translate_objects(translate_objects, str(file_path))
            
        except Exception as e:
            self.logger.error(f"应用翻译失败 {file_path}: {e}")
            return False
    
    def translate_all(self):
        """
        翻译所有配置的文件
        """
        self.logger.info("开始翻译所有文件")
        
        all_files_config = {}
        all_files_config.update(self.config.get("csv_files", {}))
        all_files_config.update(self.config.get("json_files", {}))
        all_files_config.update(self.config.get("jar_files", {}))
        
        for file_path in all_files_config.keys():
            try:
                if self.progress_manager.is_interrupted():
                    raise InterruptedError("翻译被中断")
                self.translate_file(file_path, do_not_chage_state=True)
            except InterruptedError as e:
                self.logger.warning(f"翻译已中断: {e}")
                break
            except Exception as e:
                self.logger.error(f"翻译文件失败 {file_path}: {e}")
                continue
        
        self.progress_manager.set_translated_status(ProgressManager.STATUS_IDLE, "")
        self.logger.info("所有文件翻译完成")
    
    def apply_all_translations(self):
        """
        应用所有翻译到原始文件
        """
        self.logger.info("开始应用所有翻译")
        
        all_files_config = {}
        all_files_config.update(self.config.get("csv_files", {}))
        all_files_config.update(self.config.get("json_files", {}))
        all_files_config.update(self.config.get("jar_files", {}))
        
        success_count = 0
        total_count = len(all_files_config)
        
        for file_path in all_files_config.keys():
            file_progress = self.progress_manager.get_file_progress(file_path)
            if not file_progress or file_progress.completed is False or file_progress.no_contents:
                self.logger.warning(f"文件 {file_path} 未完成翻译或无内容，跳过应用")
                success_count += 1
                continue

            if self.apply_translations(file_path):
                success_count += 1
            else:
                self.logger.error(f"应用翻译失败: {file_path}")
        
        self.logger.info(f"翻译应用完成: {success_count}/{total_count}")
        return success_count == total_count
    
    def get_progress_manager(self) -> ProgressManager:
        """
        获取进度管理器
        """
        return self.progress_manager
    
    
    def reset_file_progress(self, file_path: Optional[str] = None):
        """
        重置文件翻译进度
        
        Args:
            file_path: 指定文件路径，如果为None则重置所有文件
        """
        self.progress_manager.reset_progress(file_path)