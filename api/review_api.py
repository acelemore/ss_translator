
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
        
        # 获取数据库接口实例
        db_interface = global_values.db
        config_name = current_config_name.replace('.json', '')
        
        # 更新记录：根据前端传来的数据更新现有记录
        updated_count = 0
        memory_updated_count = 0
        translation_objects_to_update = []
        
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
                
                updated_count += 1
                
                # 准备批量更新数据库的数据
                if db_interface:
                    try:
                        translation_obj = TranslationObject.from_dict(existing_records[i])
                        
                        # 如果没有translation_key，生成一个新的
                        if not translation_obj.translation_key:
                            import hashlib
                            from datetime import datetime
                            source_text = translation_obj.original_text
                            translation_key = hashlib.md5(
                                (source_text + translation_obj.file_name + str(datetime.now())).encode('utf-8')
                            ).hexdigest()
                            translation_obj.translation_key = translation_key
                            existing_records[i]['translation_key'] = translation_key
                        
                        translation_objects_to_update.append(translation_obj)
                        
                    except Exception as obj_error:
                        logger.error(f"准备翻译对象失败: {str(obj_error)}")
                        continue
        
        # 批量更新数据库记录
        if db_interface and translation_objects_to_update:
            try:
                # 使用批量更新方法
                success_count, error_count, errors = db_interface.update_translation_batch(
                    config_name, 
                    translation_objects_to_update
                )
                memory_updated_count = success_count
                
                if errors:
                    for error in errors:
                        logger.warning(error)
                        
                logger.info(f"批量更新数据库完成: 成功 {success_count}, 失败 {error_count}")
                        
            except Exception as batch_error:
                logger.error(f"批量数据库操作失败: {str(batch_error)}")
                # 继续处理，不因为数据库错误而终止
        
        # 重写整个文件
        with open(temp_file, 'w', encoding='utf-8') as f:
            for record in existing_records:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
        
        # 构建返回消息
        message = f"翻译审核结果保存成功，共更新 {updated_count} 条工作区记录"
        if db_interface:
            message += f"，同步更新 {memory_updated_count} 条记忆库记录"
        
        return jsonify({
            "success": True, 
            "message": message,
            "updated_count": updated_count,
            "memory_updated_count": memory_updated_count
        })
        
    except Exception as e:
        logger.error(f"保存翻译审核数据失败: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "message": f"保存翻译审核数据失败: {str(e)}"})

@review_bp.route('/api/translation-review/sync-memory/<path:file_path>', methods=['POST'])
def api_sync_translation_memory(file_path):
    """同步整个文件的翻译记录到向量数据库"""
    current_config_name = global_values.current_config_name
    if not current_config_name:
        return jsonify({"success": False, "message": "未选择配置"})
    
    try:
        # 获取配置和翻译助手
        config = config_manager.load_config(current_config_name)
        translate_helper = TranslateHelper(logger, config)
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
        
        # 获取数据库接口实例
        db_interface = global_values.db
        if not db_interface:
            return jsonify({"success": False, "message": "数据库接口未初始化"})
        
        config_name = current_config_name.replace('.json', '')
        synced_count = 0
        created_count = 0
        updated_count = 0
        translation_objects_to_sync = []
        
        # 准备所有需要同步的翻译对象
        for i, record in enumerate(existing_records):
            try:
                translation_obj = TranslationObject.from_dict(record)
                
                # 如果没有translation_key，生成一个新的
                if not translation_obj.translation_key:
                    import hashlib
                    from datetime import datetime
                    source_text = translation_obj.original_text
                    translation_key = hashlib.md5(
                        (source_text + translation_obj.file_name + str(datetime.now())).encode('utf-8')
                    ).hexdigest()
                    translation_obj.translation_key = translation_key
                    existing_records[i]['translation_key'] = translation_key
                    created_count += 1
                else:
                    updated_count += 1
                
                translation_objects_to_sync.append(translation_obj)
                
            except Exception as sync_error:
                logger.error(f"准备同步记录失败 [{i}]: {str(sync_error)}")
                continue
        
        # 批量同步到数据库
        if translation_objects_to_sync:
            try:
                # 使用批量更新方法
                success_count, error_count, errors = db_interface.update_translation_batch(
                    config_name, 
                    translation_objects_to_sync
                )
                synced_count = success_count
                
                if errors:
                    for error in errors:
                        logger.warning(error)
                
                logger.info(f"批量同步数据库完成: 成功 {success_count}, 失败 {error_count}")
                
            except Exception as batch_sync_error:
                logger.error(f"批量同步失败: {str(batch_sync_error)}")
        
        # 重写文件以保存translation_key
        with open(temp_file, 'w', encoding='utf-8') as f:
            for record in existing_records:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
        
        return jsonify({
            "success": True,
            "message": f"同步完成：处理 {synced_count} 条记录，创建 {created_count} 条新记录，更新 {updated_count} 条现有记录",
            "synced_count": synced_count,
            "created_count": created_count,
            "updated_count": updated_count,
            "total_records": len(existing_records)
        })
        
    except Exception as e:
        logger.error(f"同步翻译记忆失败: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "message": f"同步翻译记忆失败: {str(e)}"})