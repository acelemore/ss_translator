
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
EXE运行时的路径管理器
处理打包后的资源路径问题
"""

import sys
import os
from pathlib import Path

def get_resource_path(relative_path):
    """获取资源文件的实际路径
    
    Args:
        relative_path: 相对路径
        
    Returns:
        实际的文件路径
    """
    if getattr(sys, 'frozen', False):
        # 打包后的环境
        base_path = Path(sys._MEIPASS)
    else:
        # 开发环境
        base_path = Path(__file__).parent
    
    return base_path / relative_path

def get_node_executable():
    """获取Node.js可执行文件路径"""
    if getattr(sys, 'frozen', False):
        # 打包后的环境
        app_dir = Path(sys._MEIPASS)
        node_exe = app_dir / 'nodejs' / 'node.exe'
        if node_exe.exists():
            return str(node_exe)
    
    # 开发环境或系统Node.js
    return 'node'

def get_working_directory():
    """获取工作目录（用户数据目录）"""
    if getattr(sys, 'frozen', False):
        # 打包后的环境，使用exe所在目录
        return Path(sys.executable).parent
    else:
        # 开发环境
        return Path.cwd()

def ensure_working_directories():
    """确保工作目录存在"""
    working_dir = get_working_directory()
    
    # 创建必要的目录
    directories = [
        'translation_work',
        'vector_memory',
        'configs'
    ]
    
    for dir_name in directories:
        dir_path = working_dir / dir_name
        dir_path.mkdir(exist_ok=True)
    
    return working_dir