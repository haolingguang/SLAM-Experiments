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
- 六、结合 Nav2 进行仿真导航
- 七、导航验收标准
- 八、常见问题速查
- 九、思考题
- 十、附录：命令速查与参考资料

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

### 步骤 5：保存地图

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

### 步骤 6：查看并导出地图

在文件管理器中打开 `~/map`，用图片查看器打开 `tb3_gmapping.pgm`：

```bash
eog ~/map/tb3_gmapping.pgm &        # 无图形界面可把文件拷出到本机查看
```

**预期现象**：看到一张黑白占据栅格地图，墙体和障碍为深色，通道为浅色，整体结构与实际 World 场景一致。

**📸 截图记录 3（实验报告必备）**

截取 `tb3_gmapping.pgm` 的地图图片，保存为 `step6_map.png`。这张就是你的实验成果。

## ✅ 五、建图验收标准

完成上述五步后，请逐一核对以下 5 项，全部满足即视为实验通过：

| **□** | **验收项** | **判定标准** |
| --- | --- | --- |
| 1 | Gazebo 仿真正常启动 | 能看到 TurtleBot3 Burger 小车 |
| 2 | Gmapping 节点运行无报错 | 终端持续输出建图日志 |
| 3 | 地图实时生成 | RViz2 中地图随小车移动逐渐成型、无明显重影 |
| 4 | 地图成功保存 | 生成 tb3_gmapping.pgm 与 tb3_gmapping.yaml |
| 5 | 三张截图齐全 | step1/step4/step6 三张图已存入实验报告 |



## 六、结合Nav2进行仿真导航

### 6.1 安装 Nav2

继续使用你已经设置好的 Ubuntu 和 ROS 2 国内 APT 源：

```bash
sudo apt update
sudo apt install -y \
  ros-humble-navigation2 \
  ros-humble-nav2-bringup \
  ros-humble-nav2-rviz-plugins \
  python3-yaml
```

`navigation2` 安装导航功能，`nav2_bringup` 提供启动文件和默认配置，RViz 插件提供导航面板与目标工具，`python3-yaml` 用于生成配置和检查地图文件。[^3]

这里使用 Nav2 的 Humble 二进制包，不需要额外克隆源码、重新编译 Gazebo，或修改现有仓库的下载地址。若更新索引仍有“不能解析域名”等错误，先恢复联网，再继续安装。

安装完成后执行：

```bash
source "$HOME/gmapping_ws/use_tb3.bash"
ros2 pkg prefix nav2_bringup
ros2 pkg prefix nav2_rviz_plugins
```

两项都应找到安装位置。以后启动终端时仍使用原来的 `use_tb3.bash`，保持相同的 `ROS_DOMAIN_ID` 和仿真环境。

### 6.2 检查 YAML 指向的图像是否存在

APT 安装完成后，在终端完整执行：

```bash
python3 - <<'PY'
from pathlib import Path
import yaml

map_file = Path.home() / "gmapping_ws/maps/tb3_gmapping.yaml"
if not map_file.is_file():
    raise SystemExit(f"找不到地图：{map_file}。请先保存地图或核对文件名。")
data = yaml.safe_load(map_file.read_text(encoding="utf-8"))
required = {"image", "resolution", "origin", "negate", "occupied_thresh", "free_thresh"}
if not isinstance(data, dict) or not required.issubset(data) or not data["image"]:
    raise SystemExit("地图 YAML 字段不完整，请检查保存的地图文件。")
if str(data["image"]).startswith("~"):
    raise SystemExit("image 字段请使用相对路径或完整绝对路径，不使用 ~。")
image_file = Path(data["image"])
if not image_file.is_absolute():
    image_file = map_file.parent / image_file
if not image_file.is_file():
    raise SystemExit(f"YAML 指向的图像不存在：{image_file}")
if float(data.get("resolution", 0)) <= 0 or len(data.get("origin", [])) != 3:
    raise SystemExit("地图 resolution 或 origin 配置不完整。")
print("地图 YAML：", map_file)
print("地图图像：", image_file.resolve())
print("分辨率：", data["resolution"])
print("地图文件检查通过。")
PY
```

