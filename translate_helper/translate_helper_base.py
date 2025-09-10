
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
import os
import shutil
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import logging
from translation_object import TranslationObject



class TranslateHelper(object):
    """
    基础翻译助手类
    """
    
    # 类变量：支持的文件类型，子类应该重写此变量
    support_file_type = ""
    
    def __init__(self, logger: logging.Logger, translate_config: Dict[str, Any]):
        self.logger = logger
        if self.support_file_type and f"{self.support_file_type}_files" in translate_config:
            self.translate_config = translate_config[f"{self.support_file_type}_files"]
        self.extract_functions = {}
        # 初始化工作目录

        self.work_dir, self.mod_path, self.mod_work_dir = self.init_workspace(translate_config)
        

    @classmethod
    def init_workspace(cls, translate_config: Dict[str, Any]):
        """
        初始化工作空间
        """
        work_dir = Path.cwd() / Path(translate_config["work_directory"])
        mod_path_str = translate_config.get("mod_path", "")
        workspace_name:str = translate_config.get("name")
        if mod_path_str:
            mod_path = Path(mod_path_str)
            mod_work_dir = work_dir / workspace_name
            mod_work_dir.mkdir(exist_ok=True)
            return (work_dir, mod_path, mod_work_dir)
        else:
            raise ValueError("配置中未指定mod_path")
            
    @classmethod
    def get_file_type(cls, file_path: str, config) -> str:
        """
        根据文件路径确定文件类型
        """
        if file_path in config.get("csv_files", {}):
            return "csv"
        elif file_path in config.get("json_files", {}):
            return "json"
        elif file_path in config.get("jar_files", {}):
            return "jar"
        else:
            return "unknown"

    # 获取所有子类
    @classmethod
    def get_all_subclasses(cls):
        subclasses = set(cls.__subclasses__())
        for ele in list(subclasses):
            subclasses.update(ele.get_all_subclasses())
        return subclasses

    @classmethod
    def get_helper_by_file_type(cls, file_type: str, logger, translate_config):
        """工厂方法, 获取翻译助手实例"""
        # 遍历所有子类
        for subclass in cls.get_all_subclasses():
            if hasattr(subclass, 'support_file_type') and subclass.support_file_type == file_type:
                return subclass(logger, translate_config)
        return None
    
    @classmethod
    def get_support_parse_func(cls) -> Dict:
        """
        遍历所有继承的子类，收集所有支持的解析函数
        返回格式: {function_name: {"description": desc, "helper_class": class_name}}
        """
        all_functions = {}
        
        # 获取所有子类
        def get_all_subclasses(cls):
            subclasses = set(cls.__subclasses__())
            for subclass in list(subclasses):
                subclasses.update(get_all_subclasses(subclass))
            return subclasses
        
        # 遍历所有子类
        for subclass in get_all_subclasses(cls):
            try:
                # 检查子类是否重写了get_support_parse_func方法
                if (hasattr(subclass, 'get_support_parse_func') and 
                    subclass.get_support_parse_func != cls.get_support_parse_func):
                    
                    # 调用子类的类方法
                    subclass_functions = subclass.get_support_parse_func()
                    
                    if isinstance(subclass_functions, dict):
                        # 直接从类变量获取文件类型
                        file_type = getattr(subclass, 'support_file_type', 'unknown')
                        
                        # 将子类支持的函数添加到总列表中
                        for func_name, description in subclass_functions.items():
                            all_functions[func_name] = {
                                'description': description,
                                'helper_class': subclass.__name__,
                                'helper_module': subclass.__module__,
                                'file_type': file_type
                            }
            except Exception as e:
                # 如果某个子类有问题，记录但不影响其他子类
                print(f"警告：处理子类 {subclass.__name__} 时出错: {e}")
                continue
        
        return all_functions
    
    def get_source_file_actual_path(self, source_file_path: str) -> Path:
        return self.mod_path / source_file_path.lstrip('./') # type: ignore
    
    def get_original_file_path(self, config_file_path: str) -> Path:
        return self.mod_work_dir / config_file_path.lstrip('./')
    
    def get_translated_temp_file_path(self, file_path: str) -> Path:
        actual_path = self.get_original_file_path(file_path)
        file_name = actual_path.name
        return actual_path.parent / f"{file_name}.temp_translation.jsonl"
    
    def ensure_translated_file(self, source_file_path: str):
        """
        确保文件存在
        """
        sp = self.get_source_file_actual_path(source_file_path)
        cp = self.get_original_file_path(source_file_path)
        if not cp.exists():
            os.makedirs(cp.parent, exist_ok=True)
            shutil.copy(sp, cp)
        return cp

    def extract_translate_objects(self, file_path: str) -> List[TranslationObject]:
        """
        从文件中提取需要翻译的对象
        子类必须实现此方法
        """
        raise NotImplementedError("子类必须实现此方法")
    
    def generate_translation_key(self, translation_obj: TranslationObject, index: int|str) -> str:
        """
        为翻译对象生成唯一标识key
        子类可以重写此方法以提供自定义key生成逻辑
        """
        return f"{translation_obj.file_name}:{index}:{translation_obj.original_text[:50]}"
    
    def get_llm_system_prompt(self) -> str:
        """
        获取LLM翻译的系统提示语
        子类可以重写此方法以提供自定义提示
        """
        return """你是一个专业的游戏本地化翻译专家，专门翻译 远行星号 游戏模组的文本。

翻译要求：
1. 保持游戏术语的一致性和准确性
2. 遇到专有名词时必须使用提供的标准翻译
3. 保持原文的格式、变量（如$faction、$ship等）和特殊字符(尤其是双百分号 %% , 要原样保留, 比如 "增加5%%的伤害" 不能翻译成 "增加5%的伤害")
4. 翻译要符合中文表达习惯，自然流畅
5. 对于游戏机制相关的术语，使用玩家熟悉的中文表达
6. 无论多简单的文本都必须翻译，不要返回空值

【重要】占位符处理规则：
- 文本中的${0}、${1}、${2} 以及任何$连接的英文单词 都是动态数值占位符，在游戏中会被替换为实际数值
- 必须在翻译中完整保留所有占位符，包括${符号和数字}
- 绝对不能删除或修改占位符格式, 并且翻译结果要符合原来的占位符顺序

【翻译建议】请判断文本是否应该翻译：
- 如果文本可能是文件路径、配置参数、枚举值、类名、变量名等，建议不翻译
- 如果文本是用户界面文本、描述性文本、提示信息等，建议翻译
- 无论建议如何，都必须提供翻译结果"""
    
    def get_llm_user_prompt(self, translation_obj: TranslationObject, 
                           similar_translations: List[Dict] = [],
                           found_terms: List[Dict] = []) -> str:
        """
        获取LLM翻译的用户提示语
        子类可以重写此方法以提供自定义提示
        """
        user_prompt_parts = []
        
        # 添加专有名词参考
        if found_terms:
            user_prompt_parts.append("【专有名词参考】")
            for term in found_terms:
                user_prompt_parts.append(f"- {term['term']} -> {term['translation']}")
            user_prompt_parts.append("")
        
        # 添加相似翻译示例
        if similar_translations:
            user_prompt_parts.append("【相似翻译示例】")
            for example in similar_translations[:3]:  # 限制为3个示例
                user_prompt_parts.append(f"原文: {example['source']}")
                target = example.get("target", "")
                if "approved" in example and example["approved"] and example.get("approved_text"):
                    target = example["approved_text"]
                user_prompt_parts.append(f"译文: {target}")
                user_prompt_parts.append("")
        
        # 添加要翻译的文本
        user_prompt_parts.append(f"需要翻译的文本: {translation_obj.process_text if translation_obj.process_text else translation_obj.original_text}")
        user_prompt_parts.append("")
        user_prompt_parts.append("请直接输出翻译结果的JSON格式：")
        user_prompt_parts.append('{"translation": "翻译后的中文文本", "should_translate": true/false, "reason": "翻译建议的理由"}')
        
        return "\n".join(user_prompt_parts)
    
    def apply_translate_objects(self, translate_objects: List[TranslationObject], 
                              file_path: str) -> bool:
        """
        应用翻译对象到原始文件
        子类必须实现此方法
        """
        raise NotImplementedError("子类必须实现此方法")
    
    def process_text_placeholder(self, text: str) -> Tuple[str, Dict[str, str]]:
        """
        将文本的占位符统一处理成LLM易读的${1}, ${2}格式
        """
        result = text
        placeholder_index = 1
        placeholders_map = {}

        # 逐个字符检查并替换控制字符
        for i in range(len(text)):
            char = text[i]
            if ord(char) < 32 and char not in ['\n', '\r', '\t']:  # 控制字符（除了常见的换行、回车、制表符）
                placeholder = f"${{{placeholder_index}}}"
                placeholders_map[placeholder] = char
                result = result.replace(char, placeholder, 1)  # 只替换第一个匹配
                placeholder_index += 1

        return (result, placeholders_map)
    
    def validate_placeholders_and_parse(self, text: str, placeholders_map: Dict[str, str]) -> str:
        """
        验证文本中的占位符，并将其解析为实际值
        """
        for placeholder, original in placeholders_map.items():
            text = text.replace(placeholder, original)
        return text
    