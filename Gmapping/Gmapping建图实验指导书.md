# Gmapping 仿真实验指导书

*ROS 2 · SLAM · LABORATORY GUIDE*

仿真实验 · 学生操作版 · Ubuntu 22.04 虚拟机 + ROS 2 Humble + Gazebo

- **实验学时**：2 学时（上机实操，约 90 分钟）
- **实验平台**：Ubuntu 22.04 虚拟机 · ROS 2 Humble · Gazebo · RViz2
- **仿真机器人**：TurtleBot3 Burger
- **算法源码**：kutschl/slam_gmapping （ humble-devel 分支）
- **文档版本**：仿真实验精简版

## 目录

- 一、实验目标
- 二、原理一句话（不看也能做）
- 三、课前准备（环境就绪验收）
- 四、实验步骤（五步走）
- 五、本章验收标准
- 六、常见问题速查
- 七、思考题
- 八、附录：命令速查与参考资料

## 📋 一、实验目标

完成本实验后，你应当能够独立做到以下三件事：

**本实验完全在仿真环境中进行**：使用 Gazebo 模拟的 TurtleBot3 小车和虚拟激光雷达，**不需要任何真实机器人或真实激光雷达硬件**。所有操作都在 Ubuntu 虚拟机里完成，靠键盘遥控虚拟小车绕场即可建图。

1. 在 Ubuntu 22.04 虚拟机中启动 ROS 2 Humble 的 TurtleBot3 Gazebo 仿真环境；
2. 运行 Gmapping 节点，遥控小车走一圈，实时构建出一张二维栅格地图；
3. 把建好的地图保存为 `.pgm` + `.yaml` 文件，并截图留证。

**本实验不要求理解算法数学**

只要照着第三、四章的命令一步步敲、看到对应的预期现象即可。原理看第二章就够了。

## 🔬 二、原理一句话（不看也能做）

**SLAM 是什么？** 机器人一边在未知环境里走、一边同时做两件事：搞清楚"我现在在哪"（定位），和画出"周围长什么样"（建图）。这两个问题互相纠缠，所以叫"同步定位与建图"。

**Gmapping 是什么？** 它是 ROS 里最经典的 2D 激光 SLAM 算法之一，输入是**激光雷达**扫描数据和**里程计**（轮子转了多少）数据，输出一张**占据栅格地图**：黑格=有障碍，白格=空地，灰格=还没探索。**在本仿真实验中，激光和里程计数据都由 Gazebo 仿真器直接提供，无需真实传感器。**

**它怎么"猜"位置的？** 用很多个"粒子"代表机器人可能在的不同位姿；每扫一帧激光，和地图匹配得上的粒子得分高、被保留，匹配不上的被淘汰。地图就随着这些幸存粒子的轨迹逐渐拼出来。所以——**小车走得越稳、越慢，地图越准**。

**适用场景提醒**

Gmapping 适合中小场景、单线激光雷达。场景很大或长时间运行会漂移，那种情况应改用 Cartographer 或 slam_toolbox。本实验仅在 TurtleBot3 World 小场景内验证即可。

## 🖥️ 三、课前准备（环境就绪验收）

### 📦 第1章 系统环境与ROS2检查

#### 1.1 打开终端并检查系统

在 Ubuntu 按 `Ctrl+Alt+T`，执行：

```bash
lsb_release -ds
uname -m
test -f /opt/ros/humble/setup.bash && echo '找到 ROS 2 Humble'
```

系统应为 Ubuntu 22.04 系列，架构应为 `x86_64`，并显示找到 Humble。若最后一行没有输出，先解决 Humble 安装位置或安装状态，再继续。

加载已有的 ROS 2：

```bash
source /opt/ros/humble/setup.bash
echo "$ROS_DISTRO"
ros2 pkg prefix rclcpp
```

应显示 `humble`，并找到 `rclcpp`。后面使用系统的 `/usr/bin/python3` 和已有的 Humble 环境。如果终端处于 Conda 环境，先用 `conda deactivate` 退出后再进行构建。

#### 1.2 安装基础构建工具

```bash
sudo apt update
sudo apt install -y \
  build-essential cmake git lld pkg-config \
  python3-colcon-common-extensions python3-rosdep \
  software-properties-common
```

输入 `sudo` 密码时终端不会显示字符，输入完成后按 Enter。

### 📦 第2章 安装 Gazebo 11 和 ROS 依赖