`image` 为相对路径时，是相对于 YAML 所在目录查找图像。若它保留了其他电脑的绝对路径，应核对实际图像位置后修正这个字段。不要修改 `resolution` 或 `origin` 来迁就显示位置，这会改变地图的物理含义。[^4]

### 6.3 生成本次导航配置

完整复制代码块，包括最后单独一行的 `PY`。若目标文件已经存在，程序会停止并保留它们；后续正常启动不需要重新生成配置。

```bash
source "$HOME/gmapping_ws/use_tb3.bash"

python3 - <<'PY'
from pathlib import Path
import yaml
from ament_index_python.packages import get_package_share_directory

share = Path(get_package_share_directory("nav2_bringup"))
folder = Path.home() / "gmapping_ws/nav2"
params_file = folder / "nav2_params.yaml"
rviz_file = folder / "navigation.rviz"
if params_file.exists() or rviz_file.exists():
    raise SystemExit("导航配置已存在，已保留原文件。已有完整配置时跳过本节。")
config = yaml.safe_load((share / "params/nav2_params.yaml").read_text())
rviz = yaml.safe_load((share / "rviz/nav2_default_view.rviz").read_text())

def enable_sim_time(node):
    if isinstance(node, dict):
        if "use_sim_time" in node:
            node["use_sim_time"] = True
        for value in node.values():
            enable_sim_time(value)
    elif isinstance(node, list):
        for value in node:
            enable_sim_time(value)

enable_sim_time(config)
amcl = config["amcl"]["ros__parameters"]
amcl.update(base_frame_id="base_footprint", odom_frame_id="odom",
            global_frame_id="map", scan_topic="/scan")
controller = config["controller_server"]["ros__parameters"]
controller["controller_frequency"] = 10.0
controller["progress_checker"]["required_movement_radius"] = 0.1
dwb = controller["FollowPath"]
if dwb["plugin"] != "dwb_core::DWBLocalPlanner":
    raise SystemExit("本机模板不是预期的 Humble DWB 配置，请先核对版本。")
dwb.update(max_vel_x=0.15, max_speed_xy=0.15, max_vel_theta=0.8,
           trans_stopped_velocity=0.05, vy_samples=1)

for name in ("local_costmap", "global_costmap"):
    costmap = config[name][name]["ros__parameters"]
    costmap.pop("footprint", None)
    costmap["robot_radius"] = 0.1
config["planner_server"]["ros__parameters"]["GridBased"]["allow_unknown"] = False
smoother = config["velocity_smoother"]["ros__parameters"]
smoother["max_velocity"] = [0.15, 0.0, 0.8]
smoother["min_velocity"] = [-0.15, 0.0, -0.8]

def prepare_displays(items):
    for item in items:
        if item.get("Name") in {"Bumper Hit", "Downsampled Costmap", "VoxelGrid", "Realsense"}:
            item["Enabled"] = False
            item["Value"] = False
        if item.get("Class") == "rviz_default_plugins/RobotModel":
            item["Enabled"] = True
            item["Value"] = True
            item["Description Topic"]["Durability Policy"] = "Transient Local"
        if isinstance(item.get("Displays"), list):
            prepare_displays(item["Displays"])

prepare_displays(rviz["Visualization Manager"]["Displays"])
rviz["Visualization Manager"]["Global Options"]["Fixed Frame"] = "map"
folder.mkdir(parents=True, exist_ok=True)
params_file.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
rviz_file.write_text(yaml.safe_dump(rviz, sort_keys=False), encoding="utf-8")
print("已生成：", params_file)
print("已生成：", rviz_file)
PY
```

生成的配置使用约 0.10 米的圆形机器人半径，最高前进速度设为 0.15 米/秒，最高角速度设为 0.8 弧度/秒，适合作为本次 Burger 仿真的起始配置。机器人半径参考 ROBOTIS 的 Burger 参数；速度是本教程选用的低速设置。[^7]

两种速度限制同时写入局部控制器和速度平滑器，避免两者上限不一致。本次全局规划禁止穿过未知区域，因此后面应在已经扫描出的连通区域内选目标。上述配置只适用于本次仿真型号，换车或换场景后应重新核对。

