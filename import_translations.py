#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
翻译数据导入脚本
用于将现有的 JSONL 翻译文件批量导入到数据库中

使用方法:
python import_translations.py {mod_path} {config_name}

参数:
- mod_path: 包含 JSONL 文件的目录路径
- config_name: 目标配置名称（不包含 .json 后缀）
"""

import os
import sys
import json
import argparse
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List
import logging

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from translation_object import TranslationObject
from db_interface import DatabaseInterface

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('import_translations.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


def find_jsonl_files(directory: Path) -> List[Path]:
    """在指定目录及子目录中递归查找所有 JSONL 文件"""
    jsonl_files = []
    
    try:
        # 递归查找所有 .jsonl 文件
        for file_path in directory.rglob("*.jsonl"):
            if file_path.is_file():
                jsonl_files.append(file_path)
                logger.info(f"发现 JSONL 文件: {file_path}")
        
        # 也查找 .temp_translation.jsonl 文件
        for file_path in directory.rglob("*.temp_translation.jsonl"):
            if file_path.is_file() and file_path not in jsonl_files:
                jsonl_files.append(file_path)
                logger.info(f"发现临时翻译文件: {file_path}")
                
    except Exception as e:
        logger.error(f"扫描目录失败 {directory}: {e}")
    
    return jsonl_files


def load_translations_from_jsonl(file_path: Path) -> List[TranslationObject]:
    """从 JSONL 文件加载翻译数据"""
    translations = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                try:
                    # 解析 JSON 数据
                    record = json.loads(line)
                    
                    # 创建 TranslationObject
                    translation_obj = TranslationObject.from_dict(record)
                    
                    # 确保有 translation_key
                    if not translation_obj.translation_key:
                        # 生成新的 translation_key
                        source_text = translation_obj.original_text
                        file_name = translation_obj.file_name or str(file_path.name)
                        translation_key = hashlib.md5(
                            (source_text + file_name + str(datetime.now())).encode('utf-8')
                        ).hexdigest()
                        translation_obj.translation_key = translation_key
                        logger.debug(f"为记录生成新的 translation_key: {translation_key}")
                    
                    translations.append(translation_obj)
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"跳过无效的 JSON 行 {file_path}:{line_num}: {e}")
                    continue
                except Exception as e:
                    logger.error(f"处理记录失败 {file_path}:{line_num}: {e}")
                    continue
        
        logger.info(f"从文件 {file_path} 加载了 {len(translations)} 条翻译记录")
        
    except Exception as e:
        logger.error(f"读取文件失败 {file_path}: {e}")
    
    return translations


def import_translations_to_database(config_name: str, translations: List[TranslationObject], 
                                   db_interface: DatabaseInterface, update_vector: bool = True) -> tuple:
    """将翻译数据导入数据库"""
    if not translations:
        return 0, 0, []
    
    try:
        # 使用批量更新方法
        success_count, error_count, errors = db_interface.update_translation_batch(
            config_name, translations, update_vector=update_vector
        )
        
        logger.info(f"数据库导入完成: 成功 {success_count}, 失败 {error_count}")
        
        if errors:
            for error in errors:
                logger.warning(f"导入错误: {error}")
        
        return success_count, error_count, errors
        
    except Exception as e:
        logger.error(f"数据库导入失败: {e}")
        return 0, len(translations), [str(e)]


def main():
    parser = argparse.ArgumentParser(description='导入 JSONL 翻译文件到数据库')
    parser.add_argument('mod_path', help='包含 JSONL 文件的模组目录路径')
    parser.add_argument('config_name', help='目标配置名称（不包含 .json 后缀）')
    parser.add_argument('--no-vector', action='store_true', help='跳过向量数据库更新（仅更新 SQLite）')
    parser.add_argument('--batch-size', type=int, default=100, help='批量处理大小（默认 100）')
    
    args = parser.parse_args()
    
    mod_path = Path(args.mod_path)
    config_name = args.config_name
    update_vector = not args.no_vector
    batch_size = args.batch_size
    
    # 验证输入参数
    if not mod_path.exists():
        logger.error(f"目录不存在: {mod_path}")
        sys.exit(1)
    
    if not mod_path.is_dir():
        logger.error(f"路径不是目录: {mod_path}")
        sys.exit(1)
    
    logger.info(f"开始导入任务:")
    logger.info(f"  模组路径: {mod_path}")
    logger.info(f"  配置名称: {config_name}")
    logger.info(f"  更新向量数据库: {update_vector}")
    logger.info(f"  批量大小: {batch_size}")
    
    # 初始化数据库接口
    try:
        db_interface = DatabaseInterface("hybrid_memory")
        logger.info("数据库接口初始化成功")
    except Exception as e:
        logger.error(f"数据库接口初始化失败: {e}")
        sys.exit(1)
    
    try:
        # 查找所有 JSONL 文件
        jsonl_files = find_jsonl_files(mod_path)
        
        if not jsonl_files:
            logger.warning(f"在目录 {mod_path} 中没有找到 JSONL 文件")
            return
        
        logger.info(f"找到 {len(jsonl_files)} 个 JSONL 文件")
        
        # 统计信息
        total_files = len(jsonl_files)
        total_translations = 0
        total_success = 0
        total_errors = 0
        processed_files = 0
        
        # 处理每个文件
        for file_path in jsonl_files:
            logger.info(f"处理文件 [{processed_files + 1}/{total_files}]: {file_path.relative_to(mod_path)}")
            
            # 加载翻译数据
            translations = load_translations_from_jsonl(file_path)
            total_translations += len(translations)
            
            if not translations:
                logger.warning(f"文件 {file_path} 中没有有效的翻译记录")
                processed_files += 1
                continue
            
            # 分批处理大文件
            if len(translations) > batch_size:
                logger.info(f"文件包含 {len(translations)} 条记录，将分批处理（每批 {batch_size} 条）")
                
                for i in range(0, len(translations), batch_size):
                    batch = translations[i:i + batch_size]
                    batch_num = i // batch_size + 1
                    total_batches = (len(translations) + batch_size - 1) // batch_size
                    
                    logger.info(f"  处理批次 {batch_num}/{total_batches} ({len(batch)} 条记录)")
                    
                    success_count, error_count, errors = import_translations_to_database(
                        config_name, batch, db_interface, update_vector
                    )
                    
                    total_success += success_count
                    total_errors += error_count
            else:
                # 小文件直接处理
                success_count, error_count, errors = import_translations_to_database(
                    config_name, translations, db_interface, update_vector
                )
                
                total_success += success_count
                total_errors += error_count
            
            processed_files += 1
            logger.info(f"文件 {file_path.name} 处理完成")
        
        # 输出最终统计
        logger.info("=" * 50)
        logger.info("导入完成统计:")
        logger.info(f"  处理文件数: {processed_files}/{total_files}")
        logger.info(f"  总翻译记录: {total_translations}")
        logger.info(f"  成功导入: {total_success}")
        logger.info(f"  导入失败: {total_errors}")
        logger.info(f"  成功率: {(total_success / total_translations * 100):.2f}%" if total_translations > 0 else "  成功率: N/A")
        
        if total_errors > 0:
            logger.warning(f"有 {total_errors} 条记录导入失败，请检查日志文件")
        
    except KeyboardInterrupt:
        logger.info("用户中断操作")
        sys.exit(1)
    except Exception as e:
        logger.error(f"导入过程发生错误: {e}")
        sys.exit(1)
    finally:
        # 关闭数据库连接
        try:
            db_interface.close()
            logger.info("数据库连接已关闭")
        except:
            pass


if __name__ == "__main__":
    main()
