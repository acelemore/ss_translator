
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
通用配置管理模块
支持动态加载和管理翻译配置
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
import importlib
import logging
import csv
import re

class ConfigManager:
    """配置管理器"""
    
    def __init__(self, configs_dir: str = "configs"):
        self.configs_dir = Path(configs_dir)
        self.configs_dir.mkdir(exist_ok=True)
        
        # 全局配置文件路径
        self.global_config_path = self.configs_dir / "global_config.json"
        
        # 创建默认全局配置（如果不存在）
        self._ensure_global_config()
        
        # 可用的提取函数映射
        self.available_extract_functions = {
            "get_raw_text": "直接提取原始文本",
            "get_script_text": "提取脚本中的引号文本",
            "get_options_text": "提取选项文本（数字:标识符:内容格式）",
            "get_json_leaf_values": "提取JSON叶子节点字符串值",
            "jar_extract": "从JAR文件提取硬编码字符串"
        }
    
    def _ensure_global_config(self):
        """确保全局配置文件存在"""
        if not self.global_config_path.exists():
            default_global_config = {
                "api_key": "your_api_key_here",
                "base_url": "https://api.deepseek.com",
                "model": "deepseek-chat",
                "max_tokens": 2000,
                "request_interval": 0.1,
                "max_retries": 10,
                "work_directory": "translation_work",
                "log_file": "translation.log",
                "terminology_file": "terminology.json",
                "progress_file": "translation_progress.json",
                "temperature": 0.1,
                "description": "全局翻译配置，包含API密钥和通用参数"
            }
            
            with open(self.global_config_path, 'w', encoding='utf-8') as f:
                json.dump(default_global_config, f, ensure_ascii=False, indent=4)
            
            logging.info(f"已创建默认全局配置文件: {self.global_config_path}")
    
    def load_global_config(self) -> Dict[str, Any]:
        """加载全局配置"""
        try:
            with open(self.global_config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"加载全局配置失败: {e}")
            return {}
    
    def save_global_config(self, config_data: Dict[str, Any]) -> bool:
        """保存全局配置"""
        try:
            with open(self.global_config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            logging.error(f"保存全局配置失败: {e}")
            return False
    
    def update_global_config(self, updates: Dict[str, Any]) -> bool:
        """更新全局配置的部分字段"""
        try:
            global_config = self.load_global_config()
            global_config.update(updates)
            return self.save_global_config(global_config)
        except Exception as e:
            logging.error(f"更新全局配置失败: {e}")
            return False
    
    def get_api_config(self) -> Dict[str, str]:
        """获取API相关配置"""
        global_config = self.load_global_config()
        return {
            "api_key": global_config.get("api_key", ""),
            "base_url": global_config.get("base_url", ""),
            "model": global_config.get("model", "")
        }
    
    def validate_api_config(self) -> tuple[bool, str]:
        """验证API配置是否有效"""
        api_config = self.get_api_config()
        
        if not api_config["api_key"] or api_config["api_key"] == "your_api_key_here":
            return False, "请设置有效的API密钥"
        
        if not api_config["base_url"]:
            return False, "请设置API基础URL"
        
        if not api_config["model"]:
            return False, "请设置翻译模型"
        
        return True, "API配置有效"
    
    def get_available_configs(self) -> List[Dict[str, str]]:
        """获取所有可用的配置文件（排除全局配置）"""
        configs = []
        
        for config_file in self.configs_dir.glob("*.json"):
            # 排除全局配置
            if config_file.stem == "global_config":
                continue
            if config_file.stem == "fix_rules":
                continue
                
            try:
                config = self.load_mod_config_only(config_file.stem)
                configs.append({
                    "filename": config_file.stem,
                    "name": config.get("config_name", config_file.stem),
                    "description": config.get("description", ""),
                    "mod_path": config.get("mod_path", "")
                })
            except Exception as e:
                logging.warning(f"无法加载配置文件 {config_file}: {e}")
                
        return configs
    
    def load_config(self, config_name: str) -> Dict[str, Any]:
        """加载指定配置，与全局配置合并"""
        # 加载全局配置
        global_config = self.load_global_config()
        
        # 如果是全局配置本身，直接返回
        if config_name == "global_config":
            return global_config
        
        # 加载模组配置
        config_path = self.configs_dir / f"{config_name}.json"
        
        if not config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            mod_config = json.load(f)
        
        # 合并配置：全局配置作为基础，模组配置覆盖
        merged_config = global_config.copy()
        merged_config.update(mod_config)
        # api密钥, 模型, api接口继承全局
        merged_config.update({
            "api_key": global_config["api_key"],
            "base_url": global_config["base_url"],
            "model": global_config["model"]
        })
        
        return merged_config
    
    def load_mod_config_only(self, config_name: str) -> Dict[str, Any]:
        """仅加载模组配置（不合并全局配置）"""
        config_path = self.configs_dir / f"{config_name}.json"
        
        if not config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def save_config(self, config_name: str, config_data: Dict[str, Any]) -> bool:
        """保存配置"""
        try:
            config_path = self.configs_dir / f"{config_name}.json"
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            logging.error(f"保存配置失败: {e}")
            return False
    
    def delete_config(self, config_name: str) -> bool:
        """删除配置"""
        try:
            config_path = self.configs_dir / f"{config_name}.json"
            if config_path.exists():
                config_path.unlink()
                return True
            return False
        except Exception as e:
            logging.error(f"删除配置失败: {e}")
            return False
    
    def create_new_config(self, config_name: str, mod_name: str, mod_path: str, description: str = "") -> Dict[str, Any]:
        """创建新配置"""
        config_data = {
            "config_name": mod_name,
            "mod_path": mod_path,
            "description": description,
            "csv_files": {},
            "json_files": {},
            "jar_files": {}
        }
        
        if self.save_config(config_name, config_data):
            return config_data
        else:
            raise Exception("创建配置失败")
        
    def auto_detect_files(self, config_name: str) -> bool:
        """
        自动扫描mod文件夹，按规则自动配置翻译文件
        
        Args:
            config_name: 配置文件名
            
        Returns:
            bool: 是否成功更新配置
        """
        try:
            config_data = self.load_mod_config_only(config_name)
            mod_path = config_data.get("mod_path", "")
            
            if not mod_path:
                logging.error(f"配置 {config_name} 缺少 mod_path")
                return False
            
            # 获取实际的mod路径
            mod_dir = Path(mod_path)
            if not mod_dir.exists():
                # 尝试相对路径
                mod_dir = Path.cwd() / mod_path
                if not mod_dir.exists():
                    logging.error(f"Mod路径不存在: {mod_path}")
                    return False
            
            # 加载CSV字段规则
            rules_file = Path("./configs/fix_rules.json")
            if rules_file.exists():
                with open(rules_file, 'r', encoding='utf-8') as f:
                    field_rules = json.load(f)
            else:
                # 使用默认规则
                field_rules = {
                    "fixed_csv_configs": {
                        "rules.csv": {
                            "notes": "get_raw_text",
                            "options": "get_options_text",
                            "script": "get_script_text",
                            "text": "get_text_with_OR"
                        }
                    },
                    "field_rules": {
                        "raw_fields": ["name", "desc", "description", "text", "notes"],
                        "never_translate": ["id", "ID", "key", "type", "class", "plugin"],
                        "script_fields": ["script"],
                        "options_fields": ["options"]
                    },
                    "skip_values": ["", " "],
                    "ignore_json_files": {
                        "sounds.json": True
                    }
                }
            
            # 初始化配置
            csv_files = {}
            json_files = {}
            jar_files = {}
            
            # 扫描data文件夹中的CSV和JSON文件
            data_dir = mod_dir / "data"
            if data_dir.exists():
                for file_path in data_dir.rglob("*"):
                    if file_path.is_file():
                        relative_path = f"./{file_path.relative_to(mod_dir).as_posix()}"
                        
                        if file_path.suffix.lower() == '.csv':
                            csv_config = self._analyze_csv_file(file_path, field_rules, relative_path)
                            if csv_config:
                                csv_files[relative_path] = csv_config
                        
                        elif file_path.suffix.lower() == '.json':
                            if file_path.name in field_rules.get("ignore_json_files", {}):
                                continue
                            json_files[relative_path] = {
                                "description": "JSON文件",
                                "extract_function": "extract_json_leaf_values"
                            }
            
            # 扫描jars文件夹中的JAR文件
            jars_dir = mod_dir / "jars"
            if jars_dir.exists():
                for file_path in jars_dir.rglob("*"):
                    if file_path.is_file() and file_path.suffix.lower() == '.jar':
                        relative_path = f"./{file_path.relative_to(mod_dir).as_posix()}"
                        jar_files[relative_path] = {
                            "backup_suffix": ".backup",
                            "description": "JAR包中的硬编码文本",
                            "extract_function": "extract_jar_strings",
                            "output_suffix": "_translated.jar"
                        }
            
            # 更新配置
            config_data["csv_files"] = csv_files
            config_data["json_files"] = json_files
            config_data["jar_files"] = jar_files
            config_data["name"] = config_name
            
            # 保存配置
            success = self.save_config(config_name, config_data)
            if success:
                logging.info(f"成功自动检测并更新配置 {config_name}:")
                logging.info(f"  - CSV文件: {len(csv_files)} 个")
                logging.info(f"  - JSON文件: {len(json_files)} 个")
                logging.info(f"  - JAR文件: {len(jar_files)} 个")
            
            return success
            
        except Exception as e:
            logging.error(f"自动检测文件失败: {e}")
            return False
    
    def _analyze_csv_file(self, file_path: Path, field_rules: Dict, relative_path: str) -> Optional[Dict[str, str]]:
        """
        分析CSV文件，确定每个字段的翻译方法
        
        Args:
            file_path: CSV文件路径
            field_rules: 字段规则配置
            relative_path: 相对路径
            
        Returns:
            Dict[str, str]: 字段名到提取函数的映射，如果不需要翻译则返回None
        """
        try:
            
            
            # 检查是否有固定配置
            file_name = file_path.name
            for fixed_file, fixed_config in field_rules["fixed_csv_configs"].items():
                if file_name == fixed_file or relative_path.endswith(fixed_file):
                    logging.info(f"使用固定配置: {file_name}")
                    return fixed_config
            
            # 读取CSV文件进行分析
            with open(file_path, 'r', encoding='utf-8', newline='') as csvfile:
                # 检测分隔符
                sample = csvfile.read(1024)
                csvfile.seek(0)
                sniffer = csv.Sniffer()
                try:
                    delimiter = sniffer.sniff(sample).delimiter
                except:
                    delimiter = ','
                
                reader = csv.DictReader(csvfile, delimiter=delimiter)
                
                if not reader.fieldnames:
                    return None
                
                # 分析每个字段
                field_config = {}
                valid_fieldnames = [f for f in reader.fieldnames if f is not None]
                field_analysis = {field: {"has_text": False, "has_numbers": False, "has_booleans": False, "has_underline": False, "has_path": False, "is_sentence": False, "has_escape": False} 
                                for field in valid_fieldnames}
                
                # 读取前100行进行分析
                row_count = 0
                for row in reader:
                    if row_count >= 100:
                        break
                    row_count += 1
                    
                    for field, value in row.items():
                        if field is None or not isinstance(value, str):
                            continue
                        if not value or value.strip() in field_rules["skip_values"]:
                            continue
                        
                        value = value.strip()
                        
                        # 检查是否包含英文句子模式（改进版，支持标点符号）
                        sentence_pattern = r'[a-zA-Z]{2,}\s+[a-zA-Z]{2,}'  # 至少2个字母的单词
                        
                        # 检查基本句子模式
                        has_sentence_pattern = re.search(sentence_pattern, value)
                        
                        if has_sentence_pattern:
                            # 进一步检查是否是真正的句子 vs 配置项
                            is_likely_sentence = True
                            
                            # 排除明显的配置项和标识符（但允许标点符号）
                            if ('_' in value and '.' not in value and '"' not in value):  # 下划线标识符（但不是句子中的引用）
                                is_likely_sentence = False
                            elif re.search(r'^[a-zA-Z]+\d+[,\s]*[a-zA-Z]*\d*$', value):  # 纯标识符列表
                                is_likely_sentence = False
                            elif re.search(r'^[a-zA-Z_]+[,\s]*[a-zA-Z_]+$', value) and '_' in value and '"' not in value:  # 包含下划线的标识符列表
                                is_likely_sentence = False
                            
                            # 如果包含句子特征，确定是需要翻译的文本
                            sentence_indicators = [
                                r'[.!?"]',  # 句号、感叹号、问号、引号
                                r'\b(the|a|an|and|or|but|in|on|at|to|for|of|with|by)\b',  # 常见英文介词/冠词
                                r'\b(you|he|she|it|they|we|I)\b',  # 人称代词
                                r'\b(is|are|was|were|have|has|had|will|would|can|could)\b',  # 常见动词
                            ]
                            
                            has_sentence_indicators = False
                            for indicator in sentence_indicators:
                                if re.search(indicator, value, re.IGNORECASE):
                                    has_sentence_indicators = True
                                    break
                            
                            # 如果有句子指示词，肯定是句子；如果没有但通过基本检查，也可能是简单的名词短语
                            if is_likely_sentence and (has_sentence_indicators or len(value.split()) <= 4):
                                field_analysis[field]["has_text"] = True
                                field_analysis[field]["is_sentence"] = True
                        
                        # 检查是否是纯数字
                        try:
                            float(value)
                            field_analysis[field]["has_numbers"] = True
                        except ValueError:
                            pass
                        
                        # 检查是否是布尔值
                        if value.upper() in ["TRUE", "FALSE"]:
                            field_analysis[field]["has_booleans"] = True
                        else:
                            # 检查是否包含有意义的文本
                            if len(value) > 1 and not value.isdigit():
                                field_analysis[field]["has_text"] = True
                                
                        # 检查是否包含下划线
                        if "_" in value:
                            field_analysis[field]["has_underline"] = True
                            
                        if "/" in value:
                            field_analysis[field]["has_path"] = True
                
                # 根据分析结果决定翻译方法
                for field in valid_fieldnames:
                    if field in field_rules["field_rules"]["never_translate"]:
                        continue
                    
                    if field in field_rules["field_rules"]["raw_fields"]:
                        field_config[field] = "get_raw_text"
                    elif field in field_rules["field_rules"]["script_fields"]:
                        field_config[field] = "get_script_text"
                    elif field in field_rules["field_rules"]["options_fields"]:
                        field_config[field] = "get_options_text"
                    else:
                        # 根据内容分析决定
                        analysis = field_analysis[field]
                        # 如果是明显的英文句子, 优先考虑翻译
                        if analysis["is_sentence"]:
                            field_config[field] = "get_raw_text"
                            continue
                        # # 存在数字或布尔值，不翻译
                        # if (analysis["has_numbers"] or analysis["has_booleans"]) and not analysis["has_text"]:
                        #     continue
                        # if analysis["has_underline"] or analysis["has_path"]:
                        #     continue
                        
                        # # 如果有文本内容
                        # if analysis["has_text"]:
                        #     field_config[field] = "get_raw_text"
                            
                
                return field_config if field_config else None
                
        except Exception as e:
            logging.warning(f"分析CSV文件失败 {file_path}: {e}")
            return None

# 全局配置管理器实例
config_manager = ConfigManager()