### 6.4 先结束上一轮建图

如果原来的仿真仍在运行，依次完成：

1. 在键盘遥控终端按空格或 `s`，使小车停止，再按 `Ctrl+C` 退出遥控。
2. 确认地图已保存，再在 Gmapping 终端按 `Ctrl+C`。
3. 关闭建图时的 RViz。
4. 在原 Gazebo 启动终端按 `Ctrl+C`，等原仿真正常退出。

下面重新启动同一个世界，让导航从固定的初始场景开始。每次只保留一套 Gazebo 和一套导航系统；不要在它们上面再启动第二套完整仿真。

### 6.5 终端A 启动 Gazebo

```bash
source "$HOME/gmapping_ws/use_tb3.bash"
ros2 launch turtlebot3_gazebo turtlebot3_world.launch.py
```

等待原来的 TurtleBot3 World 场景和 Burger 小车出现。如果底部显示暂停状态，点击播放，让仿真时间前进。保持终端A运行。

### 6.6 终端B 启动定位和导航

另开一个终端：

```bash
source "$HOME/gmapping_ws/use_tb3.bash"

ros2 launch nav2_bringup bringup_launch.py \
  map:="$HOME/gmapping_ws/maps/tb3_gmapping.yaml" \
  params_file:="$HOME/gmapping_ws/nav2/nav2_params.yaml" \
  use_sim_time:=true \
  slam:=False \
  autostart:=true \
  use_composition:=False
```

这条命令启动地图服务、AMCL 和导航节点。`slam:=False` 表示加载已有地图；`use_sim_time:=true` 使用 Gazebo 时间；`autostart:=true` 自动配置和激活节点。关闭组合进程是为了便于在终端区分各节点日志。这里的 `False` 按命令所示使用首字母大写，以兼容启动文件中的 Python 条件表达式。[^2]

此时还没有输入初始位置，可能暂时出现等待 `map → odom` 的提示。先继续打开 RViz 并设置初始位姿，不要为消除提示添加一个固定的 `map → odom` 静态变换。

### 6.7 终端C 启动导航用 RViz

再开一个终端：

```bash
source "$HOME/gmapping_ws/use_tb3.bash"

rviz2 -d "$HOME/gmapping_ws/nav2/navigation.rviz" \
  --ros-args -p use_sim_time:=true
```

窗口中应包含保存的地图、激光显示及 `Navigation 2` 面板。需要时双击 RViz 标题栏最大化窗口。确认左侧 `Global Options → Fixed Frame` 为 `map`。

若界面没有导航面板，选择 `Panels → Add New Panel`，找到 `nav2_rviz_plugins` 下的 `Navigation 2` 后添加。若缺少目标工具，点击顶部工具栏的 `+`，添加 `nav2_rviz_plugins` 下的导航目标工具。

本节界面截图统一在第6.10节完成定位与状态检查后记录，见截图记录 4。

### 6.8 告诉 AMCL 小车从哪里出发

初始位置要设置为机器人在当前地图中的实际位置，朝向也要一致：[^8]

1. 看 Gazebo，确认小车位于哪一片区域、面向哪个方向，可借助附近墙角和障碍物对照地图。
2. 在 RViz 顶部点击 `2D Pose Estimate`。
3. 在地图上小车实际所在位置按住鼠标左键。
4. 拖动箭头，使箭头朝向与小车朝向一致，然后松开鼠标。
5. 观察激光点与地图中的墙体、障碍边缘是否大致重合；不重合时重新设置位置和方向。

Gazebo 世界坐标与 Gmapping 地图坐标不一定相同。默认仿真启动文件中的出生位置为世界坐标 `x=-2.0、y=-0.5`，不能直接将这一对数值当作地图初始位姿。地图 YAML 的 `origin` 也不是机器人初始位置。[^9]

本次定位应看到机器人模型或姿态标记落在正确区域，激光轮廓与保存的地图对应。粒子显示初期较分散是正常现象，收到更多有效观测后会逐渐收敛。

完成第6.10节的导航状态检查后，再按截图记录 4 截取定位就绪画面。

### 6.9 需要时小幅辅助定位

如果初始估计已接近正确位置，但仍需让 AMCL 收集更多观测，可以临时开终端D：

