"""
翻译管理相关的 API 接口
"""
import json
import threading
import zipfile
import tempfile
import os
from pathlib import Path
from flask import Blueprint, request, jsonify, send_file
from config_manager import config_manager
import logging

from progress_manager import ProgressManager
from translate_helper.translate_helper_base import TranslateHelper
import global_values
logger = logging.getLogger(__name__)

translation_bp = Blueprint('translation', __name__)

@translation_bp.route('/api/translate/start', methods=['POST'])
def api_start_translation():
    """开始翻译"""
    current_config_name = global_values.current_config_name
    # 验证API配置
    is_valid, message = config_manager.validate_api_config()
    if not is_valid:
        return jsonify({"success": False, "message": f"API配置无效: {message}"})
    
    if global_values.translator.progress_manager.status == ProgressManager.STATUS_RUNNING:
        return jsonify({"success": False, "message": "翻译正在进行中"})
    
    if not current_config_name:
        return jsonify({"success": False, "message": "请先选择配置"})
    
    data = request.json
    file_path = data.get('file_path') if data else None
    
    def translate_worker():
        try:
            if file_path:
                # 翻译指定文件
                global_values.translator.translate_file(file_path)
                # global_values.translator.apply_translations(file_path)
            else:
                # 翻译所有文件
                global_values.translator.translate_all()
                # global_values.translator.apply_all_translations()
                        
        except Exception as e:
            print(f"翻译错误: {e}")
            logger.error(f"翻译错误: {e}")
    
    translation_thread = threading.Thread(target=translate_worker)
    translation_thread.start()
    
    return jsonify({"success": True, "message": "翻译已开始"})

@translation_bp.route('/api/translate/stop', methods=['POST'])
def api_stop_translation():
    """停止翻译"""
    if global_values.translator.progress_manager.status != ProgressManager.STATUS_RUNNING:
        return jsonify({"success": False, "message": "没有正在进行的翻译"})
    
    try:
        global_values.translator.progress_manager.set_translated_status(ProgressManager.STATUS_INTERUPTED)
        return jsonify({"success": True, "message": "已发送中断请求"})
    except Exception as e:
        logger.error(f"停止翻译失败: {e}")
        return jsonify({"success": False, "message": f"停止翻译失败: {str(e)}"})

@translation_bp.route('/api/translate/status')
def api_translation_status():
    """获取翻译状态"""

    # 获取基本翻译状态
    # print(global_values.current_config_name)
    global_values.translator.progress_manager.refresh_files_status()
    current_progress = 0
    current_file_progress = global_values.translator.progress_manager.get_file_progress(global_values.translator.progress_manager.current_translated_file)
    if current_file_progress:
        current_progress = current_file_progress.translated_count / current_file_progress.total_count if current_file_progress.total_count > 0 else 0
        current_progress = round(current_progress * 100, 2)
    status = {
        "running": global_values.translator.progress_manager.status == ProgressManager.STATUS_RUNNING,
        "status": global_values.translator.progress_manager.status,  # 添加当前状态
        "current_file": global_values.translator.progress_manager.current_translated_file,
        "progress": current_progress,
        "total_files": global_values.translator.progress_manager.total_files,
        "completed_files": global_values.translator.progress_manager.completed_files,
        "errors": []
    }
    
    # 如果有翻译器实例，获取详细进度信息
    if global_values.translator and global_values.current_config_name:
        try:
            
            # 获取总体进度统计
            overall_progress = global_values.translator.get_progress_manager().get_overall_progress()
            status.update(overall_progress)
            
            # 获取当前正在翻译的文件进度
            if status["running"] and status["current_file"]:
                file_progress = global_values.translator.get_progress_manager().get_file_progress(status["current_file"])
                if file_progress:
                    status["current_file_progress"] = {
                        "translated_count": file_progress.translated_count,
                        "total_count": file_progress.total_count,
                        "progress_percentage": file_progress.progress_percentage,
                        "status": file_progress.status
                    }
            
            # 获取所有文件的进度详情
            all_progress = global_values.translator.get_progress_manager().get_all_progress()
            status["files_detail"] = {
                file_path: {
                    "translated_count": progress.translated_count,
                    "total_count": progress.total_count,
                    "progress_percentage": progress.progress_percentage,
                    "status": progress.status,
                    "completed": progress.completed
                }
                for file_path, progress in all_progress.items()
            }
            
        except Exception as e:
            logger.error(f"获取翻译进度失败: {e}")
    
    return jsonify(status)