#### 2.1 安装 Gazebo 与 ROS 插件

```bash
sudo apt install -y \
  gazebo libgazebo-dev \
  ros-humble-gazebo-ros-pkgs \
  ros-humble-dynamixel-sdk \
  ros-humble-robot-state-publisher \
  ros-humble-xacro \
  ros-humble-rviz2 \
  ros-humble-tf2-ros \
  ros-humble-tf2-geometry-msgs \
  ros-humble-message-filters \
  ros-humble-nav2-map-server
```

`gazebo` 提供 Classic 程序；Ubuntu Jammy 的 `libgazebo-dev` 提供对应 11 系列开发文件；`gazebo_ros_pkgs` 提供 ROS 插件。Dynamixel SDK 用于编译 TurtleBot3 基础驱动，`nav2_map_server` 在本教程中只用于保存地图。[2][6]

这里不安装额外版本的 OpenCV 或 Eigen，也不向 ORB-SLAM2 添加补丁。

#### 3.2 确认找到正确的软件

```bash
source /opt/ros/humble/setup.bash
gazebo --version
ros2 pkg prefix gazebo_ros
ros2 pkg prefix nav2_map_server
```

Gazebo 应显示 `version 11...`。如果提示无法定位 `ros-humble-*` 软件包，先检查已有的 ROS APT 源和 `sudo apt update` 报错，不要换成其他 ROS 发行版的包名。

### 🗂️ 第3章 建立工作目录并下载源码

#### 3.1 创建独立工作空间

本教程的工作空间固定为 `~/gmapping_ws`。源码、构建结果、运行环境文件、模型和地图均使用这个目录。如果你已经在该目录中放过其他工程，先停下并核对内容，不要删除或覆盖原工程。首次操作时执行：

```bash
mkdir -p "$HOME/gmapping_ws/src"
cd "$HOME/gmapping_ws/src"
```

#### 3.2 下载 TurtleBot3 和 Gmapping

以下命令使用 `&&` 串接，前面的下载失败时，后面的下载不会继续。等每个仓库下载完成。

```bash
git clone --branch humble --single-branch \
  https://gitcode.com/gh_mirrors/tu/turtlebot3.git && \
git clone --branch humble --single-branch \
  https://gitcode.com/gh_mirrors/tu/turtlebot3_simulations.git && \
git clone --branch humble --single-branch \
  https://ghfast.top/https://github.com/ROBOTIS-GIT/turtlebot3_msgs.git && \
git clone --branch feature/namespace_launch --single-branch \
  https://ghfast.top/https://github.com/charlielito/slam_gmapping.git
```

#### 3.3 准备基础场景模型

TurtleBot3 World 需要地面、光源和仓库自带场景。为避免 Gazebo 第一次启动时等待远程模型数据库，本教程预先从 OSRF 模型仓库取出 `ground_plane` 和 `sun` 两个模型。[7]

```bash
git clone --depth 1 --filter=blob:none --sparse \
  https://gitcode.com/gh_mirrors/ga/gazebo_models.git \
  "$HOME/gmapping_ws/gazebo_models" && \
git -C "$HOME/gmapping_ws/gazebo_models" \
  sparse-checkout set ground_plane sun
```

此处使用 GitCode 的 Gazebo 模型镜像。模型仓库放在工作空间根目录，不放进 `src`，也不需要参与 ROS 编译。模型已经下载完整时跳过本节，不修改已有仓库的下载源。[13]

### 🔧 第4章 完成必要配置并安装源码依赖

#### 4.1 处理单机器人 TF 前缀

核对时的 `humble` 分支将空 `frame_prefix` 拼接为 `/`。本次单机器人需要不带前缀的 `base_link`、`base_scan` 等坐标系，以便与 Gazebo 插件中的帧名对应。下面只调整本次下载的仿真启动文件，移除这一条前缀覆盖，使用状态发布器默认的空前缀。[8]

完整复制以下代码块，包括最后单独一行的 `PY`：

