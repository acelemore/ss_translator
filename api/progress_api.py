
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
进度管理相关的 API 接口
"""
from flask import Blueprint, request, jsonify
from improved_translator import ImprovedTranslator
from translate_helper.translate_helper_base import TranslateHelper
import global_values

progress_bp = Blueprint('progress', __name__)

# MODIFY
@progress_bp.route('/api/progress/overview')
def api_progress_overview():
    """获取翻译进度概览"""
    
    if not global_values.translator:
        return jsonify({"success": False, "message": "未选择配置"})
    
    
    try:
        # 获取总体进度统计
        overall_progress = global_values.translator.get_progress_manager().get_overall_progress()
        # 获取所有文件的详细进度
        all_progress = global_values.translator.get_progress_manager().get_all_progress()
        files_progress = []
        config = global_values.translator.config
        for file_path, progress in all_progress.items():
            file_type = TranslateHelper.get_file_type(file_path, config)
            if file_type == "unknown":
                continue
            files_progress.append({
                "file_path": file_path,
                "file_type": progress.file_type,
                "translated_count": progress.translated_count,
                "total_count": progress.total_count,
                "progress_percentage": progress.progress_percentage,
                "status": progress.status,
                "completed": progress.completed,
                "description": progress.description
            })
        
        return jsonify({
            "success": True,
            "overall": overall_progress,
            "files": files_progress
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": f"获取进度概览失败: {str(e)}"})

@progress_bp.route('/api/progress/file/<path:file_path>')
def api_file_progress(file_path):
    """获取单个文件的详细进度"""
    
    if not global_values.current_config_name:
        return jsonify({"success": False, "message": "未选择配置"})
    
    # 确保有翻译器实例
    if not global_values.translator:
        try:
            global_values.translator = ImprovedTranslator(global_values.current_config_name)
        except Exception as e:
            return jsonify({"success": False, "message": f"初始化翻译器失败: {str(e)}"})
    
    try:
        # 获取文件进度
        file_progress = global_values.translator.get_progress_manager().get_file_progress(file_path)
        
        if not file_progress:
            return jsonify({"success": False, "message": "文件不存在或未配置"})
        
        return jsonify({
            "success": True,
            "file_path": file_path,
            "file_type": file_progress.file_type,
            "translated_count": file_progress.translated_count,
            "total_count": file_progress.total_count,
            "progress_percentage": file_progress.progress_percentage,
            "status": file_progress.status,
            "completed": file_progress.completed,
            "description": file_progress.description
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": f"获取文件进度失败: {str(e)}"})

@progress_bp.route('/api/progress/refresh', methods=['POST'])
def api_refresh_progress():
    """刷新进度信息"""
    
    if not global_values.current_config_name:
        return jsonify({"success": False, "message": "未选择配置"})
    
    # 确保有翻译器实例
    if not global_values.translator:
        try:
            global_values.translator = ImprovedTranslator(global_values.current_config_name)
        except Exception as e:
            return jsonify({"success": False, "message": f"初始化翻译器失败: {str(e)}"})
    
    data = request.json
    file_path = data.get('file_path') if data else None
    
    try:
        
        return jsonify({
            "success": True,
            "message": f"已刷新{'文件' if file_path else '所有'}进度"
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"刷新进度失败: {str(e)}"})

@progress_bp.route('/api/progress/reset', methods=['POST'])
def api_reset_progress():
    """重置翻译进度"""
    
    if not global_values.current_config_name:
        return jsonify({"success": False, "message": "未选择配置"})
    
    # 确保有翻译器实例
    if not global_values.translator:
        try:
            global_values.translator = ImprovedTranslator(global_values.current_config_name)
        except Exception as e:
            return jsonify({"success": False, "message": f"初始化翻译器失败: {str(e)}"})
    
    data = request.json
    file_path = data.get('file_path') if data else None
    
    try:
        # 使用翻译器的进度管理器重置进度
        global_values.translator.reset_file_progress(file_path)
        
        return jsonify({
            "success": True,
            "message": f"已重置{'文件' if file_path else '所有'}进度"
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"重置进度失败: {str(e)}"})

@progress_bp.route('/api/files')
def api_files():
    """获取文件列表"""
    
    if not global_values.current_config_name:
        return jsonify({"error": "未选择配置"})
    
    # 确保有翻译器实例
    if not global_values.translator:
        try:
            global_values.translator = ImprovedTranslator(global_values.current_config_name)
        except Exception as e:
            return jsonify({"error": f"初始化翻译器失败: {str(e)}"})
    
    try:
        
        # 获取所有文件进度
        all_progress = global_values.translator.get_progress_manager().get_all_progress()
        
        files = []
        for file_path, progress in all_progress.items():
            files.append({
                "path": file_path,
                "type": progress.file_type,
                "progress": progress.translated_count,
                "total_lines": progress.total_count,
                "completed": progress.completed,
                "status": progress.status,
                "description": progress.description,
                "progress_percentage": progress.progress_percentage
            })
        
        return jsonify(files)
        
    except Exception as e:
        return jsonify({"error": f"获取文件列表失败: {str(e)}"})