@translation_bp.route('/api/translations')
def api_translations():
    """获取翻译文件列表"""
    
    if not global_values.current_config_name:
        return jsonify({"error": "未选择配置"})
    
    config = config_manager.load_config(global_values.current_config_name)
    
    try:
        pm = global_values.translator.get_progress_manager()
        all_progress = pm.get_all_progress()
        
        translation_files = []
        for file_path, one_progress in all_progress.items():
            if not one_progress.completed:
                continue
            file_type = TranslateHelper.get_file_type(file_path, config)
            translated_tmp_file = pm.get_temp_file_path(file_path)
            count = 0
            approved_count = 0
            try:
                with open(translated_tmp_file, 'r', encoding='utf-8') as f:
                    lines = [line for line in f if line.strip()]
                    count = len(lines)
                    approved_count = 0
                    for line in lines:
                        try:
                            record = json.loads(line)
                            if record.get('approved', False):
                                approved_count += 1
                        except json.JSONDecodeError:
                            continue
            except:
                count = 0
                approved_count = 0
                
            translation_files.append({
                        "path": file_path,
                        "temp_file": str(translated_tmp_file),
                        "total_count": count,
                        "approved_count": approved_count,
                        "type": file_type,
                    })
        return jsonify(translation_files)
        
    except Exception as e:
        return jsonify({"error": f"获取翻译文件失败: {str(e)}"})

@translation_bp.route('/api/translations/<path:file_path>')
def api_translation_content(file_path):
    """获取翻译文件内容"""
    
    if not global_values.current_config_name:
        return jsonify({"error": "未选择配置"})
    
    try:
        config = config_manager.load_config(global_values.current_config_name)
        work_dir = Path(config["work_directory"])
        # 添加模组路径
        mod_path = config.get("mod_path", "")
        if mod_path:
            work_dir = work_dir / mod_path
        temp_file = work_dir / f"{file_path.lstrip('./').replace('/', '_')}.temp_translation.jsonl"
        
        if not temp_file.exists():
            return jsonify({"error": "翻译文件不存在"})
        
        translations = []
        with open(temp_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f):
                if line.strip():
                    try:
                        record = json.loads(line)
                        translations.append({
                            "line_num": line_num,
                            "record": record
                        })
                    except json.JSONDecodeError:
                        continue
        
        return jsonify(translations)
        
    except Exception as e:
        return jsonify({"error": f"读取翻译文件失败: {str(e)}"})

@translation_bp.route('/api/translations/<path:file_path>', methods=['PUT'])
def api_update_translation_content(file_path):
    """更新翻译文件内容"""
    
    if not global_values.current_config_name:
        return jsonify({"success": False, "message": "未选择配置"})
    
    try:
        data = request.json or {}
        translations = data.get('translations', [])
        
        config = config_manager.load_config(global_values.current_config_name)
        work_dir = Path(config["work_directory"])
        # 添加模组路径
        mod_path = config.get("mod_path", "")
        if mod_path:
            work_dir = work_dir / mod_path
        temp_file = work_dir / f"{file_path.lstrip('./').replace('/', '_')}.temp_translation.jsonl"
        
        # 重写翻译文件
        with open(temp_file, 'w', encoding='utf-8') as f:
            for translation in translations:
                f.write(json.dumps(translation['record'], ensure_ascii=False) + '\n')
        
        return jsonify({"success": True, "message": "翻译文件更新成功"})
        
    except Exception as e:
        return jsonify({"success": False, "message": f"更新翻译文件失败: {str(e)}"})

