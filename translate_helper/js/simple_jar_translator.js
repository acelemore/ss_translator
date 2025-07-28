/**
 * 改进的JAR翻译脚本
 * 基于jar-string-editor的核心功能，使用java-class-tools进行专业的常量池操作
 * 支持按translation_key进行精确翻译匹配
 */

const fs = require('fs');
const path = require('path');
const JSZip = require('jszip');
const { 
    JavaClassFileReader, 
    JavaClassFileWriter, 
    Modifier, 
    InstructionParser, 
    Opcode, 
    ConstantType 
} = require('java-class-tools');

/**
 * 改进的JAR翻译函数，支持translation_key匹配
 */
async function translateJarWithKeys(inputJarPath, outputJarPath, translationsFile) {
    console.log('=== 改进的JAR翻译器 (支持translation_key) ===');
    console.log(`源文件: ${inputJarPath}`);
    console.log(`输出文件: ${outputJarPath}`);
    console.log(`翻译文件: ${translationsFile}`);
    
    // 读取翻译数据
    const translationsContent = fs.readFileSync(translationsFile, 'utf8');
    const translations = new Map(); // original -> translation
    const translationsByKey = new Map(); // translation_key -> {original, translation, context}
    
    // 判断是JSON还是JSONL格式
    let translationCount = 0;
    try {
        // 尝试解析为JSON数组
        const translationArray = JSON.parse(translationsContent);
        if (Array.isArray(translationArray)) {
            for (const data of translationArray) {
                if (data.original && data.translation) {
                    translations.set(data.original, data.translation);
                    if (data.translation_key) {
                        translationsByKey.set(data.translation_key, data);
                    }
                    translationCount++;
                }
            }
        }
    } catch (e) {
        // 如果JSON解析失败，尝试JSONL格式
        const lines = translationsContent.split('\n');
        for (const line of lines) {
            if (line.trim()) {
                try {
                    const data = JSON.parse(line);
                    if (data.original && data.translation) {
                        translations.set(data.original, data.translation);
                        if (data.translation_key) {
                            translationsByKey.set(data.translation_key, data);
                        }
                        translationCount++;
                    }
                } catch (e) {
                    console.warn(`跳过无效行: ${line.substring(0, 50)}...`);
                }
            }
        }
    }
    
    console.log(`加载了 ${translationCount} 条翻译`);
    console.log(`其中 ${translationsByKey.size} 条包含translation_key`);
    
    // 读取JAR文件
    const jarData = fs.readFileSync(inputJarPath);
    const jar = await JSZip.loadAsync(jarData);
    
    const classReader = new JavaClassFileReader();
    const classWriter = new JavaClassFileWriter();
    
    let totalReplacements = 0;
    let keyBasedReplacements = 0;
    let processedFiles = 0;
    let modifiedFiles = 0;
    
    // 获取所有.class文件
    const classFiles = Object.entries(jar.files).filter(([fileName, file]) => 
        !file.dir && fileName.endsWith('.class')
    );
    
    console.log(`找到 ${classFiles.length} 个.class文件`);
    
    // 处理每个class文件
    for (const [fileName, file] of classFiles) {
        processedFiles++;
        
        try {
            const classData = await file.async('arraybuffer');
            const classFile = classReader.read(classData);
            const constantPool = classFile.constant_pool;
            
            let fileModified = false;
            const alreadyMappedStrings = new Set();
            
            // 方法1: 遍历所有方法中的字符串常量引用
            for (const method of classFile.methods) {
                // 跳过抽象方法
                if ((method.access_flags & Modifier.ABSTRACT) !== 0) {
                    continue;
                }
                
                // 获取Code属性
                const codeAttribute = getAttribute(classFile, method);
                if (!codeAttribute) {
                    continue;
                }
                
                // 获取方法名
                const methodName = getUtf8String(constantPool, method.name_index);
                
                if (!methodName) {
                    continue;
                }
                
                // 解析指令
                const instructions = InstructionParser.fromBytecode(codeAttribute.code);
                
                // 查找字符串常量
                for (let i = 0; i < instructions.length; i++) {
                    const { opcode, operands } = instructions[i];
                    
                    // 只处理LDC和LDC_W指令（加载常量）
                    if (opcode !== Opcode.LDC && opcode !== Opcode.LDC_W) {
                        continue;
                    }
                    
                    // 获取常量池索引
                    const constantIndex = opcode === Opcode.LDC 
                        ? operands[0] 
                        : (operands[0] << 8) | operands[1]; // LDC_W
                    
                    const constantEntry = constantPool[constantIndex];
                    
                    // 只处理字符串常量
                    if (constantEntry && constantEntry.tag === ConstantType.STRING) {
                        const stringValue = getUtf8String(constantPool, constantIndex);
                        if (stringValue) {
                            // 跳过已处理的字符串
                            if (alreadyMappedStrings.has(constantIndex)) {
                                continue;
                            }
                            
                            // 构建上下文信息
                            const context = `${methodName}()`;
                            
                            // 生成翻译键：类名:函数名:文本索引:原文哈希（与jar_text_extractor.js保持一致）
                            const textHash = hash(stringValue);
                            const translationKey = `${fileName}:${context}:${i}:${textHash}`;
                            
                            let translatedValue = null;
                            let usedKey = false;
                            
                            // 首先尝试按translation_key匹配
                            if (translationsByKey.has(translationKey)) {
                                const keyData = translationsByKey.get(translationKey);
                                if (keyData.original === stringValue && keyData.translation) {
                                    translatedValue = keyData.translation;
                                    usedKey = true;
                                    keyBasedReplacements++;
                                }
                            }
                            
                            // 如果没有key匹配，回退到原文匹配
                            if (!translatedValue && translations.has(stringValue)) {
                                translatedValue = translations.get(stringValue);
                            }
                            
                            // 应用翻译
                            if (translatedValue && translatedValue !== stringValue) {
                                // 更新常量池中的UTF8字符串
                                const utf8Entry = constantPool[constantEntry.string_index];
                                const stringBytes = stringToUtf8ByteArray(translatedValue);
                                utf8Entry.length = stringBytes.length;
                                utf8Entry.bytes = stringBytes;
                                
                                fileModified = true;
                                totalReplacements++;
                                alreadyMappedStrings.add(constantIndex);
                                
                                const keyInfo = usedKey ? ' [按key匹配]' : ' [按原文匹配]';
                                console.log(`  [${fileName}] 替换${keyInfo}: "${stringValue.substring(0, 30)}..." -> "${translatedValue.substring(0, 30)}..."`);
                            }
                        }
                    }
                }
            }
            
            // 方法2: 直接扫描常量池中的所有字符串常量（作为补充）
            for (let constantIndex = 1; constantIndex < constantPool.length; constantIndex++) {
                const entry = constantPool[constantIndex];
                if (entry && entry.tag === ConstantType.STRING) {
                    try {
                        const stringValue = getUtf8String(constantPool, constantIndex);
                        if (stringValue) {
                            // 检查是否已经在方法中找到了
                            if (alreadyMappedStrings.has(constantIndex)) {
                                continue;
                            }
                            
                            const context = 'constant_pool';
                            const textHash = hash(stringValue);
                            const translationKey = `${fileName}:${context}:${constantIndex}:${textHash}`;
                            
                            let translatedValue = null;
                            let usedKey = false;
                            
                            // 首先尝试按translation_key匹配
                            if (translationsByKey.has(translationKey)) {
                                const keyData = translationsByKey.get(translationKey);
                                if (keyData.original === stringValue && keyData.translation) {
                                    translatedValue = keyData.translation;
                                    usedKey = true;
                                    keyBasedReplacements++;
                                }
                            }
                            
                            // 如果没有key匹配，回退到原文匹配
                            if (!translatedValue && translations.has(stringValue)) {
                                translatedValue = translations.get(stringValue);
                            }
                            
                            // 应用翻译
                            if (translatedValue && translatedValue !== stringValue) {
                                // 更新常量池中的UTF8字符串
                                const utf8Entry = constantPool[entry.string_index];
                                const stringBytes = stringToUtf8ByteArray(translatedValue);
                                utf8Entry.length = stringBytes.length;
                                utf8Entry.bytes = stringBytes;
                                
                                fileModified = true;
                                totalReplacements++;
                                alreadyMappedStrings.add(constantIndex);
                                
                                const keyInfo = usedKey ? ' [按key匹配]' : ' [按原文匹配]';
                                console.log(`  [${fileName}] 替换${keyInfo}: "${stringValue.substring(0, 30)}..." -> "${translatedValue.substring(0, 30)}..."`);
                            }
                        }
                    } catch (e) {
                        // 忽略解析错误
                    }
                }
            }
            
            // 如果文件被修改，写回JAR
            if (fileModified) {
                const modifiedClassData = classWriter.write(classFile);
                jar.file(fileName, modifiedClassData.buffer);
                modifiedFiles++;
                console.log(`修改文件: ${fileName}`);
            }
            
        } catch (error) {
            console.error(`处理文件 ${fileName} 时出错:`, error.message);
        }
        
        // 每处理100个文件报告一次进度
        if (processedFiles % 100 === 0) {
            console.log(`进度: ${processedFiles}/${classFiles.length} 文件已处理`);
        }
    }
    
    // 生成新JAR
    console.log('生成新JAR文件...');
    const outputData = await jar.generateAsync({
        type: "nodebuffer",
        compression: "DEFLATE"
    });
    
    fs.writeFileSync(outputJarPath, outputData);
    
    console.log(`\n翻译完成！`);
    console.log(`处理文件: ${processedFiles}`);
    console.log(`修改文件: ${modifiedFiles}`);
    console.log(`成功替换: ${totalReplacements}`);
    console.log(`按key匹配: ${keyBasedReplacements}`);
    console.log(`按原文匹配: ${totalReplacements - keyBasedReplacements}`);
    console.log(`输出大小: ${outputData.length} 字节`);
    
    return { processedFiles, modifiedFiles, totalReplacements, keyBasedReplacements };
}