```bash
python3 - <<'PY'
from pathlib import Path

path = Path.home() / "gmapping_ws/src/turtlebot3_simulations/turtlebot3_gazebo/launch/robot_state_publisher.launch.py"
text = path.read_text(encoding="utf-8")
old = "'frame_prefix': PythonExpression([\"'\", frame_prefix, \"/'\"])"
new = "# Single robot: use the default empty frame_prefix."

if old in text:
    backup = path.with_name(path.name + ".before_single_robot_fix")
    if not backup.exists():
        backup.write_text(text, encoding="utf-8")
    path.write_text(text.replace(old, new), encoding="utf-8")
    print("已修正单机器人 TF 前缀，原文件已备份。")
elif new in text:
    print("该项已修正，无需重复修改。")
elif "'frame_prefix':" not in text:
    print("当前文件没有该前缀设置，跳过此修正。")
else:
    raise SystemExit("文件写法与本教程核对版本不同，请停在这里核对 frame_prefix，不继续盲目修改。")
PY
```

这不是添加额外静态 TF，也不需要手工发布 `odom → base_link`。机器人本体的 TF 应由仿真插件和 `robot_state_publisher` 提供。

#### 4.2 使用工作空间内的 rosdep 国内镜像配置

`rosdep init` 默认会访问 GitHub，`rosdep update` 也需要下载依赖规则与 ROS 发行版索引。本节改用清华 TUNA 的 rosdistro 镜像，并将本实验的源清单与环境文件放进 `~/gmapping_ws/rosdep`。已有的 `/etc/ros/rosdep` 源文件、Ubuntu APT 源和 ROS 2 APT 源都不覆盖。[11][12]

完整复制下面代码块，包含两处单独一行的 `EOF`。本节不再运行 `sudo rosdep init`：

```bash
mkdir -p "$HOME/gmapping_ws/rosdep/sources.list.d"

cat > "$HOME/gmapping_ws/rosdep/sources.list.d/20-tuna.list" <<'EOF'
yaml https://mirrors.tuna.tsinghua.edu.cn/rosdistro/rosdep/base.yaml
yaml https://mirrors.tuna.tsinghua.edu.cn/rosdistro/rosdep/python.yaml
yaml https://mirrors.tuna.tsinghua.edu.cn/rosdistro/rosdep/ruby.yaml
EOF

cat > "$HOME/gmapping_ws/rosdep/use_rosdep.bash" <<'EOF'
export ROSDEP_SOURCE_PATH="$HOME/gmapping_ws/rosdep/sources.list.d"
export ROSDISTRO_INDEX_URL="https://mirrors.tuna.tsinghua.edu.cn/rosdistro/index-v4.yaml"
EOF

source "$HOME/gmapping_ws/rosdep/use_rosdep.bash"
rosdep update --rosdistro humble
```

这三个 YAML 文件提供本次 Ubuntu 环境使用的依赖规则；发行版索引及 Humble 的发行版数据也从清华镜像读取。这里只为本实验指定读取入口，不重写系统中已经配置好的源。

`rosdep update` 以普通用户运行，不添加 `sudo`。看到 `Hit https://mirrors.tuna.tsinghua.edu.cn/...`、`Add distro "humble"` 和 `updated cache in ...`，且没有下载错误后继续。若显示读取的是其他源目录，先确认已执行上面的 `source` 命令。以后换终端运行本实验的 rosdep 命令时，也要先加载这个环境文件。

#### 4.3 安装本次需要编译的包的依赖

```bash
source /opt/ros/humble/setup.bash
source "$HOME/gmapping_ws/rosdep/use_rosdep.bash"
cd "$HOME/gmapping_ws"

rosdep install --from-paths \
  src/turtlebot3_msgs \
  src/turtlebot3/turtlebot3_node \
  src/turtlebot3/turtlebot3_description \
  src/turtlebot3/turtlebot3_teleop \
  src/turtlebot3_simulations/turtlebot3_gazebo \
  src/slam_gmapping \
  --ignore-src --rosdistro humble -y
```

这里按实际构建范围安装依赖。rosdep 使用第5.2节加载的依赖规则，安装软件包时继续调用你现有 APT 源，不执行换源。`slam_gmapping` 仓库内已经包含 `openslam_gmapping`，不需要再克隆一份同名包。

本教程编译 TurtleBot3 基础驱动、描述、遥控及 Gazebo 仿真包，不启动实物驱动，也不构建机械臂、Cartographer 或完整 Nav2 导航示例。不要把本教程的指定目标擅自改为构建仓库中所有包，否则会引入额外依赖。

### 🔨 第5章 编译 TurtleBot3 和 Gmapping

#### 5.1 编译 TurtleBot3 相关包

关闭其他正在执行的大型编译任务，在当前终端执行：

