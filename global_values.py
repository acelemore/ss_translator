
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
全局状态管理模块
集中管理所有跨模块共享的变量和状态
"""
from vector_translation_memory import VectorTranslationMemory
from db_interface import DatabaseInterface
from improved_translator import ImprovedTranslator

# 数据库操作统一接口（主要接口）
db = DatabaseInterface()

# 向量数据库实例（保留兼容性）
vdb = db.vector_memory

# 当前选择的配置名称
current_config_name = None

# 翻译器实例
translator = None

# 专有名词替换器实例
terminology_replacer = None




def set_config(config_name):
    """设置当前配置并重置相关状态"""
    global current_config_name, translator
    
    current_config_name = config_name
    translator = ImprovedTranslator(config_name)
    
    