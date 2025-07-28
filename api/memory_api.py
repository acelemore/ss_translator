"""
翻译记忆库管理相关的 API 接口
"""
import json
from flask import Blueprint, request, jsonify
import global_values

memory_bp = Blueprint('memory', __name__)

vector_memory = global_values.vdb

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
        search = request.args.get('search', '').strip()
        
        # 获取配置对应的翻译集合
        config_name = current_config_name.replace('.json', '')
        collection = vector_memory.get_translation_collection(config_name)
        
        # 优化搜索：使用向量数据库的查询能力
        if search:
            filtered_items = []
            filtered_ids = []
            
            # 方法1：使用向量搜索（语义搜索）
            if vector_memory.embedding_model:
                try:
                    # 使用向量搜索查找语义相似的内容
                    search_results = collection.query(
                        query_texts=[search],
                        n_results=min(1000, page * page_size + 100),  # 获取足够的结果用于分页
                    )
                    
                    if search_results['metadatas'] and search_results['ids']:
                        for metadata, chroma_id in zip(search_results['metadatas'][0], search_results['ids'][0]):
                            # 额外验证搜索词是否确实存在于这些字段中
                            source = metadata.get('source', '')
                            target = metadata.get('target', '')
                            file_path = metadata.get('file_path', '')
                            if (search.lower() in source.lower() or 
                                search.lower() in target.lower() or
                                search.lower() in file_path.lower()):
                                filtered_items.append(metadata)
                                filtered_ids.append(chroma_id)
                            
                except Exception as e:
                    print(f"向量搜索失败: {e}")
            
            # 方法2：如果向量搜索失败或没有结果，使用ChromaDB的获取和过滤
            if not filtered_items:
                try:
                    # 获取所有数据然后过滤
                    results = collection.get(
                        limit=min(5000, page * page_size + 1000)  # 限制获取数量但足够分页
                    )
                    
                    if results and results.get('metadatas') and results.get('ids'):
                        for metadata, chroma_id in zip(results['metadatas'], results['ids']):
                            source = metadata.get('source', '').lower()
                            target = metadata.get('target', '').lower()
                            file_path = metadata.get('file_path', '').lower()
                            search_lower = search.lower()
                            
                            if (search_lower in source or 
                                search_lower in target or
                                search_lower in file_path):
                                filtered_items.append(metadata)
                                filtered_ids.append(chroma_id)
                    
                except Exception as e:
                    print(f"ChromaDB查询失败: {e}")
                    filtered_items = []
                    filtered_ids = []
                    
            # 方法3：回退到全量搜索（仅在前两种方法都失败时使用）
            if not filtered_items:
                try:
                    results = collection.get()
                    if results and results.get('metadatas') and results.get('ids'):
                        for metadata, chroma_id in zip(results['metadatas'], results['ids']):
                            source = metadata.get('source', '').lower()
                            target = metadata.get('target', '').lower()
                            file_path = metadata.get('file_path', '').lower()
                            search_lower = search.lower()
                            
                            if (search_lower in source or 
                                search_lower in target or
                                search_lower in file_path):
                                filtered_items.append(metadata)
                                filtered_ids.append(chroma_id)
                except Exception as e:
                    print(f"全量搜索也失败: {e}")
                    filtered_items = []
                    filtered_ids = []
        else:
            # 无搜索条件：获取所有数据（限制数量以提高性能）
            try:
                results = collection.get(
                    limit=min(10000, page * page_size + 1000)  # 限制最大获取数量
                )
                filtered_items = results.get('metadatas', []) if results else []
                filtered_ids = results.get('ids', []) if results else []
            except Exception as e:
                print(f"获取数据失败: {e}")
                filtered_items = []
                filtered_ids = []
        
        # 计算分页
        total_count = len(filtered_items)
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        page_items = filtered_items[start_index:end_index]
        page_ids = filtered_ids[start_index:end_index] if filtered_ids else []
        
        # 格式化返回数据 - 使用ChromaDB真实ID
        translations = []
        for i, metadata in enumerate(page_items):
            # 使用ChromaDB的真实ID，如果没有则使用hash作为备用ID
            item_id = page_ids[i] if i < len(page_ids) else f"hash_{hash(metadata.get('source', '') + metadata.get('target', ''))}"
            
            translations.append({
                'id': item_id,  # 使用ChromaDB的真实ID
                'source': metadata.get('source', ''),
                'target': metadata.get('target', ''),
                'context': metadata.get('context', ''),
                'file_path': metadata.get('file_path', ''),
                'created_at': metadata.get('created_at', '')
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
        collection = vector_memory.get_translation_collection(config_name)
        
        results = collection.get()
        total_count = len(results.get('metadatas', [])) if results else 0
        
        return jsonify({
            "success": True,
            "stats": {
                "total_count": total_count
            }
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": f"获取统计信息失败: {str(e)}"})

@memory_bp.route('/api/memory/translations/<translation_id>', methods=['PUT'])
def api_update_translation(translation_id):
    """更新翻译记录"""
    current_config_name = global_values.current_config_name
    if not current_config_name:
        return jsonify({"success": False, "message": "未选择配置"})
    
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "message": "无效的数据"})
        
        new_target = data.get('target', '').strip()
        if not new_target:
            return jsonify({"success": False, "message": "译文不能为空"})
        
        config_name = current_config_name.replace('.json', '')
        collection = vector_memory.get_translation_collection(config_name)
        
        # 根据ID获取记录
        try:
            results = collection.get(ids=[translation_id])
            if not results or not results.get('metadatas') or not results['metadatas']:
                return jsonify({"success": False, "message": "记录不存在"})
            
            # 更新记录
            metadata = results['metadatas'][0]
            document = results['documents'][0] if results.get('documents') else metadata.get('source', '')
            
            metadata['target'] = new_target
            
            # 重新插入更新后的数据
            collection.upsert(
                ids=[translation_id],
                documents=[document],
                metadatas=[metadata]
            )
            
            return jsonify({"success": True, "message": "更新成功"})
            
        except Exception as chroma_error:
            return jsonify({"success": False, "message": f"记录不存在或更新失败: {str(chroma_error)}"})
        
    except Exception as e:
        return jsonify({"success": False, "message": f"更新失败: {str(e)}"})

@memory_bp.route('/api/memory/translations/<translation_id>', methods=['DELETE'])
def api_delete_translation(translation_id):
    """删除翻译记录"""
    current_config_name = global_values.current_config_name
    if not current_config_name:
        return jsonify({"success": False, "message": "未选择配置"})
    
    try:
        config_name = current_config_name.replace('.json', '')
        collection = vector_memory.get_translation_collection(config_name)
        
        # 直接使用ChromaDB的ID删除记录
        try:
            collection.delete(ids=[translation_id])
            return jsonify({"success": True, "message": "删除成功"})
        except Exception as chroma_error:
            return jsonify({"success": False, "message": f"记录不存在或删除失败: {str(chroma_error)}"})
        
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
        collection = vector_memory.get_translation_collection(config_name)
        
        # 直接使用ChromaDB的ID进行批量删除
        try:
            collection.delete(ids=translation_ids)
            deleted_count = len(translation_ids)
            return jsonify({
                "success": True, 
                "message": f"成功删除 {deleted_count} 条记录",
                "deleted_count": deleted_count
            })
        except Exception as chroma_error:
            return jsonify({"success": False, "message": f"批量删除失败: {str(chroma_error)}"})
        
    except Exception as e:
        return jsonify({"success": False, "message": f"批量删除失败: {str(e)}"})
