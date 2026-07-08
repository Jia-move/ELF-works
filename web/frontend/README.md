# 前端服务说明

前端使用 Vue 3 + Vue Router + Element Plus，提供智能导览眼镜 Web 管理页面。

## 安装依赖

```powershell
cd C:\Users\33347\Desktop\web\frontend
npm install
```

## 启动开发服务

```powershell
cd C:\Users\33347\Desktop\web\frontend
npm run serve -- --host 0.0.0.0
```

默认访问地址：

```text
http://localhost:8081
http://电脑IP:8081
```

## 构建

```powershell
npm run build
```

构建结果输出到 `dist/`。

## 页面

- `/dashboard`：系统总览
- `/recognitions`：导览识别记录
- `/scenic-spots`：导览内容库管理
- `/qa-records`：智能问答记录
- `/devices`：设备管理

## 后端代理

开发环境通过 `vue.config.js` 代理：

```text
/api       -> http://127.0.0.1:8000
/ws/events -> ws://127.0.0.1:8000
```
