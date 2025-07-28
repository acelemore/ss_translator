from dataclasses import dataclass, asdict
import json
from typing import Any, Dict

@dataclass
class TranslationObject:
    file_name: str
    original_text: str
    process_text: str = ''
    translation: str = ''
    context: str = ''
    dangerous: bool = False
    is_translated: bool = False
    is_suggested_to_translate: bool = True
    llm_reason: str = ''
    translation_key: str = ''  # 添加翻译键字段
    approved: bool = False  # 是否已被审核通过
    approved_text: str = ''  # 审核通过的翻译文本
    
    
    @classmethod
    def from_dict(cls, data: dict):
        """从字典创建实例"""
        return cls(
            file_name=data.get('file_name', ''),
            original_text=data.get('original', data.get('original_text', '')),
            process_text=data.get('process_text', ''),
            translation=data.get('translation', ''),
            context=data.get('context', ''),
            dangerous=data.get('dangerous', False),
            is_translated=data.get('is_translated', False),
            is_suggested_to_translate=data.get('is_suggested_to_translate', True),
            llm_reason=data.get('llm_reason', ''),
            translation_key=data.get('translation_key', ''),
            approved=data.get('approved', False),
            approved_text=data.get('approved_text', '')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    def to_json(self) -> str:
        """序列化为JSON字符串"""
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)
    
    def copy(self):
        """创建当前实例的副本"""
        return TranslationObject.from_dict(self.to_dict())
    
    @classmethod
    def from_json(cls, json_str: str):
        """从JSON字符串创建实例"""
        data = json.loads(json_str)
        return cls.from_dict(data)