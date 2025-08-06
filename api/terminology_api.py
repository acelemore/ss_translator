
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
专有名词和翻译记忆管理相关的 API 接口
"""
import json
import tempfile
import time
from pathlib import Path
from flask import Blueprint, request, jsonify, send_from_directory
import global_values

terminology_bp = Blueprint('terminology', __name__)

vector_memory = global_values.vdb


@terminology_bp.route('/api/terminology')
def api_terminology():
    """获取专有名词表"""
    
    terms = vector_memory.get_terminology_list()
    # 转换格式以兼容前端
    terminology_dict = {term['term']: term['translation'] for term in terms}
    return jsonify(terminology_dict)

@terminology_bp.route('/api/terminology/list')
def api_terminology_list():
    """获取详细的专有名词列表"""
    
    terms = vector_memory.get_terminology_list()
    return jsonify({"success": True, "terms": terms})

@terminology_bp.route('/api/terminology/add', methods=['POST'])
def api_add_terminology():
    """添加专有名词"""
    
    data = request.json
    if not data:
        return jsonify({"success": False, "message": "无效的数据"})
    
    term = data.get('english', '').strip()  # 兼容旧格式
    if not term:
        term = data.get('term', '').strip()
    
    translation = data.get('chinese', '').strip()  # 兼容旧格式
    if not translation:
        translation = data.get('translation', '').strip()
    
    domain = data.get('domain', 'general')
    notes = data.get('notes', '')
    
    if not term or not translation:
        return jsonify({"success": False, "message": "术语和翻译不能为空"})
    
    success = vector_memory.add_terminology(term, translation, domain, notes)
    return jsonify({
        "success": success,
        "message": "添加成功" if success else "添加失败"
    })

@terminology_bp.route('/api/terminology/delete', methods=['POST'])
def api_delete_terminology():
    """删除专有名词"""
    
    data = request.json
    if not data:
        return jsonify({"success": False, "message": "无效的数据"})
    
    term = data.get('english', '').strip()  # 兼容旧格式
    if not term:
        term = data.get('term', '').strip()
    
    success = vector_memory.delete_terminology(term)
    return jsonify({
        "success": success,
        "message": "删除成功" if success else "删除失败"
    })

@terminology_bp.route('/api/terminology/high-frequency')
def api_high_frequency_words():
    """获取高频词建议"""
    
    current_config_name = global_values.current_config_name
    
    if not (vector_memory and current_config_name):
        return jsonify({"success": False, "message": "功能不可用或未选择配置"})
    
    try:
        config_name = current_config_name.replace('.json', '')
        
        # 从翻译历史中获取所有源文本
        collection = vector_memory.get_translation_collection(config_name)
        results = collection.get()
        
        if not results['metadatas']:
            return jsonify({"success": True, "words": []})
        
        # 提取所有源文本
        source_texts = [metadata['source'] for metadata in results['metadatas']]
        
        # 分析高频词
        high_freq_words = vector_memory.analyze_high_frequency_words(source_texts)
        return jsonify({"success": True, "words": high_freq_words})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@terminology_bp.route('/api/terminology/export')
def api_export_terminology():
    """导出专有名词为JSON文件"""
    
    try:
        terms = vector_memory.get_terminology_list()
        
        # 转换为导出格式
        export_data = []
        for term in terms:
            export_data.append({
                "term": term.get('term', ''),
                "translation": term.get('translation', ''),
                "domain": term.get('domain', 'general'),
                "notes": term.get('notes', ''),
                "created_at": term.get('created_at', '')
            })
        
        # 创建临时文件
        import tempfile
        import os
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8')
        
        try:
            json.dump(export_data, temp_file, ensure_ascii=False, indent=2)
            temp_file.close()
            
            # 返回文件内容供下载
            from flask import send_file, after_this_request
            
            @after_this_request
            def remove_file(response):
                try:
                    os.remove(temp_file.name)
                except Exception:
                    pass
                return response
            
            return send_file(
                temp_file.name,
                as_attachment=True,
                download_name=f'terminology_export_{time.strftime("%Y%m%d_%H%M%S")}.json',
                mimetype='application/json'
            )
            
        except Exception as e:
            if os.path.exists(temp_file.name):
                os.remove(temp_file.name)
            raise e
            
    except Exception as e:
        return jsonify({"success": False, "message": f"导出失败: {str(e)}"})

@terminology_bp.route('/api/terminology/import', methods=['POST'])
def api_import_terminology():
    """导入专有名词JSON文件"""
    
    try:
        # 检查是否有文件上传
        if 'file' not in request.files:
            return jsonify({"success": False, "message": "没有上传文件"})
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"success": False, "message": "没有选择文件"})
        
        # 检查文件类型
        if not file.filename or not file.filename.lower().endswith('.json'):
            return jsonify({"success": False, "message": "只支持JSON文件"})
        
        # 读取文件内容
        try:
            file_content = file.read().decode('utf-8')
            import_data = json.loads(file_content)
        except json.JSONDecodeError:
            return jsonify({"success": False, "message": "JSON文件格式错误"})
        except Exception as e:
            return jsonify({"success": False, "message": f"读取文件失败: {str(e)}"})
        
        # 验证数据格式
        if not isinstance(import_data, list):
            return jsonify({"success": False, "message": "JSON文件格式错误，应为数组格式"})
        
        # 使用批量导入方法
        success_count, error_count, error_messages = vector_memory.add_terminology_batch(import_data)
        
        # 返回导入结果
        message = f"导入完成：成功 {success_count} 条"
        if error_count > 0:
            message += f"，失败 {error_count} 条"
            if len(error_messages) <= 5:  # 只显示前5个错误
                message += f"。错误详情：{'; '.join(error_messages)}"
            else:
                message += f"。错误详情：{'; '.join(error_messages[:5])}..."
        
        return jsonify({
            "success": True,
            "message": message,
            "stats": {
                "success_count": success_count,
                "error_count": error_count,
                "total_count": len(import_data)
            }
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": f"导入失败: {str(e)}"})
