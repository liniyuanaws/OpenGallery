# HTTP轮询功能测试指南

## 功能概述

当WebSocket连接失败时，系统会自动启用HTTP轮询作为备选方案，确保用户仍能接收AI生成的消息更新。

## 测试步骤

### 1. 模拟WebSocket连接失败

**方法1：关闭后端服务器**
```bash
# 停止后端服务器
pkill -f "python.*main.py"
```

**方法2：修改WebSocket连接URL**
临时修改 `react/src/lib/socket.ts` 中的连接URL：
```typescript
// 临时修改为错误的端口来模拟连接失败
return 'http://localhost:99999'  // 错误端口
```

### 2. 启动前端并观察行为

1. 启动前端：`cd react && npm run dev`
2. 打开浏览器访问：`http://localhost:5174`
3. 观察右上角的连接状态提示

**预期行为：**
- 初始显示：连接错误提示
- 5次重连失败后：显示 "🔄 Using HTTP polling mode"

### 3. 测试聊天功能

1. 重新启动后端服务器：`cd server && python main.py`
2. 在前端发送一条消息
3. 观察消息是否通过轮询更新

**预期行为：**
- HTTP请求成功发送
- 每2秒轮询一次获取消息更新
- 消息会延迟显示（相比WebSocket实时性差一些）

### 4. 测试WebSocket恢复

1. 确保后端正常运行
2. 刷新前端页面
3. 观察连接状态变化

**预期行为：**
- WebSocket连接成功
- 轮询自动停止
- 黄色提示消失

## 关键文件修改

### 前端修改
- `react/src/lib/socket.ts`: 添加轮询逻辑
- `react/src/contexts/socket.tsx`: 添加轮询状态显示
- `react/src/components/chat/Chat.tsx`: 集成轮询会话管理

### 后端修改
- `server/routers/agent.py`: 添加会话状态API

## 轮询配置参数

```typescript
private pollingDelay = 2000        // 轮询间隔2秒
private maxReconnectAttempts = 10   // 最多重连10次
private reconnectDelay = 3000       // 重连延迟3秒
```

## 注意事项

1. **性能影响**：轮询会增加服务器负载，仅在WebSocket失败时使用
2. **实时性**：轮询模式下消息更新有2秒延迟
3. **自动切换**：WebSocket恢复后会自动停止轮询
4. **会话管理**：只对活跃会话进行轮询

## 故障排除

### 轮询未启动
- 检查WebSocket是否真的失败了
- 确认有活跃的会话ID
- 查看浏览器控制台日志

### 消息未更新
- 检查后端API `/api/chat_session/{session_id}/status` 是否正常
- 确认数据库中有消息记录
- 查看网络请求是否成功

### 轮询未停止
- 检查WebSocket连接是否真的恢复
- 确认没有活跃会话残留
- 手动调用 `socketManager.stopPolling()`
