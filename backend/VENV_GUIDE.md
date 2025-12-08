# Python 虚拟环境使用指南

## 为什么使用虚拟环境？

虚拟环境可以：
- ✅ 隔离项目依赖，避免不同项目之间的包冲突
- ✅ 保持系统 Python 环境干净
- ✅ 方便项目部署和迁移
- ✅ 便于版本管理

## 创建虚拟环境

### Linux/Mac

```bash
cd backend
python3 -m venv venv
```

### Windows

```cmd
cd backend
python -m venv venv
```

## 激活虚拟环境

### Linux/Mac

```bash
source venv/bin/activate
```

激活后，命令行提示符前会显示 `(venv)`。

### Windows

```cmd
venv\Scripts\activate
```

激活后，命令行提示符前会显示 `(venv)`。

## 安装依赖

激活虚拟环境后：

```bash
# 升级 pip（推荐）
pip install --upgrade pip

# 安装项目依赖
pip install -r requirements.txt
```

## 退出虚拟环境

```bash
deactivate
```

## 常用命令

### 查看已安装的包

```bash
pip list
```

### 查看项目依赖

```bash
pip freeze > requirements.txt
```

### 安装新包

```bash
pip install package_name
```

### 卸载包

```bash
pip uninstall package_name
```

## 使用启动脚本（推荐）

项目提供了自动化的启动脚本，会自动处理虚拟环境的创建和激活：

### Linux/Mac

```bash
chmod +x start.sh
./start.sh
```

### Windows

```cmd
start.bat
```

启动脚本会：
1. 检查 Python 环境
2. 自动创建虚拟环境（如果不存在）
3. 激活虚拟环境
4. 安装/更新依赖
5. 检查配置文件
6. 启动服务

## 常见问题

### Q: 如何确认虚拟环境已激活？

A: 命令行提示符前会显示 `(venv)`，或者运行：
```bash
which python  # Linux/Mac
where python  # Windows
```
应该显示虚拟环境中的 Python 路径。

### Q: 虚拟环境创建失败？

A: 确保：
- Python 版本 >= 3.8
- 有足够的磁盘空间
- 有写入权限

### Q: 如何删除虚拟环境？

A: 直接删除 `venv` 文件夹：
```bash
rm -rf venv  # Linux/Mac
rmdir /s venv  # Windows
```

### Q: 虚拟环境中的包在哪里？

A: 
- Linux/Mac: `venv/lib/python3.x/site-packages/`
- Windows: `venv\Lib\site-packages\`

### Q: 如何在不同项目间切换？

A: 每次进入项目目录时，先激活对应的虚拟环境：
```bash
cd project1
source venv/bin/activate  # 激活 project1 的虚拟环境

# 退出
deactivate

cd project2
source venv/bin/activate  # 激活 project2 的虚拟环境
```

## 最佳实践

1. ✅ **每个项目使用独立的虚拟环境**
2. ✅ **将 `venv/` 添加到 `.gitignore`**（已配置）
3. ✅ **使用 `requirements.txt` 管理依赖**
4. ✅ **定期更新依赖包**
5. ✅ **在部署时使用虚拟环境**

## IDE 配置

### VS Code

VS Code 会自动检测虚拟环境。如果未检测到：
1. 按 `Cmd/Ctrl + Shift + P`
2. 输入 "Python: Select Interpreter"
3. 选择 `./venv/bin/python` (Linux/Mac) 或 `.\venv\Scripts\python.exe` (Windows)

### PyCharm

1. File → Settings → Project → Python Interpreter
2. 点击齿轮图标 → Add
3. 选择 Existing environment
4. 选择 `venv/bin/python` (Linux/Mac) 或 `venv\Scripts\python.exe` (Windows)

