
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