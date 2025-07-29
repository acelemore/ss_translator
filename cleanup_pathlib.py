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
pathlib冲突清理脚本
专门处理PyInstaller与pathlib包的冲突问题
"""

import subprocess
import sys
import shutil
from pathlib import Path

def log(message):
    print(f"[CLEANUP] {message}")

def clean_pathlib():
    """清理pathlib相关冲突"""
    log("开始清理pathlib冲突...")
    
    # 1. 卸载pathlib包
    log("卸载pathlib包...")
    try:
        result = subprocess.run([sys.executable, "-m", "pip", "uninstall", "pathlib", "-y"], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            log("✅ pathlib包卸载成功")
        else:
            log("⚠️ pathlib包可能未安装或已卸载")
    except Exception as e:
        log(f"卸载pathlib时出错: {e}")
    
    # 2. 清理可能的残留文件
    log("清理残留文件...")
    try:
        # 获取site-packages路径
        import site
        for site_dir in site.getsitepackages():
            site_path = Path(site_dir)
            
            # 清理pathlib相关文件
            pathlib_files = [
                site_path / "pathlib.py",
                site_path / "pathlib",
                site_path / "pathlib-*.dist-info"
            ]
            
            for pathlib_file in pathlib_files:
                if pathlib_file.exists():
                    try:
                        if pathlib_file.is_file():
                            pathlib_file.unlink()
                            log(f"删除文件: {pathlib_file}")
                        elif pathlib_file.is_dir():
                            shutil.rmtree(pathlib_file)
                            log(f"删除目录: {pathlib_file}")
                    except Exception as e:
                        log(f"删除 {pathlib_file} 时出错: {e}")
                        
            # 清理通配符匹配的文件
            try:
                for pathlib_dist in site_path.glob("pathlib*.dist-info"):
                    shutil.rmtree(pathlib_dist)
                    log(f"删除目录: {pathlib_dist}")
            except Exception as e:
                log(f"清理pathlib dist-info时出错: {e}")
                
    except Exception as e:
        log(f"清理残留文件时出错: {e}")
    
    # 3. 验证清理结果
    log("验证清理结果...")
    try:
        result = subprocess.run([sys.executable, "-c", "import pathlib; print(pathlib.__file__)"], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            pathlib_path = result.stdout.strip()
            if "site-packages" in pathlib_path:
                log(f"⚠️ 仍然发现非标准库pathlib: {pathlib_path}")
                log("需要手动删除此文件")
                return False
            else:
                log(f"✅ 使用标准库pathlib: {pathlib_path}")
                return True
        else:
            log("❌ pathlib导入失败，这可能导致其他问题")
            return False
    except Exception as e:
        log(f"验证时出错: {e}")
        return False

def main():
    log("PathLib冲突清理工具")
    log("=" * 40)
    
    if clean_pathlib():
        log("🎉 PathLib冲突清理完成！")
        log("现在可以重新运行构建脚本")
        return True
    else:
        log("❌ PathLib冲突清理失败")
        log("请手动检查并清理pathlib相关文件")
        return False

if __name__ == "__main__":
    if main():
        sys.exit(0)
    else:
        sys.exit(1)