```bash
source "$HOME/gmapping_ws/use_tb3.bash"
ros2 run turtlebot3_teleop teleop_keyboard
```

在空旷位置低速前后移动一点或小角度转动，观察激光与地图对齐。随后按空格停止，再按 `Ctrl+C` 退出遥控。**发送自主导航目标前，关闭遥控节点。**[^8]

### 6.10 确认导航系统已就绪

设置初始位置后，可在一个新终端查看：

```bash
source "$HOME/gmapping_ws/use_tb3.bash"
ros2 lifecycle get /amcl
ros2 lifecycle get /controller_server
ros2 lifecycle get /bt_navigator
```

正常情况下都应为 `active [3]`，RViz 的导航面板显示导航已激活。如果仍在等待，先按第八章和第十章检查时间、激光和 TF，再发送目标。

**📸 截图记录 4（实验报告必备）**

完成初始位姿设置、激光与地图对齐及上述节点状态检查后，将 RViz 与状态检查终端并排显示。截图应包含已加载的地图、小车位置与朝向、和墙体大致重合的激光轮廓，以及 `/amcl`、`/controller_server`、`/bt_navigator` 均为 `active [3]` 的结果，保存为 `nav1_localization.png`。

这张图用于证明导航已加载已有地图、定位基本正确且节点已就绪；只截取 Gazebo 中的小车，不能代替本项记录。

### 6.11 发送第一个目标

1. 在 RViz 顶部点击导航目标工具，通常显示为 `Nav2 Goal` 或 `Navigation2 Goal`。
2. 在小车附近、已经建好的白色可通行区域选一个位置。第一次选距离约1米、通路清楚的目标，避开墙边和灰色未知区域。
3. 在目标点按住鼠标左键，拖出箭头，指定小车到达后的朝向。
4. 松开鼠标，目标随即发送。
5. 保持 Gazebo、Nav2 和 RViz 三个终端运行，观察全局路径及 Gazebo 中的小车运动。[^8]

正常情况下，无需再按 `w/a/s/d`。小车会沿规划路线行驶，到达后调整到目标朝向并停止。终端或导航面板应报告本次目标成功，例如 `Goal succeeded` 或 `SUCCEEDED`。

**📸 截图记录 5（实验报告必备）**

第一个目标到达后、关闭窗口前，截取小车最终位置和本次导航成功状态，保存为 `nav2_goal_success.png`。画面中应能对照 RViz 的目标区域与 Gazebo 中的小车位置，并保留终端或导航面板中的 `Goal succeeded` 或 `SUCCEEDED` 提示；成功提示位于终端时，将终端与仿真窗口并排后截图。

截图前确认小车已到达指定位置、朝向已调整并停止，且键盘遥控节点已退出。本项用于记录自主到达结果。

### 6.12 验证绕障到达另一个目标

第一个目标完成后，选第二个目标：让起点与终点之间有场景中的固定障碍，但地图上存在可绕行的白色通路。仍用导航目标工具点击、拖动朝向并松开。

观察 RViz 中的规划路线绕过障碍，小车跟随路线到达目标。目标点应位于已建图且与当前位置连通的区域；没有可行通路时，导航会失败，而不是穿过障碍到达。

**📸 截图记录 6（实验报告必备）**

第二个目标需要保留两张图。发送目标后，在小车尚未到达、规划路径仍可见时，截取 RViz 中绕过固定障碍物的路径，并同时保留 Gazebo 场景中的障碍物与小车位置，保存为 `nav3a_obstacle_path.png`。路径应明显绕行障碍，起点与目标之间应存在可通行路线。

小车绕行并到达第二个目标后，再截取最终位置、停止状态与本次 `Goal succeeded` 或 `SUCCEEDED` 提示，保存为 `nav3b_goal_success.png`。本张成功提示应对应第二个目标，不要使用第一个目标的旧日志。

将截图记录 4—6 的四张图片插入实验报告，并分别标注“定位与导航就绪”“第一个目标到达”“第二个目标绕障路径”“第二个目标到达”。关闭窗口前确认图片已保存。

### 6.13 取消导航和正常结束

