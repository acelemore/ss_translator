<template>
  <div class="test-loading">
    <h3>按钮防重复点击功能测试</h3>
    
    <el-space direction="vertical" size="large">
      <!-- 基本测试 -->
      <el-card header="基本功能测试">
        <el-space>
          <el-button 
            type="primary" 
            @click="testBasicHandler" 
            :loading="testBasicLoading"
          >
            测试基本功能 (3秒)
          </el-button>
          
          <el-button 
            type="success" 
            @click="testQuickHandler" 
            :loading="testQuickLoading"
          >
            快速测试 (1秒)
          </el-button>
        </el-space>
      </el-card>
      
      <!-- 多按钮独立测试 -->
      <el-card header="多按钮独立状态测试">
        <el-space>
          <el-button 
            type="warning" 
            @click="testButton1Handler" 
            :loading="testButton1Loading"
          >
            按钮1 (2秒)
          </el-button>
          
          <el-button 
            type="info" 
            @click="testButton2Handler" 
            :loading="testButton2Loading"
          >
            按钮2 (4秒)
          </el-button>
          
          <el-button 
            type="danger" 
            @click="testButton3Handler" 
            :loading="testButton3Loading"
          >
            按钮3 (1秒)
          </el-button>
        </el-space>
      </el-card>
      
      <!-- 错误处理测试 -->
      <el-card header="错误处理测试">
        <el-space>
          <el-button 
            type="danger" 
            @click="testErrorHandler" 
            :loading="testErrorLoading"
          >
            测试错误处理
          </el-button>
        </el-space>
      </el-card>
      
      <!-- 使用指令的测试 -->
      <el-card header="自定义指令测试">
        <el-space>
          <el-button 
            type="primary" 
            v-loading-click:directive1="testDirective1"
          >
            指令测试1 (2秒)
          </el-button>
          
          <el-button 
            type="success" 
            v-loading-click:directive2="testDirective2"
          >
            指令测试2 (3秒)
          </el-button>
        </el-space>
      </el-card>
    </el-space>
  </div>
</template>

<script setup>
import { ElMessage } from 'element-plus'
import { useButtonLoading } from '../composables/useButtonLoading.js'

const { createLoadingHandler } = useButtonLoading()

// 基本功能测试
const { handler: testBasicHandler, loading: testBasicLoading } = createLoadingHandler(async () => {
  await new Promise(resolve => setTimeout(resolve, 3000))
  ElMessage.success('基本功能测试完成！')
}, 'testBasic')

const { handler: testQuickHandler, loading: testQuickLoading } = createLoadingHandler(async () => {
  await new Promise(resolve => setTimeout(resolve, 1000))
  ElMessage.success('快速测试完成！')
}, 'testQuick')

// 多按钮独立测试
const { handler: testButton1Handler, loading: testButton1Loading } = createLoadingHandler(async () => {
  await new Promise(resolve => setTimeout(resolve, 2000))
  ElMessage.success('按钮1完成！')
}, 'button1')

const { handler: testButton2Handler, loading: testButton2Loading } = createLoadingHandler(async () => {
  await new Promise(resolve => setTimeout(resolve, 4000))
  ElMessage.success('按钮2完成！')
}, 'button2')

const { handler: testButton3Handler, loading: testButton3Loading } = createLoadingHandler(async () => {
  await new Promise(resolve => setTimeout(resolve, 1000))
  ElMessage.success('按钮3完成！')
}, 'button3')

// 错误处理测试
const { handler: testErrorHandler, loading: testErrorLoading } = createLoadingHandler(async () => {
  await new Promise(resolve => setTimeout(resolve, 2000))
  throw new Error('测试错误')
}, 'testError')

// 指令测试函数
const testDirective1 = async () => {
  await new Promise(resolve => setTimeout(resolve, 2000))
  ElMessage.success('指令测试1完成！')
}

const testDirective2 = async () => {
  await new Promise(resolve => setTimeout(resolve, 3000))
  ElMessage.success('指令测试2完成！')
}
</script>

<style scoped>
.test-loading {
  max-width: 800px;
  margin: 20px auto;
  padding: 20px;
}
</style>
