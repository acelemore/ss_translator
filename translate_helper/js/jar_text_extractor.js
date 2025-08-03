/**
 * 专业JAR文本提取器 - 改进版
 * 使用java-class-tools进行专业的常量池解析
 * 支持新的翻译键格式
 */

const fs = require('fs');
const path = require('path');
const JSZip = require('jszip');
const { 
    JavaClassFileReader, 
    Modifier, 
    InstructionParser, 
    Opcode, 
    ConstantType 
} = require('java-class-tools');

// 专业的JAR文本提取脚本，使用java-class-tools进行常量池分析
async function extractTextFromJar(inputJarPath, outputJsonPath) {
    console.log('=== 专业JAR文本提取器 (改进版) ===');
    console.log(`源文件: ${inputJarPath}`);
    console.log(`输出文件: ${outputJsonPath}`);
    
    // 读取JAR文件
    const jarData = fs.readFileSync(inputJarPath);
    const jar = await JSZip.loadAsync(jarData);
    
    const classReader = new JavaClassFileReader();
    const extractedTexts = {
        properties_files: {},
        json_files: {},
        class_strings: {},
        other_text_files: {}
    };
    
    let totalStrings = 0;
    let processedFiles = 0;
    
    // 获取所有文件
    const allFiles = Object.entries(jar.files).filter(([fileName, file]) => !file.dir);
    console.log(`找到 ${allFiles.length} 个文件`);
    
    // 处理每个文件
    for (const [fileName, file] of allFiles) {
        processedFiles++;
        
        try {
            if (fileName.endsWith('.class')) {
                // 处理class文件
                const strings = await extractStringsFromClass(file, classReader, fileName);
                if (strings.length > 0) {
                    extractedTexts.class_strings[fileName] = strings;
                    totalStrings += strings.length;
                }
                
            } else if (fileName.endsWith('.properties')) {
                // 处理properties文件
                const content = await file.async('text');
                const properties = parseProperties(content);
                if (Object.keys(properties).length > 0) {
                    extractedTexts.properties_files[fileName] = properties;
                }
                
            } else if (fileName.endsWith('.json')) {
                // 处理JSON文件
                try {
                    const content = await file.async('text');
                    const jsonData = JSON.parse(content);
                    extractedTexts.json_files[fileName] = jsonData;
                } catch (e) {
                    console.warn(`无法解析JSON文件: ${fileName}`);
                }
                
            } else if (fileName.match(/\.(txt|xml|cfg|ini)$/)) {
                // 处理其他文本文件
                try {
                    const content = await file.async('text');
                    extractedTexts.other_text_files[fileName] = content;
                } catch (e) {
                    console.warn(`无法读取文本文件: ${fileName}`);
                }
            }
            
        } catch (error) {
            console.warn(`处理文件 ${fileName} 时出错: ${error.message}`);
        }
        
        // 每处理100个文件报告一次进度
        if (processedFiles % 100 === 0) {
            console.log(`进度: ${processedFiles}/${allFiles.length} 文件已处理`);
        }
    }
    
    console.log(`\n提取完成！`);
    console.log(`处理文件: ${processedFiles}`);
    console.log(`类文件数: ${Object.keys(extractedTexts.class_strings).length}`);
    console.log(`总字符串数: ${totalStrings}`);
    
    // 保存结果
    fs.writeFileSync(outputJsonPath, JSON.stringify(extractedTexts, null, 2));
    console.log(`结果已保存到: ${outputJsonPath}`);
    
    return extractedTexts;
}

