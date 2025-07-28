# Windows EXE 打包方案

本项目提供了三种打包方案，满足不同需求：

## 方案对比

| 方案 | 文件大小 | 独立性 | JAR翻译 | 适用场景 |
|------|----------|--------|---------|----------|
| 简化版 | ~50MB | 需要Node.js | ✅ (需安装Node.js) | 开发测试 |
| 完整版 | ~250MB | 完全独立 | ✅ (内置Node.js) | 生产分发 |

## 🚀 快速开始

### 方案1: 简化版 (推荐开发使用)
```bash
# 运行构建脚本
build_simple.bat
```

**特点:**
- 文件小，构建快
- 需要目标机器安装Node.js (JAR翻译功能)
- 适合开发和测试

### 方案2: 完整版 (推荐生产使用)  
```bash
# 运行构建脚本
build_full.bat
```

**特点:**
- 包含所有依赖，完全独立
- 内置便携版Node.js
- 用户无需安装任何依赖
- 适合生产环境分发

## 📋 系统要求

### 构建环境要求
- Windows 10/11
- Python 3.8+
- Node.js 16+ (构建时需要)
- 至少5GB可用磁盘空间

### 运行环境要求
- **简化版**: Windows 10/11 + Node.js
- **完整版**: 仅需Windows 10/11

## 🛠️ 构建过程

1. **前端构建**: 编译Vue.js项目
2. **依赖收集**: 收集Python包和Node.js环境
3. **代码修补**: 适配EXE运行环境
4. **打包生成**: 使用PyInstaller生成EXE
5. **文件整理**: 创建启动脚本和说明文档

## 📁 输出结构

```
dist/
├── StarsectorTranslator.exe  # 主程序
├── start.bat                 # 启动脚本
└── README.md                 # 使用说明
```

运行后会创建工作目录：
```
working_directory/
├── translation_work/         # 翻译工作文件
├── vector_memory/           # 向量记忆数据库
└── configs/                 # 配置文件
```

## 🎯 核心特性

### 1. 路径访问支持
- ✅ 程序可访问当前工作路径
- ✅ 可创建新文件夹和文件
- ✅ 支持相对路径和绝对路径

### 2. Node.js集成
- ✅ Python代码调用Node.js脚本
- ✅ 内嵌便携版Node.js (完整版)
- ✅ 自动路径解析和环境适配

### 3. 依赖包含
- ✅ 所有Python包 (Flask, OpenAI, ChromaDB等)
- ✅ Vue.js前端资源
- ✅ JavaScript翻译脚本
- ✅ Node.js运行环境 (完整版)

## ⚠️ 注意事项

### 构建前检查
1. 确保所有依赖已安装: `pip install -r requirements.txt`
2. 前端依赖已安装: `cd frontend && npm install`
3. 有足够磁盘空间 (至少5GB)

### 性能优化
- 首次启动可能需要1-2分钟 (解压临时文件)
- 建议在SSD上运行以提高启动速度
- JAR翻译功能需要较多内存 (建议4GB+)

### 分发建议
- 使用7-Zip等工具压缩dist目录
- 可制作安装包进一步简化部署
- 建议提供使用视频或详细文档

## 🔧 高级配置

### 自定义Node.js版本
编辑构建脚本中的 `NODE_VERSION` 变量：
```python
NODE_VERSION = "18.20.4"  # 修改为需要的版本
```

### 添加额外文件
在PyInstaller spec文件的 `datas` 部分添加：
```python
datas=[
    ('your_folder', 'your_folder'),
    ('your_file.txt', '.'),
]
```

### 修改图标
准备ico文件并在spec中设置：
```python
exe = EXE(
    # ... 其他参数
    icon='your_icon.ico'
)
```

## 🚨 常见问题

### Q: EXE文件很大，如何优化？
A: 使用UPX压缩，在spec文件中设置 `upx=True`

### Q: 杀毒软件误报怎么办？
A: PyInstaller生成的exe可能被误报，可以：
- 添加到杀毒软件白名单
- 使用数字签名证书签名exe文件

### Q: JAR翻译功能不工作？
A: 检查：
- Node.js环境是否正确内嵌
- JavaScript脚本是否包含在打包中
- 工作目录权限是否正确

### Q: 启动很慢怎么办？
A: 可以：
- 使用SSD存储
- 关闭实时杀毒扫描
- 使用 `--noconfirm` 参数重新打包

## 📞 技术支持

如遇到问题：
1. 查看控制台输出信息
2. 检查生成的日志文件
3. 确认系统环境符合要求
4. 尝试在不同Windows版本上测试

## 🔄 更新和维护

### 更新依赖
```bash
pip install -r requirements.txt --upgrade
cd frontend && npm update
```

### 重新构建
```bash
# 清理旧文件
rmdir /s build dist
# 重新构建
build_full.bat
```

---

**最后更新**: 2025-01-26  
**版本**: 1.0.0  
**兼容性**: Windows 10/11 x64
