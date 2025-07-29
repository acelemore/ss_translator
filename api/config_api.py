
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
配置管理相关的 API 接口
"""
from flask import Blueprint, request, jsonify
from config_manager import config_manager
import global_values


config_bp = Blueprint('config', __name__)

@config_bp.route('/api/configs')
def api_configs():
    """获取所有可用的配置"""
    configs = config_manager.get_available_configs()
    return jsonify(configs)

@config_bp.route('/api/configs/current')
def api_current_config():
    """获取当前选择的配置"""
    
    if global_values.current_config_name:
        try:
            config = config_manager.load_config(global_values.current_config_name)
            return jsonify({
                "success": True,
                "config_name": global_values.current_config_name,
                "config": config
            })
        except Exception as e:
            return jsonify({"success": False, "message": str(e)})
    else:
        return jsonify({"success": False, "message": "未选择配置"})

@config_bp.route('/api/configs/select', methods=['POST'])
def api_select_config():
    """选择配置"""
    
    data = request.json
    if data:
        config_name = data.get('config_name')
    else:
        return jsonify({"success": False, "message": "无效的配置名称"})
    
    try:
        # 使用 global_values 的便捷方法设置配置
        global_values.set_config(config_name)
        
        return jsonify({"success": True, "message": f"已选择配置: {config_name}"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@config_bp.route('/api/configs/save', methods=['POST'])
def api_save_config():
    """保存配置"""
    data = request.json
    if data:
        config_name = data.get('config_name')
        config_data = data.get('config_data')
    else:
        return jsonify({"success": False, "message": "无效的配置数据"})
    
    if not config_data:
        return jsonify({"success": False, "message": "配置数据不能为空"})
    config_data.pop('api_key', None)  # 确保不保存 api key 等敏感信息
    success = config_manager.save_config(config_name, config_data)
    return jsonify({
        "success": success,
        "message": "保存成功" if success else "保存失败"
    })

@config_bp.route('/api/configs/create', methods=['POST'])
def api_create_config():
    """创建新配置"""
    data = request.json
    if not data:
        return jsonify({"success": False, "message": "无效的配置数据"})
    config_name = data.get('config_name')
    mod_name = data.get('mod_name')
    mod_path = data.get('mod_path')
    description = data.get('description', '')
    
    try:
        config_data = config_manager.create_new_config(config_name, mod_name, mod_path, description)
        return jsonify({"success": True, "message": "创建成功", "config": config_data})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@config_bp.route('/api/configs/delete', methods=['POST'])
def api_delete_config():
    """删除配置"""
    data = request.json
    if not data:
        return jsonify({"success": False, "message": "无效的配置数据"})
    config_name = data.get('config_name')
    
    success = config_manager.delete_config(config_name)
    return jsonify({
        "success": success,
        "message": "删除成功" if success else "删除失败"
    })

@config_bp.route('/api/configs/global')
def api_global_config():
    """获取全局配置"""
    try:
        global_config = config_manager.load_global_config()
        return jsonify({
            "success": True,
            "config": global_config
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@config_bp.route('/api/configs/global', methods=['POST'])
def api_save_global_config():
    """保存全局配置"""
    try:
        config_data = request.json
        if not config_data:
            return jsonify({"success": False, "message": "配置数据不能为空"})
            
        success = config_manager.save_global_config(config_data)
        
        if success:
            # 如果当前有选择的配置，重新选择以触发全局配置刷新
            if global_values.current_config_name:
                try:
                    global_values.set_config(global_values.current_config_name)
                    return jsonify({
                        "success": True,
                        "message": "保存成功，已刷新当前配置"
                    })
                except Exception as refresh_error:
                    # 即使刷新失败，全局配置也已保存成功
                    return jsonify({
                        "success": True,
                        "message": f"保存成功，但刷新配置时出错: {str(refresh_error)}"
                    })
            else:
                return jsonify({
                    "success": True,
                    "message": "保存成功"
                })
        else:
            return jsonify({
                "success": False,
                "message": "保存失败"
            })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@config_bp.route('/api/configs/global/api-status')
def api_check_api_config():
    """检查API配置状态"""
    try:
        is_valid, message = config_manager.validate_api_config()
        api_config = config_manager.get_api_config()
        
        return jsonify({
            "success": True,
            "is_valid": is_valid,
            "message": message,
            "api_key_set": bool(api_config["api_key"] and api_config["api_key"] != "your_api_key_here"),
            "base_url": api_config["base_url"],
            "model": api_config["model"],
            "max_tokens": api_config.get("max_tokens", 2000)
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@config_bp.route('/api/configs/auto-detect', methods=['POST'])
def api_auto_detect_files():
    """自动检测文件并配置翻译"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        data = request.json
        if not data:
            return jsonify({
                "success": False,
                "message": "缺少请求数据"
            })
            
        config_name = data.get('config_name')
        
        if not config_name:
            return jsonify({
                "success": False,
                "message": "缺少配置名称"
            })
        
        # 执行自动检测
        success = config_manager.auto_detect_files(config_name)
        
        if success:
            # 获取更新后的配置统计信息
            updated_config = config_manager.load_mod_config_only(config_name)
            csv_count = len(updated_config.get('csv_files', {}))
            json_count = len(updated_config.get('json_files', {}))
            jar_count = len(updated_config.get('jar_files', {}))
            
            return jsonify({
                "success": True,
                "message": f"自动检测完成：发现 {csv_count} 个CSV文件，{json_count} 个JSON文件，{jar_count} 个JAR文件",
                "statistics": {
                    "csv_files": csv_count,
                    "json_files": json_count,
                    "jar_files": jar_count
                }
            })
        else:
            return jsonify({
                "success": False,
                "message": "自动检测失败，请检查mod路径是否正确"
            })
            
    except Exception as e:
        logger.error(f"自动检测文件失败: {e}")
        return jsonify({
            "success": False,
            "message": f"自动检测失败: {str(e)}"
        })