// 从class文件中提取字符串常量（带上下文信息和翻译键）
async function extractStringsFromClass(file, classReader, fileName) {
    const stringsWithContext = []; // 改为数组，包含上下文信息和翻译键
    
    try {
        const classData = await file.async('arraybuffer');
        const classFile = classReader.read(classData);
        const constantPool = classFile.constant_pool;
        
        // 方法1: 遍历所有方法中的字符串常量引用
        for (const method of classFile.methods) {
            // 跳过抽象方法
            if ((method.access_flags & Modifier.ABSTRACT) !== 0) {
                continue;
            }
            
            // 获取Code属性
            const codeAttribute = getAttribute(classFile, method, 'Code');
            if (!codeAttribute) {
                continue;
            }
            
            // 跳过枚举类的静态初始化方法（通常包含大量技术性字符串）
            if (isEnumClassInit(classFile, method)) {
                continue;
            }
            
            // 获取方法名 - 直接从UTF8常量池获取
            const methodName = getUtf8StringDirect(constantPool, method.name_index);
            
            if (!methodName) {
                continue;
            }
            
            // 解析指令
            const instructions = InstructionParser.fromBytecode(codeAttribute.code);
            
            // 查找字符串常量并分析调用上下文
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
                        // 分析调用上下文 - 查找字符串后面的方法调用
                        const callContext = analyzeStringUsageContext(instructions, constantPool, i);
                        
                        // 构建上下文信息 - 优先使用具体的调用方法
                        let context = `${methodName}()`;
                        let actualCaller = methodName;
                        
                        if (callContext.calledMethod) {
                            context = `${methodName}() -> ${callContext.calledMethod}()`;
                            actualCaller = callContext.calledMethod;
                        }
                        
                        // 生成翻译键：类名:函数名:文本索引:原文哈希
                        const textHash = hashString(stringValue);
                        const translationKey = `${fileName}:${actualCaller}:${i}:${textHash}`;
                        
                        stringsWithContext.push({
                            text: stringValue,
                            context: context,
                            filename: fileName,
                            method: methodName,
                            actual_caller: actualCaller,
                            called_method: callContext.calledMethod || null,
                            call_type: callContext.type || 'unknown',
                            translation_key: translationKey,
                            instruction_index: i
                        });
                    }
                }
            }
        }
        
        // 移除方法2：直接扫描常量池的做法是危险的
        // 常量池中的STRING常量可能包含不应该翻译的内容（如反射用的类名等）
        // 只保留通过LDC/LDC_W指令实际加载的字符串，这些才是真正的字符串字面量
        
    } catch (error) {
        console.warn(`解析class文件 ${fileName} 时出错: ${error.message}`);
    }
    
    return stringsWithContext;
}

// 分析字符串使用上下文 - 查找紧跟在字符串加载后的方法调用
function analyzeStringUsageContext(instructions, constantPool, stringInstructionIndex) {
    const context = {
        type: 'unknown',
        calledMethod: null,
        className: null
    };
    
    // 向前查找最多10条指令，寻找方法调用
    const maxLookAhead = Math.min(10, instructions.length - stringInstructionIndex - 1);
    
    for (let i = 1; i <= maxLookAhead; i++) {
        const nextInstruction = instructions[stringInstructionIndex + i];
        if (!nextInstruction) break;
        
        const { opcode, operands } = nextInstruction;
        
        // 查找方法调用指令
        if (opcode === Opcode.INVOKEVIRTUAL || 
            opcode === Opcode.INVOKESTATIC || 
            opcode === Opcode.INVOKESPECIAL ||
            opcode === Opcode.INVOKEINTERFACE) {
            
            // 获取方法引用索引
            const methodRefIndex = (operands[0] << 8) | operands[1];
            const methodRef = constantPool[methodRefIndex];
            
            if (methodRef && (methodRef.tag === ConstantType.METHODREF || 
                            methodRef.tag === ConstantType.INTERFACE_METHODREF)) {
                
                // 获取类名和方法名
                const classInfo = constantPool[methodRef.class_index];
                const nameAndType = constantPool[methodRef.name_and_type_index];
                
                if (classInfo && nameAndType) {
                    const className = getUtf8StringDirect(constantPool, classInfo.name_index);
                    const methodName = getUtf8StringDirect(constantPool, nameAndType.name_index);
                    
                    if (className && methodName) {
                        // 简化类名（去掉包名）
                        const simpleClassName = className.split('/').pop();
                        context.className = simpleClassName;
                        context.calledMethod = `${simpleClassName}.${methodName}`;
                        
                        // 确定调用类型
                        if (opcode === Opcode.INVOKESTATIC) {
                            context.type = 'static_call';
                        } else if (opcode === Opcode.INVOKEVIRTUAL) {
                            context.type = 'virtual_call';
                        } else if (opcode === Opcode.INVOKESPECIAL) {
                            context.type = 'special_call';
                        } else if (opcode === Opcode.INVOKEINTERFACE) {
                            context.type = 'interface_call';
                        }
                        
                        // 找到第一个方法调用就返回
                        break;
                    }
                }
            }
        }
        
        // 如果遇到其他会改变栈状态的指令，停止搜索
        if (opcode === Opcode.POP || opcode === Opcode.POP2 || 
            opcode === Opcode.RETURN || opcode === Opcode.ARETURN ||
            opcode === Opcode.IRETURN || opcode === Opcode.LRETURN ||
            opcode === Opcode.FRETURN || opcode === Opcode.DRETURN) {
            break;
        }
    }
    
    return context;
}

