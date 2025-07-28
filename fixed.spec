# -*- mode: python ; coding: utf-8 -*-
# Starsector翻译工具 PyInstaller 配置

a = Analysis(
    ['web_ui.py'],
    pathex=['.'],
    binaries=[
        ('temp_nodejs/nodejs/node.exe', 'nodejs/'),
    ],
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
        ('translate_helper', 'translate_helper'),
        ('api', 'api'),
        ('temp_nodejs/nodejs', 'nodejs/'),
    ],
    hiddenimports=[
        'flask',
        'openai',
        'anthropic',
        'requests',
        'argparse',
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
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        'configs',
        'translation_work',
        'vector_memory',
        'pathlib',  # 明确排除pathlib
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
    upx=True,
    runtime_tmpdir=None,
    console=True,
    argv_emulation=False,
)
