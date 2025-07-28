<template>
  <div class="config-view">
    <el-card class="header-card">
      <template #header>
        <div class="card-header">
          <span>⚙️ 配置管理</span>
          <p>选择或创建翻译配置文件</p>
        </div>
      </template>
      
      <!-- 配置选择区域 -->
      <div class="config-selector">
        <el-row :gutter="16" align="middle">
          <el-col :span="12">
            <el-select
              v-model="selectedConfig"
              placeholder="请选择配置..."
              style="width: 100%"
              @change="handleConfigChange"
              :loading="selectConfigLoading"
            >
              <el-option
                key="create-new"
                label="+ 创建新配置"
                value="__create_new__"
              />
              <el-option
                v-for="config in configs"
                :key="config.filename"
                :label="`${config.name} (${config.filename})`"
                :value="config.filename"
              />
            </el-select>
          </el-col>
          <el-col :span="12" v-if="currentConfig">
            <el-space>
              <el-button 
                type="warning" 
                @click="autoConfigHandler"
                :loading="autoConfigLoading"
              >
                自动配置
              </el-button>
              <el-button 
                type="info" 
                @click="exportConfigHandler" 
                :loading="exportConfigLoading"
              >
                导出配置
              </el-button>
              <el-button type="info" @click="showImportDialog = true">
                导入配置
              </el-button>
              <el-button 
                type="danger" 
                @click="deleteConfigHandler" 
                :loading="deleteConfigLoading"
              >
                删除配置
              </el-button>
            </el-space>
          </el-col>
        </el-row>
      </div>
    </el-card>

    <!-- 当前配置信息 -->
    <el-card v-if="currentConfig" class="config-info-card">
      <template #header>
        <span>📋 当前配置信息</span>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="配置名称">{{ currentConfig.name }}</el-descriptions-item>
        <el-descriptions-item label="模组名称">{{ currentConfig.mod_name }}</el-descriptions-item>
        <el-descriptions-item label="模组路径">{{ currentConfig.mod_path }}</el-descriptions-item>
        <el-descriptions-item label="工作目录">{{ currentConfig.work_directory }}</el-descriptions-item>
        <el-descriptions-item label="描述" :span="2">{{ currentConfig.description || '无描述' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- 无配置提示 -->
    <el-card v-if="!currentConfig && configs.length === 0" class="empty-config-card">
      <div class="empty-state">
        <el-icon><Document /></el-icon>
        <h3>暂无配置文件</h3>
        <p>请先创建一个翻译配置文件开始使用</p>
        <el-button type="primary" @click="showCreateDialog = true" size="large">
          创建新配置
        </el-button>
      </div>
    </el-card>

    <el-card v-else-if="!currentConfig && configs.length > 0" class="empty-config-card">
      <div class="empty-state">
        <el-icon><Document /></el-icon>
        <h3>请选择一个配置文件</h3>
        <p>从上方下拉菜单中选择一个已有的配置文件</p>
      </div>
    </el-card>

    <!-- 配置文件编辑 -->
    <el-card v-if="currentConfig" class="config-edit-card">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span>📝 编辑配置文件</span>
          <el-button 
            type="primary" 
            @click="saveConfigContentHandler"
            :loading="saveConfigContentLoading"
          >
            保存配置
          </el-button>
        </div>
      </template>
      
      <el-tabs v-model="activeConfigTab">
        <!-- CSV文件配置 -->
        <el-tab-pane label="CSV文件" name="csv">
          <div class="file-config-section">
            <div class="section-header">
              <h4>CSV文件配置 <span class="config-count">({{ csvFilesList.length }} 个文件)</span></h4>
              <el-button type="primary" @click="showAddCsvDialog = true">
                添加CSV文件
              </el-button>
            </div>
            
            <el-table :data="csvFilesList" stripe v-if="csvFilesList.length > 0">
              <el-table-column prop="path" label="文件路径" min-width="200" show-overflow-tooltip />
              <el-table-column label="字段数量" width="100">
                <template #default="scope">
                  <el-tag type="info" size="small">
                    {{ Object.keys(scope.row.fields).length }} 个字段
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="配置字段" min-width="300">
                <template #default="scope">
                  <el-tag 
                    v-for="(func, field) in scope.row.fields" 
                    :key="field"
                    type="info"
                    size="small"
                  >
                    {{ field }}: {{ extractFunctionsMap[func] || func }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="150" fixed="right">
                <template #default="scope">
                  <el-button size="small" @click="editCsvFile(scope.row)">编辑</el-button>
                  <el-button size="small" type="danger" @click="removeCsvFile(scope.row.path)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
            
            <div v-else class="empty-state">
              <el-icon><Document /></el-icon>
              <p>暂未配置CSV文件</p>
              <p>点击"添加CSV文件"按钮开始配置</p>
            </div>
          </div>
        </el-tab-pane>
        
        <!-- JSON文件配置 -->
        <el-tab-pane label="JSON文件" name="json">
          <div class="file-config-section">
            <div class="section-header">
              <h4>JSON文件配置 <span class="config-count">({{ jsonFilesList.length }} 个文件)</span></h4>
              <el-button type="primary" @click="showAddJsonDialog = true">
                添加JSON文件
              </el-button>
            </div>
            
            <el-table :data="jsonFilesList" stripe v-if="jsonFilesList.length > 0">
              <el-table-column prop="path" label="文件路径" min-width="200" show-overflow-tooltip />
              <el-table-column label="处理函数" width="200">
                <template #default="scope">
                  <el-tag type="success">{{ extractFunctionsMap[scope.row.extract_function] || scope.row.extract_function }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="description" label="描述" show-overflow-tooltip />
              <el-table-column label="操作" width="150" fixed="right">
                <template #default="scope">
                  <el-button size="small" @click="editJsonFile(scope.row)">编辑</el-button>
                  <el-button size="small" type="danger" @click="removeJsonFile(scope.row.path)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
            
            <div v-else class="empty-state">
              <el-icon><Document /></el-icon>
              <p>暂未配置JSON文件</p>
              <p>点击"添加JSON文件"按钮开始配置</p>
            </div>
          </div>
        </el-tab-pane>
        
        <!-- JAR文件配置 -->
        <el-tab-pane label="JAR文件" name="jar">
          <div class="file-config-section">
            <div class="section-header">
              <h4>JAR文件配置 <span class="config-count">({{ jarFilesList.length }} 个文件)</span></h4>
              <el-button type="primary" @click="showAddJarDialog = true">
                添加JAR文件
              </el-button>
            </div>
            
            <el-table :data="jarFilesList" stripe v-if="jarFilesList.length > 0">
              <el-table-column prop="path" label="文件路径" min-width="200" show-overflow-tooltip />
              <el-table-column label="处理函数" width="200">
                <template #default="scope">
                  <el-tag type="success">{{ extractFunctionsMap[scope.row.extract_function] || scope.row.extract_function }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="description" label="描述" show-overflow-tooltip />
              <el-table-column label="配置" width="200">
                <template #default="scope">
                  <div style="font-size: 12px; color: var(--el-text-color-secondary);">
                    备份: {{ scope.row.backup_suffix || '.backup' }}<br>
                    输出: {{ scope.row.output_suffix || '_translated.jar' }}
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="150" fixed="right">
                <template #default="scope">
                  <el-button size="small" @click="editJarFile(scope.row)">编辑</el-button>
                  <el-button size="small" type="danger" @click="removeJarFile(scope.row.path)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
            
            <div v-else class="empty-state">
              <el-icon><Document /></el-icon>
              <p>暂未配置JAR文件</p>
              <p>点击"添加JAR文件"按钮开始配置</p>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- API配置状态 -->
    <el-card class="api-status-card">
      <template #header>
        <span>🔑 API配置状态</span>
      </template>
      <el-alert
        v-if="apiStatus"
        :title="apiStatus.message"
        :type="apiStatus.is_valid ? 'success' : 'error'"
        :closable="false"
        style="margin-bottom: 16px"
      />
      <el-button type="primary" @click="showApiConfigDialog = true">
        配置API设置
      </el-button>
    </el-card>

    <!-- 测试组件 -->
    <!-- <LoadingTest /> -->

    <!-- 新建配置对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      title="新建配置"
      width="500px"
    >
      <el-form :model="newConfigForm" label-width="100px">
        <el-form-item label="配置名称" required>
          <el-input v-model="newConfigForm.configName" placeholder="不含扩展名" />
        </el-form-item>
        <el-form-item label="模组名称" required>
          <el-input v-model="newConfigForm.modName" />
        </el-form-item>
        <el-form-item label="模组路径" required>
          <el-input v-model="newConfigForm.modPath" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="newConfigForm.description" type="textarea" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button 
          type="primary" 
          @click="createConfigHandler"
          :loading="createConfigLoading"
        >
          创建
        </el-button>
      </template>
    </el-dialog>

    <!-- API配置对话框 -->
    <el-dialog
      v-model="showApiConfigDialog"
      title="API配置"
      width="600px"
    >
      <el-form :model="apiConfigForm" label-width="120px">
        <el-form-item label="API密钥" required>
          <el-input 
            v-model="apiConfigForm.api_key" 
            type="password" 
            show-password
            placeholder="请输入OpenAI API密钥"
          />
        </el-form-item>
        <el-form-item label="Base URL">
          <el-input 
            v-model="apiConfigForm.base_url" 
            placeholder="https://api.openai.com/v1"
          />
        </el-form-item>
        <el-form-item label="模型">
          <el-input 
            v-model="apiConfigForm.model" 
            placeholder="gpt-3.5-turbo"
          />
        </el-form-item>
        <el-form-item label="最大令牌数">
          <el-input-number 
            v-model="apiConfigForm.max_tokens" 
            :min="100"
            :max="10000"
            :step="100"
            placeholder="2000"
            style="width: 100%"
          />
          <div class="form-tip">
            控制LLM响应的最大长度，一般设置为1000-4000之间
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showApiConfigDialog = false">取消</el-button>
        <el-button 
          type="primary" 
          @click="saveApiConfigHandler"
          :loading="saveApiConfigLoading"
        >
          保存
        </el-button>
      </template>
    </el-dialog>

    <!-- 导入配置对话框 -->
    <el-dialog
      v-model="showImportDialog"
      title="导入配置"
      width="500px"
    >
      <el-upload
        ref="uploadRef"
        :auto-upload="false"
        :limit="1"
        accept=".json"
        @change="handleFileChange"
      >
        <el-button type="primary">选择JSON配置文件</el-button>
        <template #tip>
          <div class="el-upload__tip">
            只能上传JSON格式的配置文件
          </div>
        </template>
      </el-upload>
      <template #footer>
        <el-button @click="showImportDialog = false">取消</el-button>
        <el-button 
          type="primary" 
          @click="importConfigHandler"
          :loading="importConfigLoading"
        >
          导入
        </el-button>
      </template>
    </el-dialog>

    <!-- 添加CSV文件对话框 -->
    <el-dialog
      v-model="showAddCsvDialog"
      :title="editingCsvFile ? '编辑CSV文件' : '添加CSV文件'"
      width="800px"
      :before-close="handleCsvDialogClose"
    >
      <el-form 
        ref="csvFormRef"
        :model="csvFileForm" 
        :rules="csvFormRules"
        label-width="100px"
      >
        <el-form-item label="文件路径" prop="path">
          <el-input 
            v-model="csvFileForm.path" 
            placeholder="例如: ./data/campaign/abilities.csv"
            :disabled="editingCsvFile"
          />
          <div class="form-tip">文件路径相对于模组根目录</div>
        </el-form-item>
        <el-form-item label="字段配置" prop="fields">
          <div class="field-config-list">
            <div 
              v-for="(field, index) in csvFileForm.fields" 
              :key="index"
              class="field-config-item"
            >
              <el-input 
                v-model="field.name" 
                placeholder="字段名" 
                style="width: 200px; margin-right: 12px;"
                @blur="validateFieldName(field, index)"
              />
              <el-select 
                v-model="field.function" 
                placeholder="选择处理函数"
                style="width: 300px; margin-right: 12px;"
                filterable
              >
                <el-option
                  v-for="(desc, func) in getFilteredExtractFunctions('csv')"
                  :key="func"
                  :label="`${func} - ${desc}`"
                  :value="func"
                />
              </el-select>
              <el-button 
                type="danger" 
                size="small" 
                @click="removeCsvField(index)"
                :disabled="csvFileForm.fields.length <= 1"
              >
                删除
              </el-button>
            </div>
            <el-button type="primary" @click="addCsvField" icon="Plus">
              添加字段
            </el-button>
            <div class="form-tip">至少需要配置一个字段</div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="handleCsvDialogClose">取消</el-button>
        <el-button 
          type="primary" 
          @click="saveCsvFile"
          :loading="savingCsvFile"
        >
          确定
        </el-button>
      </template>
    </el-dialog>

    <!-- 添加JSON文件对话框 -->
    <el-dialog
      v-model="showAddJsonDialog"
      :title="editingJsonFile ? '编辑JSON文件' : '添加JSON文件'"
      width="600px"
      :before-close="handleJsonDialogClose"
    >
      <el-form 
        ref="jsonFormRef"
        :model="jsonFileForm" 
        :rules="jsonFormRules"
        label-width="100px"
      >
        <el-form-item label="文件路径" prop="path">
          <el-input 
            v-model="jsonFileForm.path" 
            placeholder="例如: ./data/strings/strings.json"
            :disabled="editingJsonFile"
          />
          <div class="form-tip">JSON文件路径相对于模组根目录</div>
        </el-form-item>
        <el-form-item label="处理函数" prop="extract_function">
          <el-select 
            v-model="jsonFileForm.extract_function" 
            style="width: 100%;"
            filterable
          >
            <el-option
              v-for="(desc, func) in getFilteredExtractFunctions('json')"
              :key="func"
              :label="`${func} - ${desc}`"
              :value="func"
            />
          </el-select>
          <div class="form-tip">选择适合的JSON解析函数</div>
        </el-form-item>
        <el-form-item label="描述">
          <el-input 
            v-model="jsonFileForm.description" 
            type="textarea"
            placeholder="文件描述（可选）"
            :rows="3"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="handleJsonDialogClose">取消</el-button>
        <el-button 
          type="primary" 
          @click="saveJsonFile"
          :loading="savingJsonFile"
        >
          确定
        </el-button>
      </template>
    </el-dialog>

    <!-- 添加JAR文件对话框 -->
    <el-dialog
      v-model="showAddJarDialog"
      :title="editingJarFile ? '编辑JAR文件' : '添加JAR文件'"
      width="600px"
      :before-close="handleJarDialogClose"
    >
      <el-form 
        ref="jarFormRef"
        :model="jarFileForm" 
        :rules="jarFormRules"
        label-width="100px"
      >
        <el-form-item label="文件路径" prop="path">
          <el-input 
            v-model="jarFileForm.path" 
            placeholder="例如: ./jars/IndEvo.jar"
            :disabled="editingJarFile"
          />
          <div class="form-tip">JAR文件路径相对于模组根目录</div>
        </el-form-item>
        <el-form-item label="处理函数" prop="extract_function">
          <el-select 
            v-model="jarFileForm.extract_function" 
            style="width: 100%;"
            filterable
          >
            <el-option
              v-for="(desc, func) in getFilteredExtractFunctions('jar')"
              :key="func"
              :label="`${func} - ${desc}`"
              :value="func"
            />
          </el-select>
          <div class="form-tip">选择适合的JAR文件处理函数</div>
        </el-form-item>
        <el-form-item label="描述">
          <el-input 
            v-model="jarFileForm.description" 
            type="textarea"
            placeholder="文件描述（可选）"
            :rows="3"
          />
        </el-form-item>
        <el-form-item label="备份后缀">
          <el-input 
            v-model="jarFileForm.backup_suffix" 
            placeholder=".backup"
          />
          <div class="form-tip">原文件备份时的后缀名</div>
        </el-form-item>
        <el-form-item label="输出后缀">
          <el-input 
            v-model="jarFileForm.output_suffix" 
            placeholder="_translated.jar"
          />
          <div class="form-tip">翻译后文件的后缀名</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="handleJarDialogClose">取消</el-button>
        <el-button 
          type="primary" 
          @click="saveJarFile"
          :loading="savingJarFile"
        >
          确定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Document, Plus } from '@element-plus/icons-vue'
import { useAppStore } from '../stores/app'
import { configAPI, translationAPI } from '../utils/api'
import { useButtonLoading } from '../composables/useButtonLoading.js'
// import LoadingTest from '../components/LoadingTest.vue'

const appStore = useAppStore()

// 使用防重复点击功能
const { createLoadingHandler } = useButtonLoading()

// 数据
const selectedConfig = ref('')
const showCreateDialog = ref(false)
const showApiConfigDialog = ref(false)
const showImportDialog = ref(false)
const uploadRef = ref()
const selectedFile = ref(null)

// 表单引用
const csvFormRef = ref()
const jsonFormRef = ref()
const jarFormRef = ref()

// 配置编辑相关
const activeConfigTab = ref('csv')
const extractFunctions = ref({})
const currentConfigContent = ref({
  csv_files: {},
  json_files: {},
  jar_files: {}
})

// 保存状态
const savingCsvFile = ref(false)
const savingJsonFile = ref(false)
const savingJarFile = ref(false)
const selectConfigLoading = ref(false)

// CSV文件相关
const showAddCsvDialog = ref(false)
const editingCsvFile = ref(false)
const csvFileForm = ref({
  path: '',
  fields: [{ name: '', function: '' }]
})

// 表单验证规则
const csvFormRules = {
  path: [
    { required: true, message: '请输入文件路径', trigger: 'blur' },
    { 
      pattern: /^\.\/.*\.csv$/i, 
      message: '文件路径必须以"./"开头且以".csv"结尾', 
      trigger: 'blur' 
    }
  ],
  fields: [
    { 
      validator: (rule, value, callback) => {
        if (!value || value.length === 0) {
          callback(new Error('至少需要配置一个字段'))
          return
        }
        
        const validFields = value.filter(field => field.name.trim() && field.function)
        if (validFields.length === 0) {
          callback(new Error('至少需要配置一个完整的字段'))
          return
        }
        
        // 检查字段名是否重复
        const fieldNames = validFields.map(field => field.name.trim())
        const uniqueNames = [...new Set(fieldNames)]
        if (fieldNames.length !== uniqueNames.length) {
          callback(new Error('字段名不能重复'))
          return
        }
        
        callback()
      }, 
      trigger: 'change' 
    }
  ]
}

const jsonFormRules = {
  path: [
    { required: true, message: '请输入文件路径', trigger: 'blur' },
    { 
      pattern: /^\.\/.*\.json$/i, 
      message: '文件路径必须以"./"开头且以".json"结尾', 
      trigger: 'blur' 
    }
  ],
  extract_function: [
    { required: true, message: '请选择处理函数', trigger: 'change' }
  ]
}

const jarFormRules = {
  path: [
    { required: true, message: '请输入文件路径', trigger: 'blur' },
    { 
      pattern: /^\.\/.*\.jar$/i, 
      message: '文件路径必须以"./"开头且以".jar"结尾', 
      trigger: 'blur' 
    }
  ],
  extract_function: [
    { required: true, message: '请选择处理函数', trigger: 'change' }
  ]
}

// JSON文件相关
const showAddJsonDialog = ref(false)
const editingJsonFile = ref(false)
const jsonFileForm = ref({
  path: '',
  extract_function: '',
  description: ''
})

// JAR文件相关
const showAddJarDialog = ref(false)
const editingJarFile = ref(false)
const jarFileForm = ref({
  path: '',
  extract_function: 'jar_extract', // 默认处理函数
  description: '',
  backup_suffix: '.backup',
  output_suffix: '_translated.jar'
})

const newConfigForm = ref({
  configName: '',
  modName: '',
  modPath: '',
  description: ''
})

const apiConfigForm = ref({
  api_key: '',
  base_url: 'https://api.openai.com/v1',
  model: 'gpt-3.5-turbo',
  max_tokens: 2000
})

const apiStatus = ref(null)

// 计算属性
const configs = computed(() => appStore.configs)
const currentConfig = computed(() => appStore.currentConfig)

// 提取函数映射（用于显示）
const extractFunctionsMap = computed(() => {
  const map = {}
  Object.entries(extractFunctions.value).forEach(([key, funcInfo]) => {
    if (typeof funcInfo === 'string') {
      // 兼容旧格式
      map[key] = funcInfo
    } else if (typeof funcInfo === 'object' && funcInfo.description) {
      // 新格式
      map[key] = funcInfo.description
    }
  })
  return map
})

// 根据文件类型过滤可用的提取函数
const getFilteredExtractFunctions = (fileType) => {
  const filtered = {}
  Object.entries(extractFunctions.value).forEach(([key, funcInfo]) => {
    if (typeof funcInfo === 'string') {
      // 兼容旧格式，所有函数都可用
      filtered[key] = funcInfo
    } else if (typeof funcInfo === 'object' && funcInfo.description) {
      // 新格式，根据文件类型过滤
      if (funcInfo.file_type === fileType || !funcInfo.file_type) {
        filtered[key] = funcInfo.description
      }
    }
  })
  return filtered
}

// 配置文件列表
const csvFilesList = computed(() => {
  return Object.entries(currentConfigContent.value.csv_files || {}).map(([path, fields]) => ({
    path,
    fields
  }))
})

const jsonFilesList = computed(() => {
  return Object.entries(currentConfigContent.value.json_files || {}).map(([path, config]) => ({
    path,
    ...config
  }))
})

const jarFilesList = computed(() => {
  return Object.entries(currentConfigContent.value.jar_files || {}).map(([path, config]) => ({
    path,
    ...config
  }))
})

// 方法
const loadConfigs = async () => {
  try {
    await appStore.loadConfigs()
  } catch (error) {
    ElMessage.error('加载配置失败')
  }
}

// 创建带loading状态的按钮处理函数
const { handler: createConfigHandler, loading: createConfigLoading } = createLoadingHandler(async () => {
  const form = newConfigForm.value
  if (!form.configName || !form.modName || !form.modPath) {
    ElMessage.warning('请填写必填项')
    return
  }
  
  try {
    const result = await configAPI.createConfig(
      form.configName,
      form.modName, 
      form.modPath,
      form.description
    )
    
    if (result.success) {
      ElMessage.success('配置创建成功')
      showCreateDialog.value = false
      const configName = form.configName
      newConfigForm.value = {
        configName: '',
        modName: '',
        modPath: '',
        description: ''
      }
      await loadConfigs()
      
      // 自动选择刚创建的配置
      selectedConfig.value = configName
      // 直接调用选择配置的逻辑
      await handleConfigChange(configName)
    } else {
      ElMessage.error(result.message)
    }
  } catch (error) {
    ElMessage.error('创建配置失败')
  }
}, 'createConfig')

const { handler: deleteConfigHandler, loading: deleteConfigLoading } = createLoadingHandler(async () => {
  if (!currentConfig.value) return
  
  try {
    await ElMessageBox.confirm(
      '确定要删除当前配置吗？此操作不可撤销。',
      '警告',
      { type: 'warning' }
    )
    
    const result = await configAPI.deleteConfig(currentConfig.value.name)
    if (result.success) {
      ElMessage.success('配置删除成功')
      appStore.clearCurrentConfig()
      selectedConfig.value = ''
      await loadConfigs()
    } else {
      ElMessage.error(result.message)
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除配置失败')
    }
  }
}, 'deleteConfig')

const { handler: exportConfigHandler, loading: exportConfigLoading } = createLoadingHandler(async () => {
  if (!currentConfig.value) return
  
  try {
    const blob = await configAPI.exportConfig(currentConfig.value.name)
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${currentConfig.value.name}_export.json`
    a.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('配置导出成功')
  } catch (error) {
    ElMessage.error('导出配置失败')
  }
}, 'exportConfig')

// 自动配置处理
const { handler: autoConfigHandler, loading: autoConfigLoading } = createLoadingHandler(async () => {
  if (!currentConfig.value) {
    ElMessage.warning('请先选择一个配置')
    return
  }
  
  try {
    await ElMessageBox.confirm(
      '该操作会完全覆盖现有配置，是否继续？',
      '自动配置确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    const configName = currentConfig.value.filename || currentConfig.value.name
    const result = await configAPI.autoDetectFiles(configName)
    if (result.success) {
      ElMessage.success(result.message)
      // 重新选择配置以加载最新内容
      await appStore.selectConfig(configName)
      await loadCurrentConfigContent()
      
      // 自动保存配置
      try {
        await saveConfigContentHandler()
        ElMessage.success('自动配置已保存')
      } catch (saveError) {
        ElMessage.warning('自动配置完成，但保存失败，请手动保存')
        console.error('自动保存失败:', saveError)
      }
    } else {
      ElMessage.error(result.message)
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('自动配置失败')
    }
  }
}, 'autoConfig')

const { handler: importConfigHandler, loading: importConfigLoading } = createLoadingHandler(async () => {
  if (!selectedFile.value) {
    ElMessage.warning('请选择文件')
    return
  }
  
  const formData = new FormData()
  formData.append('config_file', selectedFile.value)
  
  try {
    const result = await configAPI.importConfig(formData)
    if (result.success) {
      ElMessage.success(result.message)
      showImportDialog.value = false
      selectedFile.value = null
      uploadRef.value?.clearFiles()
      await loadConfigs()
    } else {
      ElMessage.error(result.message)
    }
  } catch (error) {
    ElMessage.error('导入配置失败')
  }
}, 'importConfig')

const { handler: saveApiConfigHandler, loading: saveApiConfigLoading } = createLoadingHandler(async () => {
  try {
    const result = await configAPI.saveGlobalConfig(apiConfigForm.value)
    if (result.success) {
      ElMessage.success('API配置保存成功')
      showApiConfigDialog.value = false
      await checkApiStatus()
    } else {
      ElMessage.error(result.message)
    }
  } catch (error) {
    ElMessage.error('保存API配置失败')
  }
}, 'saveApiConfig')

// 加载提取函数列表
const loadExtractFunctions = async () => {
  try {
    const data = await translationAPI.getExtractFunctions()
    extractFunctions.value = data
  } catch (error) {
    console.error('加载提取函数失败:', error)
  }
}

// 加载当前配置内容
const loadCurrentConfigContent = async () => {
  if (!currentConfig.value) return
  
  try {
    // 这里应该从后端获取完整的配置内容，暂时使用模拟数据
    currentConfigContent.value = {
      csv_files: currentConfig.value.csv_files || {},
      json_files: currentConfig.value.json_files || {},
      jar_files: currentConfig.value.jar_files || {}
    }
  } catch (error) {
    console.error('加载配置内容失败:', error)
  }
}

// 保存配置内容
const { handler: saveConfigContentHandler, loading: saveConfigContentLoading } = createLoadingHandler(async () => {
  if (!currentConfig.value) return
  
  try {
    // 验证配置完整性
    const totalFiles = Object.keys(currentConfigContent.value.csv_files).length + 
                      Object.keys(currentConfigContent.value.json_files).length + 
                      Object.keys(currentConfigContent.value.jar_files).length
    
    if (totalFiles === 0) {
      ElMessage.warning('请至少配置一个翻译文件')
      return
    }
    
    const configData = {
      ...currentConfig.value,
      csv_files: currentConfigContent.value.csv_files,
      json_files: currentConfigContent.value.json_files,
      jar_files: currentConfigContent.value.jar_files
    }
    
    const result = await configAPI.saveConfig(currentConfig.value.name, configData)
    if (result.success) {
      ElMessage.success('配置保存成功')
      // 重新选择配置以加载最新内容
      const configName = currentConfig.value.filename || currentConfig.value.name
      await appStore.selectConfig(configName)
      await loadCurrentConfigContent()
    } else {
      ElMessage.error(result.message || '保存配置失败')
    }
  } catch (error) {
    console.error('保存配置失败:', error)
    ElMessage.error('保存配置失败')
  }
}, 'saveConfigContent')

// CSV文件相关方法
const addCsvField = () => {
  csvFileForm.value.fields.push({ name: '', function: '' })
}

const removeCsvField = (index) => {
  if (csvFileForm.value.fields.length > 1) {
    csvFileForm.value.fields.splice(index, 1)
    // 重新验证字段配置
    nextTick(() => {
      csvFormRef.value?.validateField('fields')
    })
  }
}

const validateFieldName = (field, index) => {
  // 实时验证字段名
  if (field.name.trim()) {
    nextTick(() => {
      csvFormRef.value?.validateField('fields')
    })
  }
}

const editCsvFile = (file) => {
  editingCsvFile.value = true
  csvFileForm.value = {
    path: file.path,
    fields: Object.entries(file.fields).map(([name, func]) => ({ name, function: func }))
  }
  showAddCsvDialog.value = true
}

const removeCsvFile = async (path) => {
  try {
    await ElMessageBox.confirm('确定要删除这个CSV文件配置吗？', '删除确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    delete currentConfigContent.value.csv_files[path]
    ElMessage.success('CSV文件配置删除成功')
  } catch (error) {
    // 用户取消
  }
}

const saveCsvFile = async () => {
  if (!csvFormRef.value) return
  
  try {
    await csvFormRef.value.validate()
  } catch (error) {
    return
  }
  
  savingCsvFile.value = true
  
  try {
    // 检查路径是否已存在（编辑模式除外）
    if (!editingCsvFile.value && currentConfigContent.value.csv_files[csvFileForm.value.path]) {
      ElMessage.error('该文件路径已存在')
      return
    }
    
    const fields = {}
    for (const field of csvFileForm.value.fields) {
      if (field.name.trim() && field.function) {
        fields[field.name.trim()] = field.function
      }
    }
    
    currentConfigContent.value.csv_files[csvFileForm.value.path] = fields
    ElMessage.success(`CSV文件配置${editingCsvFile.value ? '更新' : '添加'}成功`)
    
    // 提示用户保存配置
    setTimeout(() => {
      if (Object.keys(currentConfigContent.value.csv_files).length > 0 ||
          Object.keys(currentConfigContent.value.json_files).length > 0 ||
          Object.keys(currentConfigContent.value.jar_files).length > 0) {
        ElMessage({
          message: '别忘了点击"保存配置"按钮保存到后端！',
          type: 'warning',
          duration: 3000
        })
      }
    }, 1000)
    
    cancelCsvEdit()
  } catch (error) {
    ElMessage.error(`${editingCsvFile.value ? '更新' : '添加'}CSV文件配置失败`)
  } finally {
    savingCsvFile.value = false
  }
}

const cancelCsvEdit = () => {
  showAddCsvDialog.value = false
  editingCsvFile.value = false
  csvFileForm.value = {
    path: '',
    fields: [{ name: '', function: '' }]
  }
  csvFormRef.value?.clearValidate()
}

const handleCsvDialogClose = () => {
  cancelCsvEdit()
}

// JSON文件相关方法
const editJsonFile = (file) => {
  editingJsonFile.value = true
  jsonFileForm.value = {
    path: file.path,
    extract_function: file.extract_function,
    description: file.description || ''
  }
  showAddJsonDialog.value = true
}

const removeJsonFile = async (path) => {
  try {
    await ElMessageBox.confirm('确定要删除这个JSON文件配置吗？', '删除确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    delete currentConfigContent.value.json_files[path]
    ElMessage.success('JSON文件配置删除成功')
  } catch (error) {
    // 用户取消
  }
}

const saveJsonFile = async () => {
  if (!jsonFormRef.value) return
  
  try {
    await jsonFormRef.value.validate()
  } catch (error) {
    return
  }
  
  savingJsonFile.value = true
  
  try {
    // 检查路径是否已存在（编辑模式除外）
    if (!editingJsonFile.value && currentConfigContent.value.json_files[jsonFileForm.value.path]) {
      ElMessage.error('该文件路径已存在')
      return
    }
    
    currentConfigContent.value.json_files[jsonFileForm.value.path] = {
      extract_function: jsonFileForm.value.extract_function,
      description: jsonFileForm.value.description
    }
    
    ElMessage.success(`JSON文件配置${editingJsonFile.value ? '更新' : '添加'}成功`)
    
    // 提示用户保存配置
    setTimeout(() => {
      ElMessage({
        message: '别忘了点击"保存配置"按钮保存到后端！',
        type: 'warning',
        duration: 3000
      })
    }, 1000)
    
    cancelJsonEdit()
  } catch (error) {
    ElMessage.error(`${editingJsonFile.value ? '更新' : '添加'}JSON文件配置失败`)
  } finally {
    savingJsonFile.value = false
  }
}

const cancelJsonEdit = () => {
  showAddJsonDialog.value = false
  editingJsonFile.value = false
  jsonFileForm.value = {
    path: '',
    extract_function: '',
    description: ''
  }
  jsonFormRef.value?.clearValidate()
}

const handleJsonDialogClose = () => {
  cancelJsonEdit()
}

// JAR文件相关方法
const editJarFile = (file) => {
  editingJarFile.value = true
  jarFileForm.value = {
    path: file.path,
    extract_function: file.extract_function || 'jar_extract',
    description: file.description || '',
    backup_suffix: file.backup_suffix || '.backup',
    output_suffix: file.output_suffix || '_translated.jar'
  }
  showAddJarDialog.value = true
}

const removeJarFile = async (path) => {
  try {
    await ElMessageBox.confirm('确定要删除这个JAR文件配置吗？', '删除确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    delete currentConfigContent.value.jar_files[path]
    ElMessage.success('JAR文件配置删除成功')
  } catch (error) {
    // 用户取消
  }
}

const saveJarFile = async () => {
  if (!jarFormRef.value) return
  
  try {
    await jarFormRef.value.validate()
  } catch (error) {
    return
  }
  
  savingJarFile.value = true
  
  try {
    // 检查路径是否已存在（编辑模式除外）
    if (!editingJarFile.value && currentConfigContent.value.jar_files[jarFileForm.value.path]) {
      ElMessage.error('该文件路径已存在')
      return
    }
    
    currentConfigContent.value.jar_files[jarFileForm.value.path] = {
      extract_function: jarFileForm.value.extract_function || 'jar_extract',
      description: jarFileForm.value.description,
      backup_suffix: jarFileForm.value.backup_suffix || '.backup',
      output_suffix: jarFileForm.value.output_suffix || '_translated.jar'
    }
    
    ElMessage.success(`JAR文件配置${editingJarFile.value ? '更新' : '添加'}成功`)
    
    // 提示用户保存配置
    setTimeout(() => {
      ElMessage({
        message: '别忘了点击"保存配置"按钮保存到后端！',
        type: 'warning',
        duration: 3000
      })
    }, 1000)
    
    cancelJarEdit()
  } catch (error) {
    ElMessage.error(`${editingJarFile.value ? '更新' : '添加'}JAR文件配置失败`)
  } finally {
    savingJarFile.value = false
  }
}

const cancelJarEdit = () => {
  showAddJarDialog.value = false
  editingJarFile.value = false
  jarFileForm.value = {
    path: '',
    extract_function: 'jar_extract', // 默认处理函数
    description: '',
    backup_suffix: '.backup',
    output_suffix: '_translated.jar'
  }
  jarFormRef.value?.clearValidate()
}

const handleJarDialogClose = () => {
  cancelJarEdit()
}

const handleFileChange = (file) => {
  selectedFile.value = file.raw
}

const loadApiConfig = async () => {
  try {
    const data = await configAPI.getGlobalConfig()
    if (data.success) {
      apiConfigForm.value = { ...data.config }
    }
  } catch (error) {
    console.error('加载API配置失败:', error)
  }
}

const checkApiStatus = async () => {
  try {
    const data = await configAPI.checkApiConfig()
    if (data.success) {
      apiStatus.value = data
    }
  } catch (error) {
    console.error('检查API状态失败:', error)
  }
}

const handleConfigChange = async (value) => {
  // 如果选择的是创建新配置选项
  if (value === '__create_new__') {
    // 重置选择，打开创建对话框
    selectedConfig.value = ''
    showCreateDialog.value = true
    return
  }
  
  // 如果选择了实际的配置，直接加载
  if (value && value !== '__create_new__') {
    selectConfigLoading.value = true
    try {
      const result = await appStore.selectConfig(value)
      if (result.success) {
        ElMessage.success(result.message)
        // 重新加载配置内容
        await loadCurrentConfigContent()
      } else {
        ElMessage.error(result.message)
        // 加载失败时重置选择
        selectedConfig.value = ''
      }
    } catch (error) {
      ElMessage.error('选择配置失败')
      // 发生错误时重置选择
      selectedConfig.value = ''
    } finally {
      selectConfigLoading.value = false
    }
  }
}

// 生命周期
onMounted(async () => {
  try {
    // 并行加载基础数据
    await Promise.all([
      loadConfigs(),
      loadExtractFunctions(),
      loadApiConfig(),
      checkApiStatus()
    ])
    
    // 获取当前配置
    await appStore.getCurrentConfig()
    
    if (currentConfig.value) {
      selectedConfig.value = currentConfig.value.filename || currentConfig.value.name
      await loadCurrentConfigContent()
    }
  } catch (error) {
    console.error('初始化失败:', error)
    ElMessage.error('页面初始化失败，请刷新重试')
  }
})
</script>

<style scoped>
.config-view {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
  min-height: 100%;
  box-sizing: border-box;
}

.header-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header span {
  font-size: 18px;
  font-weight: 600;
}

.card-header p {
  margin: 0;
  color: var(--el-text-color-regular);
  font-size: 14px;
}

.config-selector {
  padding: 16px 0;
}

.config-info-card,
.config-edit-card,
.api-status-card,
.empty-config-card {
  margin-bottom: 20px;
}

.file-config-section {
  padding: 16px 0;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-header h4 {
  margin: 0;
  color: var(--el-text-color-primary);
}

.config-count {
  font-size: 14px;
  font-weight: normal;
  color: var(--el-text-color-secondary);
}

.field-config-list {
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  padding: 16px;
  background-color: var(--el-bg-color-page);
}

.field-config-item {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
}

.field-config-item:last-child {
  margin-bottom: 16px;
}

.config-tabs {
  margin-top: 16px;
}

.empty-state {
  text-align: center;
  padding: 40px 20px;
  color: var(--el-text-color-secondary);
}

.empty-state h3 {
  margin: 16px 0 8px 0;
  color: var(--el-text-color-primary);
}

.empty-state p {
  margin: 0 0 16px 0;
  color: var(--el-text-color-secondary);
  font-size: 14px;
}

.form-tip {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
  line-height: 1.4;
}

.el-tag {
  margin: 2px 4px 2px 0;
}

/* 表格样式优化 */
.el-table {
  margin-top: 16px;
}

.el-table .cell {
  padding: 8px 12px;
}

/* 对话框样式 */
.el-dialog__body {
  padding: 20px;
}

.el-form-item__content .form-tip {
  margin-left: 0;
}

/* 按钮样式 */
.el-button + .el-button {
  margin-left: 8px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .config-view {
    padding: 0 16px;
  }
  
  .field-config-item {
    flex-direction: column;
    align-items: stretch;
  }
  
  .field-config-item > * {
    margin-right: 0 !important;
    margin-bottom: 8px;
  }
  
  .field-config-item > *:last-child {
    margin-bottom: 0;
  }
}

/* 创建新配置选项样式 */
:deep(.el-select-dropdown__item[aria-label="+ 创建新配置"]) {
  color: var(--el-color-success);
  font-weight: 500;
  border-bottom: 1px solid var(--el-border-color-light);
  margin-bottom: 4px;
}

:deep(.el-select-dropdown__item[aria-label="+ 创建新配置"]:hover) {
  background-color: var(--el-color-success-light-9);
}
</style>