如果需要取消当前任务，在 RViz 的 `Navigation 2` 面板点击 `Cancel`，等待任务取消、小车停止。需要立即暂停仿真时，先点击 Gazebo 底部的暂停按钮，再处理导航任务。[^10]

实验结束时，先取消未完成的目标，再依次在终端B、C、A按 `Ctrl+C`，结束 Nav2、RViz 和 Gazebo。单独发送一次零速度不等于取消导航任务，规划控制器仍可能继续发布速度。

### 6.14 下次如何启动

已经装好 Nav2、保存地图并生成配置后，下次从第6.5节开始，依次启动终端A、B、C，再设置初始位置和目标即可。无需重新建图或重新生成配置。

如果只重启了 Gazebo，仿真时间会重新从零开始。首次排查时建议把本次 Nav2 和 RViz 也一起正常关闭，再按三终端顺序重新启动。

## ✅ 七、导航验收标准

完成第6章导航实验后，逐项核对并在首列打勾；以下 5 项全部满足，即视为导航实验通过：

| **□** | **验收项** | **判定标准** |
| --- | --- | --- |
| □ | 仿真与地图正常加载 | Gazebo 中可见 TurtleBot3 Burger，导航使用与建图时相同的 World 场景；RViz 显示已保存的地图。 |
| □ | AMCL 定位与导航就绪 | 初始位置与朝向正确，激光与地图墙体大致对齐；三个检查节点均为 `active [3]`，且未同时运行 Gmapping。 |
| □ | 第一个目标自主到达 | 关闭键盘遥控后，小车自主到达第一个目标并停止；终端或面板报告本次导航成功。 |
| □ | 第二个目标绕障到达 | 规划路径绕过固定障碍，小车无碰撞地完成绕行并到达第二个目标，停止后报告本次导航成功。 |
| □ | 四张导航截图齐全 | `nav1_localization.png`、`nav2_goal_success.png`、`nav3a_obstacle_path.png`、`nav3b_goal_success.png` 均已插入实验报告并标注。 |

## 🛠️ 八、常见问题速查

| **现象** | **原因 / 解决办法** |
| --- | --- |
| 敲 `ros2` 提示 command not found | 忘了 source 。先执行 `source "$HOME/gmapping_ws/use_tb3.bash"` |
| Gazebo 卡在 "Loading world" 不动 | 虚拟机内存不足。关闭其他程序，或把虚拟机内存调到 8 GB 再试 |
| RViz2 里一直没地图 | 检查 /scan 话题；确认 Gmapping 节点在运行且小车已移动 |
| 地图严重重影、错位 | 建图时速度太快 / 急转。重来，放慢、平稳绕行 |
| 编译报错找不到 openslam 头文件 | 必须先编译底层的 openslam_gmapping ，再编 slam_gmapping |
| map_saver 提示无服务 / 无响应 | 确认 Gmapping 节点没被关掉；命令用 `map_saver_cli` （带 _cli ） |

## 📝 九、思考题

1. Gmapping 和"边走边画"的直觉区别在哪？为什么它需要激光雷达和里程计**两类**数据？
2. 实验中若让小车快速急转弯，地图为什么容易重影？这与粒子滤波的"粒子"有什么关系？
3. 本实验保存的是 `.pgm` + `.yaml` 两张文件，它们分别存了什么？为什么导航时要一起用？
4. 已经保存了 Gmapping 地图，为什么自主导航时仍需要 AMCL 定位，并在 RViz 中设置初始位姿？如果初始位置或朝向设置错误，激光点与地图会出现什么现象？
5. Nav2 的全局路径规划与局部避障分别解决什么问题？若目标点看起来在白色空地上，小车却无法到达，应如何从定位是否准确、通路是否连通，以及机器人尺寸与障碍物间距三个方面分析原因？

## 📎 十、附录：命令速查与参考资料

### （一）命令速查

#### 1. 新终端加载实验环境

 ```bash
 source "$HOME/gmapping_ws/use_tb3.bash"
 ```

### 2. 仿真与建图常用命令