// 简单的字符串哈希函数
function hashString(str) {
    let hash = 0;
    if (str.length === 0) return hash;
    for (let i = 0; i < str.length; i++) {
        const char = str.charCodeAt(i);
        hash = ((hash << 5) - hash) + char;
        hash = hash & hash; // 转换为32位整数
    }
    return Math.abs(hash);
}

// 解析properties文件内容
function parseProperties(content) {
    const properties = {};
    const lines = content.split('\n');
    
    for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed && !trimmed.startsWith('#') && trimmed.includes('=')) {
            const [key, ...valueParts] = trimmed.split('=');
            const value = valueParts.join('=');
            properties[key.trim()] = value.trim();
        }
    }
    
    return properties;
}

// 辅助函数：获取方法的属性
function getAttribute(classFile, method, name) {
    for (const attribute of method.attributes) {
        const nameIndex = attribute.attribute_name_index;
        const utf8Entry = classFile.constant_pool[nameIndex];
        const attributeName = Buffer.from(utf8Entry.bytes).toString('utf8');
        
        if (attributeName === name) {
            return attribute;
        }
    }
    return null;
}

// 辅助函数：检查是否是枚举类的静态初始化方法
function isEnumClassInit(classFile, method) {
    if ((classFile.access_flags & Modifier.ENUM) === 0) {
        return false;
    }
    
    const nameEntry = classFile.constant_pool[method.name_index];
    const descriptorEntry = classFile.constant_pool[method.descriptor_index];
    
    const name = Buffer.from(nameEntry.bytes).toString('utf8');
    const descriptor = Buffer.from(descriptorEntry.bytes).toString('utf8');
    
    return name === '<clinit>' && descriptor === '()V';
}

// 辅助函数：从常量池获取UTF8字符串
function getUtf8String(constantPool, stringConstantIndex) {
    try {
        const stringEntry = constantPool[stringConstantIndex];
        if (!stringEntry || stringEntry.tag !== ConstantType.STRING) {
            return null;
        }
        
        const utf8Entry = constantPool[stringEntry.string_index];
        if (!utf8Entry || utf8Entry.tag !== ConstantType.UTF8) {
            return null;
        }
        
        return Buffer.from(utf8Entry.bytes).toString('utf8');
    } catch (e) {
        return null;
    }
}

// 辅助函数：直接从UTF8常量池获取字符串
function getUtf8StringDirect(constantPool, utf8Index) {
    try {
        const utf8Entry = constantPool[utf8Index];
        if (!utf8Entry || utf8Entry.tag !== ConstantType.UTF8) {
            return null;
        }
        
        return Buffer.from(utf8Entry.bytes).toString('utf8');
    } catch (e) {
        return null;
    }
}

// 主函数
async function main() {
    const args = process.argv.slice(2);
    if (args.length < 2) {
        console.error('用法: node jar_text_extractor.js <input.jar> <output.json>');
        console.error('示例: node jar_text_extractor.js IndEvo.jar extracted_texts.json');
        process.exit(1);
    }
    
    const [inputJar, outputJson] = args;
    
    // 检查输入文件是否存在
    if (!fs.existsSync(inputJar)) {
        console.error(`错误: 输入文件不存在: ${inputJar}`);
        process.exit(1);
    }
    
    try {
        await extractTextFromJar(inputJar, outputJson);
        console.log('\n✅ 文本提取成功完成！');
        process.exit(0);
    } catch (error) {
        console.error('文本提取失败:', error);
        process.exit(1);
    }
}

// 如果直接运行此脚本
if (require.main === module) {
    main();
}

// 导出函数供其他模块使用
module.exports = {
    extractTextFromJar
};