// 辅助函数：获取方法的Code属性
function getAttribute(classFile, method) {
    for (const attribute of method.attributes) {
        const nameIndex = attribute.attribute_name_index;
        const utf8Entry = classFile.constant_pool[nameIndex];
        const attributeName = Buffer.from(utf8Entry.bytes).toString('utf8');
        
        if (attributeName === 'Code') {
            return attribute;
        }
    }
    return null;
}

// 辅助函数：从常量池获取UTF8字符串
function getUtf8String(constantPool, stringConstantIndex) {
    try {
        const stringEntry = constantPool[stringConstantIndex];
        if (!stringEntry) {
            return null;
        }
        
        // 如果是STRING常量，获取其指向的UTF8字符串
        if (stringEntry.tag === ConstantType.STRING) {
            const utf8Entry = constantPool[stringEntry.string_index];
            if (!utf8Entry || utf8Entry.tag !== ConstantType.UTF8) {
                return null;
            }
            return Buffer.from(utf8Entry.bytes).toString('utf8');
        }
        
        // 如果是UTF8常量，直接返回
        if (stringEntry.tag === ConstantType.UTF8) {
            return Buffer.from(stringEntry.bytes).toString('utf8');
        }
        
        return null;
    } catch (e) {
        return null;
    }
}

// 辅助函数：将字符串转换为UTF8字节数组
function stringToUtf8ByteArray(str) {
    const buffer = Buffer.from(str, 'utf8');
    return Array.from(buffer);
}

// 辅助函数：简单的字符串哈希函数（与jar_text_extractor.js保持一致）
function hash(str) {
    let hash = 0;
    if (str.length === 0) return hash;
    for (let i = 0; i < str.length; i++) {
        const char = str.charCodeAt(i);
        hash = ((hash << 5) - hash) + char;
        hash = hash & hash; // Convert to 32-bit integer
    }
    return Math.abs(hash);
}

// 主函数
async function main() {
    const args = process.argv.slice(2);
    if (args.length < 3) {
        console.error('用法: node simple_jar_translator.js <input.jar> <output.jar> <translations.json>');
        process.exit(1);
    }
    
    const [inputJar, outputJar, translationsFile] = args;
    
    try {
        await translateJarWithKeys(inputJar, outputJar, translationsFile);
        process.exit(0);
    } catch (error) {
        console.error('翻译失败:', error);
        process.exit(1);
    }
}

if (require.main === module) {
    main();
}

module.exports = { translateJarWithKeys, hash };