| **用途** | **命令** |
| --- | --- |
| 启动仿真 | `ros2 launch turtlebot3_gazebo turtlebot3_world.launch.py` |
| 启动建图 | `ros2 run slam_gmapping slam_gmapping` |
| 键盘遥控 | `ros2 run turtlebot3_teleop teleop_keyboard` |
| 保存地图 | `ros2 run nav2_map_server map_saver_cli -f ~/map/my_map` |
| 检查话题 | `ros2 topic echo /scan --once` |

保存地图时，保持 Gmapping 运行，在新终端加载环境后执行：

```bash
mkdir -p "$HOME/gmapping_ws/maps"
ros2 run nav2_map_server map_saver_cli \
  -f "$HOME/gmapping_ws/maps/tb3_gmapping" \
  --ros-args \
  -p use_sim_time:=true \
  -p save_map_timeout:=20.0 \
  -p map_subscribe_transient_local:=true
```

这会生成 tb3_gmapping.pgm 和 tb3_gmapping.yaml；重复保存会覆盖同名地图。需要保留旧地图时，先修改 -f 后的文件名前缀。

### 3. 自主导航三终端命令

先按第6.4节结束上一轮建图、遥控、RViz 和仿真，再按 A、B、C 的顺序启动。导航使用与建图时相同的 TurtleBot3 World 场景；AMCL 定位时不要同时运行 Gmapping。

**终端A** **启动 Gazebo**

```bash
source "$HOME/gmapping_ws/use_tb3.bash"
ros2 launch turtlebot3_gazebo turtlebot3_world.launch.py
```

**终端B** **启动地图服务、AMCL** **和 Nav2**

```bash
source "$HOME/gmapping_ws/use_tb3.bash"
ros2 launch nav2_bringup bringup_launch.py \
  map:="$HOME/gmapping_ws/maps/tb3_gmapping.yaml" \
  params_file:="$HOME/gmapping_ws/nav2/nav2_params.yaml" \
  use_sim_time:=true \
  slam:=False \
  autostart:=true \
  use_composition:=False
```

**终端C** **打开导航用 RViz**

```bash
source "$HOME/gmapping_ws/use_tb3.bash"
rviz2 -d "$HOME/gmapping_ws/nav2/navigation.rviz" \
  --ros-args -p use_sim_time:=true
```

在 RViz 中先用 2D Pose Estimate 设置机器人在地图中的实际位置与朝向；激光与墙体对齐、导航就绪后，再用 Nav2 Goal 或 Navigation2 Goal 发送目标。需要取消任务时，在 Navigation 2 面板点击 Cancel。

#### 4. 导航状态与故障定位

在新终端加载实验环境后执行；以下命令用于查看状态，不会替代初始位姿设置或导航目标操作。

| **用途**                   | **命令**                                 |
| -------------------------- | ---------------------------------------- |
| 检查 AMCL 定位节点         | ros2  lifecycle get /amcl                |
| 检查控制器节点             | ros2  lifecycle get /controller_server   |
| 检查导航行为树节点         | ros2  lifecycle get /bt_navigator        |
| 检查仿真时间是否前进       | ros2  topic echo /clock --once           |
| 查看地图到机器人坐标变换   | ros2  run tf2_ros tf2_echo map base_link |
| 查看速度话题的发布与订阅端 | ros2  topic info /cmd_vel -v             |
| 查看导航动作接口           | ros2  action list                        |

设置初始位姿并完成启动后，前三个节点通常应显示 active [3]。tf2_echo 会持续输出，检查后按 Ctrl+C 退出。导航过程中取消任务请使用 RViz 面板；单次发布零速度不能代替取消目标。

### （二）参考资料

1. G. Grisetti, C. Stachniss, W. Burgard, “Improved Techniques for Grid Mapping with Rao-Blackwellized Particle Filters,” IEEE Transactions on Robotics, 2007.（Gmapping 原始论文，Google Scholar 引用约 3600 次）
2. kutschl/slam_gmapping（ROS 2 Humble 维护分支）[EB/OL]. https://github.com/kutschl/slam_gmapping
3. OpenSLAM GMapping 官方实现 [EB/OL]. https://github.com/OpenSLAM-org/openslam_gmapping
4. ROS 2 Humble 文档 [EB/OL]. https://docs.ros.org/en/humble/
