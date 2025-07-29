
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
翻译审核和内容管理相关的 API 接口
"""
import json
from pathlib import Path
import traceback
from flask import Blueprint, request, jsonify
import logging
from config_manager import config_manager
import global_values
from translate_helper.translate_helper_base import TranslateHelper
from translation_object import TranslationObject

review_bp = Blueprint('review', __name__)

logger = logging.getLogger(__name__)

@review_bp.route('/api/translation-review/<path:file_path>')
def api_translation_review(file_path):
    """获取翻译审核数据（原文和译文分离显示）"""
    current_config_name = global_values.current_config_name
    if not current_config_name:
        return jsonify({"error": "未选择配置"})
    
    try:
        config = config_manager.load_config(current_config_name)
        translate_helper = TranslateHelper(logger, config)
        file_type = translate_helper.get_file_type(file_path, config)
        temp_file = translate_helper.get_translated_temp_file_path(file_path)
        
        if not temp_file.exists():
            return jsonify({"error": f"翻译文件不存在: {temp_file}"})
        
        # 读取翻译记录
        translations = []
        with open(temp_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                if line.strip():
                    try:
                        record = json.loads(line)
                        translate_object = TranslationObject.from_dict(record)
                        translations.append(translate_object.to_dict())
                    except json.JSONDecodeError as e:
                        # 跳过无效的JSON行
                        continue
        
        return jsonify({
            "file_path": file_path,
            "file_type": file_type,
            "total_count": len(translations),
            "translations": translations
        })
        
    except Exception as e:
        logger.error(traceback.format_exc())
        return jsonify({"error": f"读取翻译文件失败: {str(e)}"})

@review_bp.route('/api/translation-review/<path:file_path>', methods=['POST'])
def api_save_translation_review(file_path):
    """保存修改后的翻译审核数据"""
    current_config_name = global_values.current_config_name
    if not current_config_name:
        return jsonify({"success": False, "message": "未选择配置"})
    
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "message": "无效的数据"})
        
        updated_translations = data.get('translations', [])
        if not updated_translations:
            return jsonify({"success": False, "message": "没有翻译数据"})
        
        # 获取配置和翻译助手
        config = config_manager.load_config(current_config_name)
        translate_helper = TranslateHelper(logger, config)
        file_type = translate_helper.get_file_type(file_path, config)
        temp_file = translate_helper.get_translated_temp_file_path(file_path)
        
        if not temp_file.exists():
            return jsonify({"success": False, "message": f"翻译文件不存在: {temp_file}"})
        
        # 读取现有的翻译记录
        existing_records = []
        with open(temp_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                if line.strip():
                    try:
                        record = json.loads(line)
                        existing_records.append(record)
                    except json.JSONDecodeError:
                        continue
        
        # 更新记录：根据前端传来的数据更新现有记录
        for i, updated_item in enumerate(updated_translations):
            if i < len(existing_records):
                # 更新审核相关字段
                existing_records[i]['approved'] = updated_item.get('approved', False)
                existing_records[i]['approved_text'] = updated_item.get('approved_text', '')
                
                # 确保其他字段也保持同步（如果前端有修改）
                if 'translation' in updated_item:
                    existing_records[i]['translation'] = updated_item['translation']
                if 'is_translated' in updated_item:
                    existing_records[i]['is_translated'] = updated_item['is_translated']
        
        # 重写整个文件
        with open(temp_file, 'w', encoding='utf-8') as f:
            for record in existing_records:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
        
        return jsonify({
            "success": True, 
            "message": f"翻译审核结果保存成功，共更新 {len(updated_translations)} 条记录"
        })
        
    except Exception as e:
        logger.error(f"保存翻译审核数据失败: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "message": f"保存翻译审核数据失败: {str(e)}"})