```bash
source /opt/ros/humble/setup.bash
cd "$HOME/gmapping_ws"
export CMAKE_BUILD_PARALLEL_LEVEL=2
export MAKEFLAGS="-j2"

colcon build --symlink-install --executor sequential \
  --packages-up-to \
    turtlebot3_node turtlebot3_description \
    turtlebot3_teleop turtlebot3_gazebo \
  --cmake-args -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF
```

命令会同时处理依赖的本地 `turtlebot3_msgs`。Dynamixel SDK 使用第3章安装的二进制依赖。

等待出现 `Summary: ... packages finished`，且没有 `Failed` 或 `Aborted`。`warning` 不一定表示失败，真正出现错误时先停下。

#### 5.2 编译 Gmapping

继续在同一终端执行：

```bash
cd "$HOME/gmapping_ws"
export CMAKE_BUILD_PARALLEL_LEVEL=2
export MAKEFLAGS="-j2"

colcon build --symlink-install --executor sequential \
  --packages-up-to slam_gmapping \
  --cmake-args -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF
```

`--packages-up-to slam_gmapping` 会先构建仓库内的 `openslam_gmapping`，再构建 ROS 2 封装包。不要只在首次构建时写 `--packages-select slam_gmapping`，否则其本地前置库可能尚未安装。

此处不统一设置 `CMAKE_CXX_STANDARD`，由各自包选择所需标准；不要把 ORB-SLAM2 使用的 C++14 参数全局强加到 TurtleBot3 Gazebo 工程。

#### 5.3 加载并确认构建产物

```bash
source /opt/ros/humble/setup.bash
source "$HOME/gmapping_ws/install/local_setup.bash"

ros2 pkg prefix turtlebot3_gazebo
ros2 pkg prefix turtlebot3_teleop
ros2 pkg prefix slam_gmapping
ros2 pkg executables slam_gmapping
```

前三条应指向本次工作空间中的安装目录，最后应列出 `slam_gmapping slam_gmapping`。

### ⚙️ 第6章 配置统一的运行环境

#### 6.1 创建环境文件

为了避免每个终端漏掉环境变量，将运行配置放在工作空间自己的文件中。完整复制下面代码块，包含最后的 `EOF`：

```bash
cat > "$HOME/gmapping_ws/use_tb3.bash" <<'EOF'
source /opt/ros/humble/setup.bash
source /usr/share/gazebo/setup.sh
source "$HOME/gmapping_ws/install/local_setup.bash"

export TURTLEBOT3_MODEL=burger
export ROS_DOMAIN_ID=30
export ROS_LOCALHOST_ONLY=1

export GAZEBO_MODEL_PATH="$HOME/gmapping_ws/gazebo_models:$HOME/gmapping_ws/src/turtlebot3_simulations/turtlebot3_gazebo/models${GAZEBO_MODEL_PATH:+:$GAZEBO_MODEL_PATH}"
export GAZEBO_MODEL_DATABASE_URI=""
EOF
```

说明：

- `burger` 是本次使用的机器人型号。
- 所有终端使用同一个 `ROS_DOMAIN_ID`。
- `ROS_LOCALHOST_ONLY=1` 用于本次同虚拟机仿真；以后连接 Jetson 等其他机器时，需要重新配置这一项。
- 模型搜索路径包含预下载的地面／光源模型，以及 TurtleBot3 仓库自带的机器人和场景模型。
- 空模型数据库地址用于本教程已准备本地资源的场景，不等待旧的远程模型数据库。

这些设置只在你 `source` 该文件的终端中生效，不需要追加到 `.bashrc`。

#### 6.2 加载配置

```bash
source "$HOME/gmapping_ws/use_tb3.bash"
echo "$TURTLEBOT3_MODEL"
```

应输出 `burger`。

**以后每个用于本实验的新终端都先执行这条 `source` 命令！！！**

## 🚀 四、实验步骤（五步走）

下面每一步都给出**命令**、**预期现象**和**验证/截图**。请按顺序在**不同的终端标签页**里执行（每个终端都先 source 对应环境）。

### 步骤 1：启动仿真世界

终端 A：

```bash
source "$HOME/gmapping_ws/use_tb3.bash"
ros2 launch turtlebot3_gazebo turtlebot3_world.launch.py
```

**预期现象**：弹出 Gazebo 窗口，场景中停着一台 TurtleBot3 Burger 小车；RViz2（若一并启动）中可见小车模型与一圈激光扫描线。

**📸 截图记录 1（实验报告必备）**

截取 Gazebo 中显示小车的画面，保存为 `step1_gazebo.png`。

