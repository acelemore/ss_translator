#!/usr/bin/env python3
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
模型下载和管理工具
用于预下载 sentence-transformers 模型到本地
"""

import os
import sys
from pathlib import Path

def download_model():
    """下载模型到本地"""
    try:
        from sentence_transformers import SentenceTransformer
        
        model_name = 'all-MiniLM-L6-v2'
        local_path = Path("models") / model_name
        
        print(f"正在下载模型 {model_name}...")
        print("这可能需要几分钟时间，请耐心等待...")
        
        # 创建目录
        local_path.mkdir(parents=True, exist_ok=True)
        
        # 下载模型
        model = SentenceTransformer(model_name)
        
        # 保存到本地
        model.save(str(local_path))
        
        print(f"✓ 模型已成功下载到: {local_path.absolute()}")
        print("\n下次运行翻译程序时将自动使用本地模型")
        
        # 验证模型
        print("\n正在验证模型...")
        test_model = SentenceTransformer(str(local_path))
        test_embeddings = test_model.encode(["Hello world", "你好世界"])
        print(f"✓ 模型验证成功，嵌入维度: {len(test_embeddings[0])}")
        
        return True
        
    except ImportError:
        print("错误: 未安装 sentence-transformers")
        print("请先运行: pip install sentence-transformers")
        return False
    except Exception as e:
        print(f"下载模型失败: {e}")
        print("\n可能的解决方案:")
        print("1. 检查网络连接")
        print("2. 设置代理: export HTTP_PROXY=http://your-proxy:port")
        print("3. 手动从 https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2 下载")
        return False

def check_model():
    """检查本地模型状态"""
    model_paths = [
        Path("models/all-MiniLM-L6-v2"),
        Path.home() / ".cache" / "sentence_transformers" / "all-MiniLM-L6-v2",
    ]
    
    print("检查本地模型状态:")
    
    for path in model_paths:
        if path.exists():
            try:
                # 检查关键文件
                config_file = path / "config.json"
                model_file = path / "pytorch_model.bin"
                
                if config_file.exists() and model_file.exists():
                    print(f"✓ 发现完整模型: {path}")
                    
                    # 获取模型大小
                    total_size = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
                    size_mb = total_size / (1024 * 1024)
                    print(f"  模型大小: {size_mb:.1f} MB")
                    
                    return str(path)
                else:
                    print(f"⚠️ 模型不完整: {path}")
            except Exception as e:
                print(f"⚠️ 检查模型失败: {path} - {e}")
        else:
            print(f"✗ 模型不存在: {path}")
    
    print("\n未找到可用的本地模型")
    return None

def clean_cache():
    """清理模型缓存"""
    cache_paths = [
        Path("models"),
        Path.home() / ".cache" / "sentence_transformers",
    ]
    
    print("清理模型缓存:")
    
    for cache_path in cache_paths:
        if cache_path.exists():
            try:
                import shutil
                shutil.rmtree(cache_path)
                print(f"✓ 已清理: {cache_path}")
            except Exception as e:
                print(f"✗ 清理失败: {cache_path} - {e}")
        else:
            print(f"- 不存在: {cache_path}")

def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("模型管理工具")
        print("用法:")
        print("  python model_manager.py download    # 下载模型到本地")
        print("  python model_manager.py check       # 检查本地模型状态")
        print("  python model_manager.py clean       # 清理模型缓存")
        print("  python model_manager.py test        # 测试模型加载")
        return
    
    command = sys.argv[1].lower()
    
    if command == "download":
        success = download_model()
        sys.exit(0 if success else 1)
    
    elif command == "check":
        model_path = check_model()
        if model_path:
            print(f"\n推荐使用模型路径: {model_path}")
        sys.exit(0)
    
    elif command == "clean":
        clean_cache()
        sys.exit(0)
    
    elif command == "test":
        model_path = check_model()
        if model_path:
            try:
                from sentence_transformers import SentenceTransformer
                print(f"\n正在测试模型: {model_path}")
                model = SentenceTransformer(model_path)
                
                # 测试编码
                test_texts = ["Hello world", "你好世界", "This is a test"]
                embeddings = model.encode(test_texts)
                
                print(f"✓ 模型测试成功")
                print(f"  嵌入维度: {len(embeddings[0])}")
                print(f"  测试文本数: {len(test_texts)}")
                
                # 测试相似度
                similarity = model.similarity(embeddings[0:1], embeddings[1:2])[0][0]
                print(f"  相似度测试: {similarity:.4f}")
                
            except Exception as e:
                print(f"✗ 模型测试失败: {e}")
                sys.exit(1)
        else:
            print("未找到可用模型，请先下载模型")
            sys.exit(1)
    
    else:
        print(f"未知命令: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()