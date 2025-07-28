"""
全局状态管理模块
集中管理所有跨模块共享的变量和状态
"""
from vector_translation_memory import VectorTranslationMemory
from improved_translator import ImprovedTranslator

# 向量数据库实例
vdb = VectorTranslationMemory()

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
    
    