### 步骤 2：启动 Gmapping 建图节点

终端 B：

```bash
source "$HOME/gmapping_ws/use_tb3.bash"
ros2 launch slam_gmapping slam_gmapping.launch.py use_sim_time:=true
```

**预期现象**：终端持续打印日志（scan 匹配、地图更新），无明显报错。**此时还没地图**——地图要等小车动起来后才逐渐生成。

**若长时间无地图**

先确认激光话题存在：`ros2 topic echo /scan --once`。若提示无该话题，说明小车模型没起来，回到步骤 1。默认参数已足够本实验使用，无需修改。

### 步骤 3：终端C启动Rviz

```bash
source "$HOME/gmapping_ws/use_tb3.bash"
rviz2 --ros-args -p use_sim_time:=true
```

在 RViz 窗口中按下面顺序设置：

1. 在左侧 `Displays` 展开 `Global Options`，把 `Fixed Frame` 改为 `map`。
2. 点击左下角 `Add`。
3. 选择 `By topic`，展开 `/map`，选择 `Map`，点击 `OK`。
4. 再次点击 `Add → By topic`，展开 `/scan`，选择 `LaserScan`，点击 `OK`。
5. 展开刚添加的 `Map` 显示项，确认 Topic 为 `/map`；如果显示 QoS 选项，将 Reliability 设为 `Reliable`，Durability 设为 `Transient Local`。
6. 展开 `LaserScan`，确认 Topic 为 `/scan`；将 Reliability 设为 `Best Effort`，Durability 设为 `Volatile`。这一设置要与传感器数据的 QoS 兼容。
7. 如视图看不到地图，使用鼠标滚轮缩放；可将视图类型设为 `TopDownOrtho`，从上方观察。
8. 需要查看 TF 时，点击 `Add → By display type → TF → OK`。

暂时没有第一张地图时，`map` 不存在的提示可能短暂出现。先保持 Gazebo 和 Gmapping 运行，等激光和 TF 就绪；持续没有地图时按第10章排查。

建议在首次配置完成后选择 `File → Save Config As`，保存为：

```text
/home/USERNAME/gmapping_ws/tb3_gmapping.rviz
```

如果你的用户名不同，使用对应的主目录。

### 步骤 4：遥控小车建图

```bash
source "$HOME/gmapping_ws/use_tb3.bash"
ros2 run turtlebot3_teleop teleop_keyboard
```

点击这个终端，让它获得键盘焦点，再按键：

| **按键** | **作用** |
| --- | --- |
| `w` | 增加前进方向的线速度 |
| `x` | 减小线速度，可逐步变成后退 |
| `a` | 增加左转方向的角速度 |
| `d` | 减小角速度，可逐步变成右转 |
| `s` 或空格 | 立即把线速度和角速度置零 |
| `Ctrl+C` | 退出键盘控制 |

按键改变的是目标速度，不是“按住才动、松开就停”。第一次只按几次 `w`，让机器人低速前进；需要转弯时先减速，转向合适后按空格停止，再继续前进。该 Humble 遥控代码发布 `geometry_msgs/msg/Twist`，与当前仿真控制接口对应。[9]

沿场景中的可通行区域缓慢移动，并逐步观察新的墙面和障碍物。RViz 中应出现灰色未知区域、白色可通行区域及黑色占用区域，地图随机器人移动逐渐扩展。

**预期现象**：终端提示 w/a/s/d 等按键控制方向。**用方向键让小车缓慢绕场一周**，RViz2 中的地图会随移动一块块"长"出来。建图时务必**慢速、平稳**，急转弯会导致地图重影。

**📸 截图记录 2（实验报告必备）**

当小车绕场大半圈、地图轮廓基本成型时，截取 RViz2 中的地图画面，保存为 `step3_mapping.png`。

### 步骤 4：保存地图

确认地图已完整覆盖目标区域后，在**新终端 D** 执行：

```bash
source "$HOME/gmapping_ws/use_tb3.bash"
mkdir -p "$HOME/gmapping_ws/maps"

ros2 run nav2_map_server map_saver_cli \
  -f "$HOME/gmapping_ws/maps/tb3_gmapping" \
  --ros-args \
  -p use_sim_time:=true \
  -p save_map_timeout:=20.0 \
  -p map_subscribe_transient_local:=true
```

地图保存工具使用 `/map`，等待时间设置为20秒，地图订阅使用可靠、Transient Local 的方式，与所选 Gmapping 分支的地图发布设置对应。[10]

