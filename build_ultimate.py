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
Starsector翻译工具 - 修复版构建脚本
彻底解决pathlib和编码问题
"""

import os
import sys
import subprocess
import shutil
import zipfile
import urllib.request
from pathlib import Path

def log(message):
    print(f"[BUILD] {message}")

def run_command_safe(cmd, cwd=None, show_full_output=False, timeout=None):
    """最安全的命令执行方式"""
    log(f"执行: {cmd}")
    
    # 为PyInstaller设置更长的超时时间
    if 'PyInstaller' in cmd and timeout is None:
        timeout = 1800  # 30分钟
    elif timeout is None:
        timeout = 300   # 默认5分钟
    
    try:
        result = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, 
                              text=True, encoding='utf-8', errors='replace', 
                              timeout=timeout)
        
        if result.returncode != 0:
            log(f"❌ 命令失败 (返回码: {result.returncode})")
            if result.stderr:
                if show_full_output:
                    log(f"完整错误输出:\n{result.stderr}")
                else:
                    log(f"错误: {result.stderr[:500]}...")
            if result.stdout:
                if show_full_output:
                    log(f"完整标准输出:\n{result.stdout}")
                else:
                    log(f"输出: {result.stdout[:300]}...")
            return False
        
        if show_full_output and result.stdout:
            log(f"输出: {result.stdout}")
        
        return True
    except subprocess.TimeoutExpired:
        log(f"❌ 命令超时 ({timeout}秒)")
        return False
    except Exception as e:
        log(f"❌ 执行异常: {e}")
        return False

def thorough_pathlib_cleanup():
    """清理pathlib冲突 (保守模式)"""
    log("🧹 检查pathlib冲突...")
    
    # 只检查是否有pathlib冲突，不强制卸载
    try:
        result = subprocess.run(f'"{sys.executable}" -c "import pathlib; print(pathlib.__file__)"', 
                              shell=True, capture_output=True, text=True)
        if result.returncode == 0 and 'site-packages' in result.stdout:
            log("⚠️ 发现第三方pathlib包，可能需要手动处理")
            # 只在确实有冲突时才卸载
            subprocess.run(f'"{sys.executable}" -m pip uninstall pathlib -y', 
                         shell=True, capture_output=True)
        else:
            log("✅ pathlib状态正常")
    except Exception:
        log("✅ pathlib检查完成")
    
    return True

def download_nodejs():
    """下载Node.js (利用缓存)"""
    node_version = "20.18.0"
    node_url = f"https://nodejs.org/dist/v{node_version}/node-v{node_version}-win-x64.zip"
    
    temp_dir = Path("temp_nodejs")
    temp_dir.mkdir(exist_ok=True)
    
    node_zip = temp_dir / "node.zip"
    node_dir = temp_dir / "nodejs"
    
    # 检查Node.js是否已存在且版本正确
    if node_dir.exists():
        node_exe = node_dir / "node.exe"
        if node_exe.exists():
            try:
                # 验证Node.js版本
                result = subprocess.run([str(node_exe), "--version"], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0 and node_version in result.stdout:
                    log(f"✅ Node.js {node_version} 缓存有效，跳过下载")
                    return node_dir
                else:
                    log("⚠️ Node.js版本不匹配，重新下载")
            except Exception:
                log("⚠️ Node.js验证失败，重新下载")
    
    try:
        log("📥 下载Node.js...")
        urllib.request.urlretrieve(node_url, node_zip)
        
        log("📦 解压Node.js...")
        with zipfile.ZipFile(node_zip, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        extracted_dir = temp_dir / f"node-v{node_version}-win-x64"
        if extracted_dir.exists():
            extracted_dir.rename(node_dir)
        
        node_zip.unlink()
        log("✅ Node.js准备完成")
        return node_dir
        
    except Exception as e:
        log(f"❌ Node.js下载失败: {e}")
        return None

def build_frontend():
    """构建前端 (利用缓存)"""
    frontend_dir = Path("frontend")
    if not frontend_dir.exists():
        log("⚠️ 前端目录不存在，跳过")
        return True
    
    log("🔧 构建Vue前端...")
    
    # 检查node_modules是否存在且package.json没有变化
    node_modules = frontend_dir / "node_modules"
    package_json = frontend_dir / "package.json"
    package_lock = frontend_dir / "package-lock.json"
    
    need_install = True
    if node_modules.exists() and package_json.exists():
        try:
            # 比较package.json和node_modules的修改时间
            package_time = package_json.stat().st_mtime
            node_modules_time = node_modules.stat().st_mtime
            
            if node_modules_time > package_time:
                log("✅ 前端依赖缓存有效，跳过npm install")
                need_install = False
        except Exception:
            log("⚠️ 缓存检查失败，重新安装依赖")
    
    if need_install:
        log("📦 安装前端依赖...")
        if not run_command_safe("npm install", cwd=frontend_dir):
            return False
    
    # 检查是否需要重新构建
    dist_dir = frontend_dir / "dist"
    need_build = True
    
    if dist_dir.exists():
        try:
            # 检查源代码和构建结果的时间戳
            src_dir = frontend_dir / "src"
            if src_dir.exists():
                # 获取src目录下最新文件的修改时间
                src_files = list(src_dir.rglob("*"))
                if src_files:
                    latest_src_time = max(f.stat().st_mtime for f in src_files if f.is_file())
                    dist_time = dist_dir.stat().st_mtime
                    
                    if dist_time > latest_src_time:
                        log("✅ 前端构建缓存有效，跳过构建")
                        need_build = False
        except Exception:
            log("⚠️ 构建缓存检查失败，重新构建")
    
    if need_build:
        log("🔨 构建Vue前端...")
        if not run_command_safe("npm run build", cwd=frontend_dir):
            return False
    
    # 复制构建结果
    try:
        dist_dir = frontend_dir / "dist"
        if dist_dir.exists():
            # 确保目标目录存在
            Path("templates").mkdir(exist_ok=True)
            Path("static").mkdir(exist_ok=True)
            
            # 复制文件
            index_file = dist_dir / "index.html"
            if index_file.exists():
                shutil.copy2(index_file, "templates/index.html")
            
            assets_dir = dist_dir / "assets"
            if assets_dir.exists():
                if Path("static").exists():
                    shutil.rmtree("static")
                shutil.copytree(assets_dir, "static")
        
        log("✅ 前端构建完成")
        return True
    except Exception as e:
        log(f"❌ 前端文件复制失败: {e}")
        return False

def create_ultimate_spec(nodejs_dir):
    """创建PyInstaller配置"""
    nodejs_path = str(nodejs_dir).replace('\\', '/')
    
    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['web_ui.py'],
    pathex=['.'],
    binaries=[
        ('{nodejs_path}/node.exe', 'nodejs/'),
    ],
    datas=[
        ('frontend/dist', 'frontend/dist'),
        ('templates', 'templates'),
        ('static', 'static'), 
        ('translate_helper', 'translate_helper'),
        ('api', 'api'),
        ('{nodejs_path}', 'nodejs/'),
        ('models', 'models'),
    ],
    hiddenimports=[
        'flask',
        'werkzeug',
        'jinja2',
        'click',
        'itsdangerous',
        'markupsafe',
        'openai',
        'anthropic',
        'requests',
        'urllib3',
        'certifi',
        'charset_normalizer',
        'idna',
        'argparse',
        'logging',
        'json',
        'os',
        'sys',
        'threading',
        'queue',
        'time',
        'datetime',
        'hashlib',
        'uuid',
        'subprocess',
        'tempfile',
        'shutil',
        'zipfile',
        're',
        # ChromaDB相关依赖
        'chromadb',
        'chromadb.api',
        'chromadb.config',
        'chromadb.db',
        'chromadb.db.impl',
        'chromadb.db.impl.sqlite',
        'chromadb.db.impl.grpc',
        'chromadb.utils',
        'chromadb.telemetry',
        'sqlite3',
        'duckdb',
        'onnxruntime',
        'overrides',
        'posthog',
        'pulsar_client',
        'pydantic',
        'typing_extensions',
        # C扩展模块 - 提高ChromaDB性能
        '_testbuffer',
        '_testcapi',
        '_testimportmultiple',
        '_testinternalcapi',
        '_testmultiphase',
        'array',
        '_array',
        'cmath',
        'math',
        '_datetime',
        '_decimal',
        '_heapq',
        '_bisect',
        '_random',
        '_operator',
        '_collections',
        '_functools',
        '_pickle',
        '_json',
        '_struct',
        '_csv',
        '_sqlite3',
        '_lzma',
        '_bz2',
        'zlib',
        '_hashlib',
        '_md5',
        '_sha1',
        '_sha256',
        '_sha512',
        '_blake2',
        '_sha3',
        'api.config_api',
        'api.translation_api', 
        'api.progress_api',
        'api.terminology_api',
        'api.review_api',
        'api.memory_api',
        'translate_helper.translate_helper_base',
        'translate_helper.translate_helper_csv',
        'translate_helper.translate_helper_jar',
        'translate_helper.translate_helper_json',
        'config_manager',
        'global_values',
        'improved_translator',
        'progress_manager',
        'translation_object',
        'vector_translation_memory',
        'model_manager',
    ],
    hookspath=['.'],
    runtime_hooks=[],
    excludes=[
        'configs',
        'translation_work',
        'vector_memory',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts, 
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='StarsectorTranslator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,
    argv_emulation=False,
)
'''
    
    with open("ultimate.spec", "w", encoding="utf-8") as f:
        f.write(spec_content)
    
    log("✅ 配置创建完成")
    return True

def build_exe():
    """构建EXE (利用缓存)"""
    # 设置环境变量跳过模型初始化
    os.environ['PYINSTALLER_BUILD'] = '1'
    
    # 保守的pathlib清理
    thorough_pathlib_cleanup()
    
    log("📦 检查必要依赖...")
    required_packages = [
        'pyinstaller',
        'chromadb',
        'flask',
        'requests', 
        'openai',
        'anthropic'
    ]
    
    # 检查哪些包需要安装
    packages_to_install = []
    for package in required_packages:
        try:
            result = subprocess.run(f'"{sys.executable}" -m pip show {package}', 
                                  shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                packages_to_install.append(package)
            else:
                log(f"✅ {package} 已安装")
        except Exception:
            packages_to_install.append(package)
    
    # 只安装缺失的包
    if packages_to_install:
        log(f"� 安装缺失的依赖: {', '.join(packages_to_install)}")
        for package in packages_to_install:
            if not run_command_safe(f'"{sys.executable}" -m pip install {package}'):
                log(f"⚠️ {package} 安装失败，继续构建...")
    else:
        log("✅ 所有依赖已安装")
    
    # 检查是否需要重新构建
    spec_file = Path("ultimate.spec")
    exe_file = Path("dist/StarsectorTranslator.exe")
    main_file = Path("web_ui.py")
    
    need_rebuild = True
    if exe_file.exists() and spec_file.exists() and main_file.exists():
        try:
            exe_time = exe_file.stat().st_mtime
            spec_time = spec_file.stat().st_mtime
            main_time = main_file.stat().st_mtime
            
            # 检查关键Python文件的修改时间
            py_files = list(Path(".").glob("*.py"))
            latest_py_time = max(f.stat().st_mtime for f in py_files if f.is_file())
            
            if exe_time > latest_py_time and exe_time > spec_time:
                log("✅ EXE缓存有效，跳过PyInstaller构建")
                need_rebuild = False
        except Exception:
            log("⚠️ 构建缓存检查失败，重新构建")
    
    if need_rebuild:
        log("🔨 构建EXE...")
        # 使用--noconfirm但不使用--clean来保留缓存
        if not run_command_safe(f'"{sys.executable}" -m PyInstaller ultimate.spec --noconfirm', show_full_output=True):
            log("❌ PyInstaller构建失败")
            log("💡 尝试诊断问题...")
            
            # 检查关键文件是否存在
            required_files = ['web_ui.py', 'ultimate.spec']
            for file in required_files:
                if not Path(file).exists():
                    log(f"❌ 缺少必需文件: {file}")
            
            # 检查导入问题
            log("🔍 检查主模块导入...")
            try:
                # 设置环境变量进行测试
                test_env = os.environ.copy()
                test_env['PYINSTALLER_BUILD'] = '1'
                
                result = subprocess.run(f'"{sys.executable}" -c "import web_ui; print(\'web_ui导入成功\')"', 
                                      shell=True, capture_output=True, text=True, 
                                      encoding='utf-8', errors='replace', env=test_env)
                if result.returncode != 0:
                    log(f"❌ web_ui模块导入失败: {result.stderr}")
                else:
                    log("✅ web_ui模块导入正常")
            except Exception as e:
                log(f"❌ 导入测试异常: {e}")
            
            return False
    
    # 清除环境变量
    if 'PYINSTALLER_BUILD' in os.environ:
        del os.environ['PYINSTALLER_BUILD']
    
    return True

def create_distribution():
    """创建分发包"""
    dist_dir = Path("dist")
    
    # 修复的启动脚本
    start_bat = '''@echo off
chcp 65001 > nul 2>&1
cls
echo ==========================================
echo   Starsector 通用模组翻译工具
echo ==========================================
echo.
echo 启动信息:
echo   服务地址: http://localhost:5000
echo   停止服务: 按 Ctrl+C
echo.
echo 正在启动服务器，请稍候...
echo.

StarsectorTranslator.exe %*

echo.
echo 服务器已停止
echo.
pause
'''

    # 调试版本的启动脚本
    debug_bat = '''@echo off
chcp 65001 > nul 2>&1
cls
echo ==========================================
echo   Starsector 翻译工具 [调试模式]
echo ==========================================
echo.
echo 调试信息将显示在此窗口
echo 如果程序无法启动，请查看详细错误信息
echo.
echo 正在启动...
echo.

StarsectorTranslator.exe --port 5000
if ERRORLEVEL 1 (
    echo.
    echo ❌ 程序启动失败，错误码: %ERRORLEVEL%
    echo.
    echo 可能的原因:
    echo   1. 端口5000被占用，请尝试其他端口
    echo   2. 必要文件缺失
    echo   3. 权限不足
    echo.
    echo 请检查上方的错误信息
)

echo.
echo 按任意键退出...
pause > nul
'''
    
    readme = '''# Starsector 通用模组翻译工具

## 快速开始
1. 双击 start.bat 启动 (正常模式)
2. 双击 debug.bat 启动 (调试模式，显示详细错误信息)
3. 浏览器访问 http://localhost:5000 
4. 配置API并开始翻译

## 命令行使用
```
StarsectorTranslator.exe          # 默认5000端口
StarsectorTranslator.exe -p 8080  # 指定8080端口
```

## 故障排除
- 如果程序无法启动，请使用 debug.bat 查看详细错误信息
- 首次启动需要1-2分钟初始化模型
- 确保端口未被占用
- 需要网络连接调用翻译API
'''
    
    try:
        with open(dist_dir / "start.bat", "w", encoding="utf-8", errors='ignore') as f:
            f.write(start_bat)
        
        with open(dist_dir / "debug.bat", "w", encoding="utf-8", errors='ignore') as f:
            f.write(debug_bat)
        
        with open(dist_dir / "README.md", "w", encoding="utf-8") as f:
            f.write(readme)
        
        log("✅ 分发文件创建完成")
    except Exception as e:
        log(f"⚠️ 分发文件创建部分失败: {e}")

def main():
    """主构建流程"""
    log("🚀 启动构建流程...")
    
    try:
        # 1. Node.js
        nodejs_dir = download_nodejs()
        if not nodejs_dir:
            return False
        
        # 2. 前端
        if not build_frontend():
            return False
        
        # 3. 配置
        if not create_ultimate_spec(nodejs_dir):
            return False
        
        # 4. 构建
        if not build_exe():
            return False
        
        # 5. 分发
        create_distribution()
        
        # 6. 智能清理 (保留缓存)
        log("🧹 清理临时文件...")
        cleanup_items = [
            "__pycache__",
            # 保留build目录作为PyInstaller缓存
            # "build",  
        ]
        
        for item in cleanup_items:
            item_path = Path(item)
            if item_path.exists():
                if item_path.is_dir():
                    shutil.rmtree(item_path)
                else:
                    item_path.unlink()
                log(f"✅ 清理: {item}")
        
        # 保留重要缓存目录的说明
        cache_dirs = ["build", "temp_nodejs", "frontend/node_modules", "frontend/dist"]
        existing_cache = [d for d in cache_dirs if Path(d).exists()]
        if existing_cache:
            log(f"💾 保留缓存: {', '.join(existing_cache)}")
        
        log("🎉 构建完成！")
        log("📁 输出目录: dist/")
        log("🚀 启动: cd dist && start.bat")
        
        return True
        
    except Exception as e:
        log(f"❌ 构建异常: {e}")
        return False

if __name__ == "__main__":
    if main():
        sys.exit(0)
    else:
        sys.exit(1)