@translation_bp.route('/api/apply-translations', methods=['POST'])
def api_apply_translations():
    """应用翻译"""
    
    if not global_values.current_config_name:
        return jsonify({"success": False, "message": "未选择配置"})
    
    data = request.json
    file_path = data.get('file_path') if data else ""
    apply_all = data.get('apply_all', False) if data else False
    
    try:
        if apply_all:
            # 应用所有翻译
            result = global_values.translator.apply_all_translations()
            message = "所有翻译应用成功" if result else "部分翻译应用失败"
        else:
            # 应用单个文件翻译
            result = global_values.translator.apply_translations(file_path)
            message = f"文件 {file_path} 翻译应用成功" if result else f"文件 {file_path} 翻译应用失败"
        
        return jsonify({"success": result, "message": message})
        
    except Exception as e:
        return jsonify({"success": False, "message": f"应用翻译失败: {str(e)}"})

@translation_bp.route('/api/extract-functions')
def api_extract_functions():
    """获取可用的提取函数"""
    from translate_helper import TranslateHelper
    return jsonify(TranslateHelper.get_support_parse_func())

@translation_bp.route('/api/export_translation_package', methods=['POST'])
def api_export_translation_package():
    """导出翻译包"""
    if not global_values.current_config_name:
        return jsonify({"success": False, "message": "未选择配置"})
    
    try:
        mod_work_dir = global_values.translator.mod_work_dir
        if not mod_work_dir.exists():
            return jsonify({"success": False, "message": f"工作目录不存在: {mod_work_dir}"})
        
        # 查找所有以 .translated 结尾的文件
        translated_files = []
        for file_path in mod_work_dir.rglob("*.translated"):
            if file_path.is_file():
                translated_files.append(file_path)
        
        if not translated_files:
            return jsonify({"success": False, "message": "未找到已翻译的文件"})
        
        # 创建临时zip文件
        temp_dir = tempfile.mkdtemp()
        config = config_manager.load_config(global_values.current_config_name)
        
        # 获取模组名称，用于zip文件名
        mod_path = config.get("mod_path", "")
        if mod_path:
            mod_name = Path(mod_path).name
        else:
            mod_name = "translated_mod"
        
        zip_filename = f"{mod_name}_translation_package.zip"
        zip_path = Path(temp_dir) / zip_filename
        
        # 创建zip文件
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for translated_file in translated_files:
                try:
                    # 计算相对于mod_work_dir的路径
                    relative_path = translated_file.relative_to(mod_work_dir)
                    
                    # 去掉 .translated 后缀
                    original_path = str(relative_path)
                    if original_path.endswith('.translated'):
                        target_path = original_path[:-11]  # 去掉 '.translated' (11个字符)
                    else:
                        target_path = original_path
                    
                    # 添加文件到zip包中，保持相对路径结构
                    zipf.write(translated_file, target_path)
                    logger.info(f"添加文件到zip包: {target_path}")
                    
                except Exception as e:
                    logger.warning(f"处理文件 {translated_file} 时出错: {e}")
                    continue
        
        # 检查zip文件是否创建成功
        if not zip_path.exists():
            return jsonify({"success": False, "message": "创建zip文件失败"})
        
        # 返回文件给客户端下载
        try:
            return send_file(
                str(zip_path),
                as_attachment=True,
                download_name=zip_filename,
                mimetype='application/zip'
            )
        except Exception as e:
            logger.error(f"发送文件失败: {e}")
            return jsonify({"success": False, "message": f"发送文件失败: {str(e)}"})
        finally:
            # 清理临时文件（延迟清理，确保文件发送完成）
            def cleanup_temp_file():
                try:
                    import time
                    time.sleep(5)  # 等待5秒确保文件发送完成
                    if zip_path.exists():
                        os.unlink(zip_path)
                    if Path(temp_dir).exists():
                        os.rmdir(temp_dir)
                except Exception as e:
                    logger.warning(f"清理临时文件失败: {e}")
            
            # 在后台线程中清理临时文件
            cleanup_thread = threading.Thread(target=cleanup_temp_file)
            cleanup_thread.daemon = True
            cleanup_thread.start()
        
    except Exception as e:
        logger.error(f"导出翻译包失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "message": f"导出翻译包失败: {str(e)}"})