
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
Starsector 翻译工具 Web界面
提供友好的图形界面管理翻译过程
支持向量数据库的翻译记忆和专有名词管理

重构版本 - 支持端口参数和EXE打包
"""

import argparse
import logging
import os
import sys
from flask import Flask, render_template
import global_values  # 导入全局状态管理模块

# EXE支持
try:
    from exe_utils import get_resource_path, ensure_working_directories
    # 确保工作目录存在
    ensure_working_directories()
except ImportError:
    # 开发环境
    def get_resource_path(relative_path):
        return relative_path

from api.config_api import config_bp
from api.translation_api import translation_bp
from api.progress_api import progress_bp
from api.terminology_api import terminology_bp
from api.review_api import review_bp
from api.memory_api import memory_bp

logger = logging.getLogger(__name__)

def create_app():
    """创建Flask应用工厂函数"""
    app = Flask(__name__, 
                template_folder=get_resource_path('frontend/dist'),
                static_folder=get_resource_path('frontend/dist'))
    app.secret_key = 'your-secret-key-here'

    # 注册蓝图
    app.register_blueprint(config_bp)
    app.register_blueprint(translation_bp)
    app.register_blueprint(progress_bp)
    app.register_blueprint(terminology_bp)
    app.register_blueprint(review_bp)
    app.register_blueprint(memory_bp)

    @app.route('/')
    def index():
        """主页"""
        return render_template('index.html')

    @app.route('/assets/<path:filename>')
    def assets_files(filename):
        """Vue构建的资源文件服务"""
        from flask import send_from_directory
        return send_from_directory(get_resource_path('frontend/dist/assets'), filename)
    
    @app.route('/static/<path:filename>')
    def static_files(filename):
        """传统静态文件服务"""
        from flask import send_from_directory
        return send_from_directory(get_resource_path('static'), filename)
    
    return app

# 为了向后兼容，保留模块级别的app实例
app = create_app()

def main():
    """启动Web服务器"""
    print("🚀 翻译工具启动中...")
    print(f"📍 工作目录: {os.getcwd()}")
    print(f"🐍 Python版本: {sys.version}")
    print(f"📄 脚本位置: {__file__}")
    
    # 检查关键文件是否存在
    critical_files = ['configs/global_config.json']
    for file_path in critical_files:
        if os.path.exists(file_path):
            print(f"✅ 关键文件存在: {file_path}")
        else:
            print(f"❌ 关键文件缺失: {file_path}")
    
    try:
        print("📦 导入关键模块中...")
        import global_values
        print("✅ global_values 导入成功")
        
        # 检查向量数据库初始化
        if hasattr(global_values, 'vdb') and global_values.vdb:
            print("✅ 向量数据库初始化成功")
        else:
            print("⚠️ 向量数据库未初始化")
            
    except Exception as e:
        print(f"❌ 模块导入失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    parser = argparse.ArgumentParser(description='Starsector翻译工具Web服务器')
    parser.add_argument('--port', '-p', type=int, default=5000, 
                       help='服务器端口 (默认: 5000)')
    args = parser.parse_args()
    
    port = args.port
    
    print("� 创建Flask应用...")
    app_instance = create_app()
    print("✅ Flask应用创建成功")
    
    print()
    print("=" * 60)
    print("�🚀 Starsector 通用模组翻译工具")
    print(f"📱 访问地址: http://localhost:{port}")
    print("🔧 请在界面中配置API密钥和翻译设置")
    print("⚡ 按 Ctrl+C 停止服务器")
    print("=" * 60)
    print()
    
    try:
        print(f"🌐 启动Flask服务器 (host=0.0.0.0, port={port})...")
        app_instance.run(host='0.0.0.0', port=port, debug=False)
    except KeyboardInterrupt:
        print("\n服务器已停止")
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"❌ 端口 {port} 已被占用，请尝试其他端口")
            print(f"   例如: {sys.argv[0]} --port {port + 1}")
        else:
            print(f"❌ 启动失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 意外错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()