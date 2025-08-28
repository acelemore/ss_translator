
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
翻译记忆库管理相关的 API 接口
"""
import json
from flask import Blueprint, request, jsonify
import global_values

memory_bp = Blueprint('memory', __name__)

# 使用数据库操作统一接口
db_interface = global_values.db

@memory_bp.route('/api/memory/translations')
def api_get_translations():
    """获取翻译记忆列表（分页）"""
    current_config_name = global_values.current_config_name
    if not current_config_name:
        return jsonify({"success": False, "message": "未选择配置"})
    
    try:
        # 获取分页参数
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        
        # 获取搜索参数
        search_file_name = request.args.get('search_file_name', '').strip()
        search_original_text = request.args.get('search_original_text', '').strip()
        search_approved_text = request.args.get('search_approved_text', '').strip()
        search_context = request.args.get('search_context', '').strip()
        
        # 获取配置对应的翻译集合
        config_name = current_config_name.replace('.json', '')
        
        # 构建搜索参数
        search_params = {}
        if search_file_name:
            search_params['file_name'] = search_file_name
        if search_original_text:
            search_params['original_text'] = search_original_text
        if search_approved_text:
            search_params['approved_text'] = search_approved_text
        if search_context:
            search_params['context'] = search_context
        
        # 初始化变量
        filtered_items = []
        filtered_ids = []
        total_count = 0
        page_items = []
        page_ids = []
        
        # 使用新的高效搜索方法
        if search_params:
            try:
                # 添加分页参数
                search_params['limit'] = page_size
                search_params['offset'] = (page - 1) * page_size
                
                # 使用数据库接口的搜索方法
                search_results = db_interface.search_translations(config_name, search_params)
                filtered_items = [result['metadata'] for result in search_results]
                filtered_ids = [result['metadata'].get('translation_key', '') for result in search_results]
                
                # 获取总数（用于分页计算）
                total_search_params = {k: v for k, v in search_params.items() if k not in ['limit', 'offset']}
                total_results = db_interface.search_translations(config_name, total_search_params)
                total_count = len(total_results)
                
                page_items = filtered_items
                page_ids = filtered_ids
                
            except Exception as e:
                print(f"数据库接口搜索失败: {e}")
                # 变量已初始化为空列表
        else:
            # 无搜索条件：使用数据库接口获取所有记录
            try:
                # 使用数据库接口的搜索方法，不带任何搜索条件
                search_params = {
                    'limit': page_size,
                    'offset': (page - 1) * page_size
                }
                
                search_results = db_interface.search_translations(config_name, search_params)
                page_items = [result['metadata'] for result in search_results]
                page_ids = [result['metadata'].get('translation_key', '') for result in search_results]
                
                # 获取总数
                total_count = db_interface.get_translation_count(config_name)
                
            except Exception as e:
                print(f"获取数据失败: {e}")
                # 变量已初始化为空列表
        
        # 格式化返回数据 - 使用translation_key作为ID
        translations = []
        for metadata in page_items:
            # 使用translation_key作为ID
            item_id = metadata.get('translation_key', '')
            if not item_id:
                # 如果没有translation_key，生成一个临时ID
                item_id = f"temp_{hash(metadata.get('original_text', '') + metadata.get('translation', ''))}"
            
            translations.append({
                'id': item_id,
                'file_name': metadata.get('file_name', ''),
                'original_text': metadata.get('original_text', ''),
                'translation': metadata.get('translation', ''),
                'approved': metadata.get('approved', False),
                'approved_text': metadata.get('approved_text', ''),
                'context': metadata.get('context', ''),
                'created_at': metadata.get('created_at', ''),
                'updated_at': metadata.get('updated_at', '')
            })
        
        return jsonify({
            "success": True,
            "data": {
                "translations": translations,
                "total_count": total_count,
                "page": page,
                "page_size": page_size,
                "total_pages": (total_count + page_size - 1) // page_size
            }
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": f"获取翻译记忆失败: {str(e)}"})

@memory_bp.route('/api/memory/translations/stats')
def api_get_memory_stats():
    """获取翻译记忆统计信息"""
    current_config_name = global_values.current_config_name
    if not current_config_name:
        return jsonify({"success": False, "message": "未选择配置"})
    
    try:
        config_name = current_config_name.replace('.json', '')
        
        # 使用快速估算避免长时间查询
        try:
            total_count = db_interface.get_translation_count(config_name)
        except Exception as count_error:
            # 如果计数查询失败，返回估算值或0
            print(f"统计查询失败，返回默认值: {count_error}")
            total_count = 0
        
        return jsonify({
            "success": True,
            "stats": {
                "total_count": total_count
            }
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": f"获取统计信息失败: {str(e)}"})

@memory_bp.route('/api/memory/translations/<translation_id>', methods=['DELETE'])
def api_delete_translation(translation_id):
    """删除翻译记录"""
    current_config_name = global_values.current_config_name
    if not current_config_name:
        return jsonify({"success": False, "message": "未选择配置"})
    
    try:
        config_name = current_config_name.replace('.json', '')
        
        # 使用数据库接口删除记录
        success = db_interface.delete_translation(config_name, translation_id)
        if success:
            return jsonify({"success": True, "message": "删除成功"})
        else:
            return jsonify({"success": False, "message": "记录不存在或删除失败"})
    except Exception as e:
        return jsonify({"success": False, "message": f"删除失败: {str(e)}"})

@memory_bp.route('/api/memory/translations/batch', methods=['DELETE'])
def api_batch_delete_translations():
    """批量删除翻译记录"""
    current_config_name = global_values.current_config_name
    if not current_config_name:
        return jsonify({"success": False, "message": "未选择配置"})
    
    try:
        data = request.get_json()
        translation_ids = data.get('ids', [])
        
        if not translation_ids:
            return jsonify({"success": False, "message": "未选择要删除的记录"})
        
        config_name = current_config_name.replace('.json', '')
        
        # 使用新的批量删除方法
        deleted_count, failed_count, errors = db_interface.delete_translation_batch(config_name, translation_ids)
        
        if deleted_count > 0:
            message = f"成功删除 {deleted_count} 条记录"
            if failed_count > 0:
                message += f"，{failed_count} 条记录删除失败"
            if errors:
                message += f"。错误: {'; '.join(errors)}"
            return jsonify({
                "success": True, 
                "message": message,
                "deleted_count": deleted_count,
                "failed_count": failed_count,
                "errors": errors
            })
        else:
            return jsonify({
                "success": False, 
                "message": "没有记录被删除", 
                "errors": errors
            })
    except Exception as e:
        return jsonify({"success": False, "message": f"批量删除失败: {str(e)}"})