若已保存过同名地图，再执行会覆盖同名文件；需要保留旧结果时，将 `-f` 后面的名称换成新名称。

**预期现象**：终端输出类似 `Writing map to /home/.../map/tb3_gmapping.pgm` 与 `...tb3_gmapping.yaml`，表示保存成功。

**保存失败的常见原因**

若提示找不到 map 话题，确认步骤 2 的 Gmapping 节点仍在运行（别关了）。`map_saver_cli` 是 Humble 的写法，注意带 `_cli` 后缀。

### 步骤 5：查看并导出地图

在文件管理器中打开 `~/map`，用图片查看器打开 `tb3_gmapping.pgm`：

```bash
eog ~/map/tb3_gmapping.pgm &        # 无图形界面可把文件拷出到本机查看
```

**预期现象**：看到一张黑白占据栅格地图，墙体和障碍为深色，通道为浅色，整体结构与实际 World 场景一致。

**📸 截图记录 3（实验报告必备）**

截取 `tb3_gmapping.pgm` 的地图图片，保存为 `step5_map.png`。这张就是你的实验成果。

## ✅ 五、本章验收标准

完成上述五步后，请逐一核对以下 5 项，全部满足即视为实验通过：

| **□** | **验收项** | **判定标准** |
| --- | --- | --- |
| 1 | Gazebo 仿真正常启动 | 能看到 TurtleBot3 Burger 小车 |
| 2 | Gmapping 节点运行无报错 | 终端持续输出建图日志 |
| 3 | 地图实时生成 | RViz2 中地图随小车移动逐渐成型、无明显重影 |
| 4 | 地图成功保存 | 生成 tb3_gmapping.pgm 与 tb3_gmapping.yaml |
| 5 | 三张截图齐全 | step1/step3/step5 三张图已存入实验报告 |

## 🛠️ 六、常见问题速查

| **现象** | **原因 / 解决办法** |
| --- | --- |
| 敲 `ros2` 提示 command not found | 忘了 source 。先执行 `source "$HOME/gmapping_ws/use_tb3.bash"` |
| Gazebo 卡在 "Loading world" 不动 | 虚拟机内存不足。关闭其他程序，或把虚拟机内存调到 8 GB 再试 |
| RViz2 里一直没地图 | 检查 /scan 话题；确认 Gmapping 节点在运行且小车已移动 |
| 地图严重重影、错位 | 建图时速度太快 / 急转。重来，放慢、平稳绕行 |
| 编译报错找不到 openslam 头文件 | 必须先编译底层的 openslam_gmapping ，再编 slam_gmapping |
| map_saver 提示无服务 / 无响应 | 确认 Gmapping 节点没被关掉；命令用 `map_saver_cli` （带 _cli ） |

## 📝 七、思考题

1. Gmapping 和"边走边画"的直觉区别在哪？为什么它需要激光雷达和里程计**两类**数据？
2. 实验中若让小车快速急转弯，地图为什么容易重影？这与粒子滤波的"粒子"有什么关系？
3. 本实验保存的是 `.pgm` + `.yaml` 两张文件，它们分别存了什么？为什么导航时要一起用？

## 📎 八、附录：命令速查与参考资料

### （一）命令速查

| **用途** | **命令** |
| --- | --- |
| 启动仿真 | `ros2 launch turtlebot3_gazebo turtlebot3_world.launch.py` |
| 启动建图 | `ros2 run slam_gmapping slam_gmapping` |
| 键盘遥控 | `ros2 run turtlebot3_teleop teleop_keyboard` |
| 保存地图 | `ros2 run nav2_map_server map_saver_cli -f ~/map/my_map` |
| 检查话题 | `ros2 topic echo /scan --once` |

### （二）参考资料

1. G. Grisetti, C. Stachniss, W. Burgard, “Improved Techniques for Grid Mapping with Rao-Blackwellized Particle Filters,” IEEE Transactions on Robotics, 2007.（Gmapping 原始论文，Google Scholar 引用约 3600 次）
2. kutschl/slam_gmapping（ROS 2 Humble 维护分支）[EB/OL]. https://github.com/kutschl/slam_gmapping
3. OpenSLAM GMapping 官方实现 [EB/OL]. https://github.com/OpenSLAM-org/openslam_gmapping
4. ROS 2 Humble 文档 [EB/OL]. https://docs.ros.org/en/humble/
