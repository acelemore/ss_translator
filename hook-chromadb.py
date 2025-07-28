"""
PyInstaller hook for ChromaDB
"""
from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files

# 收集所有ChromaDB相关的模块和数据
datas, binaries, hiddenimports = collect_all('chromadb')

# 添加额外的隐藏导入
hiddenimports += [
    'sqlite3',
    'duckdb', 
    'onnxruntime',
    'overrides',
    'posthog',
    'pydantic',
    'typing_extensions',
    'chromadb.api',
    'chromadb.config',
    'chromadb.db',
    'chromadb.db.impl',
    'chromadb.db.impl.sqlite',
    'chromadb.utils',
    'chromadb.telemetry',
]

# 尝试收集DuckDB和SQLite的二进制文件
try:
    duckdb_datas, duckdb_binaries, duckdb_hiddenimports = collect_all('duckdb')
    datas += duckdb_datas
    binaries += duckdb_binaries
    hiddenimports += duckdb_hiddenimports
except:
    pass

# 收集ONNX运行时
try:
    onnx_datas, onnx_binaries, onnx_hiddenimports = collect_all('onnxruntime')
    datas += onnx_datas
    binaries += onnx_binaries
    hiddenimports += onnx_hiddenimports
except:
    pass
